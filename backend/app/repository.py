"""Process-local storage; reports, suggestions, and associations share one lock."""

from collections.abc import Iterable
from datetime import datetime
from threading import Lock
from typing import Literal, Protocol
from uuid import UUID, uuid4

from .duplicate_models import (
    DuplicateAssessment, DuplicateSuggestion, DuplicateSuggestionResponse,
)
from .models import Issue, IssueSnapshot


class ReviewConflict(Exception):
    """The suggestion is no longer eligible for this human decision."""


class IssueRepository(Protocol):
    def add(self, issue: Issue) -> Issue: ...
    def list(self) -> list[Issue]: ...
    def get(self, issue_id: UUID) -> Issue | None: ...
    def confirm(self, issue_id: UUID) -> Issue | None: ...
    def snapshot(self, issue_id: UUID) -> IssueSnapshot | None: ...
    def queue(self) -> list[IssueSnapshot]: ...
    def suggestions(self, issue_id: UUID) -> list[DuplicateSuggestionResponse]: ...
    def needs_comparison(self, issue_id: UUID, candidate_id: UUID) -> bool: ...
    def record_assessment(
        self, issue_id: UUID, candidate_id: UUID, assessment: DuplicateAssessment, now: datetime
    ) -> None: ...
    def review(
        self, suggestion_id: UUID, decision: Literal["confirmed", "rejected"], now: datetime
    ) -> tuple[DuplicateSuggestionResponse, list[IssueSnapshot]] | None: ...


class InMemoryIssueRepository:
    def __init__(
        self,
        initial_issues: Iterable[Issue] | None = None,
        initial_suggestions: Iterable[DuplicateSuggestion] | None = None,
    ) -> None:
        self._issues = {
            issue.id: issue.model_copy(deep=True)
            for issue in (initial_issues if initial_issues is not None else ())
        }
        # Every report maps directly to its canonical root; no nested parent chains.
        self._canonical = {issue_id: issue_id for issue_id in self._issues}
        self._suggestions: dict[UUID, DuplicateSuggestion] = {}
        self._compared: set[frozenset[UUID]] = set()
        for original in initial_suggestions or ():
            suggestion = DuplicateSuggestion.model_validate(original)
            pair = frozenset((suggestion.issue_id, suggestion.candidate_issue_id))
            if (suggestion.status != "pending" or not pair <= self._issues.keys()
                    or pair in self._compared or suggestion.id in self._suggestions):
                raise ValueError("Seeds must be unique pending suggestions for existing reports")
            self._suggestions[suggestion.id] = suggestion
            self._compared.add(pair)
        self._lock = Lock()

    def add(self, issue: Issue) -> Issue:
        with self._lock:
            if issue.id in self._issues:
                raise ValueError("Report already exists")
            self._issues[issue.id] = issue
            self._canonical[issue.id] = issue.id
            return issue

    def list(self) -> list[Issue]:
        """All original reports, including associated sources, for audit/retrieval."""
        with self._lock:
            return list(self._issues.values())

    def get(self, issue_id: UUID) -> Issue | None:
        with self._lock:
            return self._issues.get(issue_id)

    def confirm(self, issue_id: UUID) -> Issue | None:
        # Increment only the addressed source, even after association. Aggregates
        # are derived from distinct source IDs and never written back to sources.
        with self._lock:
            issue = self._issues.get(issue_id)
            if issue is None:
                return None
            updated = issue.model_copy(
                update={"confirmation_count": issue.confirmation_count + 1}
            )
            self._issues[issue_id] = updated
            return updated

    def _relevant(self, issue_id: UUID) -> list[DuplicateSuggestion]:
        root = self._canonical[issue_id]
        return [
            suggestion for suggestion in self._suggestions.values()
            if root in (self._canonical[suggestion.issue_id],
                        self._canonical[suggestion.candidate_issue_id])
            # A different human-reviewed edge may already have associated this
            # pair. Retain its record, but never offer a redundant review action.
            and (suggestion.status != "pending"
                 or self._canonical[suggestion.issue_id]
                 != self._canonical[suggestion.candidate_issue_id])
        ]

    def _snapshot(self, issue_id: UUID) -> IssueSnapshot:
        root = self._canonical[issue_id]
        # A linked source's detail remains a raw report; the queue exposes the
        # canonical view with all sources. No original issue fields are rewritten.
        sources = (
            [issue for issue in self._issues.values() if self._canonical[issue.id] == root]
            if issue_id == root else [self._issues[issue_id]]
        )
        return IssueSnapshot(
            issue=self._issues[issue_id], canonical_issue_id=root,
            source_reports=sorted(sources, key=lambda issue: (issue.created_at, issue.id.int)),
            pending_duplicate_count=sum(s.status == "pending" for s in self._relevant(issue_id)),
        )

    def snapshot(self, issue_id: UUID) -> IssueSnapshot | None:
        with self._lock:
            return self._snapshot(issue_id) if issue_id in self._issues else None

    def _queue(self) -> list[IssueSnapshot]:
        return [self._snapshot(key) for key in self._issues if self._canonical[key] == key]

    def queue(self) -> list[IssueSnapshot]:
        with self._lock:
            return self._queue()

    def _suggestion_response(self, suggestion: DuplicateSuggestion) -> DuplicateSuggestionResponse:
        return DuplicateSuggestionResponse(
            **suggestion.model_dump(), issue=self._issues[suggestion.issue_id],
            candidate=self._issues[suggestion.candidate_issue_id],
        )

    def suggestions(self, issue_id: UUID) -> list[DuplicateSuggestionResponse]:
        with self._lock:
            return [self._suggestion_response(s) for s in self._relevant(issue_id)]

    def _needs_comparison(self, issue_id: UUID, candidate_id: UUID) -> bool:
        return (
            issue_id in self._issues and candidate_id in self._issues
            and self._canonical[issue_id] != self._canonical[candidate_id]
            and frozenset((issue_id, candidate_id)) not in self._compared
        )

    def needs_comparison(self, issue_id: UUID, candidate_id: UUID) -> bool:
        with self._lock:
            return self._needs_comparison(issue_id, candidate_id)

    def record_assessment(
        self, issue_id: UUID, candidate_id: UUID, assessment: DuplicateAssessment, now: datetime
    ) -> None:
        assessment = DuplicateAssessment.model_validate(assessment)
        with self._lock:
            # Recheck after network I/O: concurrent checks/reviews cannot create
            # duplicate suggestions or overwrite a prior human decision.
            if not self._needs_comparison(issue_id, candidate_id):
                return
            if assessment.is_possible_duplicate:
                suggestion = DuplicateSuggestion(
                    id=uuid4(), issue_id=issue_id, candidate_issue_id=candidate_id,
                    confidence=assessment.confidence, reason=assessment.reason, created_at=now,
                )
                self._suggestions[suggestion.id] = suggestion
            self._compared.add(frozenset((issue_id, candidate_id)))

    def review(
        self, suggestion_id: UUID, decision: Literal["confirmed", "rejected"], now: datetime
    ) -> tuple[DuplicateSuggestionResponse, list[IssueSnapshot]] | None:
        with self._lock:
            suggestion = self._suggestions.get(suggestion_id)
            if suggestion is None:
                return None
            if suggestion.status != "pending":
                raise ReviewConflict("This suggestion has already been reviewed. Refresh the queue.")
            roots = {self._canonical[suggestion.issue_id], self._canonical[suggestion.candidate_issue_id]}
            if len(roots) != 2:
                raise ReviewConflict("These reports are already associated. Refresh the queue.")
            canonical_id = None
            members: list[Issue] = []
            if decision == "confirmed":
                members = [issue for issue in self._issues.values() if self._canonical[issue.id] in roots]
                member_ids = {issue.id for issue in members}
                if any(s.status == "rejected" and {s.issue_id, s.candidate_issue_id} <= member_ids
                       for s in self._suggestions.values()):
                    raise ReviewConflict("This association conflicts with an earlier keep-separate decision.")
                # Earliest source wins, then UUID. The model never selects a root.
                canonical_id = min(members, key=lambda issue: (issue.created_at, issue.id.int)).id
            reviewed = DuplicateSuggestion.model_validate(suggestion.model_dump() | {
                "status": decision, "reviewed_at": now, "reviewed_by": "human",
                "canonical_issue_id": canonical_id,
            })
            for issue in members:
                self._canonical[issue.id] = canonical_id
            self._suggestions[suggestion.id] = reviewed
            return self._suggestion_response(reviewed), self._queue()

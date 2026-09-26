"""Process-local storage behind a small replaceable repository interface."""

from threading import Lock
from typing import Protocol
from uuid import UUID

from .models import Issue


class IssueRepository(Protocol):
    def add(self, issue: Issue) -> Issue: ...

    def list(self) -> list[Issue]: ...

    def get(self, issue_id: UUID) -> Issue | None: ...

    def confirm(self, issue_id: UUID) -> Issue | None: ...


class InMemoryIssueRepository:
    def __init__(self) -> None:
        self._issues: dict[UUID, Issue] = {}
        self._lock = Lock()

    def add(self, issue: Issue) -> Issue:
        with self._lock:
            self._issues[issue.id] = issue
            return issue

    def list(self) -> list[Issue]:
        with self._lock:
            return list(self._issues.values())

    def get(self, issue_id: UUID) -> Issue | None:
        with self._lock:
            return self._issues.get(issue_id)

    def confirm(self, issue_id: UUID) -> Issue | None:
        # The read/increment/write is atomic across FastAPI worker threads.
        with self._lock:
            issue = self._issues.get(issue_id)
            if issue is None:
                return None
            updated = issue.model_copy(
                update={"confirmation_count": issue.confirmation_count + 1}
            )
            self._issues[issue_id] = updated
            return updated

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.demo_data import build_demo_issues, build_demo_suggestions
from app.duplicate_models import DuplicateAssessment
from app.models import Issue
from app.repository import InMemoryIssueRepository, ReviewConflict


def test_initial_issues_are_copied_and_isolated(payload, now):
    original = Issue(**payload, id=uuid4(), created_at=now, confirmation_count=3)
    initial_issues = [original]
    repository = InMemoryIssueRepository(initial_issues=initial_issues)
    other = InMemoryIssueRepository(initial_issues=initial_issues)

    assert repository.list() == [original]
    assert repository.get(original.id) is not original
    initial_issues.clear()
    repository.list().clear()
    assert repository.list() == [original]
    assert repository.confirm(original.id).confirmation_count == 4
    assert original.confirmation_count == 3
    assert other.get(original.id).confirmation_count == 3


def test_confirmations_are_atomic_and_snapshots_immutable(payload, now):
    repository = InMemoryIssueRepository()
    original = repository.add(Issue(**payload, id=uuid4(), created_at=now))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: repository.confirm(original.id), range(100)))
    assert sorted(issue.confirmation_count for issue in results) == list(range(1, 101))
    assert repository.get(original.id).confirmation_count == 100
    assert original.confirmation_count == 0
    with pytest.raises(ValidationError):
        original.confirmation_count = 99


# Duplicate review exercises the same lock as ordinary community confirmations.
MATCH = DuplicateAssessment(
    is_possible_duplicate=True, confidence=0.8,
    reason="The location, asset, timing, and reported failure appear to match.",
)


def test_duplicate_reviews_and_confirmation_increments_share_atomic_state(now):
    reports = build_demo_issues(now)
    suggestion = build_demo_suggestions(now)[0]
    repo = InMemoryIssueRepository(reports, [suggestion])
    before = repo.queue()

    def review_or_increment(index):
        if index % 2:
            return repo.confirm(reports[(index // 2) % 2].id)
        try:
            return repo.review(suggestion.id, "confirmed", now)
        except ReviewConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(review_or_increment, range(100)))
    assert sum(isinstance(result, tuple) for result in results) == 1
    assert results.count("conflict") == 49
    snapshot = repo.snapshot(reports[0].id)
    assert len(repo.queue()) == 5
    assert len(snapshot.source_reports) == 2
    assert sum(report.confirmation_count for report in snapshot.source_reports) == 61  # 8 + 3 + 50
    assert [report.confirmation_count for report in snapshot.source_reports] == [33, 28]
    assert before[0].source_reports[0].confirmation_count == 8
    assert before[1].source_reports[0].confirmation_count == 3
    assert repo.get(reports[1].id).title == reports[1].title


def test_concurrent_opposing_reviews_have_one_winner(now):
    reports = build_demo_issues(now)
    suggestion = build_demo_suggestions(now)[0]
    repo = InMemoryIssueRepository(reports, [suggestion])

    def attempt(decision):
        try:
            return repo.review(suggestion.id, decision, now)
        except ReviewConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["confirmed", "rejected"]))
    winners = [result for result in results if result is not None]
    assert len(winners) == 1
    review, queue = winners[0]
    assert len(queue) == (5 if review.status == "confirmed" else 6)
    assert repo.list() == reports


def test_concurrent_analysis_deduplicates_reversed_pairs_and_preserves_rejection(now):
    first, second, *_ = build_demo_issues(now)
    repo = InMemoryIssueRepository([first, second])
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda index: repo.record_assessment(
            first.id if index % 2 else second.id,
            second.id if index % 2 else first.id, MATCH, now,
        ), range(40)))
    suggestion, = repo.suggestions(first.id)
    repo.review(suggestion.id, "rejected", now)
    # A result from a previously started network request must not undo review.
    repo.record_assessment(second.id, first.id, MATCH, now)
    assert repo.suggestions(first.id)[0].status == "rejected"
    assert len(repo.suggestions(first.id)) == 1
    assert len(repo.queue()) == 2


def test_canonical_uuid_tiebreak_is_order_independent(now):
    template = build_demo_issues(now)[0]
    lower = template.model_copy(update={"id": UUID(int=1), "created_at": now})
    higher = template.model_copy(update={"id": UUID(int=2), "created_at": now})
    for reports in ([lower, higher], [higher, lower]):
        repo = InMemoryIssueRepository(reports)
        repo.record_assessment(reports[0].id, reports[1].id, MATCH, now)
        suggestion = repo.suggestions(lower.id)[0]
        review, queue = repo.review(suggestion.id, "confirmed", now)
        assert review.canonical_issue_id == lower.id
        assert [snapshot.issue.id for snapshot in queue] == [lower.id]
        assert [source.id for source in queue[0].source_reports] == [lower.id, higher.id]


def test_overlapping_associations_count_distinct_sources_and_can_change_root(now):
    template = build_demo_issues(now)[0]
    first = template.model_copy(update={"id": uuid4(), "created_at": now, "confirmation_count": 2})
    second = template.model_copy(update={"id": uuid4(), "created_at": now + timedelta(hours=1), "confirmation_count": 3})
    older = template.model_copy(update={"id": uuid4(), "created_at": now - timedelta(hours=1), "confirmation_count": 4})
    repo = InMemoryIssueRepository([first, second, older])
    for left, right in [(first, second), (second, older), (first, older)]:
        repo.record_assessment(left.id, right.id, MATCH, now)
    suggestions = {frozenset((s.issue_id, s.candidate_issue_id)): s for s in repo.suggestions(first.id) + repo.suggestions(second.id)}
    first_review = suggestions[frozenset((first.id, second.id))]
    second_review = suggestions[frozenset((second.id, older.id))]
    redundant = suggestions[frozenset((first.id, older.id))]
    repo.review(first_review.id, "confirmed", now)
    repo.review(second_review.id, "confirmed", now)
    snapshot, = repo.queue()
    assert snapshot.issue.id == older.id
    assert sum(source.confirmation_count for source in snapshot.source_reports) == 9
    assert len({source.id for source in snapshot.source_reports}) == 3
    assert snapshot.pending_duplicate_count == 0
    assert all(repo.snapshot(report.id).canonical_issue_id == older.id for report in [first, second, older])
    with pytest.raises(ReviewConflict, match="already associated"):
        repo.review(redundant.id, "confirmed", now)
    # Audit retains the actual root chosen at each review, even after a later union.
    assert {s.canonical_issue_id for s in repo.suggestions(older.id)} == {first.id, older.id}


def test_transitive_association_cannot_undo_a_keep_separate_decision(now):
    first, second, *_ = build_demo_issues(now)
    third = second.model_copy(update={"id": uuid4()})
    repo = InMemoryIssueRepository([first, second, third])
    for left, right in [(first, second), (first, third), (second, third)]:
        repo.record_assessment(left.id, right.id, MATCH, now)
    suggestions = {frozenset((s.issue_id, s.candidate_issue_id)): s for s in repo.suggestions(first.id) + repo.suggestions(second.id)}
    repo.review(suggestions[frozenset((first.id, second.id))].id, "rejected", now)
    repo.review(suggestions[frozenset((first.id, third.id))].id, "confirmed", now)
    before = repo.queue()
    with pytest.raises(ReviewConflict, match="keep-separate"):
        repo.review(suggestions[frozenset((second.id, third.id))].id, "confirmed", now)
    assert repo.queue() == before
    assert repo.snapshot(first.id).canonical_issue_id != repo.snapshot(second.id).canonical_issue_id


def test_seed_suggestions_are_validated_and_instances_are_isolated(now):
    reports = build_demo_issues(now)
    suggestion = build_demo_suggestions(now)[0]
    repo = InMemoryIssueRepository(reports, [suggestion])
    other = InMemoryIssueRepository(reports, [suggestion])
    repo.review(suggestion.id, "confirmed", now)
    assert other.suggestions(reports[0].id)[0].status == "pending"
    assert suggestion.status == "pending"
    with pytest.raises(ValueError):
        InMemoryIssueRepository(reports, [suggestion, suggestion])
    with pytest.raises(ValueError):
        InMemoryIssueRepository([], [suggestion])
    with pytest.raises(ValueError):
        repo.add(reports[0])  # Cannot overwrite an associated source.

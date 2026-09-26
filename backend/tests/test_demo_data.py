from datetime import timedelta, timezone

import pytest

from app.demo_data import build_demo_issues
from app.models import Issue, Severity


def test_demo_issues_have_stable_ids_and_fresh_raw_models(now):
    issues = build_demo_issues(now)
    repeated = build_demo_issues(now)
    later = build_demo_issues(now + timedelta(days=7))

    assert [str(issue.id) for issue in issues] == [
        "2f4bde9a-18c6-4bb1-8f87-6f9400000001",
        "2f4bde9a-18c6-4bb1-8f87-6f9400000002",
        "2f4bde9a-18c6-4bb1-8f87-6f9400000003",
        "2f4bde9a-18c6-4bb1-8f87-6f9400000004",
        "2f4bde9a-18c6-4bb1-8f87-6f9400000005",
        "2f4bde9a-18c6-4bb1-8f87-6f9400000006",
    ]
    assert issues == repeated
    assert issues is not repeated
    for issue, copy, shifted in zip(issues, repeated, later, strict=True):
        assert type(issue) is Issue
        assert "priority" not in issue.model_dump()
        assert issue is not copy
        assert shifted.model_dump(exclude={"created_at"}) == issue.model_dump(
            exclude={"created_at"}
        )
        assert shifted.created_at - issue.created_at == timedelta(days=7)
        assert issue.created_at < now
        assert issue.created_at.tzinfo == timezone.utc
    issues.clear()
    assert len(build_demo_issues(now)) == 6


def test_demo_scenarios_preserve_similar_reports(now):
    elevator, similar, lights, leak, network, walkway = build_demo_issues(now)
    for issue in (elevator, similar):
        assert issue.location == "Earl Gregg Swem Library"
        assert issue.category == "Elevator"
        assert issue.severity == Severity.HIGH
        assert issue.accessibility_impact is True
        assert issue.safety_impact is False
        assert issue.confirmation_count > 1
    assert elevator.id != similar.id
    assert elevator.title != similar.title
    assert lights.category == "Lighting"
    assert lights.severity == Severity.MODERATE
    assert lights.safety_impact is True
    assert leak.category == "Plumbing"
    assert leak.severity == Severity.HIGH
    assert leak.confirmation_count > 1
    assert network.category == "Network"
    assert network.severity == Severity.MODERATE
    assert network.confirmation_count > 1
    assert walkway.category == "Walkway"
    assert walkway.severity == Severity.MODERATE
    assert walkway.accessibility_impact is True
    assert walkway.safety_impact is True


def test_demo_reference_time_is_normalized_to_utc(now):
    offset_now = now.astimezone(timezone(timedelta(hours=-4)))
    issues = build_demo_issues(offset_now)
    assert issues == build_demo_issues(now)
    assert all(issue.created_at.tzinfo == timezone.utc for issue in issues)


def test_demo_rejects_naive_reference_time(now):
    with pytest.raises(ValueError, match="timezone-aware"):
        build_demo_issues(now.replace(tzinfo=None))

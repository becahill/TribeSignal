from datetime import timedelta, timezone
from math import log
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models import Issue, Severity
from app.priority import calculate_priority


def make_issue(now, **overrides):
    values = {
        "id": uuid4(),
        "title": "Broken fixture",
        "description": "A fixture needs attention.",
        "severity": Severity.LOW,
        "location": "Library",
        "category": "electrical",
        "created_at": now,
    }
    return Issue(**(values | overrides))


@pytest.mark.parametrize(
    "severity,expected", [("low", 1.0), ("moderate", 2.5), ("high", 4.0), ("critical", 5.5)]
)
def test_severity_bases(now, severity, expected):
    result = calculate_priority(make_issue(now, severity=severity), now=now)
    assert result.score == expected
    assert result.components.severity == expected


@pytest.mark.parametrize(
    "field,component,weight",
    [("accessibility_impact", "accessibility", 1.5), ("safety_impact", "safety", 2.0)],
)
def test_impact_weights(now, field, component, weight):
    base = calculate_priority(make_issue(now), now=now)
    result = calculate_priority(make_issue(now, **{field: True}), now=now)
    assert result.score - base.score == weight
    assert getattr(result.components, component) == weight
    assert getattr(base.components, component) == 0.0


@pytest.mark.parametrize(
    "count,expected",
    [(0, 0.0), (1, 0.0), (3, 0.6 * log(3)), (28, 0.6 * log(28)), (29, 2.0), (1000, 2.0)],
)
def test_confirmation_term(now, count, expected):
    result = calculate_priority(make_issue(now, confirmation_count=count), now=now)
    assert result.components.confirmations == pytest.approx(expected)
    assert result.score == round(1.0 + expected, 2)


@pytest.mark.parametrize("hours,expected", [(0, 0.0), (36, 0.5), (72, 1.0), (200, 1.0), (-1, 0.0)])
def test_aging(now, hours, expected):
    issue = make_issue(now - timedelta(hours=hours))
    result = calculate_priority(issue, now=now)
    assert result.components.aging == expected
    assert result.score == 1.0 + expected


def test_canonical_score_and_explanation(now):
    issue = make_issue(
        now, severity="high", accessibility_impact=True, confirmation_count=3
    )
    result = calculate_priority(issue, now=now)
    assert result.score == 6.16
    assert result.explanation == (
        "4.00 severity + 1.50 accessibility + 0.00 safety + "
        "0.66 confirmations + 0.00 aging = 6.16/10"
    )
    terms = " + ".join(f"{value:.2f}" for value in result.components.model_dump().values())
    assert f"{terms} = {result.score:.2f}" == "4.00 + 1.50 + 0.00 + 0.66 + 0.00 = 6.16"
    assert result == calculate_priority(issue, now=now)
    assert result.calculated_at == now


def test_score_cap_retains_auditable_components(now):
    issue = make_issue(
        now - timedelta(hours=100),
        severity="critical",
        accessibility_impact=True,
        safety_impact=True,
        confirmation_count=100,
    )
    result = calculate_priority(issue, now=now)
    assert result.score == 10.0
    assert sum(result.components.model_dump().values()) == 12.0
    assert result.explanation.endswith("= 12.00; capped at 10.00/10")


def test_round_only_after_summing_full_precision_components(now):
    # Premature component rounding would incorrectly produce 1.68.
    issue = make_issue(now - timedelta(hours=1.1), confirmation_count=3)
    result = calculate_priority(issue, now=now)
    assert result.score == 1.67
    assert result.components.aging == pytest.approx(1.1 / 72)


def test_timezone_offsets_represent_same_instant(now):
    offset = timezone(timedelta(hours=-4))
    issue = make_issue((now - timedelta(hours=36)).astimezone(offset))
    assert issue.created_at.tzinfo == timezone.utc
    result = calculate_priority(issue, now=now.astimezone(timezone(timedelta(hours=5, minutes=30))))
    assert result.components.aging == 0.5
    assert result.calculated_at.tzinfo == timezone.utc


def test_naive_creation_time_rejected(now):
    with pytest.raises(ValidationError, match="timezone"):
        make_issue(now.replace(tzinfo=None))


def test_naive_clock_rejected(now):
    with pytest.raises(ValueError, match="timezone-aware"):
        calculate_priority(make_issue(now), now=now.replace(tzinfo=None))


@pytest.mark.parametrize("count", [-1, 1.5, True, "3"])
def test_invalid_confirmation_count_rejected(now, count):
    with pytest.raises(ValidationError):
        make_issue(now, confirmation_count=count)

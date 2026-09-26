"""The sole priority authority: deterministic arithmetic, never model output."""

from datetime import datetime, timezone
from math import log

from .models import Issue, Priority, PriorityComponents, Severity


SEVERITY_BASES = {
    Severity.LOW: 1.0,
    Severity.MODERATE: 2.5,
    Severity.HIGH: 4.0,
    Severity.CRITICAL: 5.5,
}


def calculate_priority(issue: Issue, *, now: datetime) -> Priority:
    """Compute with full precision, then round the capped score to two decimals.

    An explicit aware clock makes aging reproducible. Future timestamps have
    zero age, so clock skew cannot push a score below its severity base.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    hours_open = max(0.0, (now - issue.created_at).total_seconds() / 3600)
    components = PriorityComponents(
        severity=SEVERITY_BASES[issue.severity],
        accessibility=1.5 if issue.accessibility_impact else 0.0,
        safety=2.0 if issue.safety_impact else 0.0,
        confirmations=(
            min(2.0, 0.6 * log(issue.confirmation_count))
            if issue.confirmation_count >= 1
            else 0.0
        ),
        aging=min(1.0, hours_open / 72),
    )
    total = sum(components.model_dump().values())
    score = round(min(10.0, total), 2)
    terms = " + ".join(
        f"{value:.2f} {name}" for name, value in components.model_dump().items()
    )
    explanation = (
        f"{terms} = {total:.2f}; capped at {score:.2f}/10"
        if total > 10.0
        else f"{terms} = {score:.2f}/10"
    )
    return Priority(
        score=score,
        components=components,
        explanation=explanation,
        calculated_at=now,
    )

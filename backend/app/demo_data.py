"""Fictional campus reports with fixed identities and reproducible relative ages."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from .models import Issue, Severity
from .duplicate_models import DuplicateSuggestion


def build_demo_issues(now: datetime) -> list[Issue]:
    """Return fresh raw issues relative to one aware reference time, without priority."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    return [
        Issue(
            id=UUID("2f4bde9a-18c6-4bb1-8f87-6f9400000001"),
            title="Swem Library elevator unavailable",
            description=(
                "The main elevator does not respond to floor calls, preventing "
                "step-free access to the upper-floor study areas."
            ),
            location="Earl Gregg Swem Library",
            category="Elevator",
            severity=Severity.HIGH,
            accessibility_impact=True,
            safety_impact=False,
            confirmation_count=8,
            created_at=now - timedelta(hours=36),
        ),
        # Independent until a human reviews the seeded duplicate suggestion.
        Issue(
            id=UUID("2f4bde9a-18c6-4bb1-8f87-6f9400000002"),
            title="Elevator near Swem first floor not responding",
            description=(
                "The elevator by the first-floor lobby does not open when called. "
                "Visitors using mobility aids cannot reach the upper floors."
            ),
            location="Earl Gregg Swem Library",
            category="Elevator",
            severity=Severity.HIGH,
            accessibility_impact=True,
            safety_impact=False,
            confirmation_count=3,
            created_at=now - timedelta(hours=12),
        ),
        Issue(
            id=UUID("2f4bde9a-18c6-4bb1-8f87-6f9400000003"),
            title="Exterior lights out on the Sadler Center walkway",
            description=(
                "Several walkway lights are dark after sunset, making the path "
                "edges and steps difficult to see."
            ),
            location="Sadler Center exterior walkway",
            category="Lighting",
            severity=Severity.MODERATE,
            accessibility_impact=False,
            safety_impact=True,
            confirmation_count=5,
            created_at=now - timedelta(hours=24),
        ),
        Issue(
            id=UUID("2f4bde9a-18c6-4bb1-8f87-6f9400000004"),
            title="Active water leak in a residence hall bathroom",
            description=(
                "Water is steadily leaking from a pipe beneath a shared bathroom "
                "sink and collecting along the wall."
            ),
            location="Lemon Hall, shared bathroom",
            category="Plumbing",
            severity=Severity.HIGH,
            accessibility_impact=False,
            safety_impact=False,
            confirmation_count=4,
            created_at=now - timedelta(hours=6),
        ),
        Issue(
            id=UUID("2f4bde9a-18c6-4bb1-8f87-6f9400000005"),
            title="Classroom network unavailable in Morton Hall",
            description=(
                "Classroom computers and student devices cannot connect to the "
                "campus network, interrupting access to course materials."
            ),
            location="Morton Hall, first-floor classroom",
            category="Network",
            severity=Severity.MODERATE,
            accessibility_impact=False,
            safety_impact=False,
            confirmation_count=9,
            created_at=now - timedelta(hours=3),
        ),
        Issue(
            id=UUID("2f4bde9a-18c6-4bb1-8f87-6f9400000006"),
            title="Raised paving on the path near the Wren Building",
            description=(
                "Cracked and raised paving creates a trip hazard and makes the "
                "pedestrian path difficult to navigate with a wheelchair."
            ),
            location="Wren Building pedestrian path",
            category="Walkway",
            severity=Severity.MODERATE,
            accessibility_impact=True,
            safety_impact=True,
            confirmation_count=6,
            created_at=now - timedelta(hours=48),
        ),
    ]


def build_demo_suggestions(now: datetime) -> list[DuplicateSuggestion]:
    """Explicit fixture evidence: no live model or production matching shortcut."""
    reports = build_demo_issues(now)
    return [DuplicateSuggestion(
        id=UUID("8ff68d26-41d1-4b30-9597-6f9400000001"),
        issue_id=reports[0].id,
        candidate_issue_id=reports[1].id,
        confidence=0.93,
        reason=("Both reports describe an elevator at Swem Library failing to respond "
                "to calls and preventing access to upper floors. The location and "
                "reported failure suggest the same outage, though the asset is not explicitly identified."),
        origin="demo_fixture",
        created_at=now,
    )]

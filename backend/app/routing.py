"""Backend-owned destinations derived only from the final canonical category."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StrictBool, StringConstraints


_CATEGORY_TEAMS = {
    "Elevator": "Facilities — Elevator Maintenance",
    "Electrical": "Facilities — Electrical",
    "Plumbing": "Facilities — Plumbing",
    "Walkway": "Facilities — Grounds",
    "Lighting": "Facilities — Electrical",
    "Network": "IT — Network Services",
    "Other": "Facilities — General Triage",
}

RoutingText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RoutingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    responsible_team: RoutingText
    category: RoutingText
    rule: RoutingText
    is_fallback: StrictBool


def route_category(category: str) -> RoutingDecision:
    """Resolve a destination, not a dispatch or lifecycle transition.

    Empty categories are invalid, as in IssueCreate. All other unknown text
    falls back safely without fuzzy matching or any model calls.
    """
    category = category.strip()
    if not category:
        raise ValueError("category must not be empty")
    for known_category, team in _CATEGORY_TEAMS.items():
        if category.lower() == known_category.lower():
            return RoutingDecision(
                responsible_team=team,
                category=known_category,
                rule=f"Category '{known_category}' routes to {team}.",
                is_fallback=False,
            )
    team = _CATEGORY_TEAMS["Other"]
    return RoutingDecision(
        responsible_team=team,
        category=category,
        rule=f"Unrecognized category '{category}' routes to {team} (fallback).",
        is_fallback=True,
    )

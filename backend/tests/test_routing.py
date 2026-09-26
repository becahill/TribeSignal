"""Category-only routing: explicit rules, conservative matching, safe fallback."""

import pytest

from app.routing import route_category


@pytest.mark.parametrize("category,team", [
    ("Elevator", "Facilities — Elevator Maintenance"),
    ("Electrical", "Facilities — Electrical"),
    ("Plumbing", "Facilities — Plumbing"),
    ("Walkway", "Facilities — Grounds"),
    ("Lighting", "Facilities — Electrical"),
    ("Network", "IT — Network Services"),
    ("Other", "Facilities — General Triage"),
])
def test_supported_routes_are_normalized_and_repeatable(category, team):
    expected = {
        "responsible_team": team,
        "category": category,
        "rule": f"Category '{category}' routes to {team}.",
        "is_fallback": False,
    }
    for value in [category, category.lower(), category.upper(), f" \t{category}\n "]:
        for _ in range(3):
            assert route_category(value).model_dump() == expected


@pytest.mark.parametrize("category", [
    "Unlisted equipment", "Elevators", "Ele vator", "Wi-Fi", "???", "🛠", "x" * 200,
])
def test_unknown_categories_fall_back_without_fuzzy_matching(category):
    result = route_category(f"  {category}  ")
    assert result.responsible_team == "Facilities — General Triage"
    assert result.category == category
    assert result.is_fallback is True
    assert result.rule == (
        f"Unrecognized category '{category}' routes to Facilities — General Triage (fallback)."
    )
    assert route_category(category) == result


@pytest.mark.parametrize("category", ["", " ", "\t\n"])
def test_empty_category_is_invalid_like_issue_create(category):
    with pytest.raises(ValueError, match="category must not be empty"):
        route_category(category)

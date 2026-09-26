from datetime import timedelta
from unittest.mock import Mock, call, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.demo_data import build_demo_issues
from app.main import create_app
from app.models import Issue
from app.priority import calculate_priority
from app.repository import InMemoryIssueRepository


@pytest.mark.parametrize("value", [None, "", "0", "false", "no", "off", "unexpected"])
def test_demo_disabled_starts_empty(monkeypatch, now, value):
    if value is not None:
        monkeypatch.setenv("TRIBESIGNAL_DEMO_MODE", value)
    clock = Mock(return_value=now)
    app = create_app(clock=clock)
    clock.assert_not_called()
    with TestClient(app) as client:
        response = client.get("/issues")
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE", "YeS", " ON "])
def test_demo_enabled_returns_seeded_issues(monkeypatch, now, value):
    monkeypatch.setenv("TRIBESIGNAL_DEMO_MODE", value)
    clock = Mock(return_value=now)
    app = create_app(clock=clock)
    clock.assert_called_once_with()
    with TestClient(app) as client:
        response = client.get("/issues")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 6
        assert [{k: v for k, v in item.items() if k in Issue.model_fields} for item in data] == [
            issue.model_dump(mode="json") for issue in build_demo_issues(now)
        ]


@pytest.mark.parametrize("populated", [False, True])
def test_demo_mode_preserves_injected_repository(monkeypatch, now, payload, populated):
    monkeypatch.setenv("TRIBESIGNAL_DEMO_MODE", "true")
    issues = [Issue(**payload, id=uuid4(), created_at=now)] if populated else []
    repository = InMemoryIssueRepository(initial_issues=issues)
    clock = Mock(return_value=now)
    app = create_app(repository=repository, clock=clock)
    assert app.state.repository is repository
    clock.assert_not_called()
    with TestClient(app) as client:
        response = client.get("/issues")
        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [str(issue.id) for issue in issues]


def test_demo_priorities_use_existing_engine(monkeypatch, now):
    monkeypatch.setenv("TRIBESIGNAL_DEMO_MODE", "true")
    with patch("app.main.calculate_priority", wraps=calculate_priority) as engine:
        app = create_app(clock=lambda: now)
        engine.assert_not_called()
        with TestClient(app) as client:
            response = client.get("/issues")
            assert response.status_code == 200
            data = response.json()
        issues = app.state.repository.list()
        assert engine.call_args_list == [call(issue, now=now) for issue in issues]

    assert [item["priority"] for item in data] == [
        calculate_priority(issue, now=now).model_dump(mode="json") for issue in issues
    ]
    assert len({item["priority"]["score"] for item in data}) == 6
    assert all("priority" not in issue.model_dump() for issue in issues)


def test_demo_priorities_age_and_confirm_live(monkeypatch, now):
    monkeypatch.setenv("TRIBESIGNAL_DEMO_MODE", "true")
    current = now
    app = create_app(clock=lambda: current)
    with TestClient(app) as client:
        original = client.get("/issues").json()[0]
        current += timedelta(hours=6)
        detail = client.get(f"/issues/{original['id']}")
        assert detail.status_code == 200
        aged = detail.json()
        assert aged["created_at"] == original["created_at"]
        assert aged["priority"]["score"] > original["priority"]["score"]
        response = client.post(f"/issues/{original['id']}/confirm")
        assert response.status_code == 200
        confirmed = response.json()
        assert confirmed["confirmation_count"] == original["confirmation_count"] + 1
        assert confirmed["priority"]["score"] > aged["priority"]["score"]
        updated_issue = app.state.repository.list()[0]
        assert confirmed["priority"] == calculate_priority(
            updated_issue, now=current
        ).model_dump(mode="json")
        assert client.get("/issues").json()[0] == confirmed


def test_demo_restart_restores_dataset(monkeypatch, now, payload):
    monkeypatch.setenv("TRIBESIGNAL_DEMO_MODE", "true")
    with TestClient(create_app(clock=lambda: now)) as client:
        initial = client.get("/issues").json()
        assert client.post(f"/issues/{initial[0]['id']}/confirm").status_code == 200
        assert client.post("/issues", json=payload).status_code == 201
        assert len(client.get("/issues").json()) == 7
        with TestClient(create_app(clock=lambda: now)) as restarted:
            assert restarted.get("/issues").json() == initial
        assert len(client.get("/issues").json()) == 7


@pytest.mark.parametrize("decision", ["confirm", "reject"])
def test_swem_routing_survives_human_review(monkeypatch, now, no_live_gemini, decision):
    monkeypatch.setenv("TRIBESIGNAL_DEMO_MODE", "true")
    app = create_app(clock=lambda: now)
    with TestClient(app) as client:
        before = client.get("/issues").json()
        assert len(before) == 6
        swem, second, *_ = before
        expected = {
            "responsible_team": "Facilities — Elevator Maintenance",
            "category": "Elevator",
            "rule": "Category 'Elevator' routes to Facilities — Elevator Maintenance.",
            "is_fallback": False,
        }
        assert swem["routing"] == second["routing"] == expected
        assert swem["priority"]["score"] == 7.25
        suggestion, = client.get(f"/issues/{swem['id']}/duplicate-suggestions").json()
        response = client.post(f"/duplicate-suggestions/{suggestion['id']}/{decision}")
        assert response.status_code == 200
        queue = response.json()["issues"]
        assert client.get("/issues").json() == queue
        canonical = queue[0]
        assert canonical["routing"] == expected
        assert canonical["status"] == swem["status"] == "reported"
        assert client.get(f"/issues/{swem['id']}").json() == canonical
        assert client.get(f"/issues/{second['id']}").json()["routing"] == expected
        if decision == "confirm":
            assert len(queue) == 5
            assert second["id"] not in {issue["id"] for issue in queue}
            assert len(canonical["source_reports"]) == 2
            assert [report["confirmation_count"] for report in canonical["source_reports"]] == [8, 3]
            assert canonical["effective_confirmation_count"] == 11
            assert canonical["priority"]["score"] == 7.44
            assert queue[1:] == before[2:]
            raw = app.state.repository.get(UUID(swem["id"]))
            expected_priority = calculate_priority(raw.model_copy(update={"confirmation_count": 11}), now=now)
            assert canonical["priority"] == expected_priority.model_dump(mode="json")
        else:
            assert len(queue) == 6
            for original, current in zip(before, queue, strict=True):
                assert current["routing"] == original["routing"]
                assert current["priority"] == original["priority"]
                assert current["source_reports"] == original["source_reports"]
        assert all("routing" not in report.model_dump() for report in app.state.repository.list())
    no_live_gemini.assert_not_called()

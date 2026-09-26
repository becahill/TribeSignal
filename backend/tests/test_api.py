from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_issue_create_list_and_detail(client, payload, now):
    assert client.get("/issues").json() == []
    response = client.post("/issues", json=payload)
    assert response.status_code == 201
    issue = response.json()
    UUID(issue["id"])
    assert {key: issue[key] for key in payload} == payload
    assert issue["confirmation_count"] == 0
    assert issue["status"] == "reported"
    assert datetime.fromisoformat(issue["created_at"]) == now
    assert issue["created_at"].endswith("Z")
    assert issue["priority"]["score"] == 5.5
    assert issue["priority"]["components"] == {
        "severity": 4.0, "accessibility": 1.5, "safety": 0.0,
        "confirmations": 0.0, "aging": 0.0,
    }
    assert datetime.fromisoformat(issue["priority"]["calculated_at"]) == now
    detail = client.get(f"/issues/{issue['id']}")
    assert detail.status_code == 200
    assert detail.json() == issue
    listing = client.get("/issues")
    assert listing.status_code == 200
    assert listing.json() == [issue]


def test_confirm_increments_and_recalculates(client, payload):
    issue = client.post("/issues", json=payload).json()
    for count, expected in [(1, 5.5), (2, 5.92), (3, 6.16)]:
        response = client.post(f"/issues/{issue['id']}/confirm")
        assert response.status_code == 200
        updated = response.json()
        assert updated["confirmation_count"] == count
        assert updated["priority"]["score"] == expected
        assert updated["created_at"] == issue["created_at"]
        assert updated["id"] == issue["id"]
        assert {key: updated[key] for key in payload} == payload
    assert client.get(f"/issues/{issue['id']}").json() == updated
    assert client.get("/issues").json() == [updated]


def test_reads_and_confirm_recalculate_aging(payload, now):
    current = now
    with TestClient(create_app(clock=lambda: current)) as client:
        issue = client.post("/issues", json=payload).json()
        current += timedelta(hours=36)
        for response in [
            client.get(f"/issues/{issue['id']}"),
            client.get("/issues"),
            client.post(f"/issues/{issue['id']}/confirm"),
        ]:
            data = response.json()
            if isinstance(data, list):
                data = data[0]
            assert data["priority"]["score"] == 6.0
            assert data["priority"]["components"]["aging"] == 0.5
            assert datetime.fromisoformat(data["priority"]["calculated_at"]) == current


@pytest.mark.parametrize("method,suffix", [("get", ""), ("post", "/confirm")])
def test_unknown_issue_returns_404(client, method, suffix):
    response = getattr(client, method)(f"/issues/{uuid4()}{suffix}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Issue not found"}
    assert client.get("/issues").json() == []


@pytest.mark.parametrize("method,suffix", [("get", ""), ("post", "/confirm")])
def test_invalid_issue_id(client, method, suffix):
    assert getattr(client, method)(f"/issues/not-a-uuid{suffix}").status_code == 422


@pytest.mark.parametrize("field,value", [
    ("title", " "), ("title", "x" * 201), ("description", ""),
    ("description", "x" * 10001), ("severity", "urgent"),
    ("accessibility_impact", "true"), ("accessibility_impact", 1),
    ("safety_impact", None), ("safety_impact", "false"),
    ("location", "\t"), ("category", ""),
    ("title", None), ("location", 42),
])
def test_invalid_issue_input(client, payload, field, value):
    assert client.post("/issues", json=payload | {field: value}).status_code == 422
    assert client.get("/issues").json() == []


@pytest.mark.parametrize("field", ["title", "description", "severity", "location", "category"])
def test_required_fields(client, payload, field):
    del payload[field]
    assert client.post("/issues", json=payload).status_code == 422


@pytest.mark.parametrize("field,value", [
    ("id", str(uuid4())), ("confirmation_count", 100),
    ("created_at", "2020-01-01T00:00:00Z"), ("status", "routed"),
    ("priority", {"score": 10}), ("unrecognized", "value"),
])
def test_server_owned_and_unknown_fields_rejected(client, payload, field, value):
    assert client.post("/issues", json=payload | {field: value}).status_code == 422


def test_defaults_and_whitespace_normalization(client, payload):
    del payload["accessibility_impact"]
    del payload["safety_impact"]
    payload["title"] = "  Broken elevator  "
    issue = client.post("/issues", json=payload).json()
    assert issue["title"] == "Broken elevator"
    assert issue["accessibility_impact"] is False
    assert issue["safety_impact"] is False


def test_each_app_has_isolated_storage(client, payload, now):
    client.post("/issues", json=payload)
    with TestClient(create_app(clock=lambda: now)) as other:
        assert other.get("/issues").json() == []


def test_clock_timezone_normalized_in_api(payload, now):
    offset_now = now.astimezone(timezone(timedelta(hours=-4)))
    with TestClient(create_app(clock=lambda: offset_now)) as client:
        issue = client.post("/issues", json=payload).json()
        assert issue["created_at"].endswith("Z")
        assert datetime.fromisoformat(issue["created_at"]) == now
        assert issue["priority"]["calculated_at"] == issue["created_at"]


def test_naive_app_clock_rejected(payload, now):
    with TestClient(create_app(clock=lambda: now.replace(tzinfo=None))) as client:
        with pytest.raises(ValueError, match="timezone-aware"):
            client.post("/issues", json=payload)


@pytest.mark.parametrize("origin", [
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:5173", "http://127.0.0.1:5173",
])
def test_local_cors_preflight(client, origin):
    response = client.options("/issues", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_cors_excludes_other_origins(client):
    response = client.get("/issues", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers


def test_configured_cors(monkeypatch):
    monkeypatch.setenv("TRIBESIGNAL_CORS_ORIGINS", " http://localhost:4200, ")
    with TestClient(create_app()) as client:
        response = client.get("/health", headers={"Origin": "http://localhost:4200"})
        assert response.headers["access-control-allow-origin"] == "http://localhost:4200"
        response = client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert "access-control-allow-origin" not in response.headers


def test_openapi_contract(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert set(response.json()["paths"]) == {
        "/health", "/issues", "/issues/analyze", "/issues/{issue_id}",
        "/issues/{issue_id}/confirm",
        "/issues/{issue_id}/duplicate-suggestions",
        "/issues/{issue_id}/duplicate-suggestions/analyze",
        "/duplicate-suggestions/{suggestion_id}/confirm",
        "/duplicate-suggestions/{suggestion_id}/reject",
    }

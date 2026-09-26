"""No live provider calls: exercise HTTP, emergency rules, and the SDK boundary."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.ai import GEMINI_MODEL, GEMINI_TIMEOUT_MS, GeminiIssueAnalyzer
from app.analysis_models import AnalysisCategory, AnalysisProposal, AnalysisResponse
from app.main import create_app
from app.safety import EMERGENCY_MESSAGE, is_emergency


REPORT = "The elevator in Swem is broken and a wheelchair user cannot get upstairs."
PROPOSAL = {
    "title": "Swem elevator unavailable",
    "description": "The elevator in Swem is not working, preventing wheelchair access upstairs.",
    "location": "Swem",
    "category": "Elevator",
    "accessibility_impact": True,
    "safety_impact": False,
}
FORBIDDEN_FIELDS = {
    "priority", "score", "urgency", "rank", "severity", "priority_score",
    "urgency_score", "ordering", "confidence", "response_deadline", "sla",
    "escalation_level", "severity_recommendation",
}


@pytest.fixture(autouse=True)
def no_live_gemini(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    factory = MagicMock(side_effect=AssertionError("Live Gemini client forbidden in tests"))
    monkeypatch.setattr("app.ai.genai.Client", factory)
    return factory


class FakeAnalyzer:
    def __init__(self, result=None, error=None):
        self.result = AnalysisProposal(**PROPOSAL) if result is None else result
        self.error = error
        self.calls = []

    def analyze(self, text):
        self.calls.append(text)
        if self.error:
            raise self.error
        return self.result

    def __bool__(self):
        # An explicitly supplied implementation must win even when falsey.
        return False


@pytest.mark.parametrize("body", [
    {}, {"text": ""}, {"text": " \n\t "}, {"text": "x" * 10001},
    {"text": None}, {"text": 7}, {"text": [REPORT]},
    {"text": REPORT, "severity": "critical"},
])
def test_invalid_analysis_input(body):
    analyzer = FakeAnalyzer()
    with TestClient(create_app(analyzer=analyzer)) as client:
        assert client.post("/issues/analyze", json=body).status_code == 422
        assert client.get("/issues").json() == []
    assert analyzer.calls == []


def test_injected_analyzer_receives_trimmed_text_and_does_not_create(no_live_gemini):
    analyzer = FakeAnalyzer()
    app = create_app(analyzer=analyzer)
    assert app.state.analyzer is analyzer
    with TestClient(app) as client:
        response = client.post("/issues/analyze", json={"text": f"  {REPORT}\n"})
        assert response.status_code == 200
        assert response.json() == {"status": "review", "proposal": PROPOSAL}
        assert client.get("/issues").json() == []
    assert analyzer.calls == [REPORT]
    no_live_gemini.assert_not_called()


@pytest.mark.parametrize("text", [
    "There is an active fire in the library.",
    "There is an electrical fire in the basement.",
    "The electrical panel is on fire!",
    "There is a gas leak in the lab.",
    "Gas is leaking near the kitchen.",
    "There was an explosion in the lab just now.",
    "An explosion just happened in the building.",
    "Someone is trapped in an elevator.",
    "My friend is stuck inside the lift.",
    "I’m trapped in the elevator.",
    "A person is seriously injured.",
    "This is an immediate threat to life.",
    "There is thick smoke and we cannot breathe.",
    "People are choking in the smoke.",
    "Floodwater is reaching live wires.",
    "Active flooding has water touching the sparking electrical panel.",
    "The alarm panel is damaged, but there is an active fire upstairs.",
    "There is no gas leak. Someone is trapped in an elevator.",
    "There was a drill yesterday. The kitchen is on fire now.",
])
def test_emergency_stops_before_analyzer_and_does_not_create(text, no_live_gemini):
    analyzer = FakeAnalyzer(error=AssertionError("Must not call analyzer"))
    with TestClient(create_app(analyzer=analyzer)) as client:
        response = client.post("/issues/analyze", json={"text": text})
        assert response.status_code == 200
        assert response.json() == {"status": "emergency", "message": EMERGENCY_MESSAGE}
        assert client.get("/issues").json() == []
    assert analyzer.calls == []
    no_live_gemini.assert_not_called()


@pytest.mark.parametrize("text", [
    REPORT,
    "The fire alarm panel appears damaged.",
    "An active fire alarm is beeping without smoke.",
    "There is a fire extinguisher missing from the wall.",
    "The elevator is stuck on the second floor, but no one is inside.",
    "The gas leak detector needs a new battery.",
    "There is no gas leak; the detector cover is broken.",
    "There is not an active fire.",
    "The gas leak has been repaired.",
    "The active fire was extinguished.",
    "The smoke detector battery is low.",
    "What if someone is trapped in an elevator?",
    "The fire drill involved someone trapped in an elevator.",
    "An explosion happened last week; the door still needs repair.",
    "Water is leaking beneath the bathroom sink.",
    "The walkway has raised paving and is hard to use with a wheelchair.",
])
def test_ordinary_infrastructure_and_noncurrent_language_passes(text):
    assert not is_emergency(text)
    analyzer = FakeAnalyzer()
    with TestClient(create_app(analyzer=analyzer)) as client:
        assert client.post("/issues/analyze", json={"text": text}).json()["status"] == "review"
    assert analyzer.calls == [text]


@pytest.mark.parametrize("category", list(AnalysisCategory))
def test_controlled_categories_accepted(category):
    analyzer = FakeAnalyzer(result=PROPOSAL | {"category": category.value})
    with TestClient(create_app(analyzer=analyzer)) as client:
        response = client.post("/issues/analyze", json={"text": REPORT})
        assert response.status_code == 200
        assert response.json()["proposal"]["category"] == category.value


@pytest.mark.parametrize("field,value", [
    ("category", "AI invented category"), ("category", "elevator"),
    ("title", " "), ("title", "x" * 201), ("description", "x" * 10001),
    ("location", None), ("location", "x" * 201),
    ("accessibility_impact", "true"), ("safety_impact", 1),
] + [(field, 10) for field in sorted(FORBIDDEN_FIELDS)])
def test_invalid_or_forbidden_proposal_fails_safely(field, value):
    analyzer = FakeAnalyzer(result=PROPOSAL | {field: value})
    with TestClient(create_app(analyzer=analyzer)) as client:
        response = client.post("/issues/analyze", json={"text": REPORT})
        assert response.status_code == 503
        assert response.json()["status"] == "unavailable"
        assert "proposal" not in response.json()
        assert client.get("/issues").json() == []


def test_bypassed_model_validation_is_rechecked():
    bad = AnalysisProposal.model_construct(**(PROPOSAL | {"safety_impact": "yes"}))
    with TestClient(create_app(analyzer=FakeAnalyzer(result=bad))) as client:
        assert client.post("/issues/analyze", json={"text": REPORT}).status_code == 503


def test_unknown_location_stays_blank_for_human_to_fill():
    with TestClient(create_app(analyzer=FakeAnalyzer(result=PROPOSAL | {"location": ""}))) as client:
        proposal = client.post("/issues/analyze", json={"text": REPORT}).json()["proposal"]
        assert proposal["location"] == ""
        assert client.post("/issues", json=proposal | {"severity": "low"}).status_code == 422


def test_missing_configuration_keeps_manual_reporting_working(payload, no_live_gemini):
    with TestClient(create_app()) as client:
        response = client.post("/issues/analyze", json={"text": REPORT})
        assert response.status_code == 503
        assert response.json()["status"] == "unavailable"
        assert "manually" in response.json()["message"]
        assert client.post("/issues", json=payload).status_code == 201
        assert client.get("/health").json() == {"status": "ok"}
    no_live_gemini.assert_not_called()


@pytest.mark.parametrize("error", [RuntimeError("provider detail must stay private"), TimeoutError()])
def test_provider_failure_keeps_manual_reporting_working(error, payload, caplog, capsys):
    with TestClient(create_app(analyzer=FakeAnalyzer(error=error))) as client:
        response = client.post("/issues/analyze", json={"text": REPORT})
        assert response.status_code == 503
        assert "provider detail" not in response.text
        assert client.post("/issues", json=payload).status_code == 201
    assert "provider detail" not in caplog.text + str(capsys.readouterr())


def test_analysis_then_human_creation_uses_existing_engine(now):
    analyzer = FakeAnalyzer()
    with TestClient(create_app(analyzer=analyzer, clock=lambda: now)) as client:
        proposal = client.post("/issues/analyze", json={"text": REPORT}).json()["proposal"]
        assert client.get("/issues").json() == []
        assert client.post("/issues", json=proposal).status_code == 422  # No AI severity.
        reviewed = proposal | {"title": "Corrected by reporter", "severity": "low", "safety_impact": True}
        response = client.post("/issues", json=reviewed)
        assert response.status_code == 201
        assert response.json()["priority"]["score"] == 4.5  # 1 + 1.5 + 2.
        assert response.json()["title"] == reviewed["title"]
        assert len(client.get("/issues").json()) == 1
    assert analyzer.calls == [REPORT]  # Creation never consults the analyzer.


def test_demo_mode_analysis_has_no_side_effects(monkeypatch, now):
    monkeypatch.setenv("TRIBESIGNAL_DEMO_MODE", "true")
    with TestClient(create_app(analyzer=FakeAnalyzer(), clock=lambda: now)) as client:
        before = client.get("/issues").json()
        assert len(before) == 6
        assert client.post("/issues/analyze", json={"text": REPORT}).status_code == 200
        assert client.get("/issues").json() == before


def test_public_analysis_schema_cannot_set_priority_or_severity():
    # Inspect every nested property (including referenced models), not only the
    # top-level envelope. Whitelist also prevents differently named score fields.
    expected = {"status", "proposal", "message", *PROPOSAL}

    def inspect(schema):
        if isinstance(schema, dict):
            properties = schema.get("properties", {})
            assert set(properties) <= expected
            assert not any(term in key.lower() for key in properties for term in FORBIDDEN_FIELDS)
            for value in schema.values():
                inspect(value)
        elif isinstance(schema, list):
            for value in schema:
                inspect(value)

    inspect(TypeAdapter(AnalysisResponse).json_schema())
    spec = create_app().openapi()
    # Resolve only schemas reachable from this operation, not IssueResponse.
    seen = set()

    def inspect_openapi(schema):
        inspect(schema)
        if isinstance(schema, dict):
            ref = schema.get("$ref")
            if ref and ref not in seen:
                seen.add(ref)
                inspect_openapi(spec["components"]["schemas"][ref.rsplit("/", 1)[-1]])
            for value in schema.values():
                inspect_openapi(value)
        elif isinstance(schema, list):
            for value in schema:
                inspect_openapi(value)

    for status in ("200", "503"):
        inspect_openapi(spec["paths"]["/issues/analyze"]["post"]["responses"][status])


@pytest.fixture
def sdk_client(monkeypatch):
    # Placeholder, never a real credential; all client construction is mocked.
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    client.models.generate_content.return_value = SimpleNamespace(text=json.dumps(PROPOSAL))
    monkeypatch.setattr("app.ai.genai.Client", factory)
    return factory, client


def test_sdk_uses_strict_schema_timeout_and_separate_system_instruction(sdk_client):
    factory, client = sdk_client
    assert GeminiIssueAnalyzer().analyze(REPORT).model_dump(mode="json") == PROPOSAL
    options = factory.call_args.kwargs
    assert options["vertexai"] is False
    assert options["http_options"].timeout == GEMINI_TIMEOUT_MS
    assert options["http_options"].retry_options.attempts == 1
    kwargs = client.models.generate_content.call_args.kwargs
    assert kwargs["model"] == GEMINI_MODEL
    assert kwargs["contents"] == REPORT
    config = kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == AnalysisProposal.model_json_schema()
    assert config.response_json_schema["additionalProperties"] is False
    assert "Never output severity or priority" in config.system_instruction
    factory.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize("text", [
    None, "", "not json", "[]", "null", "{}",
    json.dumps(PROPOSAL | {"priority": 10}),
    json.dumps(PROPOSAL | {"category": "Invented"}),
    json.dumps(PROPOSAL | {"safety_impact": "true"}),
])
def test_malformed_sdk_output_fails_safely(text, sdk_client):
    _, client = sdk_client
    client.models.generate_content.return_value = SimpleNamespace(text=text)
    with TestClient(create_app()) as api:
        response = api.post("/issues/analyze", json={"text": REPORT})
        assert response.status_code == 503
        assert response.json()["status"] == "unavailable"
        assert api.get("/issues").json() == []


def test_sdk_timeout_is_sanitized_and_client_closed(sdk_client):
    factory, client = sdk_client
    client.models.generate_content.side_effect = TimeoutError("private provider details")
    with TestClient(create_app()) as api:
        response = api.post("/issues/analyze", json={"text": REPORT})
        assert response.status_code == 503
        assert "private" not in response.text
    factory.return_value.__exit__.assert_called_once()


def test_emergency_does_not_even_construct_configured_sdk_client(sdk_client):
    factory, _ = sdk_client
    with TestClient(create_app()) as api:
        assert api.post("/issues/analyze", json={"text": "Someone is trapped in an elevator."}).json()["status"] == "emergency"
    factory.assert_not_called()

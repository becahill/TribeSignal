# TribeSignal
An AI-assisted triage layer for campus infrastructure issues, providing transparent classification, deterministic prioritization, and routing between reporters and response teams.

TribeSignal sits between community intake and operational teams/systems such as
TMA/FAMIS. It is a transparent triage layer, not a replacement work-order system.
AI never determines, adjusts, ranks, or overrides priority.

## Backend development

The first vertical slice provides issue intake, retrieval, confirmations, and an
auditable deterministic priority calculation. There is no AI integration in this
slice. Python 3.11+ is required.

From the repository root:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e 'backend[test]'
backend/.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Interactive API documentation: <http://localhost:8000/docs>.

Run the tests from the repository root:

```sh
backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests
```

The modules under `backend/app/` separate validated data (`models.py`), the sole
priority implementation (`priority.py`), storage (`repository.py`), and the HTTP
API (`main.py`). `create_app` accepts an injected repository and clock for tests.
No frontend priority calculation is needed.

## API contract

| Endpoint | Result |
| --- | --- |
| `GET /health` | `200`, `{"status": "ok"}` |
| `POST /issues` | `201`, newly created issue with priority |
| `GET /issues` | `200`, array of issues in creation order with current priorities |
| `GET /issues/{issue_id}` | `200`, issue with current priority |
| `POST /issues/{issue_id}/confirm` | `200`, updated issue with current priority; no body required |

Unknown UUIDs return `404`; invalid UUIDs or request bodies return `422`.

Example intake:

```sh
curl -X POST http://localhost:8000/issues \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Elevator unavailable",
    "description": "The library elevator does not respond to calls.",
    "severity": "high",
    "accessibility_impact": true,
    "safety_impact": false,
    "location": "Library, first floor",
    "category": "elevator"
  }'
```

Severity values are `low`, `moderate`, `high`, and `critical`. Both impact flags
default to `false` and accept JSON booleans only. The remaining intake fields are
required. Text is trimmed and must be nonempty; description is limited to 10,000
characters and title/location/category to 200. Location and category are free
text for now. Unknown fields, including attempts to set server-owned fields, are
rejected.

The server assigns a UUID, UTC-aware `created_at`, status `reported`, and zero
confirmations. Each issue response includes all issue fields plus `priority`
with `score`, `components`, `explanation`, and UTC `calculated_at`. Priority is
recomputed on every read and confirmation so aging does not become stale.

## Deterministic priority

`P = min(10, severity + accessibility + safety + confirmations + aging)`

- Severity: low = 1.0, moderate = 2.5, high = 4.0, critical = 5.5.
- Accessibility impact: +1.5 when true.
- Safety impact: +2.0 when true.
- Confirmations: 0 when C = 0; otherwise `min(2.0, 0.6 * ln(C))`.
- Aging: `min(1.0, HoursOpen / 72)`.

Elapsed time uses aware timestamps normalized to UTC. Naive timestamps are
rejected; future creation times have zero age to tolerate clock skew. Components
retain full precision for auditing. The final capped score is rounded to two
decimals using Python's `round`; explanatory terms are formatted to two decimals.
Displayed terms can therefore differ slightly from the rounded total. Capped
explanations explicitly show the uncapped total and the cap.

High severity, accessibility impact, no safety impact, three confirmations, and
zero age produces `score: 6.16` and:

```text
4.00 severity + 1.50 accessibility + 0.00 safety + 0.66 confirmations + 0.00 aging = 6.16/10
```

## Local development limits

Storage is in memory, isolated per application instance, and lost on restart or
reload. Use one Uvicorn worker; multiple processes would have independent data.
Confirmation increments are atomic within that process. There is no identity or
idempotency tracking: every confirmation request increments the counter,
including repeated requests from the same caller. The first confirmation adds
zero priority weight because `ln(1) = 0`.

CORS allows `localhost` and `127.0.0.1` on ports 3000 and 5173 by default. Override
with the comma-separated `TRIBESIGNAL_CORS_ORIGINS` environment variable. No
credentialed cross-origin requests are enabled.

This slice does not implement routing actions, deduplication, AI, authentication,
notifications, downstream integrations, maps, dashboards, or a production database.

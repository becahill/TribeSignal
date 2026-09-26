# TribeSignal
An AI-assisted triage layer for campus infrastructure issues, with optional report organization, human-reviewed duplicates, and transparent deterministic priority and routing.

TribeSignal sits between community intake and operational teams/systems such as
TMA/FAMIS. It is a transparent triage layer, not a replacement work-order system.
AI never determines, adjusts, ranks, or overrides priority or chooses routing.

## Backend development

The backend provides issue intake, retrieval, confirmations, optional Gemini
analysis, and auditable deterministic priority and routing. Python 3.11+ is required.

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
priority implementation (`priority.py`), category-to-team rules (`routing.py`), storage (`repository.py`), and the HTTP
API (`main.py`). `create_app` accepts an injected repository, clock, and
`IssueAnalyzer` / `DuplicateAnalyzer` for tests. `ai.py` owns the Gemini adapter and analysis service;
`analysis_models.py` defines the proposal-only contract and `safety.py` the
deterministic emergency check. Tests use fake analyzers and mocked SDK clients,
never live Gemini calls.
No frontend priority calculation is needed.

## Optional Gemini-assisted intake

The report dialog starts with **What are you seeing?**. **Analyze report** runs a
deterministic emergency pre-check before sending the description to Gemini.
The reporter then edits the proposed title, description, location, category, and
impact flags, explicitly chooses severity (no default), and confirms review.
Only **Submit report** creates an issue, through the existing `POST /issues`.
AI structures facts; it never supplies severity, priority, urgency, or ranking.
The backend priority formula is unchanged. Impact flags are proposals too and
must be reviewed because the final human-approved flags are inputs to that formula.

To enable assistance, set **`GEMINI_API_KEY` in the backend environment only**.
Optionally copy `backend/.env.example` to `backend/.env`, edit it locally, then
load it before starting the backend (the application does not auto-load files):

```sh
set -a
source backend/.env
set +a
backend/.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Never put the key in a `VITE_` variable or frontend file. Local `.env` files are
ignored; examples contain no credentials. The adapter uses the official
[Google Gen AI Python SDK](https://googleapis.github.io/python-genai/) with
schema-constrained JSON and local validation, using stable
[`gemini-3.5-flash-lite`](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).
It uses a 15-second HTTP timeout with no retries; the browser gives analysis
20 seconds and lets the reporter switch to manual entry while waiting.

**Enter details manually** is always available before analysis and on failure.
Missing configuration, provider errors, timeouts, or malformed proposals return
an unavailable state without fabricating data or storing an issue. The original
description is retained for manual entry. Raw provider errors are not returned or
logged by the application. No Gemini key is required for normal reporting or demo mode.

The emergency gate matches explicit English phrases for active fire, gas leaks,
explosions, people trapped in elevators, serious injury, smoke with breathing
danger, threats to life, and floodwater contacting live electrical equipment.
Explicit local negation, conditional, historical, and drill contexts are excluded;
a damaged fire alarm panel alone does not trigger it. A match stops analysis
before any SDK client is created and shows emergency-channel guidance, with an
option to correct the description. It never creates an issue or sets severity.
These conservative rules are not comprehensive emergency detection or medical
diagnosis. The gate applies to `/issues/analyze`; the manual `POST /issues`
contract remains unchanged.

Browser verification after starting both services:

- With a valid backend key: describe the Swem elevator problem → analyze → edit
  the proposal → verify severity starts blank → choose severity and review the
  facts/flags → submit → expand the queue's deterministic priority explanation.
- Without a key: analyze a routine report → unavailable message → enter details
  manually → choose severity → submit successfully. Direct manual entry also works.
- Analyze “Someone is trapped in an elevator.” → emergency guidance, no review
  or submit action → edit the description to correct an incorrect detection.

## Demo mode

After backend setup, start from the repository root with:

```sh
TRIBESIGNAL_DEMO_MODE=true \
backend/.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

This loads six fictional William & Mary campus reports with stable IDs, including
two intentionally similar Swem elevator reports and a pending duplicate suggestion
explicitly marked `demo_fixture`. The suggestion can be reviewed without a Gemini key. Priorities are calculated live
by the existing deterministic engine; the seed data contains no priority scores.
Restarting or reloading in demo mode restores the known dataset, with report ages
relative to startup. Changes made during a session are not persisted. The flag
also accepts `1`, `yes`, and `on` (case-insensitive). Running without the variable
preserves the empty in-memory behavior. Explicitly injected repositories are
always used as supplied, regardless of the flag.

## Human-reviewed semantic duplicate detection

```text
deterministic candidate filter
→ Gemini semantic comparison
→ human review
→ canonical issue association
→ deterministic priority recalculation
```

**AI proposes; humans confirm.** Open an issue's duplicate section and select
**Check for possible duplicates** for a live comparison. Candidate retrieval
requires an exact category and location match after case/whitespace normalization,
and creation times within 72 hours. It does not resolve aliases or ambiguous
locations. Each explicit check compares at most three previously unassessed pairs,
traversed by creation time and UUID; use the button again for remaining candidates.
Successful negative comparisons and existing suggestions are reused, including
rejected suggestions. Failed comparisons remain retryable. Queue reads, intake,
community confirmations, and review never trigger model calls.

`duplicates.py` owns the separately injectable Gemini comparison boundary;
`duplicate_models.py` defines its constrained schema. Gemini receives only the two
reports' title, description, location, category, and creation time. It returns
`is_possible_duplicate`, semantic-match `confidence`, and a factual `reason`.
The system instruction treats report text as untrusted data, preserves uncertainty,
forbids invented locations, and prohibits priority, severity, urgency, ranking,
routing, or action judgments. The backend revalidates JSON and injected analyzers,
rejects extra fields and invalid values, and conservatively rejects consequential
language in the reason. Prose is never executed or interpreted as a decision.
Keys stay backend-only, requests use the existing 15-second timeout with no retries,
and raw provider exceptions are never returned or logged. The browser allows up
to 50 seconds for a batch of three. Gemini failure does not break core reporting;
analysis returns `unavailable`, keeps any existing evidence, and never associates reports.

The card shows **Possible duplicate**, both original reports and timestamps,
semantic similarity wording (not a calibrated probability), and the explicit
message **“AI suggested this relationship. A person must review it.”** Only a
person's **Confirm same issue** or **Keep separate** action records a decision.
Review history stores the decision, timestamp, and `reviewed_by: human`. No identity
system is implemented, so this records an explicit review action, not an authenticated
reviewer's identity.

Confirmation associates sources under the earliest `created_at`, with the lowest
UUID as a deterministic tie-break. The choice is independent of AI. Both original
titles, descriptions, timestamps, raw counts, severities, and impact flags remain
preserved. Only one canonical operational issue remains in the queue; its card
shows the associated report count and expandable originals and review history.
Rejection keeps both reports independent and does not change counts or priority.
Later associations that would contradict a keep-separate decision return a conflict.

**AI confidence never affects priority.** The canonical report retains its own
severity and impact flags. Its effective community signal is the sum of raw
confirmation counts for distinct associated source IDs. That count is passed to
`priority.py`, whose formula is unchanged; no aggregate is written back to a source.
This prevents double-counting on repeated or overlapping association requests.
A subsequent community confirmation increments only the addressed source and is
reflected in the next canonical total. Reviews and source increments share the
repository lock; model calls run outside it. Without voter identity, confirmations
from the same person on different source reports cannot be deduplicated.

To demonstrate the seeded Swem case:

1. Start the backend in demo mode using the command above, then start the frontend
   using the commands below. No Gemini key is needed.
2. Open **Possible duplicate** on **Swem Library elevator unavailable**. Inspect
   the second Swem report, explanation, similarity label, and demo-fixture label.
   The card already shows **Routes to: Facilities — Elevator Maintenance**.
3. Choose **Confirm same issue**. The queue goes from six to five items. The older
   Swem issue now shows **2 community reports**, **11 confirmations** (8 + 3), and
   **Duplicate reviewed by human**. At startup ages, priority rises from about
   **7.25 to 7.44**, solely through the deterministic confirmation term.
4. Expand **View original reports & review history** and **Why this priority?**
   to inspect both source counts, original text, review timestamp, and priority factors.
   One operational card remains for Swem, still showing **Routes to:
   Facilities — Elevator Maintenance**, with the Elevator category rule visible.
5. Restart the demo backend to reset, then choose **Keep separate**. Both Swem
   issues remain, their counts/priorities are unchanged, and the pending badge disappears.

Backend tests block all live SDK clients; adapter tests mock Gemini. `npm test`
uses Node's built-in runner to verify the actual TypeScript runtime validators and
API methods without new test dependencies.

## Frontend development

The React/TypeScript frontend provides issue reporting, a queue sorted by the
backend's priority scores, expandable priority explanations, routing destinations and rules, and confirmations.
It is a triage workspace, not a replacement work-order system. No downstream
handoff functionality is connected.

With Node.js 22.12+ and npm installed, run in a second terminal from the repository
root (leave the backend command above running):

```sh
cd frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. The frontend calls <http://localhost:8000> directly;
the backend already allows this frontend origin through its development CORS
configuration. Vite uses port 5173 strictly so a port conflict cannot silently
move the app to an origin the backend does not allow.

To use another backend URL, copy `frontend/.env.example` to `frontend/.env.local`,
set `VITE_API_BASE_URL`, and restart Vite. Only public configuration belongs in
Vite environment variables. If changing the frontend port/origin, update the
backend's `TRIBESIGNAL_CORS_ORIGINS` too.

Frontend checks (from `frontend/`):

```sh
npm test
npm run typecheck
npm run build
npm run preview
```

Preview serves the production build at <http://127.0.0.1:5173> and requires the
backend to be running. Stop the development server before starting preview.
Fonts are bundled locally; no external font service is needed.

For a quick demo, start with the empty queue, submit a high-severity elevator
report with accessibility impact, then expand **Why this priority?**. Confirm it
three times to see the backend score reach approximately 6.16 (aging may add more
over time). Each confirmation refreshes the displayed issue from the response.
Repeated community confirmations remain possible because voter identity is not
tracked. Human duplicate review associates reports; it does not deduplicate people. Use **Refresh queue** to fetch current aging and reports from
other browser sessions; there is no background polling. Reports are lost when
the in-memory backend restarts.

API calls and response validation live in `frontend/src/api/issues.ts`; the
backend contract is mirrored in `frontend/src/types/issue.ts`. React components
only display returned components, scores, destinations, and explanations. There is no frontend
priority formula or category-to-team mapping. Failed refreshes retain the last loaded queue; failed report
submissions retain form input. A network failure during a write can leave its
outcome uncertain: check the queue before retrying to avoid duplicate reports or
confirmations. The client does not automatically retry writes.

## API contract

| Endpoint | Result |
| --- | --- |
| `GET /health` | `200`, `{"status": "ok"}` |
| `POST /issues` | `201`, newly created issue with priority and routing |
| `POST /issues/analyze` | `200`, editable proposal or emergency stop; `503`, assistance unavailable |
| `GET /issues` | `200`, canonical operational issues in creation order with current priorities and routing |
| `GET /issues/{issue_id}` | `200`, issue with current priority and canonical routing destination |
| `POST /issues/{issue_id}/confirm` | `200`, updated issue with current priority and routing; no body required |
| `GET /issues/{issue_id}/duplicate-suggestions` | `200`, relevant suggestions with both source reports and review history; never calls Gemini |
| `POST /issues/{issue_id}/duplicate-suggestions/analyze` | `200`, `complete` or `unavailable`, suggestions, and `remaining_candidates`; no body required |
| `POST /duplicate-suggestions/{suggestion_id}/confirm` | `200`, human-reviewed suggestion and refreshed canonical queue with routing |
| `POST /duplicate-suggestions/{suggestion_id}/reject` | `200`, human-reviewed suggestion and unchanged independent queue with routing |

Unknown UUIDs return `404`; invalid UUIDs or request bodies return `422`.
Duplicate review accepts no body or `{}`; extra fields are rejected. A repeated,
opposing, already-associated, or contradictory review returns `409` without
changing state. Clients never automatically retry writes.

Analysis accepts exactly `{"text": "..."}`: whitespace is trimmed, content must
be nonempty, and the limit is 10,000 characters. Responses are discriminated by
`status`: `review` with `proposal`, `emergency` with `message`, or `unavailable`
with `message`. Proposals contain only `title`, `description`, `location`,
`category`, `accessibility_impact`, and `safety_impact`. An unknown location stays
blank for the human to fill. Categories are `Elevator`, `Electrical`, `Plumbing`,
`Walkway`, `Lighting`, `Network`, and `Other`; unsupported provider categories or
extra fields are rejected with the manual-fallback state. Analysis never stores
an issue, changes the queue, or calls the priority engine.

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
text in the creation API for compatibility; only AI proposals use the controlled
category set. Unknown fields, including attempts to set server-owned fields, are
rejected.

The server assigns a UUID, UTC-aware `created_at`, status `reported`, and zero
confirmations. Each issue response includes all issue fields plus `priority`
with `score`, `components`, `explanation`, and UTC `calculated_at`. Priority is
recomputed on every read and confirmation so aging does not become stale.
`confirmation_count` remains the raw source count. `effective_confirmation_count`
is the sum of distinct `source_reports` in that response and is the count used for
its priority. Canonical responses contain all associated sources; linked-source
detail responses retain their own raw fields, count, and individual priority.
`canonical_issue_id` points to the current operational issue (self for an
independent/canonical report); `pending_duplicate_count` drives the review badge.
The canonical queue omits associated sources, but their original IDs remain
readable through `GET /issues/{issue_id}` and their full reports remain visible
under the canonical card. Searching the queue includes associated source text.

Every issue response also includes backend-computed `routing`:

```json
{
  "responsible_team": "Facilities — Elevator Maintenance",
  "category": "Elevator",
  "rule": "Category 'Elevator' routes to Facilities — Elevator Maintenance.",
  "is_fallback": false
}
```

Routing is derived on response construction and is never stored on reports or
accepted in intake. Client-supplied `routing` or team fields return `422` through
the existing extra-field rejection. Source report snapshots retain their raw fields;
linked-source detail and confirmation responses expose the canonical destination
in `routing` while preserving the source's original category and individual priority.

## Deterministic routing

```text
category → deterministic routing rule → responsible operational team
```

Routing is backend-owned: `backend/app/routing.py` is the single authoritative
mapping. Matching trims outer whitespace and ignores case; it never uses fuzzy
matching, embeddings, confidence scores, or AI. AI does not choose routing.
Gemini may propose a category during intake, but a human reviews it before submission;
the final category is the only routing input.

| Category | Responsible operational team |
| --- | --- |
| Elevator | Facilities — Elevator Maintenance |
| Electrical | Facilities — Electrical |
| Plumbing | Facilities — Plumbing |
| Walkway | Facilities — Grounds |
| Lighting | Facilities — Electrical |
| Network | IT — Network Services |
| Other | Facilities — General Triage |
| Unknown category | Facilities — General Triage (fallback) |

Known matches return the standard category label. Unknown free-text categories
preserve their trimmed text as the routing basis, set `is_fallback: true`, and
explain the General Triage fallback on the card. `Other` is an explicit supported
rule, not a fallback. Empty/whitespace-only categories remain invalid (`422`),
as do non-text categories and categories longer than 200 characters.

Canonical issues have one routing destination based on the canonical category.
Duplicate confidence, source counts, severity, aging, and priority never enter
routing. Human-reviewed associations preserve source reports and remove linked
sources from the operational queue. Priority and routing remain independent.

**Routes to** exposes a destination; it does not mean an external handoff was
performed, Facilities accepted the issue, or a work order was created. Routing
does not change lifecycle status. TMA/FAMIS integration is intentionally outside
this hackathon slice.

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

This slice does not implement dispatch, work-order creation, authentication,
notifications, downstream integrations, maps, analytics dashboards, or a production database.

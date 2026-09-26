import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  ApiError, issuesApi, parseIssue, parseQueue, parseDuplicateSuggestion,
  parseDuplicateSuggestions, parseDuplicateAnalysis, parseDuplicateReview,
} from '../src/api/issues.ts';

const source = {
  id: '2f4bde9a-18c6-4bb1-8f87-6f9400000001',
  title: 'Swem Library elevator unavailable', description: 'The elevator does not respond to calls.',
  location: 'Earl Gregg Swem Library', category: 'Elevator', severity: 'high',
  accessibility_impact: true, safety_impact: false, confirmation_count: 8,
  created_at: '2026-09-25T00:00:00Z', status: 'reported',
};
const candidate = { ...source, id: '2f4bde9a-18c6-4bb1-8f87-6f9400000002', confirmation_count: 3,
  title: 'Elevator near Swem first floor not responding', created_at: '2026-09-26T00:00:00Z' };
const suggestion = {
  id: '8ff68d26-41d1-4b30-9597-6f9400000001', issue_id: source.id, candidate_issue_id: candidate.id,
  confidence: 0.93, reason: 'Both reports describe the same elevator failure.', status: 'pending',
  origin: 'demo_fixture', created_at: '2026-09-26T12:00:00Z', reviewed_at: null, reviewed_by: null,
  canonical_issue_id: null, issue: source, candidate,
};
const issue = {
  ...source, canonical_issue_id: source.id, effective_confirmation_count: 11,
  source_reports: [source, candidate], pending_duplicate_count: 0,
  routing: { responsible_team: 'Facilities — Elevator Maintenance', category: 'Elevator',
    rule: "Category 'Elevator' routes to Facilities — Elevator Maintenance.", is_fallback: false },
  priority: { score: 7.44, components: { severity: 4, accessibility: 1.5, safety: 0, confirmations: 1.4387, aging: 0.5 },
    explanation: 'Backend calculation', calculated_at: '2026-09-26T12:00:00Z' },
};
const confirmed = { ...suggestion, status: 'confirmed', reviewed_by: 'human',
  reviewed_at: '2026-09-26T12:01:00Z', canonical_issue_id: source.id };
const rejected = { ...confirmed, status: 'rejected', canonical_issue_id: null };
const result = { suggestion: confirmed, issues: [issue] };

// Native Node tests exercise the actual runtime parser without new test dependencies.
test('accepts backend routing and fallback decisions without choosing a team', () => {
  assert.deepEqual(parseIssue(issue).routing, issue.routing);
  const routing = { responsible_team: 'Facilities — General Triage', category: 'Unknown equipment',
    rule: 'Unrecognized category routes to Facilities — General Triage (fallback).', is_fallback: true };
  assert.deepEqual(parseIssue({ ...issue, routing }).routing, routing);
  // Validation checks the shape; only the backend owns category-to-team rules.
  const backendDecision = { ...routing, responsible_team: 'Backend-provided team' };
  assert.deepEqual(parseIssue({ ...issue, routing: backendDecision }).routing, backendDecision);
});

test('rejects missing or malformed routing on issues, queues, and review responses', () => {
  const invalid = [undefined, null, [], {}, ...Object.keys(issue.routing).map((key) => {
    const routing = { ...issue.routing };
    delete routing[key];
    return routing;
  })];
  for (const key of ['responsible_team', 'category', 'rule']) {
    for (const value of ['', ' \t', null, 42, {}, []]) invalid.push({ ...issue.routing, [key]: value });
  }
  for (const value of ['false', 0, 1, null]) invalid.push({ ...issue.routing, is_fallback: value });
  for (const routing of invalid) {
    const malformed = { ...issue, routing };
    assert.throws(() => parseIssue(malformed), ApiError);
    assert.throws(() => parseQueue([malformed]), ApiError);
    assert.throws(() => parseDuplicateReview({ ...result, issues: [malformed] }), ApiError);
  }
});

test('accepts valid pending, confirmed, rejected, and canonical responses', () => {
  for (const item of [suggestion, confirmed, rejected]) assert.deepEqual(parseDuplicateSuggestion(item), item);
  assert.deepEqual(parseDuplicateSuggestions([suggestion]), [suggestion]);
  assert.deepEqual(parseIssue(issue), issue);
  assert.deepEqual(parseQueue([issue]), [issue]);
  assert.deepEqual(parseDuplicateReview(result), result);
  for (const status of ['complete', 'unavailable']) {
    const data = { status, suggestions: [suggestion], remaining_candidates: 1 };
    assert.deepEqual(parseDuplicateAnalysis(data), data);
  }
});

const badSuggestions = [
  null, [], {}, { ...suggestion, id: 'bad' }, { ...suggestion, issue_id: candidate.id },
  { ...suggestion, candidate_issue_id: source.id }, { ...suggestion, confidence: '0.93' },
  ...[-1, 1.01, NaN, Infinity].map((confidence) => ({ ...suggestion, confidence })),
  ...['', ' ', 'x'.repeat(1001), null].map((reason) => ({ ...suggestion, reason })),
  ...['priority', 'severity', 'urgency', 'ranking'].map((key) => ({ ...suggestion, [key]: 10 })),
  { ...suggestion, origin: 'unknown' }, { ...suggestion, status: 'auto_confirmed' },
  { ...suggestion, reviewed_by: 'human' }, { ...suggestion, created_at: '2026-09-26T12:00:00' },
  { ...confirmed, reviewed_by: 'AI' }, { ...confirmed, reviewed_at: null },
  { ...confirmed, canonical_issue_id: null }, { ...rejected, canonical_issue_id: source.id },
  { ...suggestion, candidate: { ...candidate, confirmation_count: -1 } },
  { ...suggestion, issue: { ...source, safety_impact: 'false' } },
];
for (const [index, value] of badSuggestions.entries()) {
  test(`rejects malformed duplicate response ${index + 1}`, () => {
    assert.throws(() => parseDuplicateSuggestion(value), ApiError);
  });
}

test('rejects missing required fields and duplicate suggestion IDs', () => {
  for (const key of Object.keys(suggestion)) {
    const copy = { ...suggestion };
    delete copy[key];
    assert.throws(() => parseDuplicateSuggestion(copy), ApiError);
  }
  assert.throws(() => parseDuplicateSuggestions([suggestion, suggestion]), ApiError);
  assert.throws(() => parseDuplicateSuggestions({ suggestions: [] }), ApiError);
});

test('rejects malformed issue aggregation metadata without calculating priority', () => {
  for (const value of [
    { ...issue, canonical_issue_id: null }, { ...issue, effective_confirmation_count: -1 },
    { ...issue, effective_confirmation_count: 1.5 }, { ...issue, pending_duplicate_count: '1' },
    { ...issue, source_reports: [] }, { ...issue, source_reports: [source, source] },
    { ...issue, source_reports: [candidate] }, { ...issue, priority: { ...issue.priority, score: NaN } },
  ]) assert.throws(() => parseIssue(value), ApiError);
  assert.throws(() => parseQueue([issue, issue]), ApiError);
  assert.throws(() => parseQueue([{ ...issue, canonical_issue_id: candidate.id }]), ApiError);
  // Score is displayed as returned; the client has no confirmation/priority formula.
  assert.equal(parseIssue({ ...issue, priority: { ...issue.priority, score: 2 } }).priority.score, 2);
});

test('rejects malformed analysis and review envelopes', () => {
  for (const value of [null, {}, { status: 'confirmed', suggestions: [], remaining_candidates: 0 },
    { status: 'complete', suggestions: [], remaining_candidates: -1 },
    { status: 'complete', suggestions: [null], remaining_candidates: 0 },
    { status: 'complete', suggestions: [], remaining_candidates: 0, priority: 10 },
  ]) assert.throws(() => parseDuplicateAnalysis(value), ApiError);
  for (const value of [null, {}, { ...result, suggestion }, { ...result, issues: [null] },
    { ...result, priority: 10 },
  ]) assert.throws(() => parseDuplicateReview(value), ApiError);
});

test('API methods validate responses, encode IDs, and do not automatically retry writes', async (t) => {
  globalThis.window = { setTimeout, clearTimeout };
  const calls = [];
  let body = result;
  let status = 200;
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  });
  assert.deepEqual(await issuesApi.reviewDuplicate(suggestion.id, 'confirm'), result);
  assert.match(calls[0].url, new RegExp(`/duplicate-suggestions/${suggestion.id}/confirm$`));
  assert.equal(calls[0].options.method, 'POST');
  body = { ...result, suggestion: rejected };
  await assert.rejects(issuesApi.reviewDuplicate(suggestion.id, 'confirm'), ApiError);
  body = [suggestion];
  assert.deepEqual(await issuesApi.duplicateSuggestions('a/b'), [suggestion]);
  assert.match(calls.at(-1).url, /a%2Fb\/duplicate-suggestions$/);
  body = { status: 'unavailable', suggestions: [], remaining_candidates: 1 };
  assert.equal((await issuesApi.analyzeDuplicates(source.id)).status, 'unavailable');
  status = 409;
  body = { detail: 'Already reviewed' };
  const before = calls.length;
  await assert.rejects(issuesApi.reviewDuplicate(suggestion.id, 'confirm'), /conflicts/);
  assert.equal(calls.length, before + 1);
  delete globalThis.window;
});

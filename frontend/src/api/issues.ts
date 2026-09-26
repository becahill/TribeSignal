import {
  analysisCategories,
  severities,
  type AnalysisResponse,
  type Issue,
  type IssueCreate,
  type RoutingDecision,
  type SourceReport,
  type DuplicateSuggestion,
  type DuplicateAnalysisResponse,
  type DuplicateReviewResponse,
} from '../types/issue.ts';

const API_BASE = (
  import.meta.env?.VITE_API_BASE_URL || 'http://localhost:8000'
).replace(/\/$/, '');
export type FieldErrors = Partial<Record<keyof IssueCreate, string>>;

export class ApiError extends Error {
  readonly fields: FieldErrors;

  constructor(
    message: string,
    fields: FieldErrors = {},
  ) {
    super(message);
    this.name = 'ApiError';
    this.fields = fields;
  }
}

const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const text = (value: unknown): value is string =>
  typeof value === 'string' && value.trim().length > 0;
const finite = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);
const timestamp = (value: unknown): value is string =>
  text(value) &&
  /(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
  Number.isFinite(Date.parse(value));

const uuid = (value: unknown): value is string =>
  text(value) && /^[\da-f]{8}(?:-[\da-f]{4}){3}-[\da-f]{12}$/i.test(value);
const count = (value: unknown): value is number =>
  finite(value) && Number.isSafeInteger(value) && value >= 0;
const exactKeys = (value: Record<string, unknown>, keys: string[]) =>
  Object.keys(value).length === keys.length && Object.keys(value).every((key) => keys.includes(key));

function isSourceReport(value: unknown): value is SourceReport {
  return record(value) && uuid(value.id) &&
    ['title', 'description', 'location', 'category'].every((key) => text(value[key])) &&
    severities.some((severity) => severity === value.severity) &&
    text(value.status) && ['reported', 'triaged', 'routed'].includes(value.status) &&
    typeof value.accessibility_impact === 'boolean' &&
    typeof value.safety_impact === 'boolean' && count(value.confirmation_count) &&
    timestamp(value.created_at);
}

function isRoutingDecision(value: unknown): value is RoutingDecision {
  return record(value) && text(value.responsible_team) && text(value.category) &&
    text(value.rule) && typeof value.is_fallback === 'boolean';
}

function isIssue(value: unknown): value is Issue {
  if (!record(value) || !isSourceReport(value) || !record(value.priority) ||
      !record(value.priority.components) || !isRoutingDecision(value.routing)) return false;
  const priority = value.priority;
  const components = value.priority.components;
  return uuid(value.canonical_issue_id) && count(value.effective_confirmation_count) &&
    count(value.pending_duplicate_count) && Array.isArray(value.source_reports) &&
    value.source_reports.length > 0 && value.source_reports.every(isSourceReport) &&
    value.source_reports.some((source) => source.id === value.id) &&
    new Set(value.source_reports.map((source) => source.id)).size === value.source_reports.length &&
    finite(priority.score) && priority.score >= 1 && priority.score <= 10 &&
    text(priority.explanation) && timestamp(priority.calculated_at) &&
    ['severity', 'accessibility', 'safety', 'confirmations', 'aging'].every(
      (key) => finite(components[key]) && components[key] >= 0,
    );
}

export function parseIssue(value: unknown): Issue {
  if (!isIssue(value))
    throw new ApiError('The service returned an unexpected issue response. Refresh the queue to try again.');
  return value;
}

export function parseQueue(value: unknown): Issue[] {
  if (!Array.isArray(value)) throw new ApiError('The service returned an unexpected queue response.');
  const issues = value.map(parseIssue);
  if (new Set(issues.map((issue) => issue.id)).size !== issues.length ||
      issues.some((issue) => issue.canonical_issue_id !== issue.id))
    throw new ApiError('The service returned inconsistent issue IDs. Please refresh the queue.');
  return issues;
}

export function parseDuplicateSuggestion(value: unknown): DuplicateSuggestion {
  if (record(value) && exactKeys(value, [
    'id', 'issue_id', 'candidate_issue_id', 'confidence', 'reason', 'status', 'origin',
    'created_at', 'reviewed_at', 'reviewed_by', 'canonical_issue_id', 'issue', 'candidate',
  ]) && uuid(value.id) && uuid(value.issue_id) && uuid(value.candidate_issue_id) &&
    value.issue_id !== value.candidate_issue_id &&
    finite(value.confidence) && value.confidence >= 0 && value.confidence <= 1 &&
    text(value.reason) && value.reason.length <= 1000 && timestamp(value.created_at) &&
    (value.origin === 'gemini' || value.origin === 'demo_fixture') &&
    isSourceReport(value.issue) && value.issue.id === value.issue_id &&
    isSourceReport(value.candidate) && value.candidate.id === value.candidate_issue_id) {
    const pending = value.status === 'pending' && value.reviewed_at === null &&
      value.reviewed_by === null && value.canonical_issue_id === null;
    const reviewed = timestamp(value.reviewed_at) && value.reviewed_by === 'human' && (
      (value.status === 'confirmed' && uuid(value.canonical_issue_id)) ||
      (value.status === 'rejected' && value.canonical_issue_id === null)
    );
    if (pending || reviewed) return value as unknown as DuplicateSuggestion;
  }
  throw new ApiError('The service returned invalid duplicate evidence. Refresh the queue before reviewing.');
}

export function parseDuplicateSuggestions(value: unknown): DuplicateSuggestion[] {
  if (!Array.isArray(value)) throw new ApiError('The service returned an invalid suggestion list.');
  const suggestions = value.map(parseDuplicateSuggestion);
  if (new Set(suggestions.map((item) => item.id)).size !== suggestions.length)
    throw new ApiError('The service returned duplicate suggestion IDs.');
  return suggestions;
}

export function parseDuplicateAnalysis(value: unknown): DuplicateAnalysisResponse {
  if (!record(value) || !exactKeys(value, ['status', 'suggestions', 'remaining_candidates']) ||
      !['complete', 'unavailable'].includes(String(value.status)) || !count(value.remaining_candidates))
    throw new ApiError('Duplicate analysis is unavailable. Your reports remain preserved.');
  return {
    status: value.status as DuplicateAnalysisResponse['status'],
    suggestions: parseDuplicateSuggestions(value.suggestions),
    remaining_candidates: value.remaining_candidates,
  };
}

export function parseDuplicateReview(value: unknown): DuplicateReviewResponse {
  if (!record(value) || !exactKeys(value, ['suggestion', 'issues']))
    throw new ApiError('The service returned an invalid review response. Refresh the queue.');
  const suggestion = parseDuplicateSuggestion(value.suggestion);
  if (suggestion.status === 'pending') throw new ApiError('The review was not recorded. Refresh the queue.');
  return { suggestion, issues: parseQueue(value.issues) };
}

function parseAnalysis(value: unknown): AnalysisResponse {
  if (record(value)) {
    if (
      (value.status === 'emergency' || value.status === 'unavailable') &&
      Object.keys(value).length === 2 &&
      text(value.message)
    )
      return { status: value.status, message: value.message };
    if (
      value.status === 'review' &&
      Object.keys(value).length === 2 &&
      record(value.proposal)
    ) {
      const proposal = value.proposal;
      const fields = [
        'title',
        'description',
        'location',
        'category',
        'accessibility_impact',
        'safety_impact',
      ];
      if (
        Object.keys(proposal).length === fields.length &&
        Object.keys(proposal).every((key) => fields.includes(key)) &&
        text(proposal.title) &&
        proposal.title.length <= 200 &&
        text(proposal.description) &&
        proposal.description.length <= 10000 &&
        typeof proposal.location === 'string' &&
        proposal.location.length <= 200 &&
        analysisCategories.some((category) => category === proposal.category) &&
        typeof proposal.accessibility_impact === 'boolean' &&
        typeof proposal.safety_impact === 'boolean'
      )
        return value as AnalysisResponse;
    }
  }
  throw new ApiError(
    'AI returned an invalid proposal. You can enter the report details manually.',
  );
}

function responseError(data: unknown, status: number): ApiError {
  if (record(data) && Array.isArray(data.detail)) {
    const fields: FieldErrors = {};
    const inputFields = [
      'title',
      'description',
      'severity',
      'location',
      'category',
      'accessibility_impact',
      'safety_impact',
    ];
    for (const item of data.detail) {
      if (record(item) && Array.isArray(item.loc) && text(item.msg)) {
        const field = item.loc[1];
        if (typeof field === 'string' && inputFields.includes(field))
          fields[field as keyof IssueCreate] = item.msg;
      }
    }
    return new ApiError(
      'Please check the report details and try again.',
      fields,
    );
  }
  if (status === 409)
    return new ApiError('This review conflicts with an existing decision. Refresh the queue to see the current state.');
  if (status === 404)
    return new ApiError(
      'This issue is no longer available. Refresh the queue; the local service may have restarted.',
    );
  return new ApiError(
    'The triage service could not complete this request. Please try again.',
  );
}

async function request(
  path: string,
  options: RequestInit = {},
  signal?: AbortSignal,
  timeoutMs = 10000,
): Promise<unknown> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener('abort', abort, { once: true });
  if (signal?.aborted) controller.abort();
  const timeout = window.setTimeout(abort, timeoutMs);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
    });
    let data: unknown;
    try {
      data = await response.json();
    } catch {
      throw new ApiError(
        'The service returned an unreadable response. Refresh the queue to try again.',
      );
    }
    if (!response.ok) {
      if (path === '/issues/analyze' && response.status === 503) {
        const analysis = parseAnalysis(data);
        if (analysis.status === 'unavailable') return analysis;
      }
      throw responseError(data, response.status);
    }
    return data;
  } catch (error) {
    if (signal?.aborted) throw error;
    if (error instanceof ApiError) throw error;
    const uncertain =
      options.method === 'POST' && path !== '/issues/analyze'
        ? ' Check the queue before retrying; your request may have been saved.'
        : ' Check that the local backend is running, then try again.';
    throw new ApiError(`Unable to reach the triage service.${uncertain}`);
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}

export const issuesApi = {
  async analyze(text: string, signal?: AbortSignal): Promise<AnalysisResponse> {
    try {
      return parseAnalysis(
        await request(
          '/issues/analyze',
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
          },
          signal,
          20000,
        ),
      );
    } catch (error) {
      if (signal?.aborted) throw error;
      // Analysis never writes. Failure must not imply an issue might be saved.
      throw new ApiError(
        'AI assistance is unavailable. You can enter the report details manually.',
      );
    }
  },
  async list(signal?: AbortSignal): Promise<Issue[]> {
    return parseQueue(await request('/issues', {}, signal));
  },
  async duplicateSuggestions(id: string): Promise<DuplicateSuggestion[]> {
    return parseDuplicateSuggestions(await request(`/issues/${encodeURIComponent(id)}/duplicate-suggestions`));
  },
  async analyzeDuplicates(id: string): Promise<DuplicateAnalysisResponse> {
    return parseDuplicateAnalysis(await request(
      `/issues/${encodeURIComponent(id)}/duplicate-suggestions/analyze`,
      { method: 'POST' }, undefined, 50000,
    ));
  },
  async reviewDuplicate(id: string, decision: 'confirm' | 'reject'): Promise<DuplicateReviewResponse> {
    const result = parseDuplicateReview(await request(
      `/duplicate-suggestions/${encodeURIComponent(id)}/${decision}`, { method: 'POST' },
    ));
    if (result.suggestion.id !== id || result.suggestion.status !== (decision === 'confirm' ? 'confirmed' : 'rejected'))
      throw new ApiError('The service returned a different review. Refresh the queue.');
    return result;
  },
  async create(payload: IssueCreate): Promise<Issue> {
    return parseIssue(
      await request('/issues', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }),
    );
  },
  async confirm(id: string): Promise<Issue> {
    const issue = parseIssue(
      await request(`/issues/${encodeURIComponent(id)}/confirm`, {
        method: 'POST',
      }),
    );
    if (issue.id !== id)
      throw new ApiError(
        'The service returned a different issue. Refresh the queue before retrying.',
      );
    return issue;
  },
};

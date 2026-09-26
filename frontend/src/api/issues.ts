import { severities, type Issue, type IssueCreate } from '../types/issue';

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
).replace(/\/$/, '');
export type FieldErrors = Partial<Record<keyof IssueCreate, string>>;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly fields: FieldErrors = {},
  ) {
    super(message);
    this.name = 'ApiError';
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

function isIssue(value: unknown): value is Issue {
  if (
    !record(value) ||
    !record(value.priority) ||
    !record(value.priority.components)
  )
    return false;
  const priority = value.priority;
  const components = value.priority.components;
  return (
    text(value.id) &&
    /^[\da-f]{8}(?:-[\da-f]{4}){3}-[\da-f]{12}$/i.test(value.id) &&
    ['title', 'description', 'location', 'category'].every((key) =>
      text(value[key]),
    ) &&
    severities.some((severity) => severity === value.severity) &&
    text(value.status) &&
    ['reported', 'triaged', 'routed'].includes(value.status) &&
    typeof value.accessibility_impact === 'boolean' &&
    typeof value.safety_impact === 'boolean' &&
    finite(value.confirmation_count) &&
    Number.isSafeInteger(value.confirmation_count) &&
    value.confirmation_count >= 0 &&
    timestamp(value.created_at) &&
    finite(priority.score) &&
    priority.score >= 1 &&
    priority.score <= 10 &&
    text(priority.explanation) &&
    timestamp(priority.calculated_at) &&
    ['severity', 'accessibility', 'safety', 'confirmations', 'aging'].every(
      (key) => finite(components[key]) && components[key] >= 0,
    )
  );
}

function parseIssue(value: unknown): Issue {
  if (!isIssue(value))
    throw new ApiError(
      'The service returned an unexpected issue response. Refresh the queue to try again.',
    );
  return value;
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
): Promise<unknown> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener('abort', abort, { once: true });
  if (signal?.aborted) controller.abort();
  const timeout = window.setTimeout(abort, 10000);
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
    if (!response.ok) throw responseError(data, response.status);
    return data;
  } catch (error) {
    if (signal?.aborted) throw error;
    if (error instanceof ApiError) throw error;
    const uncertain =
      options.method === 'POST'
        ? ' Check the queue before retrying; your request may have been saved.'
        : ' Check that the local backend is running, then try again.';
    throw new ApiError(`Unable to reach the triage service.${uncertain}`);
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}

export const issuesApi = {
  async list(signal?: AbortSignal): Promise<Issue[]> {
    const data = await request('/issues', {}, signal);
    if (!Array.isArray(data))
      throw new ApiError(
        'The service returned an unexpected queue response. Please try again.',
      );
    const issues = data.map(parseIssue);
    if (new Set(issues.map((issue) => issue.id)).size !== issues.length) {
      throw new ApiError(
        'The service returned duplicate issue IDs. Please refresh the queue.',
      );
    }
    return issues;
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

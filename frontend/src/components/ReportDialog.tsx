import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  Accessibility,
  ArrowRight,
  AlertTriangle,
  LoaderCircle,
  X,
} from 'lucide-react';
import { ApiError, issuesApi, type FieldErrors } from '../api/issues';
import {
  analysisCategories,
  severityLabels,
  type Issue,
  type IssueCreate,
  type Severity,
} from '../types/issue';

type ReportForm = Omit<IssueCreate, 'severity'> & { severity: Severity | '' };

const initialForm: ReportForm = {
  title: '',
  description: '',
  location: '',
  category: '',
  severity: '',
  accessibility_impact: false,
  safety_impact: false,
};

export function ReportDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (issue: Issue) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const inFlight = useRef(false);
  const analysisRequest = useRef<AbortController | null>(null);
  const [stage, setStage] = useState<'describe' | 'review' | 'emergency'>(
    'describe',
  );
  const [rawText, setRawText] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState('');
  const [emergency, setEmergency] = useState<{
    text: string;
    message: string;
  } | null>(null);
  const [assisted, setAssisted] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [reviewError, setReviewError] = useState('');
  const [form, setForm] = useState<ReportForm>(initialForm);
  const [pending, setPending] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState('');

  useEffect(() => {
    const modal = dialog.current;
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    modal?.showModal();
    return () => {
      analysisRequest.current?.abort();
      modal?.close();
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, []);

  useEffect(() => {
    const id =
      stage === 'describe'
        ? 'report-text'
        : stage === 'review'
          ? 'report-title'
          : 'emergency-heading';
    document.getElementById(id)?.focus();
    dialog.current?.scrollTo(0, 0);
  }, [stage]);

  function cancelAnalysis() {
    analysisRequest.current?.abort();
    analysisRequest.current = null;
    setAnalyzing(false);
  }

  function enterManually() {
    if (emergency?.text === rawText.trim()) return;
    cancelAnalysis();
    setForm({ ...initialForm, description: rawText.trim() });
    setAssisted(false);
    setReviewed(false);
    setErrors({});
    setError('');
    setReviewError('');
    setStage('review');
  }

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (analysisRequest.current) return;
    const text = rawText.trim();
    if (!text || text.length > 10000) {
      setAnalysisError('Enter a description between 1 and 10,000 characters.');
      document.getElementById('report-text')?.focus();
      return;
    }
    const controller = new AbortController();
    analysisRequest.current = controller;
    setAnalyzing(true);
    setAnalysisError('');
    try {
      const result = await issuesApi.analyze(text, controller.signal);
      if (controller.signal.aborted) return;
      if (result.status === 'emergency') {
        setEmergency({ text, message: result.message });
        setStage('emergency');
      } else if (result.status === 'unavailable') {
        setAnalysisError(result.message);
      } else {
        setForm({ ...result.proposal, severity: '' });
        setAssisted(true);
        setReviewed(false);
        setErrors({});
        setError('');
        setReviewError('');
        setStage('review');
      }
    } catch (error) {
      if (!controller.signal.aborted)
        setAnalysisError(
          error instanceof Error
            ? error.message
            : 'AI assistance is unavailable. Enter details manually.',
        );
    } finally {
      if (analysisRequest.current === controller) {
        analysisRequest.current = null;
        setAnalyzing(false);
      }
    }
  }

  function setField<K extends keyof ReportForm>(key: K, value: ReportForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
    setReviewed(false);
    setReviewError('');
  }

  function focusInvalid(fields: FieldErrors) {
    const first = Object.keys(fields)[0];
    window.requestAnimationFrame(() =>
      document.getElementById(`report-${first}`)?.focus(),
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || stage !== 'review') return;
    const payload = {
      ...form,
      title: form.title.trim(),
      description: form.description.trim(),
      location: form.location.trim(),
      category: form.category.trim(),
    };
    const fields: FieldErrors = {};
    if (!form.severity) fields.severity = 'Please choose severity yourself.';
    for (const key of [
      'title',
      'description',
      'location',
      'category',
    ] as const) {
      if (!payload[key]) fields[key] = 'Please enter a value.';
      else if (payload[key].length > (key === 'description' ? 10000 : 200))
        fields[key] = 'This value is too long.';
    }
    setErrors(fields);
    setError('');
    if (Object.keys(fields).length) {
      focusInvalid(fields);
      return;
    }
    if (assisted && !reviewed) {
      setReviewError(
        'Please review the facts and impact flags before submitting.',
      );
      document.getElementById('report-reviewed')?.focus();
      return;
    }
    if (!form.severity) return;
    inFlight.current = true;
    setPending(true);
    try {
      onCreated(
        await issuesApi.create({ ...payload, severity: form.severity }),
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : 'Unable to submit your report. Please try again.',
      );
      if (error instanceof ApiError) {
        setErrors(error.fields);
        focusInvalid(error.fields);
      }
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  const fieldError = (key: keyof IssueCreate) =>
    errors[key] && (
      <span className="field-error" id={`error-${key}`}>
        {errors[key]}
      </span>
    );

  return (
    <dialog
      ref={dialog}
      className="report-dialog"
      aria-labelledby="report-heading"
      aria-describedby="report-intro"
      onCancel={(event) => {
        event.preventDefault();
        if (!pending) onClose();
      }}
      onKeyDown={(event) => {
        if (event.key !== 'Tab') return;
        const controls = event.currentTarget.querySelectorAll<HTMLElement>(
          'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled)',
        );
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (!first) {
          event.preventDefault();
          return;
        }
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }}
    >
      <div className="dialog-header">
        <div>
          <span className="eyebrow">COMMUNITY INTAKE</span>
          <h2 id="report-heading">Report an issue</h2>
        </div>
        <button
          className="icon-button"
          onClick={onClose}
          disabled={pending}
          aria-label="Close report form"
        >
          <X size={22} />
        </button>
      </div>
      <p id="report-intro" className="dialog-description">
        AI helps organize your description. You review every field before
        anything is submitted. Priority is calculated separately using
        transparent rules.
      </p>
      {stage === 'describe' && (
        <form onSubmit={analyze} noValidate aria-busy={analyzing}>
          <div className="form-field">
            <label htmlFor="report-text">
              What are you seeing? <span>1 · Describe</span>
            </label>
            <textarea
              id="report-text"
              rows={6}
              maxLength={10000}
              required
              disabled={analyzing}
              value={rawText}
              onChange={(event) => {
                setRawText(event.target.value);
                setAnalysisError('');
              }}
              placeholder="The elevator in Swem has not been working since this morning and someone using a wheelchair could not reach the upper floor."
              aria-describedby="analysis-help"
            />
            <span id="analysis-help" className="field-help">
              Optional AI-assisted organization. Analyze report sends this
              description to Google Gemini.
            </span>
          </div>
          {analysisError && (
            <p className="form-error error-message" role="alert">
              {analysisError}
            </p>
          )}
          {analyzing && (
            <p className="intake-note" role="status">
              Organizing your description… You can switch to manual entry at any
              time.
            </p>
          )}
          {emergency?.text === rawText.trim() && (
            <p className="intake-note">
              Correct the description if the emergency check was mistaken, then
              try again.
            </p>
          )}
          <div className="dialog-footer intake-actions">
            <button
              type="button"
              className="button button-secondary"
              onClick={enterManually}
              disabled={emergency?.text === rawText.trim()}
            >
              Enter details manually
            </button>
            <button
              type="submit"
              className="button button-primary"
              disabled={analyzing}
            >
              {analyzing ? (
                <LoaderCircle size={17} className="spin" />
              ) : (
                <ArrowRight size={17} />
              )}
              {analyzing ? 'Analyzing…' : 'Analyze report'}
            </button>
          </div>
        </form>
      )}
      {stage === 'emergency' && (
        <div className="emergency-notice" role="alert">
          <AlertTriangle size={25} aria-hidden="true" />
          <h3 id="emergency-heading" tabIndex={-1}>
            This may describe an active emergency.
          </h3>
          <p>{emergency?.message}</p>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => setStage('describe')}
          >
            Edit description
          </button>
        </div>
      )}
      {stage === 'review' && (
        <>
          <div className="intake-note">
            <strong>
              {assisted
                ? '2 · Review AI-assisted organization'
                : 'Enter report details'}
            </strong>
            <p>
              {assisted
                ? 'AI organized this report. Compare it with your description, correct the facts and impact flags, and choose severity.'
                : 'You can complete and submit this report without AI assistance.'}
            </p>
            <p>
              Deterministic priority is calculated by the backend after you
              submit.
            </p>
          </div>
          {assisted && (
            <details className="original-report">
              <summary>Your original description</summary>
              <p>{rawText}</p>
            </details>
          )}
          <form onSubmit={submit} noValidate aria-busy={pending}>
            <fieldset disabled={pending}>
              <legend className="sr-only">Issue details</legend>
              <div className="form-field">
                <label htmlFor="report-title">
                  Issue title <span>Required</span>
                </label>
                <input
                  id="report-title"
                  maxLength={200}
                  required
                  value={form.title}
                  onChange={(event) => setField('title', event.target.value)}
                  placeholder="e.g. Library elevator is not responding"
                  aria-invalid={!!errors.title}
                  aria-describedby={errors.title ? 'error-title' : undefined}
                />
                {fieldError('title')}
              </div>
              <div className="form-field">
                <label htmlFor="report-description">
                  What’s happening? <span>Required</span>
                </label>
                <textarea
                  id="report-description"
                  rows={3}
                  required
                  maxLength={10000}
                  value={form.description}
                  onChange={(event) =>
                    setField('description', event.target.value)
                  }
                  placeholder="Describe the issue and who it affects."
                  aria-invalid={!!errors.description}
                  aria-describedby={
                    errors.description ? 'error-description' : undefined
                  }
                />
                {fieldError('description')}
              </div>
              <div className="form-row">
                <div className="form-field">
                  <label htmlFor="report-location">
                    Location <span>Required</span>
                  </label>
                  <input
                    id="report-location"
                    required
                    maxLength={200}
                    value={form.location}
                    onChange={(event) =>
                      setField('location', event.target.value)
                    }
                    placeholder="Building, floor, or nearby landmark"
                    aria-invalid={!!errors.location}
                    aria-describedby={
                      errors.location ? 'error-location' : undefined
                    }
                  />
                  {fieldError('location')}
                </div>
                <div className="form-field">
                  <label htmlFor="report-category">
                    Category <span>Required</span>
                  </label>
                  <input
                    id="report-category"
                    list="issue-categories"
                    required
                    maxLength={200}
                    value={form.category}
                    onChange={(event) =>
                      setField('category', event.target.value)
                    }
                    placeholder="e.g. Elevator or plumbing"
                    aria-invalid={!!errors.category}
                    aria-describedby={
                      errors.category ? 'error-category' : undefined
                    }
                  />
                  <datalist id="issue-categories">
                    {analysisCategories.map((category) => (
                      <option key={category} value={category} />
                    ))}
                  </datalist>
                  {fieldError('category')}
                </div>
              </div>
              <div className="form-field">
                <label htmlFor="report-severity">
                  Severity <span>Required</span>
                </label>
                <select
                  id="report-severity"
                  required
                  value={form.severity}
                  onChange={(event) =>
                    setField('severity', event.target.value as Severity | '')
                  }
                  aria-invalid={!!errors.severity}
                  aria-describedby={
                    errors.severity
                      ? 'severity-help error-severity'
                      : 'severity-help'
                  }
                >
                  <option value="" disabled>
                    Choose severity
                  </option>
                  <option value="low">
                    {severityLabels.low} — a minor inconvenience
                  </option>
                  <option value="moderate">
                    {severityLabels.moderate} — service is affected
                  </option>
                  <option value="high">
                    {severityLabels.high} — significant disruption
                  </option>
                  <option value="critical">
                    {severityLabels.critical} — essential access or service is
                    unavailable
                  </option>
                </select>
                <span id="severity-help" className="field-help">
                  You choose severity. AI does not determine priority.
                </span>
                {fieldError('severity')}
              </div>
              <div className="impact-controls">
                <label className="impact-control">
                  <input
                    id="report-accessibility_impact"
                    type="checkbox"
                    checked={form.accessibility_impact}
                    onChange={(event) =>
                      setField('accessibility_impact', event.target.checked)
                    }
                  />
                  <Accessibility size={22} />
                  <span>
                    <strong>Accessibility impact</strong>
                    <small>
                      Limits someone’s ability to access or use a space.
                    </small>
                  </span>
                </label>
                <label className="impact-control">
                  <input
                    id="report-safety_impact"
                    type="checkbox"
                    checked={form.safety_impact}
                    onChange={(event) =>
                      setField('safety_impact', event.target.checked)
                    }
                  />
                  <AlertTriangle size={22} />
                  <span>
                    <strong>Safety impact</strong>
                    <small>Creates a potential risk of harm.</small>
                  </span>
                </label>
              </div>
              {assisted && (
                <div className="review-confirmation">
                  <label htmlFor="report-reviewed">
                    <input
                      id="report-reviewed"
                      type="checkbox"
                      checked={reviewed}
                      aria-describedby={
                        reviewError ? 'review-error' : undefined
                      }
                      onChange={(event) => {
                        setReviewed(event.target.checked);
                        setReviewError('');
                      }}
                    />
                    I reviewed the facts and impact flags and chose severity
                    myself.
                  </label>
                  {reviewError && (
                    <p id="review-error" className="field-error" role="alert">
                      {reviewError}
                    </p>
                  )}
                </div>
              )}
            </fieldset>
            {error && (
              <p className="form-error error-message" role="alert">
                {error}
              </p>
            )}
            <div className="dialog-footer">
              <button
                type="button"
                className="button button-secondary"
                disabled={pending}
                onClick={() => setStage('describe')}
              >
                Back to description
              </button>
              <div>
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={onClose}
                  disabled={pending}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="button button-primary"
                  disabled={pending}
                >
                  {pending ? (
                    <LoaderCircle size={17} className="spin" />
                  ) : (
                    <ArrowRight size={17} />
                  )}
                  {pending ? 'Submitting…' : 'Submit report'}
                </button>
              </div>
            </div>
          </form>
        </>
      )}
    </dialog>
  );
}

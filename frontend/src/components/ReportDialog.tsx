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
  severityLabels,
  type Issue,
  type IssueCreate,
  type Severity,
} from '../types/issue';

const initialForm: IssueCreate = {
  title: '',
  description: '',
  location: '',
  category: '',
  severity: 'moderate',
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
  const [form, setForm] = useState<IssueCreate>(initialForm);
  const [pending, setPending] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState('');

  useEffect(() => {
    const modal = dialog.current;
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    modal?.showModal();
    modal?.querySelector<HTMLInputElement>('input')?.focus();
    return () => {
      modal?.close();
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, []);

  function setField<K extends keyof IssueCreate>(
    key: K,
    value: IssueCreate[K],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  }

  function focusInvalid(fields: FieldErrors) {
    const first = Object.keys(fields)[0];
    window.requestAnimationFrame(() =>
      document.getElementById(`report-${first}`)?.focus(),
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current) return;
    const payload = {
      ...form,
      title: form.title.trim(),
      description: form.description.trim(),
      location: form.location.trim(),
      category: form.category.trim(),
    };
    const fields: FieldErrors = {};
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
    inFlight.current = true;
    setPending(true);
    try {
      onCreated(await issuesApi.create(payload));
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
        Share what you’re seeing. Your report enters the campus triage queue
        with a transparent priority breakdown.
      </p>
      <form onSubmit={submit} noValidate aria-busy={pending}>
        <fieldset disabled={pending}>
          <legend className="sr-only">Issue details</legend>
          <div className="form-field">
            <label htmlFor="report-title">
              Issue title <span>Required</span>
            </label>
            <input
              id="report-title"
              autoFocus
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
              onChange={(event) => setField('description', event.target.value)}
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
                onChange={(event) => setField('location', event.target.value)}
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
                onChange={(event) => setField('category', event.target.value)}
                placeholder="e.g. Elevator or plumbing"
                aria-invalid={!!errors.category}
                aria-describedby={
                  errors.category ? 'error-category' : undefined
                }
              />
              <datalist id="issue-categories">
                {[
                  'Elevator',
                  'Electrical',
                  'Plumbing',
                  'Walkways',
                  'Lighting',
                  'Network',
                  'Other',
                ].map((category) => (
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
              value={form.severity}
              onChange={(event) =>
                setField('severity', event.target.value as Severity)
              }
              aria-describedby="severity-help"
            >
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
              Choose the severity that best matches what you observe.
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
        </fieldset>
        {error && (
          <p className="form-error error-message" role="alert">
            {error}
          </p>
        )}
        <div className="dialog-footer">
          <p>
            Reports enter triage.
            <br />
            Operational teams handle the work.
          </p>
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
    </dialog>
  );
}

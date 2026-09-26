import { useRef, useState } from 'react';
import {
  Accessibility,
  AlertTriangle,
  Check,
  Clock3,
  LoaderCircle,
  MapPin,
  Plus,
  Users,
} from 'lucide-react';
import { issuesApi } from '../api/issues';
import { severityLabels, statusLabels, type Issue } from '../types/issue';
import { PriorityBreakdown } from './PriorityBreakdown';

interface Props {
  issue: Issue;
  isNew: boolean;
  onUpdated: (issue: Issue) => void;
}

export function IssueCard({ issue, isNew, onUpdated }: Props) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const inFlight = useRef(false);

  async function confirm() {
    if (inFlight.current) return;
    inFlight.current = true;
    setPending(true);
    setError('');
    setSuccess('');
    try {
      const updated = await issuesApi.confirm(issue.id);
      onUpdated(updated);
      setSuccess(
        `Confirmation recorded. Priority is now ${updated.priority.score.toFixed(2)} / 10.`,
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : 'Unable to confirm this issue. Please try again.',
      );
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  return (
    <li>
      <article
        className={`issue-card${isNew ? ' new-issue' : ''}`}
        aria-labelledby={`title-${issue.id}`}
      >
        <div className="issue-main">
          <div
            className="score-block"
            aria-label={`Priority ${issue.priority.score.toFixed(2)} out of 10`}
          >
            <span className="score-label">Priority</span>
            <strong>{issue.priority.score.toFixed(2)}</strong>
            <span className="score-scale">/ 10</span>
          </div>
          <div className="issue-body">
            <div className="issue-tags">
              <span className={`severity severity-${issue.severity}`}>
                {severityLabels[issue.severity]} severity
              </span>
              <span className="status-label">
                <span aria-hidden="true" className="status-dot" />
                {statusLabels[issue.status]}
              </span>
              {isNew && <span className="new-label">Just reported</span>}
            </div>
            <h3 id={`title-${issue.id}`} tabIndex={-1}>
              {issue.title}
            </h3>
            <div className="issue-meta">
              <span>
                <MapPin size={14} />
                {issue.location}
              </span>
              <span className="category-label">{issue.category}</span>
            </div>
            <p className="issue-description">{issue.description}</p>
            {(issue.accessibility_impact || issue.safety_impact) && (
              <div className="impact-tags">
                {issue.accessibility_impact && (
                  <span>
                    <Accessibility size={14} />
                    Accessibility impact
                  </span>
                )}
                {issue.safety_impact && (
                  <span className="safety-impact">
                    <AlertTriangle size={14} />
                    Safety impact
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="issue-footer">
          <div className="issue-footer-meta">
            <span>
              <Users size={15} />
              <strong>{issue.confirmation_count}</strong>{' '}
              {issue.confirmation_count === 1
                ? 'confirmation'
                : 'confirmations'}
            </span>
            <span>
              <Clock3 size={14} />
              <time
                dateTime={issue.created_at}
                title={new Date(issue.created_at).toLocaleString()}
              >
                {new Date(issue.created_at).toLocaleDateString(undefined, {
                  month: 'short',
                  day: 'numeric',
                })}
              </time>
            </span>
          </div>
          <button
            className="button button-confirm"
            onClick={confirm}
            disabled={pending}
            aria-label={`I'm seeing this too: ${issue.title}`}
          >
            {pending ? (
              <LoaderCircle size={16} className="spin" />
            ) : success ? (
              <Check size={16} />
            ) : (
              <Plus size={16} />
            )}
            {pending ? 'Confirming…' : "I'm seeing this too"}
          </button>
        </div>
        {error && (
          <p className="card-message error-message" role="alert">
            {error}
          </p>
        )}
        <div className="confirmation-status" role="status">
          {success && <p className="card-message success-message">{success}</p>}
        </div>
        <PriorityBreakdown
          priority={issue.priority}
          description={issue.description}
        />
      </article>
    </li>
  );
}

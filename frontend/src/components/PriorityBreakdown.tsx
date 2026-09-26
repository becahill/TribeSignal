import { ChevronDown, ShieldCheck } from 'lucide-react';
import type { Priority } from '../types/issue';

const labels: Record<keyof Priority['components'], string> = {
  severity: 'Severity',
  accessibility: 'Accessibility impact',
  safety: 'Safety impact',
  confirmations: 'Community confirmations',
  aging: 'Time open',
};

export function PriorityBreakdown({
  priority,
  description,
}: {
  priority: Priority;
  description: string;
}) {
  return (
    <details className="priority-details">
      <summary>
        <ShieldCheck size={16} /> Why this priority?{' '}
        <ChevronDown size={16} className="disclosure-arrow" />
      </summary>
      <div className="priority-content">
        <div className="breakdown-heading">
          <span>Deterministic. Explainable. Auditable.</span>
          <span>From the triage service</span>
        </div>
        <dl className="component-grid">
          {(Object.keys(labels) as (keyof Priority['components'])[]).map(
            (key) => (
              <div key={key}>
                <dt>{labels[key]}</dt>
                <dd>+{priority.components[key].toFixed(2)}</dd>
              </div>
            ),
          )}
        </dl>
        <div className="priority-total">
          <span>Final priority</span>
          <strong>
            {priority.score.toFixed(2)} <span>/ 10</span>
          </strong>
        </div>
        <p className="explanation">{priority.explanation}</p>
        <p className="calculation-note">
          Components are displayed to two decimals. Calculated{' '}
          <time dateTime={priority.calculated_at}>
            {new Date(priority.calculated_at).toLocaleString()}
          </time>
          .
        </p>
        <div className="full-report">
          <h4>Original report</h4>
          <p>{description}</p>
        </div>
      </div>
    </details>
  );
}

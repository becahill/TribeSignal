import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, ChevronDown, GitCompareArrows, LoaderCircle } from 'lucide-react';
import { issuesApi } from '../api/issues';
import type { DuplicateReviewResponse, DuplicateSuggestion, Issue, SourceReport } from '../types/issue';

interface Props {
  issue: Issue;
  busy: boolean;
  onReview: (id: string, decision: 'confirm' | 'reject') => Promise<DuplicateReviewResponse>;
  onRefresh: () => void;
}

function ReportEvidence({ report, label }: { report: SourceReport; label: string }) {
  return (
    <div className="comparison-report">
      <span className="small-label">{label}</span>
      <h4>{report.title}</h4>
      <p className="comparison-location">{report.location}</p>
      <p>{report.description}</p>
      <time dateTime={report.created_at}>{new Date(report.created_at).toLocaleString()}</time>
    </div>
  );
}

export function DuplicateReview({ issue, busy, onReview, onRefresh }: Props) {
  const [open, setOpen] = useState(false);
  const [suggestions, setSuggestions] = useState<DuplicateSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const generation = useRef(0);
  const checkingRef = useRef(false);

  useEffect(() => {
    if (!open) return;
    const token = ++generation.current;
    setLoading(true);
    setError('');
    issuesApi.duplicateSuggestions(issue.id).then((data) => {
      if (generation.current === token) setSuggestions(data);
    }).catch((error: unknown) => {
      if (generation.current === token)
        setError(error instanceof Error ? error.message : 'Unable to load suggestions.');
    }).finally(() => {
      if (generation.current === token) setLoading(false);
    });
    return () => { generation.current += 1; };
  }, [open, issue]);

  async function check() {
    if (checkingRef.current) return;
    checkingRef.current = true;
    setChecking(true);
    setError('');
    setMessage('Checking reports at the same location and category…');
    try {
      const result = await issuesApi.analyzeDuplicates(issue.id);
      setSuggestions(result.suggestions);
      setOpen(true);
      setMessage(result.status === 'unavailable'
        ? 'Some comparisons are unavailable. Your reports and existing reviews are preserved. You can try again.'
        : result.remaining_candidates > 0
          ? 'This check is complete. Check again to compare the remaining candidates.'
          : result.suggestions.some((item) => item.status === 'pending')
            ? 'Possible matches are ready for your review.'
            : 'No new possible matches from this check. Reports remain independent unless a person confirms a relationship.');
      onRefresh();
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Duplicate analysis is unavailable.');
      setMessage('');
    } finally {
      checkingRef.current = false;
      setChecking(false);
    }
  }

  async function review(suggestion: DuplicateSuggestion, decision: 'confirm' | 'reject') {
    setError('');
    setMessage('');
    try {
      const result = await onReview(suggestion.id, decision);
      setSuggestions((current) => current.map((item) => item.id === suggestion.id ? result.suggestion : item));
      setMessage(decision === 'confirm'
        ? 'Duplicate reviewed by human. Original reports are preserved under the canonical issue.'
        : 'Kept separate by human review. Confirmations and priorities are unchanged.');
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unable to save this review. Refresh the queue.');
    }
  }

  const pending = suggestions.filter((suggestion) => suggestion.status === 'pending');
  const reviewed = suggestions.filter((suggestion) => suggestion.status !== 'pending');
  const associated = issue.source_reports.length > 1;

  return (
    <section className="duplicate-section" aria-label={`Duplicate review for ${issue.title}`}>
      {associated && (
        <div className="association-note">
          <CheckCircle2 size={17} />
          <div><strong>Duplicate reviewed by human</strong>
            <p>{issue.source_reports.length} community reports associated with this issue</p>
          </div>
        </div>
      )}
      <button className={`duplicate-toggle${issue.pending_duplicate_count ? ' has-suggestion' : ''}`}
        aria-expanded={open} aria-controls={`duplicates-${issue.id}`} onClick={() => setOpen(!open)}>
        <GitCompareArrows size={16} />
        {issue.pending_duplicate_count > 0
          ? `Possible duplicate${issue.pending_duplicate_count > 1 ? ` · ${issue.pending_duplicate_count}` : ''}`
          : associated ? 'View original reports & review history' : 'Duplicate checks & review history'}
        <ChevronDown size={15} className={open ? 'disclosure-arrow rotated' : 'disclosure-arrow'} />
      </button>
      {open && (
        <div className="duplicate-content" id={`duplicates-${issue.id}`}>
          {loading ? <p role="status"><LoaderCircle size={15} className="spin" /> Loading comparison…</p> : (
            <>
              {pending.map((suggestion) => {
                const currentIsCandidate = suggestion.candidate_issue_id === issue.id;
                return (
                  <div className="duplicate-comparison" key={suggestion.id}>
                    <div className="comparison-grid">
                      <ReportEvidence report={currentIsCandidate ? suggestion.candidate : suggestion.issue} label="Current report" />
                      <ReportEvidence report={currentIsCandidate ? suggestion.issue : suggestion.candidate} label="Possible match" />
                    </div>
                    <div className="comparison-reason">
                      <h4>Why this was suggested</h4>
                      <p>{suggestion.reason}</p>
                      <span className="similarity-label">
                        {suggestion.confidence >= 0.85 ? 'High' : suggestion.confidence >= 0.6 ? 'Moderate' : 'Low'} semantic similarity
                      </span>
                      <span className="similarity-note">Model assessment, not a calibrated probability.</span>
                      {suggestion.origin === 'demo_fixture' && <span className="fixture-label">Demo fixture · seeded semantic assessment</span>}
                    </div>
                    <p className="human-review-note">AI suggested this relationship. A person must review it.</p>
                    <p className="association-explanation">Confirming preserves both reports under the earliest report and combines their confirmations. Priority is recalculated by the existing deterministic rules.</p>
                    <div className="review-actions">
                      <button className="button button-primary" disabled={busy || checking}
                        onClick={() => void review(suggestion, 'confirm')}>Confirm same issue</button>
                      <button className="button button-secondary" disabled={busy || checking}
                        onClick={() => void review(suggestion, 'reject')}>Keep separate</button>
                    </div>
                    {busy && <p role="status">Saving review…</p>}
                  </div>
                );
              })}
              {associated && (
                <div className="source-reports">
                  <h4>Preserved community reports</h4>
                  <p>Each source count is retained. The canonical total counts each report once.</p>
                  {issue.source_reports.map((report) => (
                    <details key={report.id}>
                      <summary>{report.title} <span>{report.confirmation_count} confirmations</span></summary>
                      <ReportEvidence report={report} label={report.id === issue.id ? 'Canonical report' : 'Associated source report'} />
                      <p className="source-id">Report ID: {report.id}</p>
                    </details>
                  ))}
                </div>
              )}
              {reviewed.length > 0 && <div className="review-history">
                <h4>Human review history</h4>
                {reviewed.map((item) => <p key={item.id}>
                  <strong>{item.status === 'confirmed' ? 'Confirmed same issue' : 'Kept separate'}</strong>
                  {' · Human review · '}<time dateTime={item.reviewed_at!}>{new Date(item.reviewed_at!).toLocaleString()}</time>
                  <span>{item.issue.title} / {item.candidate.title}</span>
                </p>)}
              </div>}
              {!pending.length && !associated && !reviewed.length && <p>No saved duplicate suggestions for this report.</p>}
            </>
          )}
          <button className="text-button" onClick={() => void check()} disabled={checking || busy || loading}>
            {checking && <LoaderCircle size={15} className="spin" />}
            {checking ? 'Checking possible duplicates…' : 'Check for possible duplicates'}
          </button>
        </div>
      )}
      {error && <p className="card-message error-message" role="alert">{error}</p>}
      <div role="status">{message && <p className="card-message">{message}</p>}</div>
    </section>
  );
}

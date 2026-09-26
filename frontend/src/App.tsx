import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowDownWideNarrow,
  ArrowRight,
  CheckCircle2,
  CircleHelp,
  ClipboardList,
  Layers3,
  LoaderCircle,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Signal,
  Unplug,
  X,
} from 'lucide-react';
import { issuesApi } from './api/issues';
import { IssueCard } from './components/IssueCard';
import { ReportDialog } from './components/ReportDialog';
import type { Issue } from './types/issue';

export default function App() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  const [lastLoaded, setLastLoaded] = useState<Date | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [newIssueId, setNewIssueId] = useState<string | null>(null);
  const [createdMessage, setCreatedMessage] = useState('');
  const activeLoad = useRef<AbortController | null>(null);

  const loadQueue = useCallback(async () => {
    activeLoad.current?.abort();
    const controller = new AbortController();
    activeLoad.current = controller;
    setLoading(true);
    setError('');
    try {
      const data = await issuesApi.list(controller.signal);
      if (controller.signal.aborted) return;
      setIssues(data);
      setLoaded(true);
      setLastLoaded(new Date());
    } catch (error) {
      if (!controller.signal.aborted)
        setError(
          error instanceof Error ? error.message : 'Unable to load the queue.',
        );
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadQueue();
    return () => activeLoad.current?.abort();
  }, [loadQueue]);

  function updateIssue(issue: Issue) {
    // A list request started before this mutation must not overwrite its result.
    activeLoad.current?.abort();
    setLoading(false);
    setIssues((current) => [
      issue,
      ...current.filter((item) => item.id !== issue.id),
    ]);
  }

  function issueCreated(issue: Issue) {
    updateIssue(issue);
    setReportOpen(false);
    setQuery('');
    setNewIssueId(issue.id);
    setCreatedMessage(`“${issue.title}” has been added to triage.`);
    void loadQueue();
    window.requestAnimationFrame(() =>
      document.getElementById(`title-${issue.id}`)?.focus(),
    );
  }

  const search = query.trim().toLocaleLowerCase();
  const visibleIssues = issues
    .filter(
      (issue) =>
        !search ||
        [issue.title, issue.description, issue.location, issue.category].some(
          (value) => value.toLocaleLowerCase().includes(search),
        ),
    )
    // Sorting compares server scores only. No priority formula lives in the UI.
    .sort(
      (a, b) =>
        b.priority.score - a.priority.score ||
        b.created_at.localeCompare(a.created_at) ||
        a.id.localeCompare(b.id),
    );

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to triage queue
      </a>
      <aside className="sidebar">
        <a className="brand" href="#main" aria-label="TribeSignal home">
          <span className="brand-mark">
            <Signal size={27} strokeWidth={2.5} />
          </span>
          <span>
            Tribe<span className="brand-light">Signal</span>
          </span>
        </a>
        <div className="workspace-label">
          <span />
          CAMPUS WORKSPACE
        </div>
        <nav aria-label="Main navigation">
          <a className="nav-link active" href="#queue" aria-current="page">
            <Layers3 size={18} />
            Triage queue
            <span className="nav-count">
              {loaded || issues.length ? issues.length : '—'}
            </span>
          </a>
          <button className="nav-link" onClick={() => setReportOpen(true)}>
            <Plus size={18} />
            Report an issue
          </button>
          <a className="nav-link" href="#triage-process">
            <CircleHelp size={18} />
            How it works
          </a>
        </nav>
        <div className="sidebar-note">
          <div className="signal-art" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
          </div>
          <h2>
            Every report.
            <br />A clearer picture.
          </h2>
          <p>
            Community observations.
            <br />
            Shared understanding.
            <br />
            Better-informed response.
          </p>
          <span className="sidebar-note-rule" />
          <span className="small-label">BUILT FOR CAMPUS COMMUNITIES</span>
        </div>
        <div className="sidebar-footer">
          <span className="demo-dot" />
          Local demo<span>v0.1</span>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span>
            <strong>Community triage</strong>
          </div>
          <div
            className={`connection-state${error ? ' connection-error' : ''}`}
          >
            <span />
            {error
              ? 'Connection needs attention'
              : loading
                ? 'Syncing queue…'
                : 'Queue connected'}
          </div>
        </header>
        <main id="main" className="main-content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">SEE IT. SIGNAL IT.</span>
              <h1>
                Campus triage<span className="heading-dot">.</span>
              </h1>
              <p>Transparent triage for campus infrastructure issues.</p>
            </div>
            <button
              className="button button-primary report-action"
              onClick={() => setReportOpen(true)}
            >
              <Plus size={18} />
              Report an Issue
            </button>
          </div>

          <section
            className="process-strip"
            id="triage-process"
            aria-label="How TribeSignal works"
          >
            <div className="process-step">
              <span className="step-number">01</span>
              <div>
                <h2>Report</h2>
                <p>Share what you observe</p>
              </div>
            </div>
            <ArrowRight className="process-arrow" size={17} />
            <div className="process-step current-step">
              <span className="step-number">02</span>
              <div>
                <h2>Triage</h2>
                <p>Understand what needs attention</p>
              </div>
            </div>
            <ArrowRight className="process-arrow" size={17} />
            <div className="process-step">
              <span className="step-number">03</span>
              <div>
                <h2>Handoff</h2>
                <p>To existing operational teams</p>
              </div>
            </div>
          </section>

          <div role="status" className="creation-status">
            {createdMessage && (
              <div className="success-banner">
                <CheckCircle2 size={19} />
                <span>{createdMessage}</span>
                <button
                  className="icon-button"
                  aria-label="Dismiss report confirmation"
                  onClick={() => setCreatedMessage('')}
                >
                  <X size={17} />
                </button>
              </div>
            )}
          </div>

          <div className="content-columns">
            <section
              className="queue-section"
              id="queue"
              aria-labelledby="queue-heading"
              aria-busy={loading}
            >
              <div className="queue-heading">
                <div>
                  <h2 id="queue-heading">
                    Triage queue{' '}
                    <span className="count-badge">
                      {loaded || issues.length ? issues.length : '—'}
                    </span>
                  </h2>
                  <p>Community reports, ordered by clear priorities.</p>
                </div>
                <button
                  className="icon-button refresh-button"
                  onClick={() => void loadQueue()}
                  disabled={loading}
                  aria-label="Refresh queue"
                >
                  <RefreshCw size={17} className={loading ? 'spin' : ''} />
                </button>
              </div>
              <div className="queue-toolbar">
                <label className="search-field">
                  <Search size={17} />
                  <span className="sr-only">Search issues</span>
                  <input
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search issues or locations"
                  />
                </label>
                <span className="sort-label">
                  <ArrowDownWideNarrow size={16} />
                  Highest priority first
                </span>
              </div>

              {error && (
                <div className="queue-error" role="alert">
                  <Unplug size={22} />
                  <div>
                    <h3>We couldn’t refresh the queue</h3>
                    <p>{error}</p>
                    {issues.length > 0 && (
                      <p>Your last loaded reports are still shown below.</p>
                    )}
                    <button
                      className="text-button"
                      onClick={() => void loadQueue()}
                      disabled={loading}
                    >
                      Try again <ArrowRight size={14} />
                    </button>
                  </div>
                </div>
              )}

              {loading && !loaded && issues.length === 0 ? (
                <div className="loading-state" role="status">
                  <LoaderCircle size={25} className="spin" />
                  <h3>Gathering campus signals…</h3>
                  <p>Loading reports and their priority breakdowns.</p>
                </div>
              ) : !error && issues.length === 0 ? (
                <div className="empty-state">
                  <span className="empty-icon">
                    <ClipboardList size={34} strokeWidth={1.5} />
                  </span>
                  <span className="eyebrow">A CLEAR QUEUE STARTS HERE</span>
                  <h3>Be the first to send a signal.</h3>
                  <p>
                    Noticed something that needs attention?
                    <br />
                    Share a report to start the triage process.
                  </p>
                  <button
                    className="button button-primary"
                    onClick={() => setReportOpen(true)}
                  >
                    <Plus size={17} />
                    Report the first issue
                  </button>
                  <span className="empty-footnote">
                    A small observation can make a meaningful difference.
                  </span>
                </div>
              ) : visibleIssues.length > 0 ? (
                <ol className="issue-list">
                  {visibleIssues.map((issue) => (
                    <IssueCard
                      key={issue.id}
                      issue={issue}
                      isNew={newIssueId === issue.id}
                      onUpdated={updateIssue}
                    />
                  ))}
                </ol>
              ) : issues.length > 0 ? (
                <div className="no-results">
                  <Search size={25} />
                  <h3>No matching reports</h3>
                  <p>Try a different issue, category, or location.</p>
                  <button className="text-button" onClick={() => setQuery('')}>
                    Clear search
                  </button>
                </div>
              ) : null}

              <div className="queue-footnote">
                <span>
                  {lastLoaded
                    ? `Queue checked at ${lastLoaded.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}. Refresh for current priorities.`
                    : 'Priorities are provided by the triage service.'}
                </span>
                <span>
                  Transparent by design <ShieldCheck size={13} />
                </span>
              </div>
            </section>

            <aside className="context-column" aria-label="About triage">
              <section className="transparency-card">
                <span className="context-icon">
                  <ShieldCheck size={24} strokeWidth={1.6} />
                </span>
                <span className="eyebrow">NO BLACK BOX</span>
                <h2>
                  Priority you
                  <br />
                  can understand.
                </h2>
                <p>
                  Every score comes with a clear breakdown. Open{' '}
                  <strong>“Why this priority?”</strong> on any report to see
                  what contributes.
                </p>
                <div className="principle">
                  <CheckCircle2 size={16} />
                  Deterministic scoring
                </div>
                <div className="principle">
                  <CheckCircle2 size={16} />
                  Visible contributing factors
                </div>
                <div className="principle">
                  <CheckCircle2 size={16} />
                  No AI priority decisions
                </div>
                <div className="transparency-footer">
                  Clear reasoning. Shared trust.
                </div>
              </section>
              <section className="handoff-note">
                <span className="small-label">WHERE TRIBESIGNAL FITS</span>
                <h2>A bridge to response.</h2>
                <p>
                  Reports help teams understand what needs attention before
                  handoff to existing operational systems.
                </p>
                <p className="handoff-limit">
                  This workspace tracks triage, not maintenance work orders.
                  Downstream handoffs aren’t connected in this demo.
                </p>
              </section>
            </aside>
          </div>
          <footer className="page-footer">
            <span>TribeSignal</span>
            <p>Community insight. Transparent triage.</p>
          </footer>
        </main>
      </div>
      {reportOpen && (
        <ReportDialog
          onClose={() => setReportOpen(false)}
          onCreated={issueCreated}
        />
      )}
    </div>
  );
}

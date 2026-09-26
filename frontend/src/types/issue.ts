// Mirrors the backend contract. Priority and routing are supplied only by the API.
export const severities = ['low', 'moderate', 'high', 'critical'] as const;
export type Severity = (typeof severities)[number];
export type IssueStatus = 'reported' | 'triaged' | 'routed';

export const analysisCategories = [
  'Elevator',
  'Electrical',
  'Plumbing',
  'Walkway',
  'Lighting',
  'Network',
  'Other',
] as const;

// This proposal cannot supply severity or server-owned priority data.
export interface AnalysisProposal {
  title: string;
  description: string;
  location: string;
  category: (typeof analysisCategories)[number];
  accessibility_impact: boolean;
  safety_impact: boolean;
}

export type AnalysisResponse =
  | { status: 'review'; proposal: AnalysisProposal }
  | { status: 'emergency'; message: string }
  | { status: 'unavailable'; message: string };

export interface IssueCreate {
  title: string;
  description: string;
  severity: Severity;
  accessibility_impact: boolean;
  safety_impact: boolean;
  location: string;
  category: string;
}

export interface Priority {
  score: number;
  components: {
    severity: number;
    accessibility: number;
    safety: number;
    confirmations: number;
    aging: number;
  };
  explanation: string;
  calculated_at: string;
}

export interface SourceReport extends IssueCreate {
  id: string;
  confirmation_count: number;
  created_at: string;
  status: IssueStatus;
}

export interface RoutingDecision {
  responsible_team: string;
  category: string;
  rule: string;
  is_fallback: boolean;
}

export interface Issue extends SourceReport {
  priority: Priority;
  routing: RoutingDecision;
  canonical_issue_id: string;
  effective_confirmation_count: number;
  source_reports: SourceReport[];
  pending_duplicate_count: number;
}

export interface DuplicateSuggestion {
  id: string;
  issue_id: string;
  candidate_issue_id: string;
  confidence: number;
  reason: string;
  status: 'pending' | 'confirmed' | 'rejected';
  origin: 'gemini' | 'demo_fixture';
  created_at: string;
  reviewed_at: string | null;
  reviewed_by: 'human' | null;
  canonical_issue_id: string | null;
  issue: SourceReport;
  candidate: SourceReport;
}

export interface DuplicateAnalysisResponse {
  status: 'complete' | 'unavailable';
  suggestions: DuplicateSuggestion[];
  remaining_candidates: number;
}

export interface DuplicateReviewResponse {
  suggestion: DuplicateSuggestion;
  issues: Issue[];
}

export const severityLabels: Record<Severity, string> = {
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
  critical: 'Critical',
};
export const statusLabels: Record<IssueStatus, string> = {
  reported: 'Reported',
  triaged: 'Triaged',
  routed: 'Routed',
};

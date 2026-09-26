// Mirrors backend/app/models.py. Priority values are supplied only by the API.
export const severities = ['low', 'moderate', 'high', 'critical'] as const;
export type Severity = (typeof severities)[number];
export type IssueStatus = 'reported' | 'triaged' | 'routed';

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

export interface Issue extends IssueCreate {
  id: string;
  confirmation_count: number;
  created_at: string;
  status: IssueStatus;
  priority: Priority;
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

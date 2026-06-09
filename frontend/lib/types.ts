export type Priority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type ApprovalMode = 'GATE' | 'SUGGEST';

export interface AxisScore {
  axis: string;
  raw_score: number;
  explanation: string;
}

export interface TriageResult {
  axes: AxisScore[];
  composite_score: number;
  priority: Priority;
  approval_mode: ApprovalMode;
  email_type?: string;
  triage_reasoning?: string;
  dynamic_weights?: Record<string, number>;
}

export interface ClassificationResult {
  priority: Priority;
  category: string;
  confidence: number;
}

export interface Attachment {
  attachment_id: string;
  filename: string;
  mime_type: string;
  size: number;
}

export interface Email {
  id: string;
  sender: string;
  subject: string;
  body: string;           // plain text — used by agents for LLM processing
  html_body?: string;     // HTML — used by frontend for display (may be undefined for plain-text emails)
  received_at: string;
  triage?: TriageResult;
  composite_score?: number;
  isStarred?: boolean;
  isRead?: boolean;
  hasAttachments?: boolean;
  attachments?: Attachment[];
}

export interface CommitmentItem {
  id: string;
  commitment: string;
  deadline: string | null;
  confidence: number;
  approved?: boolean;
  confirmed?: boolean;
  task_url?: string;
  event_url?: string;
  conflict_badge?: boolean;
  conflict_detail?: string | null;
}

export interface PrecedentItem {
  email_id: string;
  subject: string;
  snippet: string;
  similarity_score: number;
}

export interface CalendarEvent {
  title: string;
  start_time: string;
  end_time: string;
  organizer: string;
}

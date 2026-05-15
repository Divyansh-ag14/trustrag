export interface User {
  id: string;
  email: string;
  name: string;
  role: "admin" | "member" | "viewer";
  workspace_id: string;
  created_at: string;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
  workspace: Workspace;
}

export interface Document {
  id: string;
  title: string;
  source_type: string;
  status: "processing" | "active" | "failed" | "archived";
  version: number;
  total_chunks: number;
  file_size_bytes: number | null;
  mime_type: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  token_count: number;
}

export interface Citation {
  index: number;
  document_title: string;
  chunk_snippet: string;
  document_id: string;
  relevance_score: number;
}

export interface ChatResponse {
  query_id: string;
  result_id: string;
  session_id: string;
  answer: string;
  citations: Citation[];
  confidence_score: number;
  status: string;
  has_conflicts: boolean;
  follow_up_suggestions: string[];
  escalation_needed: boolean;
  escalation_reason: string | null;
  latency_breakdown: Record<string, number>;
  token_usage: Record<string, number>;
  cost_usd: number;
}

export interface ChatSession {
  session_id: string;
  query_count: number;
  last_query_at: string | null;
}

export interface FeedbackItem {
  id: string;
  query_result_id: string;
  user_id: string | null;
  rating: "up" | "down";
  comment: string | null;
  corrected_answer: string | null;
  reviewed_by: string | null;
  review_note: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface EvaluationRun {
  id: string;
  dataset_id: string;
  name: string | null;
  metrics: Record<string, number>;
  status: "running" | "completed" | "failed";
  started_at: string;
  completed_at: string | null;
}

export interface ApiError {
  detail: string;
}

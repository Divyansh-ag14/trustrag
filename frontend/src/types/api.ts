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

export interface EvaluationDataset {
  id: string;
  name: string;
  description: string | null;
  item_count: number;
  created_at: string;
}

export interface EvaluationItem {
  id: string;
  question: string;
  expected_answer: string;
  expected_source_docs: string[];
  query_type: string | null;
  difficulty: string | null;
  tags: string[];
}

export interface EvaluationRun {
  id: string;
  dataset_id: string;
  name: string | null;
  metrics: Record<string, number>;
  status: "queued" | "running" | "completed" | "failed";
  started_at: string;
  completed_at: string | null;
}

export interface EvaluationRunDetail extends EvaluationRun {
  per_item_results: EvalItemResult[];
}

export interface EvalItemResult {
  item_id: string;
  question: string;
  expected_answer: string;
  actual_answer: string;
  status: string;
  confidence: number;
  has_citation: boolean;
  latency_ms: number;
  cost_usd: number;
  query_type: string | null;
  difficulty: string | null;
  metrics: {
    recall_at_10: number;
    precision_at_10: number;
    mrr: number;
    ndcg_at_10: number;
    hit_rate: number;
    avg_precision: number;
    faithfulness?: number;
    citation_accuracy?: number;
    hallucination_rate?: number;
  };
}

export interface FeedbackStats {
  total: number;
  positive: number;
  negative: number;
  reviewed: number;
  unreviewed: number;
}

export interface KnowledgeGap {
  id: string;
  query_id: string | null;
  question: string;
  reason: string;
  missing_topic: string | null;
  weak_sources: { title: string; score: number }[];
  occurrences: number;
  status: string;
  assigned_to: string | null;
  resolution_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeGapStats {
  total: number;
  open: number;
  resolved: number;
  by_reason: Record<string, number>;
}

export interface Connector {
  id: string;
  name: string;
  connector_type: "notion" | "github" | "web_scraper";
  config: Record<string, unknown>;
  sync_enabled: boolean;
  sync_interval_hours: number;
  status: "active" | "syncing" | "error" | "disabled";
  last_synced_at: string | null;
  last_sync_error: string | null;
  documents_synced: number;
  created_at: string;
  updated_at: string;
}

export interface ConnectorCreate {
  name: string;
  connector_type: "notion" | "github" | "web_scraper";
  credentials: Record<string, string>;
  config: Record<string, unknown>;
  sync_enabled?: boolean;
  sync_interval_hours?: number;
}

export interface ApiError {
  detail: string;
}

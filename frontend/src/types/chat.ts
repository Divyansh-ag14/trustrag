import type { Citation } from "./api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  confidence?: number;
  status?: string;
  has_conflicts?: boolean;
  follow_up_suggestions?: string[];
  latency_breakdown?: Record<string, number>;
  isStreaming?: boolean;
  timestamp: number;
}

export interface ChatSessionState {
  id: string;
  messages: ChatMessage[];
}

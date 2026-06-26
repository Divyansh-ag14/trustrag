import { create } from "zustand";
import type { Citation } from "@/types/api";
import type { ChatMessage } from "@/types/chat";

interface ChatStore {
  messages: ChatMessage[];
  sessionId: string | null;
  isStreaming: boolean;
  activeCitation: Citation | null;

  addUserMessage: (content: string) => string;
  addAssistantMessage: () => string;
  appendToLastAssistant: (token: string) => void;
  finalizeAssistant: (
    messageId: string,
    data: {
      content?: string;
      citations?: Citation[];
      confidence?: number;
      status?: string;
      verified?: boolean;
      has_conflicts?: boolean;
      follow_up_suggestions?: string[];
      latency_breakdown?: Record<string, number>;
      result_id?: string;
    },
  ) => void;
  setStreaming: (streaming: boolean) => void;
  setSessionId: (id: string) => void;
  setActiveCitation: (citation: Citation | null) => void;
  clearMessages: () => void;
}

let nextId = 0;
function generateId() {
  nextId += 1;
  return `msg_${Date.now()}_${nextId}`;
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  sessionId: null,
  isStreaming: false,
  activeCitation: null,

  addUserMessage: (content) => {
    const id = generateId();
    set((s) => ({
      messages: [
        ...s.messages,
        {
          id,
          role: "user",
          content,
          timestamp: Date.now(),
        },
      ],
    }));
    return id;
  },

  addAssistantMessage: () => {
    const id = generateId();
    set((s) => ({
      messages: [
        ...s.messages,
        {
          id,
          role: "assistant",
          content: "",
          isStreaming: true,
          timestamp: Date.now(),
        },
      ],
    }));
    return id;
  },

  appendToLastAssistant: (token) => {
    set((s) => {
      const msgs = [...s.messages];
      const lastIdx = msgs.length - 1;
      if (lastIdx >= 0 && msgs[lastIdx].role === "assistant") {
        msgs[lastIdx] = {
          ...msgs[lastIdx],
          content: msgs[lastIdx].content + token,
        };
      }
      return { messages: msgs };
    });
  },

  finalizeAssistant: (messageId, data) => {
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === messageId
          ? { ...m, ...data, isStreaming: false }
          : m,
      ),
    }));
  },

  setStreaming: (streaming) => set({ isStreaming: streaming }),
  setSessionId: (id) => set({ sessionId: id }),
  setActiveCitation: (citation) => set({ activeCitation: citation }),
  clearMessages: () =>
    set({ messages: [], sessionId: null, activeCitation: null }),
}));

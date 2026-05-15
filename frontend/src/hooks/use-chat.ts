import { useCallback } from "react";
import { API_BASE_URL } from "@/lib/constants";
import { useChatStore } from "@/stores/chat-store";

export function useChat() {
  const {
    messages,
    sessionId,
    isStreaming,
    addUserMessage,
    addAssistantMessage,
    appendToLastAssistant,
    finalizeAssistant,
    setStreaming,
    setSessionId,
    clearMessages,
  } = useChatStore();

  const sendMessage = useCallback(
    async (query: string) => {
      if (isStreaming || !query.trim()) return;

      addUserMessage(query);
      const assistantId = addAssistantMessage();
      setStreaming(true);

      try {
        const token = localStorage.getItem("access_token");
        const response = await fetch(`${API_BASE_URL}/chat/query`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            query,
            session_id: sessionId,
          }),
        });

        if (!response.ok) {
          const error = await response.json().catch(() => ({ detail: "Request failed" }));
          finalizeAssistant(assistantId, {
            status: "error",
            confidence: 0,
          });
          appendToLastAssistant(error.detail || "Something went wrong.");
          setStreaming(false);
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          setStreaming(false);
          return;
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const data = line.slice(6).trim();
            if (data === "[DONE]") continue;

            try {
              const event = JSON.parse(data);

              if (event.type === "token") {
                appendToLastAssistant(event.data);
              } else if (event.type === "metadata") {
                const meta = event.data;
                finalizeAssistant(assistantId, {
                  citations: meta.citations || [],
                  confidence: meta.confidence_score ?? meta.confidence,
                  status: meta.status || "success",
                  has_conflicts: meta.has_conflicts,
                  follow_up_suggestions: meta.follow_up_suggestions || [],
                  latency_breakdown: meta.latency_breakdown,
                });
                if (meta.session_id) {
                  setSessionId(meta.session_id);
                }
              } else if (event.type === "error") {
                appendToLastAssistant(event.data || "An error occurred.");
                finalizeAssistant(assistantId, {
                  status: "error",
                  confidence: 0,
                });
              }
            } catch {
              // skip malformed event
            }
          }
        }
      } catch (err) {
        appendToLastAssistant(
          err instanceof Error ? err.message : "Connection failed.",
        );
        finalizeAssistant(assistantId, { status: "error", confidence: 0 });
      } finally {
        setStreaming(false);
      }
    },
    [
      isStreaming,
      sessionId,
      addUserMessage,
      addAssistantMessage,
      appendToLastAssistant,
      finalizeAssistant,
      setStreaming,
      setSessionId,
    ],
  );

  return {
    messages,
    sessionId,
    isStreaming,
    sendMessage,
    clearMessages,
  };
}

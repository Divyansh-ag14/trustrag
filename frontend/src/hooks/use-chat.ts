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
          if (response.status === 401) {
            localStorage.removeItem("access_token");
            localStorage.removeItem("refresh_token");
            window.location.href = "/login";
            return;
          }
          const error = await response.json().catch(() => ({ detail: "Request failed" }));
          finalizeAssistant(assistantId, {
            status: "error",
            confidence: 0,
          });
          appendToLastAssistant(error.detail || "Something went wrong.");
          setStreaming(false);
          return;
        }

        const data = await response.json();

        appendToLastAssistant(data.answer || "No answer generated.");
        finalizeAssistant(assistantId, {
          citations: data.citations || [],
          confidence: data.confidence_score ?? 0,
          status: data.status || "success",
          verified: data.verified || false,
          has_conflicts: data.has_conflicts || false,
          follow_up_suggestions: data.follow_up_suggestions || [],
          latency_breakdown: data.latency_breakdown || {},
          result_id: data.result_id,
        });
        if (data.session_id) {
          setSessionId(data.session_id);
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

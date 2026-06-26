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
        const response = await fetch(`${API_BASE_URL}/chat/query/stream`, {
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

        if (!response.ok || !response.body) {
          if (response.status === 401) {
            localStorage.removeItem("access_token");
            localStorage.removeItem("refresh_token");
            window.location.href = "/login";
            return;
          }
          finalizeAssistant(assistantId, { status: "error", confidence: 0 });
          appendToLastAssistant("Something went wrong.");
          setStreaming(false);
          return;
        }

        // Parse the SSE stream: tokens arrive live, then a final `verdict` event
        // with citations/confidence/status once the safety checks have run.
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let accumulated = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const blocks = buffer.split("\n\n");
          buffer = blocks.pop() || "";

          for (const block of blocks) {
            if (!block.trim()) continue;
            let eventType = "message";
            let dataStr = "";
            for (const line of block.split("\n")) {
              if (line.startsWith("event:")) eventType = line.slice(6).trim();
              else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
            }
            let data: Record<string, unknown> = {};
            try {
              data = dataStr ? JSON.parse(dataStr) : {};
            } catch {
              continue;
            }

            if (eventType === "token") {
              const t = (data.data as string) || "";
              accumulated += t;
              appendToLastAssistant(t);
            } else if (eventType === "verdict") {
              const override = data.answer_override as string | null;
              const note = data.note as string | null;
              let content: string | undefined;
              if (override) content = override;
              else if (note) content = `${accumulated}\n\nNote: ${note}`;
              finalizeAssistant(assistantId, {
                ...(content !== undefined ? { content } : {}),
                citations: (data.citations as never[]) || [],
                confidence: (data.confidence as number) ?? 0,
                status: (data.status as string) || "success",
                verified: (data.verified as boolean) || false,
                has_conflicts: (data.has_conflicts as boolean) || false,
                follow_up_suggestions: (data.follow_up_suggestions as string[]) || [],
                result_id: data.result_id as string,
              });
              if (data.session_id) setSessionId(data.session_id as string);
            } else if (eventType === "error") {
              appendToLastAssistant((data.detail as string) || "Something went wrong.");
              finalizeAssistant(assistantId, { status: "error", confidence: 0 });
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

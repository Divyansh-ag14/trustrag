"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown, Loader2, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfidenceBadge } from "./confidence-badge";
import { useChatStore } from "@/stores/chat-store";
import { api } from "@/lib/api-client";
import { useAppStore } from "@/stores/app-store";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/chat";
import type { Citation } from "@/types/api";

interface MessageBubbleProps {
  message: ChatMessage;
  onSendMessage?: (query: string) => void;
}

function renderContentWithCitations(
  content: string,
  citations: Citation[] | undefined,
  onCitationClick: (citation: Citation) => void,
) {
  if (!citations?.length) {
    return <span>{content}</span>;
  }

  const parts = content.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      const idx = parseInt(match[1]);
      const citation = citations.find((c) => c.index === idx);
      if (citation) {
        return (
          <button
            key={i}
            className="inline-flex items-center justify-center h-5 min-w-5 px-1 mx-0.5 rounded text-xs font-medium bg-primary/20 text-primary hover:bg-primary/30 transition-colors cursor-pointer"
            onClick={() => onCitationClick(citation)}
          >
            {idx}
          </button>
        );
      }
    }
    return <span key={i}>{part}</span>;
  });
}

export function MessageBubble({ message, onSendMessage }: MessageBubbleProps) {
  const setActiveCitation = useChatStore((s) => s.setActiveCitation);
  const setCitationPanelOpen = useAppStore((s) => s.setCitationPanelOpen);
  const isUser = message.role === "user";
  const [feedbackSent, setFeedbackSent] = useState<"up" | "down" | null>(null);

  const handleCitationClick = (citation: Citation) => {
    setActiveCitation(citation);
    setCitationPanelOpen(true);
  };

  const handleFeedback = async (rating: "up" | "down") => {
    if (feedbackSent || !message.result_id) return;
    try {
      await api.post("/feedback", {
        query_result_id: message.result_id,
        rating,
      });
      setFeedbackSent(rating);
    } catch {
      // silent
    }
  };

  return (
    <div className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[75%] rounded-lg px-4 py-3",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-card border border-border/40",
        )}
      >
        <div className="text-sm leading-relaxed whitespace-pre-wrap">
          {isUser
            ? message.content
            : renderContentWithCitations(
                message.content,
                message.citations,
                handleCitationClick,
              )}
          {message.isStreaming && (
            <Loader2 className="inline-block h-3 w-3 ml-1 animate-spin" />
          )}
        </div>

        {!isUser && !message.isStreaming && message.confidence !== undefined && (
          <div className="flex items-center gap-2 mt-3 pt-2 border-t border-border/30">
            <ConfidenceBadge confidence={message.confidence} />
            <div className="flex-1" />
            {feedbackSent ? (
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                {feedbackSent === "up" ? "Helpful" : "Not helpful"}
              </span>
            ) : (
              <>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-emerald-400"
                  onClick={() => handleFeedback("up")}
                >
                  <ThumbsUp className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-red-400"
                  onClick={() => handleFeedback("down")}
                >
                  <ThumbsDown className="h-3.5 w-3.5" />
                </Button>
              </>
            )}
          </div>
        )}

        {!isUser && message.follow_up_suggestions && message.follow_up_suggestions.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {message.follow_up_suggestions.map((suggestion, i) => (
              <button
                key={i}
                className="text-xs text-muted-foreground hover:text-foreground border border-border/40 rounded-md px-2 py-1 transition-colors"
                onClick={() => onSendMessage?.(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

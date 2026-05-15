"use client";

import { ThumbsUp, ThumbsDown, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfidenceBadge } from "./confidence-badge";
import { useChatStore } from "@/stores/chat-store";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/chat";
import type { Citation } from "@/types/api";

interface MessageBubbleProps {
  message: ChatMessage;
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

export function MessageBubble({ message }: MessageBubbleProps) {
  const setActiveCitation = useChatStore((s) => s.setActiveCitation);
  const isUser = message.role === "user";

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
                setActiveCitation,
              )}
          {message.isStreaming && (
            <Loader2 className="inline-block h-3 w-3 ml-1 animate-spin" />
          )}
        </div>

        {!isUser && !message.isStreaming && message.confidence !== undefined && (
          <div className="flex items-center gap-2 mt-3 pt-2 border-t border-border/30">
            <ConfidenceBadge confidence={message.confidence} />
            <div className="flex-1" />
            <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-emerald-400">
              <ThumbsUp className="h-3.5 w-3.5" />
            </Button>
            <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-red-400">
              <ThumbsDown className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}

        {!isUser && message.follow_up_suggestions && message.follow_up_suggestions.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {message.follow_up_suggestions.map((suggestion, i) => (
              <button
                key={i}
                className="text-xs text-muted-foreground hover:text-foreground border border-border/40 rounded-md px-2 py-1 transition-colors"
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

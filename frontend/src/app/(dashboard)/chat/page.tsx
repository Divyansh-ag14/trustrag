"use client";

import { useEffect, useRef } from "react";
import { MessageSquare, BookOpen, PanelRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatInput } from "@/components/chat/chat-input";
import { MessageBubble } from "@/components/chat/message-bubble";
import { CitationPanel } from "@/components/chat/citation-panel";
import { useChat } from "@/hooks/use-chat";
import { useAppStore } from "@/stores/app-store";

export default function ChatPage() {
  const { messages, isStreaming, sendMessage, clearMessages } = useChat();
  const { citationPanelOpen, toggleCitationPanel } = useAppStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="flex h-full">
      <div className="flex flex-1 flex-col">
        {messages.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8">
            <div className="rounded-full bg-primary/10 p-4">
              <MessageSquare className="h-8 w-8 text-primary" />
            </div>
            <div className="text-center max-w-md">
              <h2 className="text-lg font-semibold mb-1">
                Ask your knowledge base
              </h2>
              <p className="text-sm text-muted-foreground">
                Get grounded answers with citations from your ingested documents.
                Every claim is traced back to its source.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-4 max-w-lg">
              {[
                "What is the refund policy for enterprise customers?",
                "How do I set up the Slack integration?",
                "What changed in the latest release?",
                "What are the API rate limits?",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => sendMessage(q)}
                  className="text-left text-sm border border-border/40 rounded-lg p-3 hover:bg-accent/50 transition-colors text-muted-foreground hover:text-foreground"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <ScrollArea className="flex-1 p-4" ref={scrollRef}>
            <div className="max-w-3xl mx-auto space-y-4 pb-4">
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} onSendMessage={sendMessage} />
              ))}
            </div>
          </ScrollArea>
        )}

        <div className="flex items-center gap-2 px-4 pb-1 max-w-3xl mx-auto w-full">
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-muted-foreground gap-1 h-7"
            onClick={clearMessages}
          >
            <MessageSquare className="h-3 w-3" />
            New chat
          </Button>
          <div className="flex-1" />
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-muted-foreground gap-1 h-7"
            onClick={toggleCitationPanel}
          >
            {citationPanelOpen ? (
              <PanelRight className="h-3 w-3" />
            ) : (
              <BookOpen className="h-3 w-3" />
            )}
            Sources
          </Button>
        </div>
        <ChatInput onSend={sendMessage} disabled={isStreaming} />
      </div>

      <CitationPanel />
    </div>
  );
}

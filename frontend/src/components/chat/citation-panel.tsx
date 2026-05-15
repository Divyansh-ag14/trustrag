"use client";

import { X, FileText, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { useChatStore } from "@/stores/chat-store";
import { useAppStore } from "@/stores/app-store";
import { cn } from "@/lib/utils";

export function CitationPanel() {
  const activeCitation = useChatStore((s) => s.activeCitation);
  const setActiveCitation = useChatStore((s) => s.setActiveCitation);
  const { citationPanelOpen, setCitationPanelOpen } = useAppStore();
  const messages = useChatStore((s) => s.messages);

  const allCitations = messages
    .filter((m) => m.role === "assistant" && m.citations?.length)
    .flatMap((m) => m.citations || []);

  const uniqueCitations = allCitations.filter(
    (c, i, arr) => arr.findIndex((x) => x.index === c.index && x.document_id === c.document_id) === i,
  );

  if (!citationPanelOpen) return null;

  return (
    <div className="w-80 border-l border-border/40 bg-card/30 flex flex-col">
      <div className="flex items-center justify-between h-14 px-4 border-b border-border/40">
        <h3 className="text-sm font-medium">Sources</h3>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={() => setCitationPanelOpen(false)}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-3 space-y-2">
          {uniqueCitations.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No sources cited yet. Ask a question to see citations.
            </p>
          ) : (
            uniqueCitations.map((citation) => (
              <button
                key={`${citation.document_id}-${citation.index}`}
                onClick={() => setActiveCitation(citation)}
                className={cn(
                  "w-full text-left rounded-lg border p-3 transition-colors",
                  activeCitation?.index === citation.index &&
                    activeCitation?.document_id === citation.document_id
                    ? "border-primary/50 bg-primary/5"
                    : "border-border/40 hover:border-border/60 bg-card/50",
                )}
              >
                <div className="flex items-start gap-2">
                  <Badge variant="outline" className="shrink-0 text-xs">
                    [{citation.index}]
                  </Badge>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                      <p className="text-sm font-medium truncate">
                        {citation.document_title}
                      </p>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-3">
                      {citation.chunk_snippet}
                    </p>
                    <div className="flex items-center gap-2 mt-2">
                      <span className="text-xs text-muted-foreground">
                        Relevance: {Math.round(citation.relevance_score * 100)}%
                      </span>
                    </div>
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </ScrollArea>

      {activeCitation && (
        <div className="border-t border-border/40 p-4">
          <h4 className="text-sm font-medium mb-2 flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5" />
            {activeCitation.document_title}
          </h4>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {activeCitation.chunk_snippet}
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="mt-2 text-xs h-7 gap-1"
            onClick={() => {
              window.open(`/documents/${activeCitation.document_id}`, "_blank");
            }}
          >
            <ExternalLink className="h-3 w-3" />
            View document
          </Button>
        </div>
      )}
    </div>
  );
}

"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  FileText,
  Hash,
  Clock,
  Loader2,
  RefreshCw,
  Archive,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api-client";
import type { Document, DocumentChunk } from "@/types/api";

const STATUS_COLORS: Record<string, string> = {
  active: "border-emerald-500/30 text-emerald-400",
  processing: "border-blue-500/30 text-blue-400",
  failed: "border-red-500/30 text-red-400",
  archived: "border-zinc-500/30 text-zinc-400",
};

const SOURCE_LABELS: Record<string, string> = {
  pdf: "PDF",
  markdown: "Markdown",
  text: "Text",
  html: "HTML",
  csv: "CSV",
  faq: "FAQ",
  slack_export: "Slack Export",
};

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [doc, setDoc] = useState<Document | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [totalChunks, setTotalChunks] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expandedChunk, setExpandedChunk] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const fetchDocument = useCallback(async () => {
    if (!params?.id) return;
    try {
      const [d, c] = await Promise.all([
        api.get<Document>(`/documents/${params.id}`),
        api.get<{ chunks: DocumentChunk[]; total: number }>(
          `/documents/${params.id}/chunks?limit=20`
        ),
      ]);
      setDoc(d);
      setChunks(c.chunks);
      setTotalChunks(c.total);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [params?.id]);

  useEffect(() => {
    fetchDocument();
  }, [fetchDocument]);

  const loadMore = async () => {
    if (!params?.id || loadingMore) return;
    setLoadingMore(true);
    try {
      const c = await api.get<{ chunks: DocumentChunk[]; total: number }>(
        `/documents/${params.id}/chunks?skip=${chunks.length}&limit=20`
      );
      setChunks((prev) => [...prev, ...c.chunks]);
    } catch {
      // silent
    } finally {
      setLoadingMore(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="p-6">
        <p className="text-sm text-muted-foreground">Document not found</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          className="gap-1.5"
          onClick={() => router.push("/documents")}
        >
          <ArrowLeft className="h-4 w-4" />
          Documents
        </Button>
      </div>

      {/* Document Info */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <h1 className="text-lg font-semibold">{doc.title}</h1>
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <Badge
              variant="outline"
              className={STATUS_COLORS[doc.status] || ""}
            >
              {doc.status}
            </Badge>
            <span>{SOURCE_LABELS[doc.source_type] || doc.source_type}</span>
            <span>v{doc.version}</span>
          </div>
        </div>
      </div>

      {/* Metadata Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetaCard
          icon={Hash}
          label="Chunks"
          value={totalChunks.toString()}
        />
        <MetaCard
          icon={FileText}
          label="Source Type"
          value={SOURCE_LABELS[doc.source_type] || doc.source_type}
        />
        <MetaCard
          icon={Clock}
          label="Created"
          value={new Date(doc.created_at).toLocaleDateString()}
        />
        <MetaCard
          icon={Clock}
          label="Updated"
          value={new Date(doc.updated_at).toLocaleDateString()}
        />
      </div>

      {/* Chunks */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-muted-foreground">
            Document Chunks ({totalChunks})
          </h2>
        </div>

        {chunks.length === 0 ? (
          <Card className="border-border/40 bg-card/50">
            <CardContent className="flex items-center justify-center py-12">
              <p className="text-sm text-muted-foreground">
                {doc.status === "processing"
                  ? "Document is still being processed..."
                  : "No chunks available"}
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {chunks.map((chunk) => (
              <Card
                key={chunk.id}
                className="border-border/40 bg-card/50 overflow-hidden"
              >
                <div
                  className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-muted/20 transition-colors"
                  onClick={() =>
                    setExpandedChunk(
                      expandedChunk === chunk.id ? null : chunk.id
                    )
                  }
                >
                  {expandedChunk === chunk.id ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
                  )}
                  <span className="text-xs font-mono text-muted-foreground w-8 shrink-0">
                    #{chunk.chunk_index}
                  </span>
                  <span className="text-sm truncate flex-1">
                    {chunk.content.slice(0, 120)}...
                  </span>
                  <Badge
                    variant="outline"
                    className="text-[10px] shrink-0"
                  >
                    {chunk.token_count} tokens
                  </Badge>
                </div>

                {expandedChunk === chunk.id && (
                  <div className="px-4 pb-4 pt-1 border-t border-border/20">
                    <pre className="text-xs leading-relaxed whitespace-pre-wrap text-muted-foreground/90 max-h-96 overflow-y-auto">
                      {chunk.content}
                    </pre>
                    <div className="flex items-center gap-4 mt-3 text-[10px] text-muted-foreground/60">
                      <span>ID: {chunk.id.slice(0, 8)}...</span>
                      <span>Index: {chunk.chunk_index}</span>
                      <span>Tokens: {chunk.token_count}</span>
                    </div>
                  </div>
                )}
              </Card>
            ))}

            {chunks.length < totalChunks && (
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={loadMore}
                disabled={loadingMore}
              >
                {loadingMore ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                ) : null}
                Load more ({chunks.length}/{totalChunks})
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function MetaCard({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof FileText;
  label: string;
  value: string;
}) {
  return (
    <Card className="border-border/40 bg-card/50">
      <CardContent className="flex items-center gap-3 py-3 px-4">
        <Icon className="h-4 w-4 text-muted-foreground/60 shrink-0" />
        <div>
          <p className="text-[10px] text-muted-foreground">{label}</p>
          <p className="text-sm font-medium">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

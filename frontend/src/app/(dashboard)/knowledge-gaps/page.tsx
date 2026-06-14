"use client";

import { useEffect, useState, useCallback } from "react";
import { Lightbulb, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api-client";
import type { KnowledgeGap, KnowledgeGapStats } from "@/types/api";

const REASON_LABELS: Record<string, string> = {
  no_answer: "No answer",
  low_confidence: "Low confidence",
  hallucination_blocked: "Blocked (hallucination)",
};

const REASON_COLORS: Record<string, string> = {
  no_answer: "border-red-500/30 text-red-400",
  low_confidence: "border-yellow-500/30 text-yellow-400",
  hallucination_blocked: "border-orange-500/30 text-orange-400",
};

const STATUS_COLORS: Record<string, string> = {
  open: "border-blue-500/30 text-blue-400",
  assigned: "border-purple-500/30 text-purple-400",
  resolved: "border-emerald-500/30 text-emerald-400",
  dismissed: "border-zinc-500/30 text-zinc-400",
};

export default function KnowledgeGapsPage() {
  const [gaps, setGaps] = useState<KnowledgeGap[]>([]);
  const [stats, setStats] = useState<KnowledgeGapStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("all");

  const fetchGaps = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (activeTab !== "all") params.set("status", activeTab);
      const [items, statsData] = await Promise.all([
        api.get<KnowledgeGap[]>(`/knowledge-gaps?${params.toString()}`),
        api.get<KnowledgeGapStats>("/knowledge-gaps/stats"),
      ]);
      setGaps(items);
      setStats(statsData);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    setLoading(true);
    fetchGaps();
  }, [fetchGaps]);

  const updateStatus = async (id: string, status: string) => {
    try {
      await api.patch(`/knowledge-gaps/${id}`, { status });
      fetchGaps();
    } catch {
      // silent
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Knowledge Gaps</h1>
        <p className="text-sm text-muted-foreground">
          Questions the system couldn&apos;t answer reliably — turn failed answers into action.
        </p>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-6 text-sm">
        <span className="text-muted-foreground">
          Total <span className="font-semibold text-foreground">{stats?.total ?? 0}</span>
        </span>
        <span className="text-blue-400">Open {stats?.open ?? 0}</span>
        <span className="text-emerald-400">Resolved {stats?.resolved ?? 0}</span>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="open">Open</TabsTrigger>
          <TabsTrigger value="resolved">Resolved</TabsTrigger>
          <TabsTrigger value="dismissed">Dismissed</TabsTrigger>
        </TabsList>
      </Tabs>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : gaps.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Lightbulb className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground mt-3">
            No knowledge gaps here — answers are landing well.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {gaps.map((gap) => (
            <div
              key={gap.id}
              className="rounded-lg border border-border/40 bg-card/50 p-4 space-y-2"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium">{gap.question}</p>
                <div className="flex items-center gap-1.5 shrink-0">
                  {gap.occurrences > 1 && (
                    <Badge variant="outline" className="border-border/50 text-muted-foreground">
                      ×{gap.occurrences}
                    </Badge>
                  )}
                  <Badge variant="outline" className={REASON_COLORS[gap.reason] ?? ""}>
                    {REASON_LABELS[gap.reason] ?? gap.reason}
                  </Badge>
                  <Badge variant="outline" className={STATUS_COLORS[gap.status] ?? ""}>
                    {gap.status}
                  </Badge>
                </div>
              </div>

              {gap.weak_sources.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  Weak sources: {gap.weak_sources.map((s) => s.title).join(", ")}
                </p>
              )}

              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">
                  {new Date(gap.created_at).toLocaleDateString()}
                </span>
                {gap.status !== "resolved" && gap.status !== "dismissed" && (
                  <div className="flex items-center gap-1.5">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 gap-1 text-xs"
                      onClick={() => updateStatus(gap.id, "resolved")}
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" /> Resolve
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 gap-1 text-xs text-muted-foreground"
                      onClick={() => updateStatus(gap.id, "dismissed")}
                    >
                      <XCircle className="h-3.5 w-3.5" /> Dismiss
                    </Button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

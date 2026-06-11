"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BarChart3,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  TrendingUp,
  TrendingDown,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api-client";
import type {
  EvaluationDataset,
  EvaluationRun,
  EvaluationRunDetail,
  EvalItemResult,
} from "@/types/api";

interface MetricCard {
  label: string;
  key: string;
  format: "percent" | "ms" | "usd" | "number";
  target?: number;
  higherIsBetter: boolean;
}

const METRIC_CARDS: MetricCard[] = [
  { label: "Recall@10", key: "recall_at_10", format: "percent", target: 0.8, higherIsBetter: true },
  { label: "MRR", key: "mrr", format: "percent", target: 0.7, higherIsBetter: true },
  { label: "NDCG@10", key: "ndcg_at_10", format: "percent", target: 0.75, higherIsBetter: true },
  { label: "Faithfulness", key: "faithfulness", format: "percent", target: 0.85, higherIsBetter: true },
  { label: "Citation Accuracy", key: "citation_accuracy", format: "percent", target: 0.9, higherIsBetter: true },
  { label: "Answer Relevance", key: "answer_relevance", format: "percent", target: 0.8, higherIsBetter: true },
  { label: "Hallucination", key: "hallucination_rate", format: "percent", target: 0.1, higherIsBetter: false },
  { label: "Avg Confidence", key: "avg_confidence", format: "percent", target: 0.8, higherIsBetter: true },
  { label: "Avg Latency", key: "avg_latency_ms", format: "ms", target: 5000, higherIsBetter: false },
  { label: "Precision@10", key: "precision_at_10", format: "percent", target: 0.6, higherIsBetter: true },
];

function formatMetric(value: number | undefined, format: string): string {
  if (value === undefined || value === null) return "--";
  switch (format) {
    case "percent":
      return `${(value * 100).toFixed(1)}%`;
    case "ms":
      return `${Math.round(value)}ms`;
    case "usd":
      return `$${value.toFixed(4)}`;
    default:
      return value.toFixed(2);
  }
}

function getMetricColor(value: number, target: number, higherIsBetter: boolean): string {
  const meets = higherIsBetter ? value >= target : value <= target;
  const close = higherIsBetter
    ? value >= target * 0.85
    : value <= target * 1.15;

  if (meets) return "text-emerald-400";
  if (close) return "text-yellow-400";
  return "text-red-400";
}

export default function EvaluationsPage() {
  const [datasets, setDatasets] = useState<EvaluationDataset[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<EvaluationRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [expandedItem, setExpandedItem] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [ds, rs] = await Promise.all([
        api.get<EvaluationDataset[]>("/evaluation/datasets"),
        api.get<EvaluationRun[]>("/evaluation/runs"),
      ]);
      setDatasets(ds);
      setRuns(rs);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Poll for running evaluations
  useEffect(() => {
    const hasRunning = runs.some((r) => r.status === "running" || r.status === "queued");
    if (!hasRunning) return;

    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [runs, fetchData]);

  const triggerRun = async () => {
    if (datasets.length === 0) return;
    setTriggering(true);
    try {
      await api.post("/evaluation/runs", {
        dataset_id: datasets[0].id,
      });
      await fetchData();
    } catch {
      // silent
    } finally {
      setTriggering(false);
    }
  };

  const loadRunDetail = async (runId: string) => {
    if (selectedRun?.id === runId) {
      setSelectedRun(null);
      return;
    }
    try {
      const detail = await api.get<EvaluationRunDetail>(
        `/evaluation/runs/${runId}`
      );
      setSelectedRun(detail);
    } catch {
      // silent
    }
  };

  const completedRuns = runs
    .filter((r) => r.status === "completed")
    .sort((a, b) => {
      const aTime = a.completed_at ? new Date(a.completed_at).getTime() : new Date(a.started_at).getTime();
      const bTime = b.completed_at ? new Date(b.completed_at).getTime() : new Date(b.started_at).getTime();
      return bTime - aTime;
    });
  const latestRun = completedRuns[0];
  const previousRun = completedRuns[1];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Evaluations</h1>
          <p className="text-sm text-muted-foreground">
            Track retrieval quality and answer accuracy over time
          </p>
        </div>
        <Button
          size="sm"
          className="gap-1.5"
          onClick={triggerRun}
          disabled={triggering || datasets.length === 0}
        >
          {triggering ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          Run evaluation
        </Button>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9 gap-3">
        {METRIC_CARDS.map((metric) => {
          const currentValue = latestRun?.metrics?.[metric.key];
          const previousValue = previousRun?.metrics?.[metric.key];
          const delta =
            currentValue !== undefined && previousValue !== undefined
              ? currentValue - previousValue
              : undefined;

          return (
            <Card key={metric.label} className="border-border/40 bg-card/50">
              <CardHeader className="pb-1 pt-4 px-4">
                <CardTitle className="text-xs text-muted-foreground font-normal">
                  {metric.label}
                </CardTitle>
              </CardHeader>
              <CardContent className="px-4 pb-4">
                <p
                  className={`text-2xl font-semibold ${
                    currentValue !== undefined && metric.target
                      ? getMetricColor(currentValue, metric.target, metric.higherIsBetter)
                      : ""
                  }`}
                >
                  {formatMetric(currentValue, metric.format)}
                </p>
                {delta !== undefined && delta !== 0 && (
                  <div className="flex items-center gap-0.5 mt-0.5">
                    {(metric.higherIsBetter ? delta > 0 : delta < 0) ? (
                      <TrendingUp className="h-3 w-3 text-emerald-400" />
                    ) : (
                      <TrendingDown className="h-3 w-3 text-red-400" />
                    )}
                    <span
                      className={`text-xs ${
                        (metric.higherIsBetter ? delta > 0 : delta < 0)
                          ? "text-emerald-400"
                          : "text-red-400"
                      }`}
                    >
                      {metric.format === "percent"
                        ? `${(Math.abs(delta) * 100).toFixed(1)}%`
                        : Math.abs(delta).toFixed(1)}
                    </span>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Runs Table */}
      {runs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <BarChart3 className="h-10 w-10 text-muted-foreground/40 mb-3" />
          <p className="text-sm text-muted-foreground">No evaluation runs yet</p>
          <p className="text-xs text-muted-foreground/60 mt-1">
            {datasets.length === 0
              ? "Load a golden dataset first, then run your first evaluation"
              : "Click 'Run evaluation' to start"}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          <h2 className="text-sm font-medium text-muted-foreground">
            Evaluation Runs
          </h2>
          <div className="border border-border/40 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/40 bg-muted/30">
                  <th className="text-left py-2.5 px-4 font-medium text-muted-foreground w-8" />
                  <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">
                    Name
                  </th>
                  <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">
                    Status
                  </th>
                  <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">
                    Recall
                  </th>
                  <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">
                    MRR
                  </th>
                  <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">
                    Faithfulness
                  </th>
                  <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">
                    Latency
                  </th>
                  <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <RunRow
                    key={run.id}
                    run={run}
                    isSelected={selectedRun?.id === run.id}
                    onToggle={() => loadRunDetail(run.id)}
                    detail={selectedRun?.id === run.id ? selectedRun : null}
                    expandedItem={expandedItem}
                    onExpandItem={setExpandedItem}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Dataset Info */}
      {datasets.length > 0 && (
        <div className="text-xs text-muted-foreground/60">
          Dataset: {datasets[0].name} ({datasets[0].item_count} items)
        </div>
      )}
    </div>
  );
}

function RunRow({
  run,
  isSelected,
  onToggle,
  detail,
  expandedItem,
  onExpandItem,
}: {
  run: EvaluationRun;
  isSelected: boolean;
  onToggle: () => void;
  detail: EvaluationRunDetail | null;
  expandedItem: string | null;
  onExpandItem: (id: string | null) => void;
}) {
  return (
    <>
      <tr
        className="border-b border-border/20 hover:bg-muted/20 cursor-pointer transition-colors"
        onClick={onToggle}
      >
        <td className="py-2.5 px-4">
          {isSelected ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </td>
        <td className="py-2.5 px-4 font-medium">{run.name || "Unnamed run"}</td>
        <td className="py-2.5 px-4">
          <StatusBadge status={run.status} />
        </td>
        <td className="py-2.5 px-4">
          {run.status === "completed"
            ? formatMetric(run.metrics?.recall_at_10, "percent")
            : "--"}
        </td>
        <td className="py-2.5 px-4">
          {run.status === "completed"
            ? formatMetric(run.metrics?.mrr, "percent")
            : "--"}
        </td>
        <td className="py-2.5 px-4">
          {run.status === "completed"
            ? formatMetric(run.metrics?.faithfulness, "percent")
            : "--"}
        </td>
        <td className="py-2.5 px-4">
          {run.status === "completed"
            ? formatMetric(run.metrics?.avg_latency_ms, "ms")
            : "--"}
        </td>
        <td className="py-2.5 px-4 text-muted-foreground">
          {new Date(run.completed_at || run.started_at).toLocaleDateString()}
        </td>
      </tr>

      {/* Per-item drill-down */}
      {isSelected && detail?.per_item_results && (
        <tr>
          <td colSpan={8} className="bg-muted/10 px-4 py-3">
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-muted-foreground mb-2">
                Per-Question Results ({detail.per_item_results.length} items)
              </p>
              {detail.per_item_results.map((item) => (
                <ItemRow
                  key={item.item_id}
                  item={item}
                  isExpanded={expandedItem === item.item_id}
                  onToggle={() =>
                    onExpandItem(
                      expandedItem === item.item_id ? null : item.item_id
                    )
                  }
                />
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function ItemRow({
  item,
  isExpanded,
  onToggle,
}: {
  item: EvalItemResult;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const passed = item.metrics.recall_at_10 > 0 && item.confidence >= 0.6;

  return (
    <div className="border border-border/30 rounded-md bg-card/30">
      <div
        className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-muted/20 transition-colors"
        onClick={(e) => {
          e.stopPropagation();
          onToggle();
        }}
      >
        {passed ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
        ) : (
          <XCircle className="h-4 w-4 text-red-400 shrink-0" />
        )}
        <span className="text-sm flex-1 truncate">{item.question}</span>
        <div className="flex items-center gap-3 text-xs text-muted-foreground shrink-0">
          {item.query_type && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0">
              {item.query_type}
            </Badge>
          )}
          {item.difficulty && (
            <Badge
              variant="outline"
              className={`text-[10px] px-1.5 py-0 ${
                item.difficulty === "hard"
                  ? "border-red-500/30 text-red-400"
                  : item.difficulty === "medium"
                  ? "border-yellow-500/30 text-yellow-400"
                  : "border-emerald-500/30 text-emerald-400"
              }`}
            >
              {item.difficulty}
            </Badge>
          )}
          <span>R: {(item.metrics.recall_at_10 * 100).toFixed(0)}%</span>
          <span>C: {(item.confidence * 100).toFixed(0)}%</span>
          <span>{item.latency_ms}ms</span>
        </div>
      </div>

      {isExpanded && (
        <div className="px-3 py-3 border-t border-border/20 space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-muted-foreground mb-1">
                Expected Answer
              </p>
              <p className="text-xs leading-relaxed">{item.expected_answer}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-1">
                Actual Answer
              </p>
              <p className="text-xs leading-relaxed">
                {item.actual_answer || "No answer generated"}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-2 text-xs">
            <div>
              <span className="text-muted-foreground">Recall</span>
              <p className="font-medium">
                {(item.metrics.recall_at_10 * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">Precision</span>
              <p className="font-medium">
                {(item.metrics.precision_at_10 * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">MRR</span>
              <p className="font-medium">
                {(item.metrics.mrr * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">NDCG</span>
              <p className="font-medium">
                {(item.metrics.ndcg_at_10 * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">Faithfulness</span>
              <p className="font-medium">
                {item.metrics.faithfulness !== undefined
                  ? `${(item.metrics.faithfulness * 100).toFixed(1)}%`
                  : "--"}
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">Citation Acc.</span>
              <p className="font-medium">
                {item.metrics.citation_accuracy !== undefined
                  ? `${(item.metrics.citation_accuracy * 100).toFixed(1)}%`
                  : "--"}
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">Hallucination</span>
              <p className="font-medium">
                {item.metrics.hallucination_rate !== undefined
                  ? `${(item.metrics.hallucination_rate * 100).toFixed(1)}%`
                  : "--"}
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">Confidence</span>
              <p className="font-medium">
                {(item.confidence * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">Cost</span>
              <p className="font-medium">${item.cost_usd.toFixed(4)}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return (
        <Badge
          variant="outline"
          className="border-emerald-500/30 text-emerald-400 text-xs"
        >
          <CheckCircle2 className="h-3 w-3 mr-1" />
          Completed
        </Badge>
      );
    case "running":
    case "queued":
      return (
        <Badge
          variant="outline"
          className="border-blue-500/30 text-blue-400 text-xs"
        >
          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
          {status === "queued" ? "Queued" : "Running"}
        </Badge>
      );
    case "failed":
      return (
        <Badge
          variant="outline"
          className="border-red-500/30 text-red-400 text-xs"
        >
          <XCircle className="h-3 w-3 mr-1" />
          Failed
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

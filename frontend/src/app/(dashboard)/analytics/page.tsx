"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Activity,
  TrendingUp,
  DollarSign,
  Clock,
  Loader2,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api-client";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from "recharts";

interface UsageData {
  total_queries: number;
  total_users: number;
  total_sessions: number;
  status_breakdown: Record<string, number>;
  volume: { period: string; query_count: number; unique_users: number }[];
}

interface QualityData {
  avg_confidence: number;
  avg_faithfulness: number;
  avg_citation_accuracy: number;
  avg_hallucination: number;
  trends: {
    period: string;
    avg_confidence: number;
    avg_faithfulness: number;
    avg_citation_accuracy: number;
    avg_hallucination: number;
    count: number;
  }[];
}

interface CostData {
  total_cost: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  avg_cost_per_query: number;
  breakdown: {
    period: string;
    total_cost: number;
    prompt_tokens: number;
    completion_tokens: number;
    query_count: number;
  }[];
}

interface LatencyData {
  p50: number;
  p75: number;
  p95: number;
  p99: number;
  avg_latency: number;
  min_latency: number;
  max_latency: number;
  count: number;
  stage_breakdown: Record<string, number>;
}

type Range = "7" | "30" | "90";

const RANGE_OPTIONS: { label: string; value: Range }[] = [
  { label: "7d", value: "7" },
  { label: "30d", value: "30" },
  { label: "90d", value: "90" },
];

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatCost(v: number): string {
  return `$${v.toFixed(4)}`;
}

const CHART_COLORS = {
  primary: "#10b981",
  secondary: "#6366f1",
  tertiary: "#f59e0b",
  danger: "#ef4444",
  muted: "#64748b",
};

export default function AnalyticsPage() {
  const [range, setRange] = useState<Range>("30");
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [quality, setQuality] = useState<QualityData | null>(null);
  const [costs, setCosts] = useState<CostData | null>(null);
  const [latency, setLatency] = useState<LatencyData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [u, q, c, l] = await Promise.all([
        api.get<UsageData>(`/analytics/usage?days=${range}`),
        api.get<QualityData>(`/analytics/quality?days=${range}`),
        api.get<CostData>(`/analytics/costs?days=${range}`),
        api.get<LatencyData>(`/analytics/latency?days=${range}`),
      ]);
      setUsage(u);
      setQuality(q);
      setCosts(c);
      setLatency(l);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [range]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const volumeData = (usage?.volume || []).map((v) => ({
    ...v,
    date: formatDate(v.period),
  }));

  const qualityData = (quality?.trends || []).map((t) => ({
    ...t,
    date: formatDate(t.period),
    confidence: +(t.avg_confidence * 100).toFixed(1),
    faithfulness: +(t.avg_faithfulness * 100).toFixed(1),
    citation: +(t.avg_citation_accuracy * 100).toFixed(1),
  }));

  const costData = (costs?.breakdown || []).map((b) => ({
    ...b,
    date: formatDate(b.period),
  }));

  const stageData = latency?.stage_breakdown
    ? Object.entries(latency.stage_breakdown)
        .filter(([, v]) => v > 0)
        .map(([stage, ms]) => ({
          stage: stage.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
          ms,
        }))
        .sort((a, b) => b.ms - a.ms)
    : [];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Analytics</h1>
          <p className="text-sm text-muted-foreground">
            Monitor query volume, quality, cost, and latency
          </p>
        </div>
        <div className="flex items-center gap-1 bg-muted/30 rounded-md p-0.5">
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setRange(opt.value)}
              className={`px-3 py-1 text-xs rounded-sm transition-colors ${
                range === opt.value
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <SummaryCard
          title="Total Queries"
          value={usage?.total_queries?.toString() || "0"}
          subtitle={`${usage?.total_sessions || 0} sessions`}
          icon={Activity}
        />
        <SummaryCard
          title="Avg Confidence"
          value={quality ? `${(quality.avg_confidence * 100).toFixed(1)}%` : "--"}
          subtitle={
            quality
              ? `Faithfulness: ${(quality.avg_faithfulness * 100).toFixed(0)}%`
              : undefined
          }
          icon={TrendingUp}
          valueColor={
            quality && quality.avg_confidence >= 0.8
              ? "text-emerald-400"
              : quality && quality.avg_confidence >= 0.6
              ? "text-yellow-400"
              : "text-red-400"
          }
        />
        <SummaryCard
          title="Total Cost"
          value={costs ? `$${costs.total_cost.toFixed(4)}` : "$0.00"}
          subtitle={
            costs
              ? `$${costs.avg_cost_per_query.toFixed(4)} / query`
              : undefined
          }
          icon={DollarSign}
        />
        <SummaryCard
          title="p95 Latency"
          value={latency ? `${(latency.p95 / 1000).toFixed(1)}s` : "--"}
          subtitle={
            latency
              ? `Avg: ${(latency.avg_latency / 1000).toFixed(1)}s`
              : undefined
          }
          icon={Clock}
          valueColor={
            latency && latency.p95 <= 5000
              ? "text-emerald-400"
              : latency && latency.p95 <= 10000
              ? "text-yellow-400"
              : "text-red-400"
          }
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Query Volume */}
        <Card className="border-border/40 bg-card/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Query Volume</CardTitle>
          </CardHeader>
          <CardContent>
            {volumeData.length === 0 ? (
              <EmptyChart />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={volumeData}>
                  <defs>
                    <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={CHART_COLORS.primary} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={CHART_COLORS.primary} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#888" }} />
                  <YAxis tick={{ fontSize: 11, fill: "#888" }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1c1c1c",
                      border: "1px solid #333",
                      borderRadius: "6px",
                      fontSize: 12,
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="query_count"
                    stroke={CHART_COLORS.primary}
                    fill="url(#volGrad)"
                    strokeWidth={2}
                    name="Queries"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Quality Metrics */}
        <Card className="border-border/40 bg-card/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Quality Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            {qualityData.length === 0 ? (
              <EmptyChart />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={qualityData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#888" }} />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#888" }}
                    domain={[0, 100]}
                    tickFormatter={(v: number) => `${v}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1c1c1c",
                      border: "1px solid #333",
                      borderRadius: "6px",
                      fontSize: 12,
                    }}
                    formatter={(v) => `${v}%`}
                  />
                  <Legend
                    iconSize={8}
                    wrapperStyle={{ fontSize: 11 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="confidence"
                    stroke={CHART_COLORS.primary}
                    strokeWidth={2}
                    dot={false}
                    name="Confidence"
                  />
                  <Line
                    type="monotone"
                    dataKey="faithfulness"
                    stroke={CHART_COLORS.secondary}
                    strokeWidth={2}
                    dot={false}
                    name="Faithfulness"
                  />
                  <Line
                    type="monotone"
                    dataKey="citation"
                    stroke={CHART_COLORS.tertiary}
                    strokeWidth={2}
                    dot={false}
                    name="Citation Acc."
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Cost Breakdown */}
        <Card className="border-border/40 bg-card/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Cost per Day</CardTitle>
          </CardHeader>
          <CardContent>
            {costData.length === 0 ? (
              <EmptyChart />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={costData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#888" }} />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#888" }}
                    tickFormatter={(v: number) => `$${v.toFixed(2)}`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1c1c1c",
                      border: "1px solid #333",
                      borderRadius: "6px",
                      fontSize: 12,
                    }}
                    formatter={(v) => formatCost(v as number)}
                  />
                  <Bar
                    dataKey="total_cost"
                    fill={CHART_COLORS.secondary}
                    radius={[4, 4, 0, 0]}
                    name="Cost"
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Latency Stage Breakdown */}
        <Card className="border-border/40 bg-card/50">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">Latency Breakdown</CardTitle>
              {latency && (
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span>p50: {latency.p50}ms</span>
                  <span>p75: {latency.p75}ms</span>
                  <span>p95: {latency.p95}ms</span>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {stageData.length === 0 ? (
              <EmptyChart />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={stageData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11, fill: "#888" }}
                    tickFormatter={(v: number) => `${v}ms`}
                  />
                  <YAxis
                    type="category"
                    dataKey="stage"
                    tick={{ fontSize: 10, fill: "#888" }}
                    width={120}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1c1c1c",
                      border: "1px solid #333",
                      borderRadius: "6px",
                      fontSize: 12,
                    }}
                    formatter={(v) => `${v}ms`}
                  />
                  <Bar dataKey="ms" radius={[0, 4, 4, 0]} name="Avg ms">
                    {stageData.map((entry, index) => (
                      <Cell
                        key={entry.stage}
                        fill={
                          entry.ms > 2000
                            ? CHART_COLORS.danger
                            : entry.ms > 500
                            ? CHART_COLORS.tertiary
                            : CHART_COLORS.primary
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Status Breakdown + Token Usage */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="border-border/40 bg-card/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Response Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-3">
              {Object.entries(usage?.status_breakdown || {}).map(([status, count]) => (
                <div
                  key={status}
                  className="flex items-center gap-2 px-3 py-2 bg-muted/20 rounded-md"
                >
                  <Badge
                    variant="outline"
                    className={`text-[10px] ${
                      status === "success"
                        ? "border-emerald-500/30 text-emerald-400"
                        : status === "error"
                        ? "border-red-500/30 text-red-400"
                        : "border-yellow-500/30 text-yellow-400"
                    }`}
                  >
                    {status}
                  </Badge>
                  <span className="text-lg font-semibold">{count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/40 bg-card/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Token Usage</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">Prompt Tokens</p>
                <p className="text-lg font-semibold">
                  {(costs?.total_prompt_tokens || 0).toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Completion Tokens</p>
                <p className="text-lg font-semibold">
                  {(costs?.total_completion_tokens || 0).toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Total</p>
                <p className="text-lg font-semibold">
                  {(
                    (costs?.total_prompt_tokens || 0) +
                    (costs?.total_completion_tokens || 0)
                  ).toLocaleString()}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function SummaryCard({
  title,
  value,
  subtitle,
  icon: Icon,
  valueColor,
}: {
  title: string;
  value: string;
  subtitle?: string;
  icon: typeof Activity;
  valueColor?: string;
}) {
  return (
    <Card className="border-border/40 bg-card/50">
      <CardHeader className="flex flex-row items-center justify-between pb-1 pt-4 px-4">
        <CardTitle className="text-xs text-muted-foreground font-normal">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground/60" />
      </CardHeader>
      <CardContent className="px-4 pb-4">
        <p className={`text-2xl font-semibold ${valueColor || ""}`}>{value}</p>
        {subtitle && (
          <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>
        )}
      </CardContent>
    </Card>
  );
}

function EmptyChart() {
  return (
    <div className="flex items-center justify-center h-[220px] text-sm text-muted-foreground">
      No data available for this period
    </div>
  );
}

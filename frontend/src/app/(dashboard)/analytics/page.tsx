"use client";

import { Activity, TrendingUp, DollarSign, Clock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const SUMMARY_CARDS = [
  {
    title: "Total Queries",
    value: "0",
    change: null,
    icon: Activity,
  },
  {
    title: "Avg Confidence",
    value: "--",
    change: null,
    icon: TrendingUp,
  },
  {
    title: "Total Cost",
    value: "$0.00",
    change: null,
    icon: DollarSign,
  },
  {
    title: "p95 Latency",
    value: "--",
    change: null,
    icon: Clock,
  },
];

export default function AnalyticsPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Analytics</h1>
        <p className="text-sm text-muted-foreground">
          Monitor query volume, quality, cost, and latency
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {SUMMARY_CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <Card key={card.title} className="border-border/40 bg-card/50">
              <CardHeader className="flex flex-row items-center justify-between pb-1 pt-4 px-4">
                <CardTitle className="text-xs text-muted-foreground font-normal">
                  {card.title}
                </CardTitle>
                <Icon className="h-4 w-4 text-muted-foreground/60" />
              </CardHeader>
              <CardContent className="px-4 pb-4">
                <p className="text-2xl font-semibold">{card.value}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="border-border/40 bg-card/50">
          <CardHeader>
            <CardTitle className="text-sm">Query Volume</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center h-48 text-sm text-muted-foreground">
              Chart will render when query data is available
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/40 bg-card/50">
          <CardHeader>
            <CardTitle className="text-sm">Quality Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center h-48 text-sm text-muted-foreground">
              Chart will render when quality data is available
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/40 bg-card/50">
          <CardHeader>
            <CardTitle className="text-sm">Cost Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center h-48 text-sm text-muted-foreground">
              Chart will render when cost data is available
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/40 bg-card/50">
          <CardHeader>
            <CardTitle className="text-sm">Latency Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center h-48 text-sm text-muted-foreground">
              Chart will render when latency data is available
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

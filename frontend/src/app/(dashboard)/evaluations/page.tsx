"use client";

import { BarChart3, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const METRIC_CARDS = [
  { label: "Recall@10", value: "--", description: "Retrieval recall" },
  { label: "MRR", value: "--", description: "Mean reciprocal rank" },
  { label: "Faithfulness", value: "--", description: "Answer grounding" },
  { label: "Citation Accuracy", value: "--", description: "Citation validity" },
  { label: "Hallucination Rate", value: "--", description: "Unsupported claims" },
  { label: "Avg Latency", value: "--", description: "End-to-end time" },
];

export default function EvaluationsPage() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Evaluations</h1>
          <p className="text-sm text-muted-foreground">
            Track retrieval quality and answer accuracy over time
          </p>
        </div>
        <Button size="sm" className="gap-1.5" disabled>
          <Play className="h-4 w-4" />
          Run evaluation
        </Button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {METRIC_CARDS.map((metric) => (
          <Card key={metric.label} className="border-border/40 bg-card/50">
            <CardHeader className="pb-1 pt-4 px-4">
              <CardTitle className="text-xs text-muted-foreground font-normal">
                {metric.label}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <p className="text-2xl font-semibold">{metric.value}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {metric.description}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex flex-col items-center justify-center py-20 text-center">
        <BarChart3 className="h-10 w-10 text-muted-foreground/40 mb-3" />
        <p className="text-sm text-muted-foreground">No evaluation runs yet</p>
        <p className="text-xs text-muted-foreground/60 mt-1">
          Create a golden dataset and run your first evaluation
        </p>
      </div>
    </div>
  );
}

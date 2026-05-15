import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { CONFIDENCE_THRESHOLDS } from "@/lib/constants";

interface ConfidenceBadgeProps {
  confidence: number;
}

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  const percent = Math.round(confidence * 100);

  let variant: "default" | "secondary" | "destructive" | "outline" = "default";
  let colorClass = "";
  let label = "";

  if (confidence >= CONFIDENCE_THRESHOLDS.HIGH) {
    variant = "outline";
    colorClass = "border-emerald-500/30 text-emerald-400 bg-emerald-500/10";
    label = "High confidence";
  } else if (confidence >= CONFIDENCE_THRESHOLDS.MEDIUM) {
    variant = "outline";
    colorClass = "border-amber-500/30 text-amber-400 bg-amber-500/10";
    label = "Medium confidence";
  } else {
    variant = "outline";
    colorClass = "border-red-500/30 text-red-400 bg-red-500/10";
    label = "Low confidence";
  }

  return (
    <Badge variant={variant} className={cn("text-xs font-normal", colorClass)}>
      {label} ({percent}%)
    </Badge>
  );
}

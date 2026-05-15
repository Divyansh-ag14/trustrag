export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

export const APP_NAME = "TrustRAG";

export const NAV_ITEMS = [
  { label: "Ask", href: "/chat", icon: "MessageSquare" },
  { label: "Documents", href: "/documents", icon: "FileText" },
  { label: "Evaluations", href: "/evaluations", icon: "BarChart3" },
  { label: "Feedback", href: "/feedback", icon: "ThumbsUp" },
  { label: "Analytics", href: "/analytics", icon: "Activity" },
  { label: "Settings", href: "/settings", icon: "Settings" },
] as const;

export const CONFIDENCE_THRESHOLDS = {
  HIGH: 0.8,
  MEDIUM: 0.6,
} as const;

export const SOURCE_TYPE_LABELS: Record<string, string> = {
  pdf: "PDF",
  markdown: "Markdown",
  text: "Text",
  html: "HTML",
  csv: "CSV",
  faq: "FAQ",
  slack_export: "Slack",
  api_doc: "API Doc",
  release_note: "Release Note",
};

export const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  processing: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  failed: "bg-red-500/10 text-red-400 border-red-500/20",
  archived: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
};

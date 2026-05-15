"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  MessageSquare,
  FileText,
  BarChart3,
  ThumbsUp,
  Activity,
  Settings,
  Shield,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useAppStore } from "@/stores/app-store";
import { cn } from "@/lib/utils";

const ICON_MAP = {
  MessageSquare,
  FileText,
  BarChart3,
  ThumbsUp,
  Activity,
  Settings,
} as const;

const NAV_ITEMS = [
  { label: "Ask", href: "/chat", icon: "MessageSquare" as const },
  { label: "Documents", href: "/documents", icon: "FileText" as const },
  { label: "Evaluations", href: "/evaluations", icon: "BarChart3" as const },
  { label: "Feedback", href: "/feedback", icon: "ThumbsUp" as const },
  { label: "Analytics", href: "/analytics", icon: "Activity" as const },
];

const BOTTOM_ITEMS = [
  { label: "Settings", href: "/settings", icon: "Settings" as const },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, toggleSidebar } = useAppStore();

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-border/40 bg-card/30 transition-all duration-200",
        sidebarOpen ? "w-56" : "w-14",
      )}
    >
      <div className="flex h-14 items-center gap-2 px-3">
        {sidebarOpen && (
          <Link href="/chat" className="flex items-center gap-2 px-1">
            <Shield className="h-5 w-5 text-primary" />
            <span className="text-sm font-semibold tracking-tight">TrustRAG</span>
          </Link>
        )}
        <Button
          variant="ghost"
          size="icon"
          className={cn("h-8 w-8 shrink-0", sidebarOpen ? "ml-auto" : "mx-auto")}
          onClick={toggleSidebar}
        >
          {sidebarOpen ? (
            <PanelLeftClose className="h-4 w-4" />
          ) : (
            <PanelLeftOpen className="h-4 w-4" />
          )}
        </Button>
      </div>

      <Separator className="opacity-40" />

      <nav className="flex flex-1 flex-col gap-1 p-2">
        {NAV_ITEMS.map((item) => {
          const Icon = ICON_MAP[item.icon];
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                !sidebarOpen && "justify-center px-0",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {sidebarOpen && <span>{item.label}</span>}
            </Link>
          );
        })}

        <div className="flex-1" />

        <Separator className="opacity-40 my-1" />

        {BOTTOM_ITEMS.map((item) => {
          const Icon = ICON_MAP[item.icon];
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                !sidebarOpen && "justify-center px-0",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {sidebarOpen && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

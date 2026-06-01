"use client";

import { useState } from "react";
import {
  RefreshCw,
  Trash2,
  Pencil,
  Loader2,
  Plug,
  Globe,
  GitBranch,
  FileText,
  AlertCircle,
} from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { CONNECTOR_TYPE_LABELS, CONNECTOR_STATUS_COLORS } from "@/lib/constants";
import type { Connector } from "@/types/api";

interface ConnectorListProps {
  connectors: Connector[];
  loading: boolean;
  onSync: (id: string) => void;
  onEdit: (connector: Connector) => void;
  onDelete: (id: string) => void;
  syncingIds: Set<string>;
}

const TYPE_ICONS: Record<string, typeof Globe> = {
  notion: FileText,
  github: GitBranch,
  web_scraper: Globe,
};

function formatDate(dateStr: string | null) {
  if (!dateStr) return "Never";
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ConnectorList({
  connectors,
  loading,
  onSync,
  onEdit,
  onDelete,
  syncingIds,
}: ConnectorListProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (connectors.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Plug className="h-10 w-10 text-muted-foreground/40 mb-3" />
        <p className="text-sm text-muted-foreground">No connectors configured</p>
        <p className="text-xs text-muted-foreground/60 mt-1">
          Connect external data sources to enrich your knowledge base
        </p>
      </div>
    );
  }

  return (
    <TooltipProvider>
      <Table>
        <TableHeader>
          <TableRow className="border-border/40 hover:bg-transparent">
            <TableHead className="text-xs">Name</TableHead>
            <TableHead className="text-xs">Type</TableHead>
            <TableHead className="text-xs">Status</TableHead>
            <TableHead className="text-xs text-right">Documents</TableHead>
            <TableHead className="text-xs">Last Synced</TableHead>
            <TableHead className="text-xs text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {connectors.map((conn) => {
            const Icon = TYPE_ICONS[conn.connector_type] || Plug;
            const isSyncing = syncingIds.has(conn.id) || conn.status === "syncing";

            return (
              <TableRow key={conn.id} className="border-border/40">
                <TableCell className="font-medium text-sm">
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    {conn.name}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className="text-xs font-normal">
                    {CONNECTOR_TYPE_LABELS[conn.connector_type] || conn.connector_type}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1.5">
                    <Badge
                      variant="outline"
                      className={`text-xs font-normal ${CONNECTOR_STATUS_COLORS[conn.status] || ""}`}
                    >
                      {conn.status}
                    </Badge>
                    {conn.status === "error" && conn.last_sync_error && (
                      <Tooltip>
                        <TooltipTrigger>
                          <AlertCircle className="h-3.5 w-3.5 text-red-400" />
                        </TooltipTrigger>
                        <TooltipContent side="top" className="max-w-xs">
                          <p className="text-xs">{conn.last_sync_error}</p>
                        </TooltipContent>
                      </Tooltip>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-right text-sm text-muted-foreground">
                  {conn.documents_synced}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {formatDate(conn.last_synced_at)}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => onSync(conn.id)}
                      disabled={isSyncing}
                      title="Sync now"
                    >
                      {isSyncing ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <RefreshCw className="h-3.5 w-3.5" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => onEdit(conn)}
                      title="Edit"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-muted-foreground hover:text-destructive"
                      onClick={() => onDelete(conn.id)}
                      title="Delete"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TooltipProvider>
  );
}

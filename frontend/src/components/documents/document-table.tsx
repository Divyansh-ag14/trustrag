"use client";

import { useRouter } from "next/navigation";
import {
  FileText,
  RotateCw,
  Trash2,
  Globe,
  GitBranch,
  StickyNote,
  FileCode,
  FileSpreadsheet,
  HelpCircle,
  MessageSquare,
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
import { SOURCE_TYPE_LABELS, STATUS_COLORS } from "@/lib/constants";
import type { Document } from "@/types/api";

const SOURCE_TYPE_ICONS: Record<string, typeof FileText> = {
  pdf: FileText,
  markdown: FileCode,
  text: FileText,
  html: Globe,
  csv: FileSpreadsheet,
  faq: HelpCircle,
  slack_export: MessageSquare,
  notion: StickyNote,
  github: GitBranch,
  web: Globe,
};

interface DocumentTableProps {
  documents: Document[];
  loading: boolean;
  onReindex: (id: string) => void;
  onDelete: (id: string) => void;
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function DocumentTable({
  documents,
  loading,
  onReindex,
  onDelete,
}: DocumentTableProps) {
  const router = useRouter();
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <FileText className="h-10 w-10 text-muted-foreground/40 mb-3" />
        <p className="text-sm text-muted-foreground">No documents yet</p>
        <p className="text-xs text-muted-foreground/60 mt-1">
          Upload documents to build your knowledge base
        </p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow className="border-border/40 hover:bg-transparent">
          <TableHead className="text-xs">Title</TableHead>
          <TableHead className="text-xs">Type</TableHead>
          <TableHead className="text-xs">Status</TableHead>
          <TableHead className="text-xs text-right">Chunks</TableHead>
          <TableHead className="text-xs">Updated</TableHead>
          <TableHead className="text-xs text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {documents.map((doc) => (
          <TableRow
            key={doc.id}
            className="border-border/40 cursor-pointer"
            onClick={() => router.push(`/documents/${doc.id}`)}
          >
            <TableCell className="font-medium text-sm">{doc.title}</TableCell>
            <TableCell>
              {(() => {
                const Icon = SOURCE_TYPE_ICONS[doc.source_type] || FileText;
                return (
                  <Badge variant="outline" className="text-xs font-normal gap-1">
                    <Icon className="h-3 w-3" />
                    {SOURCE_TYPE_LABELS[doc.source_type] || doc.source_type}
                  </Badge>
                );
              })()}
            </TableCell>
            <TableCell>
              <Badge
                variant="outline"
                className={`text-xs font-normal ${STATUS_COLORS[doc.status] || ""}`}
              >
                {doc.status}
              </Badge>
            </TableCell>
            <TableCell className="text-right text-sm text-muted-foreground">
              {doc.total_chunks}
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {formatDate(doc.updated_at)}
            </TableCell>
            <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-end gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => onReindex(doc.id)}
                  title="Reindex"
                >
                  <RotateCw className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-destructive"
                  onClick={() => onDelete(doc.id)}
                  title="Delete"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

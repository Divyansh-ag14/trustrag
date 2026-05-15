"use client";

import { useState, useEffect, useCallback } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { UploadZone } from "@/components/documents/upload-zone";
import { DocumentTable } from "@/components/documents/document-table";
import { api } from "@/lib/api-client";
import type { Document } from "@/types/api";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);

  const fetchDocuments = useCallback(async () => {
    try {
      const data = await api.get<{ documents: Document[]; total: number }>(
        "/documents",
      );
      setDocuments(data.documents);
    } catch {
      // handled by api client
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  async function handleReindex(id: string) {
    try {
      await api.post(`/documents/${id}/reindex`);
      fetchDocuments();
    } catch {
      // toast error
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.delete(`/documents/${id}`);
      fetchDocuments();
    } catch {
      // toast error
    }
  }

  function handleUploadComplete() {
    setUploadOpen(false);
    fetchDocuments();
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Documents</h1>
          <p className="text-sm text-muted-foreground">
            Manage your knowledge base documents
          </p>
        </div>
        <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
          <DialogTrigger
            render={
              <Button size="sm" className="gap-1.5">
                <Plus className="h-4 w-4" />
                Upload
              </Button>
            }
          />
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Upload documents</DialogTitle>
            </DialogHeader>
            <UploadZone onUploadComplete={handleUploadComplete} />
          </DialogContent>
        </Dialog>
      </div>

      <DocumentTable
        documents={documents}
        loading={loading}
        onReindex={handleReindex}
        onDelete={handleDelete}
      />
    </div>
  );
}

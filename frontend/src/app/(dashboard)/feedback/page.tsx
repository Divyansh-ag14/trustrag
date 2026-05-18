"use client";

import { useEffect, useState, useCallback } from "react";
import {
  ThumbsUp,
  ThumbsDown,
  MessageCircle,
  Loader2,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api-client";
import type { FeedbackItem, FeedbackStats } from "@/types/api";

export default function FeedbackPage() {
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);
  const [stats, setStats] = useState<FeedbackStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("all");
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewNote, setReviewNote] = useState("");

  const fetchFeedback = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (activeTab === "positive") params.set("rating", "up");
      if (activeTab === "negative") params.set("rating", "down");
      if (activeTab === "unreviewed") params.set("reviewed", "false");

      const [items, statsData] = await Promise.all([
        api.get<FeedbackItem[]>(`/api/v1/feedback?${params.toString()}`),
        api.get<FeedbackStats>("/api/v1/feedback/stats"),
      ]);
      setFeedback(items);
      setStats(statsData);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    setLoading(true);
    fetchFeedback();
  }, [fetchFeedback]);

  const submitReview = async (feedbackId: string) => {
    if (!reviewNote.trim()) return;
    try {
      await api.patch(`/api/v1/feedback/${feedbackId}/review`, {
        review_note: reviewNote,
      });
      setReviewingId(null);
      setReviewNote("");
      fetchFeedback();
    } catch {
      // silent
    }
  };

  const renderEmpty = (icon: React.ReactNode, message: string) => (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      {icon}
      <p className="text-sm text-muted-foreground mt-3">{message}</p>
    </div>
  );

  const renderFeedbackList = (items: FeedbackItem[]) => {
    if (items.length === 0) {
      return renderEmpty(
        <MessageCircle className="h-10 w-10 text-muted-foreground/40" />,
        "No feedback to display"
      );
    }

    return (
      <div className="space-y-2">
        {items.map((item) => (
          <FeedbackRow
            key={item.id}
            item={item}
            isReviewing={reviewingId === item.id}
            reviewNote={reviewingId === item.id ? reviewNote : ""}
            onStartReview={() => {
              setReviewingId(item.id);
              setReviewNote("");
            }}
            onCancelReview={() => setReviewingId(null)}
            onNoteChange={setReviewNote}
            onSubmitReview={() => submitReview(item.id)}
          />
        ))}
      </div>
    );
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header with stats */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Feedback</h1>
          <p className="text-sm text-muted-foreground">
            Review user feedback and improve answer quality
          </p>
        </div>
        {stats && (
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <ThumbsUp className="h-3.5 w-3.5 text-emerald-400" />
              {stats.positive}
            </span>
            <span className="flex items-center gap-1">
              <ThumbsDown className="h-3.5 w-3.5 text-red-400" />
              {stats.negative}
            </span>
            <span className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5 text-yellow-400" />
              {stats.unreviewed} unreviewed
            </span>
          </div>
        )}
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="all" className="text-xs">
            All
            {stats && (
              <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5 py-0">
                {stats.total}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="positive" className="text-xs">
            <ThumbsUp className="h-3 w-3 mr-1" />
            Positive
          </TabsTrigger>
          <TabsTrigger value="negative" className="text-xs">
            <ThumbsDown className="h-3 w-3 mr-1" />
            Negative
          </TabsTrigger>
          <TabsTrigger value="unreviewed" className="text-xs">
            Unreviewed
            {stats && stats.unreviewed > 0 && (
              <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5 py-0 bg-yellow-500/20 text-yellow-400">
                {stats.unreviewed}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <>
            <TabsContent value="all" className="mt-4">
              {renderFeedbackList(feedback)}
            </TabsContent>
            <TabsContent value="positive" className="mt-4">
              {renderFeedbackList(feedback)}
            </TabsContent>
            <TabsContent value="negative" className="mt-4">
              {renderFeedbackList(feedback)}
            </TabsContent>
            <TabsContent value="unreviewed" className="mt-4">
              {renderFeedbackList(feedback)}
            </TabsContent>
          </>
        )}
      </Tabs>
    </div>
  );
}

function FeedbackRow({
  item,
  isReviewing,
  reviewNote,
  onStartReview,
  onCancelReview,
  onNoteChange,
  onSubmitReview,
}: {
  item: FeedbackItem;
  isReviewing: boolean;
  reviewNote: string;
  onStartReview: () => void;
  onCancelReview: () => void;
  onNoteChange: (note: string) => void;
  onSubmitReview: () => void;
}) {
  return (
    <div className="border border-border/40 rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          {item.rating === "up" ? (
            <ThumbsUp className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" />
          ) : (
            <ThumbsDown className="h-4 w-4 text-red-400 mt-0.5 shrink-0" />
          )}
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium truncate">
              Query Result: {item.query_result_id.slice(0, 8)}...
            </p>
            {item.comment && (
              <p className="text-sm text-muted-foreground mt-1">
                &ldquo;{item.comment}&rdquo;
              </p>
            )}
            {item.corrected_answer && (
              <div className="mt-2 p-2 bg-muted/30 rounded text-xs">
                <span className="text-muted-foreground">Corrected answer: </span>
                {item.corrected_answer}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {item.reviewed_at ? (
            <Badge variant="outline" className="text-[10px] border-emerald-500/30 text-emerald-400">
              <CheckCircle2 className="h-3 w-3 mr-1" />
              Reviewed
            </Badge>
          ) : (
            <Button size="sm" variant="outline" onClick={onStartReview} className="text-xs h-7">
              Review
            </Button>
          )}
          <span className="text-xs text-muted-foreground">
            {new Date(item.created_at).toLocaleDateString()}
          </span>
        </div>
      </div>

      {/* Review section */}
      {item.reviewed_at && item.review_note && (
        <div className="pl-7 text-xs text-muted-foreground">
          <span className="font-medium">Review note:</span> {item.review_note}
        </div>
      )}

      {isReviewing && (
        <div className="pl-7 space-y-2">
          <textarea
            className="w-full bg-muted/30 border border-border/40 rounded-md px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-ring"
            rows={2}
            placeholder="Add review notes..."
            value={reviewNote}
            onChange={(e) => onNoteChange(e.target.value)}
          />
          <div className="flex items-center gap-2">
            <Button size="sm" className="text-xs h-7" onClick={onSubmitReview}>
              Mark Reviewed
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="text-xs h-7"
              onClick={onCancelReview}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

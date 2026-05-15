"use client";

import { ThumbsUp, ThumbsDown, MessageCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function FeedbackPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Feedback</h1>
        <p className="text-sm text-muted-foreground">
          Review user feedback and improve answer quality
        </p>
      </div>

      <Tabs defaultValue="all">
        <TabsList>
          <TabsTrigger value="all" className="text-xs">
            All
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
            <Badge variant="secondary" className="ml-1.5 text-xs px-1.5 py-0">
              0
            </Badge>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="all" className="mt-4">
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <MessageCircle className="h-10 w-10 text-muted-foreground/40 mb-3" />
            <p className="text-sm text-muted-foreground">No feedback yet</p>
            <p className="text-xs text-muted-foreground/60 mt-1">
              Feedback will appear here when users rate answers
            </p>
          </div>
        </TabsContent>

        <TabsContent value="positive" className="mt-4">
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <ThumbsUp className="h-10 w-10 text-muted-foreground/40 mb-3" />
            <p className="text-sm text-muted-foreground">No positive feedback</p>
          </div>
        </TabsContent>

        <TabsContent value="negative" className="mt-4">
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <ThumbsDown className="h-10 w-10 text-muted-foreground/40 mb-3" />
            <p className="text-sm text-muted-foreground">No negative feedback</p>
          </div>
        </TabsContent>

        <TabsContent value="unreviewed" className="mt-4">
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <MessageCircle className="h-10 w-10 text-muted-foreground/40 mb-3" />
            <p className="text-sm text-muted-foreground">
              All feedback has been reviewed
            </p>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

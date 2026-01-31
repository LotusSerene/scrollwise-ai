"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/components/MockAuthProvider";
import { Loader2, History } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { toast } from "sonner";

// Matches the GenerationHistoryEntry in backend/models.py
interface GenerationHistoryEntry {
  id: string;
  timestamp: string;
  num_chapters: number;
  word_count: number | null;
  plot: string;
  writing_style: string;
  instructions: {
    styleGuide?: string;
    additionalInstructions?: string;
    [key: string]: string | number | undefined; // More specific type
  };
}

interface HistoryTabProps {
  projectId: string;
  onLoadHistory: (historyEntry: GenerationHistoryEntry) => void;
}

const HistoryTab: React.FC<HistoryTabProps> = ({
  projectId,
  onLoadHistory,
}) => {
  const [history, setHistory] = useState<GenerationHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const auth = useAuth();

  const fetchHistory = useCallback(async () => {
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to view history.");
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    const token = auth.user.id_token;
    const apiUrl = `${process.env.NEXT_PUBLIC_BACKEND_URL}/projects/${projectId}/generation-history`;

    try {
      const response = await fetch(apiUrl, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          `Failed to fetch generation history: ${response.status} - ${errorText}`
        );
      }

      const data = await response.json();
      setHistory(data);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An unknown error occurred.";
      console.error(errorMessage);
      setError(errorMessage);
      toast.error("Failed to load generation history.");
    } finally {
      setIsLoading(false);
    }
  }, [projectId, auth.isAuthenticated, auth.user?.id_token]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center p-8">
        <p className="text-destructive">{error}</p>
        <Button onClick={fetchHistory} className="mt-4">
          Retry
        </Button>
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div className="text-center p-8 border-2 border-dashed border-muted rounded-lg">
        <History className="mx-auto h-12 w-12 text-muted-foreground" />
        <h3 className="mt-4 text-lg font-medium text-foreground">
          No Generation History
        </h3>
        <p className="mt-1 text-sm text-muted-foreground">
          You haven&apos;t generated any chapters for this project yet. Once you do,
          your settings will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {history.map((entry) => (
        <Card key={entry.id} className="bg-card/50">
          <CardHeader>
            <CardTitle className="flex justify-between items-center">
              <span>
                Generated on{" "}
                {new Date(entry.timestamp).toLocaleString()}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onLoadHistory(entry)}
              >
                Load
              </Button>
            </CardTitle>
            <CardDescription>
              {entry.num_chapters} chapter(s)
              {entry.word_count && ` · Approx. ${entry.word_count} words each`}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <h4 className="font-semibold text-sm">Plot / Outline</h4>
              <p className="text-muted-foreground text-sm truncate">
                {entry.plot}
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-sm">Writing Style</h4>
              <p className="text-muted-foreground text-sm truncate">
                {entry.writing_style}
              </p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
};

export default HistoryTab;

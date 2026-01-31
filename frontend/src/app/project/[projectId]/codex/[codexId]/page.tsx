"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { fetchApi } from "@/lib/api";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import {
  Loader2,
  AlertTriangle,
  ArrowLeft,
  Feather,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth
import { CodexEntry, CodexItemType } from "@/types"; // Import CodexEntry and CodexItemType

export default function ProjectCodexDetailPage() {
  // Renamed component
  const params = useParams();
  // Add null checks for params
  const projectId = params?.projectId as string; // Get projectId
  const codexId = params?.codexId as string;

  const [codexItem, setCodexItem] = useState<CodexEntry | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const auth = useAuth(); // Use the hook

  useEffect(() => {
    // Wait for auth to be ready and project/codex IDs to be available
    if (!auth.isLoading && !projectId && !codexId) {
      setError("Project or Codex ID missing.");
      setIsLoading(false);
      return;
    }
    if (auth.isLoading || !projectId || !codexId) return; // Wait if auth is loading or IDs missing

    if (!auth.isAuthenticated) {
      setError("Authentication required.");
      setIsLoading(false);
      // Optionally redirect or show login prompt
      return;
    }

    const fetchCodexItem = async (token: string | undefined) => {
      setIsLoading(true);
      setError(null);
      // Token is passed as argument

      if (!token) {
        setError("Authentication token not available.");
        setIsLoading(false);
        return;
      }

      try {
        // Use the project-specific endpoint
        const item = await fetchApi<CodexEntry>(
          `/projects/${projectId}/codex-items/${codexId}`,
          {},
          token
        );
        setCodexItem(item);
      } catch (err: unknown) {
        console.error("Error fetching codex item:", err);
        const errorMessage =
          err instanceof Error ? err.message : "Failed to load codex item.";
        setError(errorMessage);
        setCodexItem(null);
      } finally {
        setIsLoading(false);
      }
    };

    // Fetch only if authenticated and token is available
    if (auth.isAuthenticated && auth.user?.id_token) {
      fetchCodexItem(auth.user.id_token);
    } else if (!auth.isLoading) {
      // Handle case where auth is loaded but not authenticated
      setError("Authentication required.");
      setIsLoading(false);
    }
    // Add auth state to dependencies
  }, [
    projectId,
    codexId,
    auth.isLoading,
    auth.isAuthenticated,
    auth.user?.id_token,
  ]);

  // Add checks for projectId and codexId before proceeding
  if (!projectId || !codexId) {
    return <div>Invalid Project or Codex ID.</div>;
  }

  if (isLoading) {
    // ... loading spinner ...
    return (
      <div className="flex justify-center items-center min-h-screen">
        <Loader2 className="h-16 w-16 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    // ... error display ...
    return (
      <div className="container mx-auto px-6 py-12 text-center">
        <AlertTriangle className="h-12 w-12 mx-auto mb-4 text-destructive" />
        <h2 className="text-2xl font-semibold mb-4 text-destructive-foreground">
          Error Loading Codex Item
        </h2>
        <p className="text-muted-foreground mb-6">{error}</p>
        {/* Link back to project dashboard */}
        <Link href={`/project-dashboard/${projectId}`}>
          <Button variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Project
          </Button>
        </Link>
      </div>
    );
  }

  if (!codexItem) {
    // ... not found display ...
    return (
      <div className="container mx-auto px-6 py-12 text-center">
        <h2 className="text-2xl font-semibold mb-4">Codex Item Not Found</h2>
        <p className="text-muted-foreground mb-6">
          The requested codex item could not be found.
        </p>
        {/* Link back to project dashboard */}
        <Link href={`/project-dashboard/${projectId}`}>
          <Button variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Project
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-6 py-16">
      {/* Link back to project dashboard */}
      <Link
        href={`/project-dashboard/${projectId}`}
        className="mb-10 inline-block"
      >
        <Button variant="outline" size="sm">
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Project
        </Button>
      </Link>

      <Card className="max-w-3xl mx-auto">
        <CardHeader>
          <CardTitle className="text-3xl font-bold">{codexItem.name}</CardTitle>
          <CardDescription className="text-lg capitalize pt-2">
            Type: {codexItem.type}
            {/* Add subtype display if available */}
            {codexItem.subtype && ` - ${codexItem.subtype}`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="prose dark:prose-invert max-w-none">
            {/* Use description field */}
            <p>{codexItem.description || "No description available."}</p>
          </div>

          {/* Display Character Voice Profile if available */}
          {codexItem.type === CodexItemType.CHARACTER &&
            codexItem.voice_profile && (
              <div className="mt-6 pt-6 border-t border-border">
                <div className="flex items-center mb-3">
                  <Sparkles className="h-5 w-5 mr-2 text-purple-500" />
                  <h3 className="text-xl font-semibold text-purple-600">
                    Character Voice Profile
                  </h3>
                </div>
                <div className="space-y-3 text-sm">
                  {codexItem.voice_profile.vocabulary && (
                    <div>
                      <strong className="font-medium text-foreground">
                        Vocabulary:
                      </strong>
                      <p className="text-muted-foreground whitespace-pre-wrap break-words">
                        {codexItem.voice_profile.vocabulary}
                      </p>
                    </div>
                  )}
                  {codexItem.voice_profile.sentence_structure && (
                    <div>
                      <strong className="font-medium text-foreground">
                        Sentence Structure:
                      </strong>
                      <p className="text-muted-foreground whitespace-pre-wrap break-words">
                        {codexItem.voice_profile.sentence_structure}
                      </p>
                    </div>
                  )}
                  {codexItem.voice_profile.speech_patterns_tics && (
                    <div>
                      <strong className="font-medium text-foreground">
                        Speech Patterns/Tics:
                      </strong>
                      <p className="text-muted-foreground whitespace-pre-wrap break-words">
                        {codexItem.voice_profile.speech_patterns_tics}
                      </p>
                    </div>
                  )}
                  {codexItem.voice_profile.tone && (
                    <div>
                      <strong className="font-medium text-foreground">
                        Tone:
                      </strong>
                      <p className="text-muted-foreground whitespace-pre-wrap break-words">
                        {codexItem.voice_profile.tone}
                      </p>
                    </div>
                  )}
                  {codexItem.voice_profile.habits_mannerisms && (
                    <div>
                      <strong className="font-medium text-foreground">
                        Habits/Mannerisms:
                      </strong>
                      <p className="text-muted-foreground whitespace-pre-wrap break-words">
                        {codexItem.voice_profile.habits_mannerisms}
                      </p>
                    </div>
                  )}
                  {!codexItem.voice_profile.vocabulary &&
                    !codexItem.voice_profile.sentence_structure &&
                    !codexItem.voice_profile.speech_patterns_tics &&
                    !codexItem.voice_profile.tone &&
                    !codexItem.voice_profile.habits_mannerisms && (
                      <p className="text-muted-foreground italic">
                        No voice profile details defined.
                      </p>
                    )}
                </div>
              </div>
            )}
        </CardContent>
      </Card>

      <div className="w-full max-w-md mx-auto h-px bg-border/50 relative my-8">
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-background px-6">
          <Feather className="h-4 w-4 text-primary/40" />
        </div>
      </div>
      <footer className="text-center text-sm text-muted-foreground">
        &copy; {new Date().getFullYear()} ScrollWise. All rights reserved.
      </footer>
    </div>
  );
}

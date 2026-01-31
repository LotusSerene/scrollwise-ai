"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { fetchApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Terminal } from "lucide-react";
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth

interface Character {
  id: string;
  name: string;
  description: string;
  backstory: string | null;
  type: string;
  // Add other relevant fields if needed
}

interface GeneratedBackstoryResponse {
  generated_backstory: string;
}

export default function CharacterJourneyPage() {
  const auth = useAuth(); // Use the hook
  const params = useParams();
  const projectId = params?.projectId as string;
  const characterId = params?.characterId as string;

  const [character, setCharacter] = useState<Character | null>(null);
  const [editableBackstory, setEditableBackstory] = useState<string>("");
  const [isLoadingCharacter, setIsLoadingCharacter] = useState(true);
  const [isSavingBackstory, setIsSavingBackstory] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);

  const fetchCharacterDetails = useCallback(
    async (token: string | undefined) => {
      if (!projectId || !characterId) return;
      if (!token) {
        setError("Authentication token is missing.");
        setIsLoadingCharacter(false);
        return;
      }
      setIsLoadingCharacter(true);
      setError(null);
      // Token is passed as argument
      try {
        // Explicitly setting the path with /codex-items/
        const apiUrl = `/projects/${projectId}/codex-items/${characterId}`;
        console.log(`Fetching character details from: ${apiUrl}`); // Log the URL being fetched
        const data = await fetchApi<Character>(
          apiUrl,
          { method: "GET" },
          token
        );
        if (data.type !== "character") {
          throw new Error("This codex item is not a character.");
        }
        setCharacter(data);
        setEditableBackstory(data.backstory || "");
      } catch (err: unknown) {
        console.error("Failed to fetch character details:", err);
        const message =
          err instanceof Error ? err.message : "An unknown error occurred";
        setError(message || "Failed to load character details.");
        setCharacter(null);
      } finally {
        setIsLoadingCharacter(false);
      }
    },
    [projectId, characterId]
  ); // Keep dependencies

  useEffect(() => {
    // Fetch data only when authenticated and token is available
    if (!auth.isLoading && auth.isAuthenticated && auth.user?.id_token) {
      fetchCharacterDetails(auth.user.id_token);
    } else if (!auth.isLoading && !auth.isAuthenticated) {
      setError("Authentication required to view character journey.");
      setIsLoadingCharacter(false);
    }
    // Depend on auth state and fetchCharacterDetails function
  }, [
    auth.isLoading,
    auth.isAuthenticated,
    auth.user?.id_token,
    fetchCharacterDetails,
  ]);

  // Add check for projectId and characterId after hooks
  if (!projectId || !characterId) {
    return <div>Invalid Project or Character ID.</div>;
  }

  const handleBackstoryChange = (
    event: React.ChangeEvent<HTMLTextAreaElement>
  ) => {
    setEditableBackstory(event.target.value);
  };

  const handleSaveBackstory = async () => {
    if (!character) return;
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to save backstory.");
      return;
    }
    setIsSavingBackstory(true);
    setError(null);
    setSaveSuccess(null);
    const token = auth.user.id_token; // Get token from auth context
    try {
      await fetchApi(
        `/projects/${projectId}/codex-items/characters/${characterId}/backstory`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ backstory_content: editableBackstory }),
        },
        token
      );
      // Re-fetch character data to ensure consistency, though not strictly necessary
      // if the PUT returns the updated character. Assuming it doesn't here.
      setCharacter((prev) =>
        prev ? { ...prev, backstory: editableBackstory } : null
      );
      setSaveSuccess("Backstory saved successfully!");
      setTimeout(() => setSaveSuccess(null), 3000); // Clear success message after 3s
    } catch (err: unknown) {
      console.error("Failed to save backstory:", err);
      const message =
        err instanceof Error ? err.message : "An unknown error occurred";
      setError(message || "Failed to save backstory.");
    } finally {
      setIsSavingBackstory(false);
    }
  };

  const handleAnalyzeJourney = async () => {
    if (!character) return;
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to analyze journey.");
      return;
    }
    setIsAnalyzing(true);
    setError(null);
    const token = auth.user.id_token; // Get token from auth context
    try {
      const response = await fetchApi<GeneratedBackstoryResponse>(
        `/projects/${projectId}/codex-items/characters/${characterId}/analyze-journey`,
        { method: "POST" },
        token
      );
      setEditableBackstory(response.generated_backstory);
    } catch (err: unknown) {
      console.error("Failed to generate backstory:", err);
      let detail = "Failed to generate character backstory from manuscript.";
      if (err instanceof Error) {
        detail = err.message;
      }
      setError(detail);
    } finally {
      setIsAnalyzing(false);
    }
  };

  if (isLoadingCharacter) {
    return (
      // Apply theme styles to Skeleton container
      <div className="space-y-6">
        {/* Use theme background for Skeleton */}
        <Skeleton className="h-8 w-1/3 bg-muted" />
        <Skeleton className="h-6 w-2/3 bg-muted" />
        {/* Apply theme styles to Skeleton Card structure */}
        <Card className="bg-card border-border">
          <CardHeader>
            <Skeleton className="h-6 w-1/4 bg-muted" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-32 w-full bg-muted" />
            <Skeleton className="h-10 w-24 mt-4 bg-muted" />
          </CardContent>
        </Card>
        <Card className="bg-card border-border">
          <CardHeader>
            <Skeleton className="h-6 w-1/4 bg-muted" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-10 w-32 mb-4 bg-muted" />
            <Skeleton className="h-40 w-full bg-muted" />
          </CardContent>
        </Card>
      </div>
    );
  }

  // Error display moved up to handle loading errors more clearly
  if (error && !character) {
    // Show a prominent error if character loading failed completely
    return (
      // Apply theme styles to Alert
      <Alert
        variant="destructive"
        className="bg-destructive/10 border-destructive text-destructive-foreground"
      >
        <Terminal className="h-4 w-4" />
        <AlertTitle>Error Loading Character</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!character) {
    // This case might occur briefly or if loading fails without setting an error somehow
    // Apply theme style
    return (
      <p className="text-muted-foreground">
        Character not found or could not be loaded.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {/* Display general errors here if character loaded but subsequent actions failed */}
      {error && (
        // Apply theme styles to Alert
        <Alert
          variant="destructive"
          className="mt-4 bg-destructive/10 border-destructive text-destructive-foreground"
        >
          <Terminal className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {saveSuccess && (
        // Apply theme styles to success Alert (using default variant with custom colors for now)
        <Alert
          variant="default"
          className="mt-4 bg-primary/10 border-primary/50 text-primary-foreground" // Use primary theme colors for success indication
        >
          <Terminal className="h-4 w-4" />
          <AlertTitle>Success</AlertTitle>
          <AlertDescription>{saveSuccess}</AlertDescription>
        </Alert>
      )}

      {/* Apply theme styles to header */}
      <h1 className="text-3xl font-bold text-primary font-display">
        {character.name}
      </h1>
      <p className="text-muted-foreground italic">{character.description}</p>

      {/* Apply theme styles to Backstory Card */}
      <Card className="bg-card border border-border rounded-lg">
        <CardHeader>
          {/* Apply theme styles */}
          <CardTitle className="text-xl text-primary font-display">
            Backstory
          </CardTitle>
          <CardDescription className="text-muted-foreground">
            Edit the character&apos;s backstory below.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Textarea inherits theme styles */}
          <Textarea
            value={editableBackstory}
            onChange={handleBackstoryChange}
            placeholder="Enter character backstory here, or click 'Generate Backstory' below..."
            rows={15}
            className="min-h-[200px]" // Adjust height as needed
            disabled={isSavingBackstory}
          />
          {/* Apply theme styles to Button */}
          <Button
            onClick={handleSaveBackstory}
            disabled={isSavingBackstory}
            className="mt-4" // Default variant inherits theme styles
          >
            {isSavingBackstory ? "Saving..." : "Save Backstory"}
          </Button>
        </CardContent>
      </Card>

      {/* Apply theme styles to Generate Backstory Card */}
      <Card className="bg-card border border-border rounded-lg">
        <CardHeader>
          {/* Apply theme styles */}
          <CardTitle className="text-xl text-primary font-display">
            Generate Backstory from Manuscript
          </CardTitle>
          <CardDescription className="text-muted-foreground">
            Analyze the manuscript content to generate a potential backstory for
            this character.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Apply theme styles to Button */}
          <Button
            onClick={handleAnalyzeJourney}
            disabled={isAnalyzing}
            className="mb-4 disabled:opacity-50" // Default variant inherits theme styles
          >
            {isAnalyzing ? "Generating..." : "Generate Backstory"}
          </Button>
          {/* Apply theme styles to Skeleton */}
          {isAnalyzing && (
            <div className="space-y-2 mt-4">
              <Skeleton className="h-4 w-4/5 bg-muted" />
              <Skeleton className="h-4 w-full bg-muted" />
              <Skeleton className="h-4 w-3/4 bg-muted" />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

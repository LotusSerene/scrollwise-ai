"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { fetchApi } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Terminal, ChevronRight } from "lucide-react";
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth

interface CodexItemBase {
  id: string;
  name: string;
  description: string;
  type: string; // Keep as string, filter client-side
  // Add other common fields if needed
}

interface CharacterItem extends CodexItemBase {
  type: "character";
  backstory: string | null;
}

export default function CharacterJourneysListPage() {
  const auth = useAuth(); // Use the hook
  const params = useParams();
  const projectId = params?.projectId as string;

  const [characters, setCharacters] = useState<CharacterItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCharacters = useCallback(
    async (token: string | undefined) => {
      if (!projectId) return;
      if (!token) {
        setError("Authentication token is missing.");
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      setError(null);
      // Token is passed as argument
      try {
        // Fetch all codex items for the project
        // Expect a direct array of items, not an object wrapping the array.
        const allItems = await fetchApi<CodexItemBase[]>(
          `/projects/${projectId}/codex-items/`,
          { method: "GET" },
          token
        );
        // const allItems = response.codex_items; // This line is removed/replaced by the direct assignment above

        // Ensure allItems is actually an array before filtering (optional safety check)
        if (!Array.isArray(allItems)) {
          throw new Error("API response for codex items was not an array.");
        }

        // Filter for characters client-side
        const characterItems = allItems.filter(
          (item): item is CharacterItem => item.type === "character"
        );
        setCharacters(characterItems);
      } catch (err: unknown) {
        console.error("Failed to fetch characters:", err);
        const message =
          err instanceof Error ? err.message : "An unknown error occurred";
        setError(message || "Failed to load characters.");
      } finally {
        setIsLoading(false);
      }
    },
    [projectId]
  ); // Keep projectId dependency

  useEffect(() => {
    // Fetch data only when authenticated and token is available
    if (!auth.isLoading && auth.isAuthenticated && auth.user?.id_token) {
      fetchCharacters(auth.user.id_token);
    } else if (!auth.isLoading && !auth.isAuthenticated) {
      setError("Authentication required to view journeys.");
      setIsLoading(false);
    }
    // Depend on auth state and fetchCharacters function
  }, [
    auth.isLoading,
    auth.isAuthenticated,
    auth.user?.id_token,
    fetchCharacters,
  ]);

  // Add check for projectId after all hooks
  if (!projectId) {
    return <div>Invalid Project ID.</div>;
  }

  if (isLoading) {
    return (
      // Apply theme styles to Skeleton container
      <div className="space-y-4">
        <div className="flex justify-between items-center mb-4">
          {/* Use theme background for Skeleton */}
          <Skeleton className="h-8 w-1/4 bg-muted" />
        </div>
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-20 w-full bg-muted" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      // Apply theme styles to Alert
      <Alert
        variant="destructive"
        className="bg-destructive/10 border-destructive text-destructive-foreground"
      >
        <Terminal className="h-4 w-4" />
        <AlertTitle>Error Loading Characters</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center mb-4">
        {/* Apply theme styles to header */}
        <h1 className="text-2xl font-bold text-primary font-display">
          Character Journeys
        </h1>
      </div>

      {characters.length === 0 ? (
        // Apply theme style for empty state
        <p className="text-muted-foreground italic">
          No characters found in this project&apos;s codex yet.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {characters.map((char) => (
            <Link
              key={char.id}
              href={`/project-dashboard/${projectId}/journey/${char.id}`}
              passHref
              legacyBehavior // Keep legacyBehavior for <a> tag styling
            >
              {/* Apply theme styles to the link acting as a card */}
              <a className="block bg-card border border-border rounded-lg p-4 shadow-sm hover:bg-accent hover:border-primary/50 transition-colors group">
                <div className="flex justify-between items-center">
                  <div>
                    {/* Apply theme styles to character name and description */}
                    <h2 className="text-lg font-semibold text-foreground group-hover:text-primary">
                      {char.name}
                    </h2>
                    <p className="text-sm text-muted-foreground line-clamp-2 mt-1">
                      {char.description || "No description."}
                    </p>
                    <p className="text-xs text-muted-foreground/80 mt-2">
                      {char.backstory
                        ? "Backstory available"
                        : "No backstory yet"}
                    </p>
                  </div>
                  {/* Style the chevron */}
                  <ChevronRight className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
                </div>
              </a>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { fetchApi } from "@/lib/api";
import {
  Loader2,
  Users,
  AlertTriangle,
  Plus,
  Edit,
  Trash2,
  Brain,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { CodexEntry, Relationship } from "@/types";
import { AnalyzeRelationshipsModal } from "@/components/AnalyzeRelationshipsModal";
import { RelationshipFormModal } from "@/components/RelationshipFormModal";
import { RelationshipGraph } from "@/components/RelationshipGraph";
import { useAuth } from "@/components/MockAuthProvider";

// Update Relationship type to expect names from backend
interface RelationshipWithNames extends Relationship {
  character1_name?: string;
  character2_name?: string;
}

interface RelationshipsApiResponse {
  relationships: RelationshipWithNames[];
}

interface CharactersApiResponse {
  characters: CodexEntry[]; // Use CodexEntry directly
}

export default function CharacterRelationshipsPage() {
  const params = useParams();
  const projectId = params?.projectId as string;
  const [relationships, setRelationships] = useState<RelationshipWithNames[]>(
    []
  );
  const [characters, setCharacters] = useState<CodexEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAnalyzeModalOpen, setIsAnalyzeModalOpen] = useState(false);
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [relationshipToEdit, setRelationshipToEdit] =
    useState<RelationshipWithNames | null>(null);
  const auth = useAuth();

  const fetchData = useCallback(
    async (token: string | undefined) => {
      if (!projectId || !token) {
        if (!token) setError("Authentication required.");
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      setError(null);
      // Token is passed as argument
      try {
        // Fetch characters (still needed for modals and potentially graph if it needs full character objects)
        const charResponse = await fetchApi<CharactersApiResponse>(
          `/projects/${projectId}/codex/characters`,
          {},
          token
        );
        const chars = charResponse.characters || [];
        setCharacters(chars);

        // Fetch relationships (now expects names included)
        const relResponse = await fetchApi<RelationshipsApiResponse>(
          `/projects/${projectId}/relationships`,
          {},
          token
        );
        // Ensure fallback names if backend doesn't provide them for some reason
        const relationshipsWithFallbackNames = (
          relResponse.relationships || []
        ).map((rel) => ({
          ...rel,
          character1_name:
            rel.character1_name ||
            `Unknown (${rel.character_id?.substring(0, 6)}...)`,
          character2_name:
            rel.character2_name ||
            `Unknown (${rel.related_character_id?.substring(0, 6)}...)`,
        }));
        setRelationships(relationshipsWithFallbackNames);
      } catch (err: unknown) {
        console.error("Failed to fetch relationships or characters:", err);
        const message =
          err instanceof Error ? err.message : "An unknown error occurred";
        setError(`Failed to load data: ${message}`);
        setRelationships([]);
        setCharacters([]);
      } finally {
        setIsLoading(false);
      }
    },
    [projectId]
  ); // Keep projectId dependency

  useEffect(() => {
    fetchData(auth.user?.id_token); // Pass token here
  }, [fetchData, auth.user?.id_token, projectId]); // Added projectId

  const handleAnalysisComplete = () => {
    // Pass token when calling fetchData
    fetchData(auth.user?.id_token);
  };

  const handleSaveComplete = () => {
    // Refresh data only if authenticated
    if (auth.isAuthenticated && auth.user?.id_token) {
      fetchData(auth.user.id_token);
    }
  };

  const openAddModal = () => {
    setRelationshipToEdit(null); // Ensure we are in add mode
    setIsFormModalOpen(true);
  };

  const openEditModal = (relationship: RelationshipWithNames) => {
    setRelationshipToEdit(relationship);
    setIsFormModalOpen(true);
  };

  const handleDelete = async (relationshipId: string) => {
    if (!confirm("Are you sure you want to delete this relationship?")) {
      return;
    }
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to delete relationship.");
      return;
    }
    const token = auth.user.id_token; // Get token
    setError(null);
    try {
      await fetchApi(
        `/projects/${projectId}/relationships/${relationshipId}`,
        { method: "DELETE" },
        token
      );
      if (auth.isAuthenticated && auth.user?.id_token) {
        fetchData(auth.user.id_token); // Refresh list after delete
      }
    } catch (err) {
      console.error("Failed to delete relationship:", err);
      const message =
        err instanceof Error ? err.message : "An unknown error occurred";
      setError(`Failed to delete relationship: ${message}`);
    }
  };

  // Add check for projectId after hooks
  if (!projectId) {
    return <div>Invalid Project ID.</div>;
  }

  return (
    // Adjust container padding if needed, remove explicit container class if layout provides it
    <section className="py-8">
      {/* Apply theme styles to Card */}
      <Card className="bg-card border-border rounded-lg">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            {/* Apply theme styles to CardTitle and CardDescription */}
            <CardTitle className="flex items-center gap-2 text-foreground font-display">
              {/* Use primary color for icon */}
              <Users className="h-6 w-6 text-primary" />
              Character Relationships
            </CardTitle>
            <CardDescription className="text-muted-foreground">
              View, manage, and analyze the connections between your characters.
            </CardDescription>
          </div>
          <div className="flex gap-2">
            {/* Apply theme styles to Buttons */}
            <Button
              variant="outline"
              onClick={() => setIsAnalyzeModalOpen(true)}
              disabled={isLoading || characters.length < 2}
              className="border-primary/50 text-primary hover:bg-primary/10 hover:text-primary/90" // Example outline styling
            >
              <Brain className="h-4 w-4 mr-2" />
              Analyze
            </Button>
            <Button
              onClick={openAddModal}
              disabled={isLoading || characters.length < 2}
              // Default button variant inherits theme styles
            >
              <Plus className="h-4 w-4 mr-2" />
              Add
            </Button>
            <Button
              variant="secondary"
              onClick={() => fetchData(auth.user?.id_token)} // Pass token on refresh
              disabled={isLoading || characters.length < 2}
            >
              {isLoading ? "Refreshing..." : "Refresh Data"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading && (
            // Apply theme styles to loading state
            <div className="flex justify-center items-center py-10 text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="ml-2">Loading relationships...</p>
            </div>
          )}
          {error && (
            // Apply theme styles to error message
            <div className="my-4 p-3 bg-destructive/10 border border-destructive text-destructive-foreground text-sm rounded-md flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {!isLoading && !error && relationships.length === 0 && (
            // Apply theme styles to empty state
            <div className="text-center py-10 text-muted-foreground">
              <p>No relationships found for this project.</p>
              <div className="mt-4 flex justify-center gap-4">
                <Button
                  onClick={openAddModal}
                  disabled={characters.length < 2}
                  // Default button variant inherits theme styles
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add Relationship Manually
                </Button>
                <Button
                  variant="link" // Link variant inherits theme styles
                  onClick={() => setIsAnalyzeModalOpen(true)}
                  disabled={characters.length < 2}
                >
                  or Analyze Existing Content?
                </Button>
              </div>
            </div>
          )}
          {!isLoading && !error && relationships.length > 0 && (
            <ul className="space-y-3">
              {relationships.map((rel) => (
                // Apply theme styles to list items
                <li
                  key={rel.id}
                  className="p-4 bg-accent/50 border border-border rounded-md flex justify-between items-center"
                >
                  <div>
                    {/* Apply theme text colors */}
                    <span className="font-semibold text-primary">
                      {rel.character1_name || "Unknown"}
                    </span>
                    <span className="text-muted-foreground mx-2"></span>
                    <span className="font-semibold text-primary">
                      {rel.character2_name || "Unknown"}
                    </span>
                    <p className="text-sm text-muted-foreground mt-1">
                      <span className="font-medium text-foreground">Type:</span>{" "}
                      {rel.relationship_type}
                      {rel.description && (
                        <span className="ml-4">
                          <span className="font-medium text-foreground">
                            Desc:
                          </span>{" "}
                          {rel.description}
                        </span>
                      )}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {/* Apply theme styles to action buttons */}
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => openEditModal(rel)}
                      className="border-border hover:bg-accent hover:text-accent-foreground"
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="destructive"
                      size="icon"
                      onClick={() => handleDelete(rel.id)}
                      // Destructive variant inherits theme styles
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {/* Graph Visualization Area */}
          {!isLoading && !error && relationships.length > 0 && (
            // Apply theme styles to graph section
            <div className="mt-8 pt-6 border-t border-border">
              <h3 className="text-lg font-semibold mb-4 text-foreground font-display">
                Relationship Map
              </h3>
              {/* Assuming RelationshipGraph component handles its own internal styling or inherits */}
              <RelationshipGraph
                characters={characters}
                relationships={relationships}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Assuming Modals use themed components internally */}
      <AnalyzeRelationshipsModal
        isOpen={isAnalyzeModalOpen}
        onOpenChange={setIsAnalyzeModalOpen}
        projectId={projectId}
        characters={characters}
        onAnalysisComplete={handleAnalysisComplete}
      />

      <RelationshipFormModal
        isOpen={isFormModalOpen}
        onOpenChange={setIsFormModalOpen}
        projectId={projectId}
        characters={characters}
        relationshipToEdit={relationshipToEdit}
        onSaveComplete={handleSaveComplete}
      />
    </section>
  );
}

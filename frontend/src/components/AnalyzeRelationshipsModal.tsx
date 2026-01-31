"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2, AlertTriangle, ScanSearch } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { CodexEntry, Relationship } from "@/types";
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth

// Response type from the analyze endpoint
interface AnalyzeResponse {
  message?: string;
  relationships?: Relationship[]; // Use the shared Relationship type
  alreadyAnalyzed?: boolean;
  error?: string;
}

interface AnalyzeRelationshipsModalProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  projectId: string;
  characters: CodexEntry[];
  onAnalysisComplete: () => void; // Callback after successful analysis
}

export function AnalyzeRelationshipsModal({
  isOpen,
  onOpenChange,
  projectId,
  characters,
  onAnalysisComplete,
}: AnalyzeRelationshipsModalProps) {
  const [selectedCharacterIds, setSelectedCharacterIds] = useState<Set<string>>(
    new Set()
  );
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisMessage, setAnalysisMessage] = useState<string | null>(null);
  const auth = useAuth(); // Use the hook

  // Reset state when dialog opens/closes
  useEffect(() => {
    if (!isOpen) {
      setSelectedCharacterIds(new Set());
      setError(null);
      setAnalysisMessage(null);
      // Don't reset isAnalyzing here, let the API call finish
    }
  }, [isOpen]);

  const handleCheckboxChange = (characterId: string, checked: boolean) => {
    setSelectedCharacterIds((prev) => {
      const newSet = new Set(prev);
      if (checked) {
        newSet.add(characterId);
      } else {
        newSet.delete(characterId);
      }
      return newSet;
    });
  };

  const handleAnalyze = async () => {
    if (selectedCharacterIds.size < 2) {
      setError("Please select at least two characters to analyze.");
      return;
    }
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to run analysis.");
      return;
    }

    setIsAnalyzing(true);
    setError(null);
    setAnalysisMessage(null);
    const token = auth.user.id_token; // Get token from auth context
    const characterIdsArray = Array.from(selectedCharacterIds);

    try {
      const response = await fetchApi<AnalyzeResponse>(
        `/projects/${projectId}/relationships/analyze`,
        {
          method: "POST",
          body: JSON.stringify(characterIdsArray), // Send array of IDs
        },
        token
      );

      console.log("Analysis Response:", response);

      if (response.error) {
        throw new Error(response.error);
      }

      if (response.alreadyAnalyzed) {
        setAnalysisMessage(
          response.message ||
            "Analysis already performed or no new relationships found based on selected characters."
        );
      } else {
        setAnalysisMessage(
          response.message ||
            "Analysis complete. New relationships may have been added."
        );
        onAnalysisComplete(); // Trigger data refresh on the parent page
      }
      // Optionally close the dialog after a short delay or keep it open to show message
      // setTimeout(() => onOpenChange(false), 2000);
      onOpenChange(false); // Close immediately for now
    } catch (err: unknown) {
      console.error("Failed to analyze relationships:", err);
      const message =
        err instanceof Error ? err.message : "An unknown error occurred";
      setError(`Analysis failed: ${message}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      {/* Apply theme styles to DialogContent */}
      <DialogContent className="sm:max-w-[500px] bg-card border-border text-card-foreground rounded-lg">
        <DialogHeader>
          {/* Apply theme styles to DialogTitle and DialogDescription */}
          <DialogTitle className="flex items-center gap-2 text-foreground font-display">
            {/* Use primary color for icon */}
            <ScanSearch className="h-5 w-5 text-primary" />
            Analyze Character Relationships
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Select the characters whose relationships you want the AI to analyze
            based on the story content. Select at least two characters.
          </DialogDescription>
        </DialogHeader>

        {/* Apply theme styles to error message */}
        {error && (
          <div className="my-2 p-3 bg-destructive/10 border border-destructive text-destructive-foreground text-sm rounded-md flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
        {/* Apply theme styles to analysis message (using primary/info style) */}
        {analysisMessage && (
          <div className="my-2 p-3 bg-primary/10 border border-primary/50 text-primary-foreground text-sm rounded-md flex items-center gap-2">
            <span>{analysisMessage}</span>
          </div>
        )}

        {/* Apply theme styles to ScrollArea borders */}
        <ScrollArea className="max-h-[40vh] my-4 pr-4 border-t border-b border-border py-4">
          <div className="space-y-3">
            {characters.length === 0 && (
              // Apply theme style for empty state
              <p className="text-center text-muted-foreground">
                No characters found in this project.
              </p>
            )}
            {characters.map((char) => (
              <div key={char.id} className="flex items-center space-x-2">
                {/* Checkbox inherits theme styles */}
                <Checkbox
                  id={`char-${char.id}`}
                  checked={selectedCharacterIds.has(char.id)}
                  onCheckedChange={(checked) =>
                    handleCheckboxChange(char.id, !!checked)
                  }
                  disabled={isAnalyzing}
                />
                {/* Apply theme style to Label */}
                <Label
                  htmlFor={`char-${char.id}`}
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-foreground"
                >
                  {char.name}
                </Label>
              </div>
            ))}
          </div>
        </ScrollArea>

        <DialogFooter>
          {/* Buttons inherit theme styles */}
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isAnalyzing}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleAnalyze}
            disabled={isAnalyzing || selectedCharacterIds.size < 2}
            // Default variant inherits theme styles
          >
            {isAnalyzing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isAnalyzing ? "Analyzing..." : "Run Analysis"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

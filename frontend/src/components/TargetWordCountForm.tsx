"use client";

import React, { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { fetchApi } from "@/lib/api";
import { Loader2, CheckCircle, AlertTriangle, Target } from "lucide-react";
import { useRouter } from "next/navigation"; // Import useRouter for refresh
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth

interface TargetWordCountFormProps {
  projectId: string;
  initialTarget: number;
}

export function TargetWordCountForm({
  projectId,
  initialTarget,
}: TargetWordCountFormProps) {
  const [target, setTarget] = useState<number | string>(
    initialTarget > 0 ? initialTarget : ""
  );

  // Sync state with prop changes
  React.useEffect(() => {
    setTarget(initialTarget > 0 ? initialTarget : "");
  }, [initialTarget]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const router = useRouter(); // Initialize router
  const auth = useAuth(); // Use the hook

  const handleSave = async () => {
    const numericTarget = Number(target);
    if (isNaN(numericTarget) || numericTarget < 0) {
      setError(
        "Please enter a valid non-negative number for the target word count."
      );
      setSuccess(false);
      return;
    }
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to save target word count.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setSuccess(false);
    const token = auth.user.id_token; // Get token

    try {
      // Use the specific target-word-count endpoint
      await fetchApi(
        `/projects/${projectId}/target-word-count`,
        {
          method: "PUT",
          body: JSON.stringify({ targetWordCount: numericTarget }), // Match backend model field name
        },
        token
      );
      setSuccess(true);
      setTarget(numericTarget); // Immediate UI update
      // Refresh server components to reflect the change
      router.refresh();

      // Use window.location.reload() as fallback after a delay
      setTimeout(() => {
        window.location.reload();
      }, 1000);

      // Optionally hide success message after a delay
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : "An unknown error occurred";
      console.error("Failed to update target word count:", err);
      setError(`Failed to save: ${errorMessage}`);
      setSuccess(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null); // Clear error on input change
    setSuccess(false); // Clear success on input change
    setTarget(e.target.value); // Allow string input temporarily
  };

  return (
    // Use theme border color
    <div className="space-y-3 mt-6 border-t border-border pt-6">
      <Label
        htmlFor="target-word-count"
        // Use theme muted foreground color
        className="flex items-center text-muted-foreground mb-2"
      >
        <Target className="h-4 w-4 mr-2" /> Target Word Count
      </Label>
      <div className="flex items-center gap-2">
        <Input
          id="target-word-count"
          type="number"
          min="0"
          placeholder="Enter target words"
          value={target}
          onChange={handleInputChange}
          // Remove explicit bg/border, rely on Shadcn theme
          className=""
          disabled={isLoading}
        />
        <Button
          onClick={handleSave}
          disabled={isLoading || String(target) === String(initialTarget)}
          className="min-w-[80px]" // Keep min-width for layout consistency
          // Button styles are inherited from Shadcn theme
        >
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save"}
        </Button>
      </div>
      {error && (
        // Use theme destructive color
        <p className="text-xs text-destructive flex items-center gap-1">
          <AlertTriangle className="h-3 w-3" /> {error}
        </p>
      )}
      {success && (
        // Use a success color (e.g., primary or a dedicated success variable if defined)
        <p className="text-xs text-green-500 flex items-center gap-1">
          {" "}
          {/* Keeping green for now, could use theme variable */}
          <CheckCircle className="h-3 w-3" /> Target saved!
        </p>
      )}
    </div>
  );
}

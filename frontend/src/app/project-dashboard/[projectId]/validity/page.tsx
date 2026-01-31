"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Loader2, Trash2, AlertTriangle, Info } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth

// Interface matching the backend response for a single validity check
// Updated to camelCase to match ValidityCheck.to_dict() in backend/database.py
interface ValidityCheck {
  id: string;
  chapterId: string;
  chapterTitle: string;
  isValid: boolean;
  overallScore: number;
  generalFeedback: string;
  styleGuideAdherenceScore: number;
  styleGuideAdherenceExplanation: string;
  continuityScore: number;
  continuityExplanation: string;
  areasForImprovement: string[]; // Should be an array after parsing
  createdAt: string;
}

export default function ValidityChecksPage() {
  const params = useParams();
  const projectId = params?.projectId as string;
  const auth = useAuth(); // Use the hook

  const [validityChecks, setValidityChecks] = useState<ValidityCheck[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isDeletingId, setIsDeletingId] = useState<string | null>(null);
  const [selectedCheck, setSelectedCheck] = useState<ValidityCheck | null>(
    null
  );

  const fetchValidityChecks = useCallback(
    async (token: string | undefined) => {
      if (!token) {
        setError("Authentication token is missing.");
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      setError(null);
      // Token is passed as argument
      try {
        // Expect a direct array of ValidityCheck objects
        const response = await fetchApi<ValidityCheck[]>(
          `/projects/${projectId}/validity`,
          {},
          token
        );

        // Check if the response is an array before sorting
        if (Array.isArray(response)) {
          // Sort and parse areasForImprovement
          const processedChecks = response
            .sort((a, b) =>
              b.createdAt && a.createdAt
                ? new Date(b.createdAt).getTime() -
                  new Date(a.createdAt).getTime()
                : 0
            )
            .map((check) => {
              let parsedAreas: string[] = [];
              if (
                check.areasForImprovement &&
                typeof check.areasForImprovement === "string"
              ) {
                try {
                  parsedAreas = JSON.parse(check.areasForImprovement);
                  // Ensure it's actually an array after parsing
                  if (!Array.isArray(parsedAreas)) {
                    console.warn(
                      `Parsed 'areasForImprovement' for check ${check.id} is not an array:`,
                      parsedAreas
                    );
                    parsedAreas = []; // Default to empty array if parsing resulted in non-array
                  }
                } catch (parseError) {
                  console.error(
                    `Failed to parse areasForImprovement for check ${check.id}:`,
                    parseError,
                    "Raw value:",
                    check.areasForImprovement
                  );
                  // Keep areasForImprovement as empty array on parse error
                }
              } else if (Array.isArray(check.areasForImprovement)) {
                // If it's somehow already an array, use it directly
                parsedAreas = check.areasForImprovement;
              }
              // Return a new object with the potentially parsed array
              return { ...check, areasForImprovement: parsedAreas };
            });

          setValidityChecks(processedChecks);
        } else {
          // Handle cases where response is not an array (e.g., API error structured differently)
          console.error("API response was not an array:", response);
          setError("Received an unexpected response format from the server.");
          setValidityChecks([]); // Clear previous checks or set to empty
        }
      } catch (err) {
        console.error("Failed to load validity checks:", err);
        setError(
          err instanceof Error ? err.message : "An unknown error occurred"
        );
      } finally {
        setIsLoading(false);
      }
    },
    [projectId]
  ); // Keep projectId dependency

  // Depends on auth state and fetch function
  useEffect(() => {
    // Fetch only when authenticated
    if (!auth.isLoading && auth.isAuthenticated && auth.user?.id_token) {
      fetchValidityChecks(auth.user.id_token);
    } else if (!auth.isLoading && !auth.isAuthenticated) {
      setError("Authentication required to view validity checks.");
      setIsLoading(false);
    }
  }, [
    auth.isLoading,
    auth.isAuthenticated,
    auth.user?.id_token,
    fetchValidityChecks,
  ]);

  // Add check for projectId after hooks
  if (!projectId) {
    return <div>Invalid Project ID.</div>;
  }

  const handleDeleteCheck = async (
    checkId: string,
    event: React.MouseEvent
  ) => {
    event.stopPropagation();
    if (
      !window.confirm("Are you sure you want to delete this validity check?")
    ) {
      return;
    }
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to delete check.");
      return;
    }
    setIsDeletingId(checkId);
    setError(null);
    const token = auth.user.id_token; // Get token
    try {
      await fetchApi(
        `/projects/${projectId}/validity/${checkId}`,
        {
          method: "DELETE",
        },
        token
      );
      // Refresh list after successful deletion
      setValidityChecks((prev) => prev.filter((check) => check.id !== checkId));
      // Close modal if the deleted item was selected
      if (selectedCheck?.id === checkId) {
        setSelectedCheck(null);
      }
    } catch (err) {
      console.error(`Failed to delete validity check ${checkId}:`, err);
      setError(
        err instanceof Error
          ? `Failed to delete: ${err.message}`
          : "Failed to delete check."
      );
    } finally {
      setIsDeletingId(null);
    }
  };

  // Commenting out the duplicated handleRunChecks
  // const handleRunChecks = async () => {
  //   if (!auth.isAuthenticated || !auth.user?.id_token) {
  //     // ... existing code ...
  //   }
  // };

  return (
    // Adjust max-width and padding as needed
    <div className="max-w-6xl mx-auto space-y-6 p-4 md:p-0">
      {/* Apply theme styles */}
      <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-primary font-display">
        Chapter Validity Checks
      </h1>

      {/* Apply theme styles */}
      {error && (
        <Alert
          variant="destructive"
          className="bg-destructive/10 border-destructive text-destructive-foreground"
        >
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        // Apply theme styles
        <div className="flex justify-center items-center h-64 text-muted-foreground">
          <Loader2 className="h-12 w-12 animate-spin text-primary" />
        </div>
      ) : validityChecks.length === 0 ? (
        // Apply theme styles
        <Alert className="bg-card border-border text-muted-foreground">
          <Info className="h-4 w-4" />
          <AlertTitle>No Checks Found</AlertTitle>
          <AlertDescription>
            No validity checks have been recorded for this project yet. Generate
            chapters with validation enabled.
          </AlertDescription>
        </Alert>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {validityChecks.map((check) => (
            // Apply theme styles to Card
            <Card
              key={check.id}
              className="bg-card border border-border text-card-foreground flex flex-col cursor-pointer hover:border-primary/50 transition-colors duration-200 rounded-lg"
              onClick={() => setSelectedCheck(check)}
            >
              <CardHeader>
                <CardTitle className="flex justify-between items-start">
                  {/* Apply theme styles */}
                  <span className="text-foreground mr-4 font-display">
                    {check.chapterTitle}
                  </span>
                  {/* Badge inherits theme variants */}
                  <Badge
                    variant={check.isValid ? "default" : "destructive"}
                    className={`whitespace-nowrap ${
                      check.isValid
                        ? "bg-green-600/80 border-green-500 text-green-foreground hover:bg-green-600" // Example success styling (adjust if needed)
                        : "" // Destructive variant handles invalid style
                    }`}
                  >
                    {check.isValid ? "Valid" : "Invalid"}
                  </Badge>
                </CardTitle>
                {/* Apply theme styles */}
                <CardDescription className="text-xs text-muted-foreground">
                  Checked on:{" "}
                  {check.createdAt
                    ? new Date(check.createdAt).toLocaleString()
                    : "Unknown date"}
                </CardDescription>
              </CardHeader>
              {/* Apply theme styles */}
              <CardContent className="space-y-3 flex-grow text-sm text-muted-foreground">
                <p>
                  <strong className="text-foreground">Overall Score:</strong>{" "}
                  {check.overallScore}/10
                </p>
                <p className="line-clamp-2">
                  <strong className="text-foreground">Continuity:</strong>{" "}
                  {check.continuityScore}/10 - {check.continuityExplanation}
                </p>
                <p className="line-clamp-2">
                  <strong className="text-foreground">Style Adherence:</strong>{" "}
                  {check.styleGuideAdherenceScore}/10 -{" "}
                  {check.styleGuideAdherenceExplanation}
                </p>
                <p className="line-clamp-3">
                  <strong className="text-foreground">General Feedback:</strong>{" "}
                  {check.generalFeedback}
                </p>
              </CardContent>
              {/* Apply theme styles */}
              <CardFooter className="border-t border-border/50 pt-4 flex justify-end">
                {/* Button inherits theme styles */}
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={(e) => handleDeleteCheck(check.id, e)}
                  disabled={isDeletingId === check.id}
                >
                  {isDeletingId === check.id ? (
                    <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4 mr-1.5" />
                  )}
                  {isDeletingId === check.id ? "Deleting..." : "Delete"}
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      {/* Apply theme styles to Dialog */}
      <Dialog
        open={!!selectedCheck}
        onOpenChange={(isOpen) => !isOpen && setSelectedCheck(null)}
      >
        <DialogContent className="sm:max-w-xl md:max-w-2xl lg:max-w-3xl bg-card border-border text-card-foreground rounded-lg max-h-[90vh] overflow-y-auto">
          {selectedCheck && (
            <>
              <DialogHeader>
                {/* Apply theme styles */}
                <DialogTitle className="text-primary text-xl font-display">
                  Validity Check Details: {selectedCheck.chapterTitle}
                </DialogTitle>
                <DialogDescription className="text-muted-foreground text-sm">
                  Checked on:{" "}
                  {new Date(selectedCheck.createdAt).toLocaleString()}
                </DialogDescription>
              </DialogHeader>

              <div className="grid gap-4 py-4 text-sm">
                <div className="grid grid-cols-[150px_1fr] items-center gap-4">
                  {/* Apply theme styles */}
                  <span className="text-muted-foreground">Status:</span>
                  <Badge
                    variant={selectedCheck.isValid ? "default" : "destructive"}
                    className={`w-fit ${
                      selectedCheck.isValid
                        ? "bg-green-600/80 border-green-500 text-green-foreground hover:bg-green-600" // Example success styling
                        : ""
                    }`}
                  >
                    {selectedCheck.isValid ? "Valid" : "Invalid"}
                  </Badge>
                </div>
                <div className="grid grid-cols-[150px_1fr] items-center gap-4">
                  <span className="text-muted-foreground">Overall Score:</span>
                  <span className="font-medium text-foreground">
                    {selectedCheck.overallScore}/10
                  </span>
                </div>

                {/* Apply theme styles */}
                <div className="border-t border-border pt-4 mt-2">
                  <h4 className="font-semibold mb-2 text-foreground">
                    Continuity
                  </h4>
                  <div className="grid grid-cols-[150px_1fr] items-start gap-4 mb-2">
                    <span className="text-muted-foreground">Score:</span>
                    <span className="font-medium text-foreground">
                      {selectedCheck.continuityScore}/10
                    </span>
                  </div>
                  <div className="grid grid-cols-[150px_1fr] items-start gap-4">
                    <span className="text-muted-foreground">Explanation:</span>
                    <p className="text-card-foreground">
                      {selectedCheck.continuityExplanation}
                    </p>
                  </div>
                </div>

                <div className="border-t border-border pt-4 mt-2">
                  <h4 className="font-semibold mb-2 text-foreground">
                    Style Adherence
                  </h4>
                  <div className="grid grid-cols-[150px_1fr] items-start gap-4 mb-2">
                    <span className="text-muted-foreground">Score:</span>
                    <span className="font-medium text-foreground">
                      {selectedCheck.styleGuideAdherenceScore}/10
                    </span>
                  </div>
                  <div className="grid grid-cols-[150px_1fr] items-start gap-4">
                    <span className="text-muted-foreground">Explanation:</span>
                    <p className="text-card-foreground">
                      {selectedCheck.styleGuideAdherenceExplanation}
                    </p>
                  </div>
                </div>

                <div className="border-t border-border pt-4 mt-2">
                  <h4 className="font-semibold mb-2 text-foreground">
                    General Feedback
                  </h4>
                  <p className="text-card-foreground">
                    {selectedCheck.generalFeedback}
                  </p>
                </div>

                {selectedCheck.areasForImprovement &&
                  selectedCheck.areasForImprovement.length > 0 && (
                    <div className="border-t border-border pt-4 mt-2">
                      <h4 className="font-semibold mb-2 text-foreground">
                        Areas for Improvement
                      </h4>
                      <ul className="list-disc list-inside pl-4 text-card-foreground space-y-1">
                        {selectedCheck.areasForImprovement.map((area, idx) => (
                          <li key={idx}>{area}</li>
                        ))}
                      </ul>
                    </div>
                  )}
              </div>

              {/* Apply theme styles */}
              <DialogFooter className="sm:justify-end border-t border-border pt-4">
                <DialogClose asChild>
                  {/* Button inherits theme styles */}
                  <Button type="button" variant="secondary">
                    Close
                  </Button>
                </DialogClose>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

// Add badge variants if needed in global css or here if specific
// Example:
// .badge-success { background-color: green; color: white; }
// .badge-destructive { background-color: red; color: white; }

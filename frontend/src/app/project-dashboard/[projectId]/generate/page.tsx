"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import PresetManager, {
  Preset,
} from "@/components/preset-manager/PresetManager";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import HistoryTab from "@/components/generate/HistoryTab";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/components/MockAuthProvider";
import { toast } from "sonner";

// Define the structure for generation instructions (matches backend expectations if possible)
// Using a simplified version for now
interface GenerationInstructions {
  styleGuide: string;
  additionalInstructions?: string;
  // Add other instruction fields as needed based on backend/AgentManager
}

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
    [key: string]: string | number | undefined;
  };
}

// --- Types ---
type GenerationStatus = "idle" | "checking" | "running" | "error";

export default function GenerateChapterPage() {
  const params = useParams();
  const projectId = params?.projectId as string;
  const auth = useAuth(); // Use the hook

  // --- State ---
  const [numChapters, setNumChapters] = useState<number>(1);
  const [plot, setPlot] = useState<string>("");
  const [writingStyle, setWritingStyle] = useState<string>("");
  const [instructions, setInstructions] = useState<GenerationInstructions>({
    styleGuide: "",
  });
  const [wordCountInput, setWordCountInput] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false); // Loading state for the generate button click
  const [generationStatus, setGenerationStatus] =
    useState<GenerationStatus>("idle"); // State reflecting the backend status
  const [errorMessage, setErrorMessage] = useState<string | null>(null); // Separate error message state
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [historyToLoad, setHistoryToLoad] =
    useState<GenerationHistoryEntry | null>(null);

  // --- Refs ---
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null); // Ref to hold the interval ID
  const isCheckingRef = useRef<boolean>(false); // Add this ref to track API call status without affecting renders

  // --- Polling Logic ---

  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
      console.log("Polling stopped.");
    }
  }, []); // No dependencies needed

  const checkStatus = useCallback(async () => {
    if (!projectId || !auth.isAuthenticated || !auth.user?.id_token) {
      setGenerationStatus("idle"); // Can't check if not authenticated
      stopPolling();
      return;
    }

    const token = auth.user?.id_token;
    const apiUrl = `${process.env.NEXT_PUBLIC_BACKEND_URL}/projects/${projectId}/generation-status`;

    // Use isCheckingRef instead of generationStatus to avoid getting stuck
    if (isCheckingRef.current) {
      console.log("Status check already in progress, skipping.");
      return;
    }

    console.log("Checking backend generation status for project:", projectId);
    // Use the ref to track the API call instead of state
    isCheckingRef.current = true;

    try {
      const response = await fetch(apiUrl, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(
          `Failed to fetch generation status: ${response.status} - ${errorText}. Stopping poll.`
        );
        setGenerationStatus("error");
        setErrorMessage(`Failed to fetch status: ${response.status}`);
        stopPolling();
        return; // Exit checkStatus
      }

      const data = await response.json();
      console.log("Received status data:", data); // Add this log to see the exact response
      const newStatus = data.status === "running" ? "running" : "idle"; // Determine new status

      // --- Add Notification Logic ---
      if (generationStatus === "running" && newStatus === "idle") {
        toast.success("Chapter generation finished!");
      }
      // --- End Notification Logic ---

      if (newStatus === "running") {
        console.log("Backend reports generation is running.");
        setGenerationStatus("running");
        setErrorMessage(null); // Clear previous errors

        // Start polling only if not already started
        if (!pollingIntervalRef.current) {
          console.log("Starting polling interval...");
          pollingIntervalRef.current = setInterval(checkStatus, 15000); // Poll every 15 seconds
        }
      } else {
        // Includes "idle" or any other status
        console.log(
          "Backend reports generation is idle or finished. Stopping poll."
        );
        setGenerationStatus("idle");
        setErrorMessage(null); // Clear previous errors
        stopPolling(); // Stop polling if not running
      }
    } catch (err) {
      console.error("Error checking generation status:", err);
      setGenerationStatus("error");
      setErrorMessage(
        err instanceof Error ? err.message : "Network error checking status"
      );
      stopPolling(); // Stop polling on error
    } finally {
      // Always reset the checking flag in finally block
      isCheckingRef.current = false;
    }
    // Dependencies: Include everything needed by the function that might change
  }, [
    projectId,
    auth.isAuthenticated,
    auth.user?.id_token,
    stopPolling,
    generationStatus,
  ]);

  // --- Effect for Initial Check and Cleanup ---
  useEffect(() => {
    // Perform initial check when component mounts or auth state changes
    if (projectId && auth.isAuthenticated) {
      checkStatus();
    }

    // Cleanup function: always clear interval when component unmounts
    return () => {
      stopPolling();
    };
    // Dependencies: Only run on mount/unmount and when essential params change
  }, [projectId, auth.isAuthenticated, checkStatus, stopPolling]);

  if (!projectId) {
    return <div>Invalid Project ID.</div>;
  }

  const isFormDirty =
    plot !== "" ||
    writingStyle !== "" ||
    instructions.styleGuide !== "" ||
    instructions.additionalInstructions !== "" ||
    numChapters !== 1 ||
    wordCountInput !== "";

  const loadHistoryEntry = (entry: GenerationHistoryEntry) => {
    setPlot(entry.plot || "");
    setWritingStyle(entry.writing_style || "");
    setInstructions({
      styleGuide: entry.instructions.styleGuide || "",
      additionalInstructions: entry.instructions.additionalInstructions || "",
    });
    setNumChapters(entry.num_chapters || 1);
    setWordCountInput(entry.word_count?.toString() || "");
    toast.success("Loaded settings from history.");
  };

  const handleHistorySelect = (entry: GenerationHistoryEntry) => {
    if (isFormDirty) {
      setHistoryToLoad(entry);
      setShowConfirmDialog(true);
    } else {
      loadHistoryEntry(entry);
    }
  };

  const handleConfirmLoad = () => {
    if (historyToLoad) {
      loadHistoryEntry(historyToLoad);
    }
    setShowConfirmDialog(false);
    setHistoryToLoad(null);
  };

  // Handler to load data from the selected preset (passed to PresetManager)
  const handlePresetDataLoad = (presetData: Preset["data"]) => {
    // Use imported Preset type
    setPlot(presetData.plot || "");
    setWritingStyle(presetData.writingStyle || "");
    // Correctly set instructions from flattened fields
    setInstructions({
      styleGuide: presetData.styleGuide || "",
      additionalInstructions: presetData.additionalInstructions || "",
    });
    if (presetData.numChapters !== undefined) {
      setNumChapters(presetData.numChapters);
    }
    if (presetData.wordCount !== undefined) {
      setWordCountInput(presetData.wordCount.toString());
    } else {
      setWordCountInput("");
    }
  };

  // Handler for changes in the main instruction fields
  const handleInstructionChange = (
    field: keyof Omit<GenerationInstructions, "wordCount">, // Exclude wordCount here
    value: string
  ) => {
    setInstructions((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setErrorMessage("Authentication required to generate chapters.");
      setGenerationStatus("error"); // Set status to error
      return;
    }

    setIsLoading(true); // Indicate API call is starting
    setErrorMessage(null); // Clear previous errors
    setGenerationStatus("checking"); // Assume checking while submitting
    stopPolling(); // Stop any existing polling just in case
    const token = auth.user.id_token;

    // Basic validation
    if (numChapters <= 0 || !plot.trim() || !writingStyle.trim()) {
      setErrorMessage(
        "Please fill in all required fields (Number of Chapters, Plot, Writing Style)."
      );
      setGenerationStatus("error");
      setIsLoading(false);
      return;
    }

    let targetWordCount: number | undefined = undefined;
    if (wordCountInput) {
      targetWordCount = parseInt(wordCountInput, 10);
      if (isNaN(targetWordCount) || targetWordCount <= 0) {
        setErrorMessage(
          "Approx. Words per Chapter must be a valid positive number if provided."
        );
        setGenerationStatus("error");
        setIsLoading(false);
        return;
      }
    }

    // Construct the request body (match backend ChapterGenerationRequest)
    const finalInstructions: Record<string, string | number | undefined> = {
      ...instructions,
    };
    if (targetWordCount !== undefined) {
      finalInstructions.wordCount = targetWordCount;
    }

    const requestBody = {
      numChapters,
      plot,
      writingStyle,
      instructions: finalInstructions,
    };

    try {
      console.log("Sending generation request:", requestBody); // Log request

      const apiUrl = `${process.env.NEXT_PUBLIC_BACKEND_URL}/projects/${projectId}/chapters/generate`;
      console.log("Target API URL:", apiUrl);

      // Use standard fetch to get the Response object
      const fetchResponse = await fetch(
        apiUrl, // Use the correctly constructed URL
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(requestBody),
        }
      );

      // Check if the request was accepted (202) or other success (e.g. 200 OK)
      if (fetchResponse.ok) {
        if (fetchResponse.status === 202) {
          console.log("Generation request accepted (202).");
          // Parse the JSON body for the message
          const responseBody = await fetchResponse.json();
          toast.success(
            responseBody.message || // Use message from backend if available
              `Generation started for ${numChapters} chapter(s)! Check back later.`
          );
          setGenerationStatus("running"); // OPTIMISTIC: Assume running
          // Introduce a small delay before the first check
          setTimeout(() => {
            checkStatus(); // Immediately check status to confirm & start polling
          }, 1000); // Wait 1 second
        } else {
          // Handle unexpected success codes (e.g., 200 OK if backend wasn't changed)
          console.warn(
            "Generation endpoint returned an unexpected success status:",
            fetchResponse.status
          );
          toast.info(
            "Generation might have finished synchronously (unexpected)."
          );
          // Try to parse body if needed
          try {
            const responseBody = await fetchResponse.json();
            console.log("Response body on unexpected success:", responseBody);
          } catch {
            // No need to declare parseError if unused
            console.error(
              "Could not parse response body on unexpected success"
            );
          }
          setGenerationStatus("idle"); // Assume idle if not 202
          stopPolling();
        }
      } else {
        // Handle HTTP errors (4xx, 5xx)
        const errorBody = await fetchResponse.text(); // Get error details if possible
        console.error(
          `Generation initiation failed with status ${fetchResponse.status}:`,
          errorBody
        );
        // Check for 409 Conflict specifically
        if (fetchResponse.status === 409) {
          setErrorMessage(
            "Generation is already in progress for this project."
          );
          toast.error("Generation is already in progress for this project.");
          setGenerationStatus("running"); // Set state to reflect existing background job
          await checkStatus(); // Check status to start polling if needed
        } else {
          const parsedError = errorBody.substring(0, 150); // Limit error length
          const errorMessage = `Failed to start generation (Status: ${fetchResponse.status}): ${parsedError}`;
          setErrorMessage(errorMessage);
          toast.error(errorMessage);
          setGenerationStatus("error");
          stopPolling();
        }
      }
    } catch (err) {
      // Handle network errors (fetch itself failed)
      console.error("Network error during generation initiation:", err);
      const message =
        err instanceof Error
          ? err.message
          : "A network error occurred trying to start generation.";
      setErrorMessage(message);
      toast.error(`Network Error: ${message}`);
      setGenerationStatus("error");
      stopPolling();
    } finally {
      setIsLoading(false); // API call finished (accepted or failed)
    }
  };

  return (
    // Adjust max-width and padding as needed
    <div className="max-w-4xl mx-auto p-4 md:p-0">
      <Tabs defaultValue="generate">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="generate" className="generate-tab-trigger">Generate</TabsTrigger>
          <TabsTrigger value="history" className="history-tab-trigger">History</TabsTrigger>
        </TabsList>
        <TabsContent value="generate">
          <Card className="bg-card border-border rounded-lg">
            <CardHeader>
              {/* Apply theme styles */}
              <CardTitle className="text-2xl text-primary font-display">
                Generate New Chapters
              </CardTitle>
              <CardDescription className="text-muted-foreground">
                Use the AI assistant to generate new chapters based on your
                specifications.
              </CardDescription>
            </CardHeader>
            <form onSubmit={handleSubmit}>
              <CardContent className="space-y-6">
                {/* Preset Manager Component */}
                <PresetManager
                  projectId={projectId}
                  onPresetSelect={handlePresetDataLoad}
                />

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                {/* Apply theme styles */}
                <Label htmlFor="numChapters" className="text-foreground">
                  Number of Chapters
                </Label>
                {/* Input inherits theme styles */}
                <Input
                  id="numChapters"
                  type="number"
                  min="1"
                  value={numChapters}
                  onChange={(e) =>
                    setNumChapters(parseInt(e.target.value, 10) || 1)
                  }
                  className="" // Removed explicit styles
                  required
                  disabled={generationStatus === "running" || isLoading} // Disable if running or submitting
                />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="targetWordCount" className="text-foreground">
                  Approx. Words per Chapter (Optional)
                </Label>
                <Input
                  id="targetWordCount"
                  type="number"
                  min="50" // Example min
                  placeholder="e.g., 1500"
                  value={wordCountInput}
                  onChange={
                    (e) => setWordCountInput(e.target.value) // Update string state directly
                  }
                  className="" // Removed explicit styles
                  disabled={generationStatus === "running" || isLoading}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="plot" className="text-foreground">
                Plot / Scene Outline
              </Label>
              {/* Textarea inherits theme styles */}
              <Textarea
                id="plot"
                placeholder="Describe the main events, characters involved, and setting for the chapter(s)..."
                value={plot}
                onChange={(e) => setPlot(e.target.value)}
                className="min-h-[100px]" // Removed explicit styles
                required
                disabled={generationStatus === "running" || isLoading}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="writingStyle" className="text-foreground">
                Writing Style
              </Label>
              <Textarea
                id="writingStyle"
                placeholder="Describe the desired tone, perspective (e.g., third-person limited), sentence structure, vocabulary level, etc. Be specific!"
                value={writingStyle}
                onChange={(e) => setWritingStyle(e.target.value)}
                className="min-h-[80px]" // Removed explicit styles
                required
                disabled={generationStatus === "running" || isLoading}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="styleGuide" className="text-foreground">
                Style Guide / Rules
              </Label>
              <Textarea
                id="styleGuide"
                placeholder="e.g., Avoid adverbs. Use short sentences. Mention character X's internal thoughts..."
                value={instructions.styleGuide || ""}
                onChange={(e) =>
                  handleInstructionChange("styleGuide", e.target.value)
                }
                className="min-h-[80px]" // Removed explicit styles
                required
                disabled={generationStatus === "running" || isLoading}
              />
            </div>

            <div className="space-y-2">
              <Label
                htmlFor="additionalInstructions"
                className="text-foreground"
              >
                Other Instructions (Optional)
              </Label>
              <Textarea
                id="additionalInstructions"
                placeholder="Any other specific requirements, things to include or avoid..."
                value={instructions.additionalInstructions || ""}
                onChange={(e) =>
                  handleInstructionChange(
                    "additionalInstructions",
                    e.target.value
                  )
                }
                className="min-h-[80px]" // Removed explicit styles
                disabled={generationStatus === "running" || isLoading}
              />
            </div>
          </CardContent>
          {/* Apply theme styles */}
          <CardFooter className="flex justify-between items-center border-t border-border pt-4">
            {/* Status/Error Message Area */}
            <div className="text-sm min-h-[20px]">
              {" "}
              {/* Ensure consistent height */}
              {generationStatus === "error" && errorMessage && (
                <p className="text-destructive">{errorMessage}</p>
              )}
              {generationStatus === "running" && (
                <p className="text-muted-foreground flex items-center">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generation in progress...
                </p>
              )}
              {generationStatus === "checking" && (
                <p className="text-muted-foreground flex items-center">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Checking status...
                </p>
              )}
              {/* Placeholder for spacing when idle/no error */}
              {generationStatus === "idle" && !errorMessage && (
                <div>&nbsp;</div>
              )}
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              disabled={
                isLoading ||
                generationStatus === "running" ||
                generationStatus === "checking"
              } // Disable if loading OR already running OR checking
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Starting...
                </>
              ) : generationStatus === "running" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />{" "}
                  Generating...
                </>
              ) : generationStatus === "checking" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Checking...
                </>
              ) : (
                "Generate Chapters"
              )}
            </Button>
          </CardFooter>
        </form>
      </Card>
        </TabsContent>
        <TabsContent value="history">
          <Card>
            <CardHeader>
              <CardTitle>Generation History</CardTitle>
              <CardDescription>
                Review and reuse settings from previous chapter generations.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <HistoryTab
                projectId={projectId}
                onLoadHistory={handleHistorySelect}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <AlertDialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Overwrite current settings?</AlertDialogTitle>
            <AlertDialogDescription>
              You have unsaved changes in the form. Loading a history entry
              will replace the current content. Are you sure you want to
              continue?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setHistoryToLoad(null)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmLoad}>
              Confirm
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

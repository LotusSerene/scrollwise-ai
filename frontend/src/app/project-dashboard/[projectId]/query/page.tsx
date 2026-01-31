"use client";

import React, { use } from "react";
import { fetchApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth

interface ChatMessage {
  type: "human" | "ai";
  content: string;
  sources?: SourceMetadata[]; // Use a specific type for sources
}

// Define a type for the source metadata
interface SourceMetadata {
  id?: string;
  name?: string;
  type?: string;
  [key: string]: unknown; // Use unknown instead of any
}

interface KnowledgeBaseQueryPayload {
  query: string;
  chatHistory: { type: string; content: string }[]; // Keep this for the query payload
}

// Update response interface to match backend
interface KnowledgeBaseQueryResponse {
  answer: string;
  sources: SourceMetadata[]; // Use the specific type
}

interface QueryPageProps {
  params: Promise<{
    projectId: string;
  }>;
}

export default function QueryPage(props: QueryPageProps) {
  const params = use(props.params);
  const { projectId } = params;

  const [query, setQuery] = React.useState("");
  const [chatHistory, setChatHistory] = React.useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const chatContainerRef = React.useRef<HTMLDivElement>(null);
  const auth = useAuth(); // Use the hook

  React.useEffect(() => {
    // Fetch history only if projectId is available
    if (!projectId) {
      // Optionally set an error or specific state
      setError("Project ID is missing, cannot load history.");
      setIsLoading(false);
      return;
    }

    const fetchHistory = async (token: string | undefined) => {
      if (!token) {
        setError("Authentication token is missing.");
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      setError(null);
      // Token is passed as argument
      try {
        // Define interface for the expected history response structure
        interface GetChatHistoryResponse {
          chatHistory: ChatMessage[];
        }
        // Use the projectId obtained from params
        const historyResult = await fetchApi<
          GetChatHistoryResponse | unknown // Allow unknown for robust error checking
        >(
          `/projects/${projectId}/knowledge-base/chat-history`,
          { method: "GET" },
          token
        );

        // Check if the result is an object and has the chatHistory property which is an array
        if (
          typeof historyResult === "object" &&
          historyResult !== null &&
          Array.isArray((historyResult as GetChatHistoryResponse).chatHistory)
        ) {
          // Extract the array from the response object
          const messages = (historyResult as GetChatHistoryResponse)
            .chatHistory;

          // Validate structure of messages within the array (optional but good practice)
          const validHistory = messages.filter(
            (msg): msg is ChatMessage =>
              typeof msg === "object" &&
              msg !== null &&
              (msg.type === "human" || msg.type === "ai") &&
              typeof msg.content === "string"
          );
          setChatHistory(validHistory);
        } else {
          console.warn(
            "Received unexpected response structure when fetching chat history:",
            historyResult
          );
          setChatHistory([]); // Set to empty if structure is wrong
        }
      } catch (err) {
        console.error("Failed to fetch chat history:", err);
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load chat history. Please try refreshing."
        );
        setChatHistory([]);
      } finally {
        setIsLoading(false);
      }
    };

    // Fetch only when authenticated
    if (!auth.isLoading && auth.isAuthenticated && auth.user?.id_token) {
      fetchHistory(auth.user.id_token);
    } else if (!auth.isLoading && !auth.isAuthenticated) {
      setError("Authentication required to load chat history.");
      setIsLoading(false);
    }
    // Depend on auth state and projectId
  }, [projectId, auth.isLoading, auth.isAuthenticated, auth.user?.id_token]);

  const handleQuerySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Ensure projectId is available
    if (!query.trim() || isLoading || !projectId) return;

    const currentQuery = query;
    const userMessage: ChatMessage = { type: "human", content: currentQuery };

    // Capture history state *before* adding the user message
    const historyBeforeUserMessage = [...chatHistory];

    // Use the state *before* adding the user message for the query payload
    const historyForQueryPayload = chatHistory.map(({ type, content }) => ({
      type,
      content,
    }));

    // Add user message optimistically AFTER preparing the query payload history
    setChatHistory((prev) => [...prev, userMessage]);
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to send query.");
      setChatHistory((prev) => [
        ...prev,
        { type: "ai", content: "Error: Authentication required.", sources: [] },
      ]);
      return;
    }
    setQuery("");
    setIsLoading(true);
    setError(null);
    const token = auth.user.id_token; // Get token

    try {
      // Prepare payload for AI using history *before* user message
      const queryPayload: KnowledgeBaseQueryPayload = {
        query: currentQuery,
        chatHistory: historyForQueryPayload,
      };

      // Fetch AI Response
      const result = await fetchApi<KnowledgeBaseQueryResponse>(
        `/projects/${projectId}/knowledge-base/query`, // Use projectId from params
        {
          method: "POST",
          body: JSON.stringify(queryPayload),
        },
        token
      );

      // Process AI Response and Update Local State
      if (result && typeof result.answer === "string") {
        const newAiMessage: ChatMessage = {
          type: "ai",
          content: result.answer,
          sources: result.sources || [],
        };
        // 1. Construct the correct, final history including the user message and the new AI message
        const finalCompleteHistory = [
          ...historyBeforeUserMessage,
          userMessage,
          newAiMessage,
        ];

        // 2. Update the UI state with the complete history
        //    This replaces the optimistic user message update with the complete final state.
        setChatHistory(finalCompleteHistory);

        // --- Save Updated History to Backend --- (Fire-and-forget for now)
        // Map the latest history to the format expected by the save endpoint
        // 3. Map the FINAL history for saving
        const mappedHistoryToSave = finalCompleteHistory.map(
          ({ type, content }) => ({ type, content })
        );

        // The body should match the `ChatHistoryRequest` Pydantic model, which is { chatHistory: [...] }
        // 4. Create the request body
        const saveBody = { chatHistory: mappedHistoryToSave };

        // Call the save endpoint using the project-specific path
        // 5. Call the save endpoint
        fetchApi<{ message: string }>(
          `/projects/${projectId}/chat-history`, // <-- Use project-specific path
          {
            method: "POST",
            body: JSON.stringify(saveBody), // Send only the history in the body
          },
          token
        ).catch((saveError) => {
          // Optional: Handle save error (e.g., log it, show a non-blocking warning)
          console.error("Failed to save chat history silently:", saveError);
        });
        // --- End Save ---
      } else {
        console.error("Received invalid response structure:", result);
        // Optionally add an AI error message to state here if needed, similar to the catch block
        // For now, the state will still show the user message due to the optimistic update
        throw new Error("Received invalid response structure from AI.");
      }
    } catch (err) {
      // Handle errors from the AI query itself
      console.error("Failed to submit query:", err);
      const errorMessage =
        err instanceof Error
          ? err.message
          : "Failed to get response. Please try again.";
      setError(errorMessage); // Set top-level error

      // Add error message to chat state. We need to base it on the state *including* the user message.
      setChatHistory((prev) => [
        // Use functional update to ensure it's based on latest state
        ...prev, // Should include the optimistically added user message
        { type: "ai", content: `Error: ${errorMessage}`, sources: [] }, // Add empty sources for errors
      ]);
      // Note: We don't save history if the query fails
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetChat = async () => {
    // Ensure projectId is available
    if (isLoading || !projectId) return;
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to reset chat.");
      return;
    }

    setIsLoading(true);
    setError(null);
    const token = auth.user.id_token; // Get token
    try {
      await fetchApi<null>(
        `/projects/${projectId}/knowledge-base/reset-chat-history`, // Use projectId from params
        { method: "POST" },
        token
      );
      setChatHistory([]);
    } catch (err) {
      console.error("Failed to reset chat history:", err);
      setError(
        err instanceof Error
          ? err.message
          : "Failed to reset chat. Please try again."
      );
    } finally {
      setIsLoading(false);
    }
  };

  React.useEffect(() => {
    chatContainerRef.current?.scrollTo({
      top: chatContainerRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [chatHistory]);

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] max-h-[calc(100vh-10rem)] bg-card border border-border rounded-lg shadow-sm p-4">
      <h2 className="text-xl font-semibold mb-4 text-primary border-b border-border pb-2 font-display">
        Query Knowledge Base
      </h2>

      {error &&
        !chatHistory.some(
          (msg) => msg.type === "ai" && msg.content.startsWith("Error:")
        ) && (
          <div className="mb-4 p-3 bg-destructive/10 border border-destructive text-destructive-foreground rounded-md text-sm">
            {error}
          </div>
        )}

      <div
        ref={chatContainerRef}
        className="flex-grow overflow-y-auto mb-4 pr-2 space-y-4 scrollbar-thin scrollbar-thumb-muted scrollbar-track-card"
      >
        {isLoading && chatHistory.length === 0 && (
          <div className="flex justify-center items-center h-full text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
            <span className="ml-2">Loading history...</span>
          </div>
        )}
        {chatHistory.length === 0 && !isLoading && !error && (
          <div className="text-center text-muted-foreground mt-8">
            No chat history yet. Ask something about your project context.
          </div>
        )}
        {Array.isArray(chatHistory) &&
          chatHistory.map((message, index) => (
            <div
              key={index}
              className={`p-3 rounded-lg max-w-[85%] w-fit text-sm ${
                message.type === "human"
                  ? "bg-primary text-primary-foreground ml-auto"
                  : message.content.startsWith("Error:")
                  ? "bg-destructive text-destructive-foreground mr-auto"
                  : "bg-accent text-accent-foreground mr-auto prose prose-sm dark:prose-invert"
              }`}
            >
              {message.type === "ai" &&
              !message.content.startsWith("Error:") ? (
                <>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {message.content}
                  </ReactMarkdown>
                  {message.sources && message.sources.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-border/50 text-xs opacity-70">
                      <strong>Sources:</strong>
                      <ul className="list-disc pl-4">
                        {message.sources.map((source, i) => (
                          <li key={i}>
                            {source.name || `Source ${i + 1}`} (
                            {source.type || "N/A"})
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              ) : (
                message.content.split("\n").map((line, i, arr) => (
                  <p
                    key={i}
                    className={`whitespace-pre-wrap ${
                      i === arr.length - 1 ? "" : "mb-1"
                    }`}
                  >
                    {line || "\u00A0"} {/* Render empty lines */}
                  </p>
                ))
              )}
            </div>
          ))}
        {isLoading && chatHistory[chatHistory.length - 1]?.type === "human" && (
          <div className="p-3 rounded-lg max-w-[80%] w-fit bg-accent text-accent-foreground mr-auto flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground italic">
              AI is thinking...
            </p>
          </div>
        )}
      </div>

      <form
        onSubmit={handleQuerySubmit}
        className="flex gap-2 border-t border-border pt-4"
      >
        <Input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask something about your project..."
          disabled={isLoading}
          className="flex-grow"
        />
        <Button
          type="submit"
          disabled={isLoading || !query.trim()}
          size="icon"
          aria-label="Send query"
        >
          {isLoading &&
          chatHistory[chatHistory.length - 1]?.type === "human" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="lucide lucide-send-horizontal"
            >
              <path d="m3 3 3 9-3 9 19-9Z" />
              <path d="M6 12h16" />
            </svg>
          )}
        </Button>
        <Button
          type="button"
          variant="destructive"
          onClick={handleResetChat}
          disabled={isLoading}
          title="Reset Chat History"
          size="icon"
          aria-label="Reset chat history"
        >
          {isLoading && chatHistory.length > 0 ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="lucide lucide-trash-2"
            >
              <path d="M3 6h18" />
              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
              <line x1="10" x2="10" y1="11" y2="17" />
              <line x1="14" x2="14" y1="11" y2="17" />
            </svg>
          )}
        </Button>
      </form>
    </div>
  );
}

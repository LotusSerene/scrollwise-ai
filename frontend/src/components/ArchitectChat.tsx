"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "@/components/MockAuthProvider";
import { fetchApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Loader2,
  Sparkles,
  User,
  Bot,
  SendHorizonal,
  AlertTriangle,
  Trash2,
  X,
  Minus,
  Square,
  Wrench,
} from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { motion, AnimatePresence } from "framer-motion";

const MESSAGE_PAGE_SIZE = 30; // Number of messages to fetch per page

// Define interfaces for chat items, request, and response
interface ArchitectChatHistoryItem {
  role: "user" | "assistant";
  content: string;
  id?: string; // Optional ID for animation keys
  isToolCall?: boolean; // Flag to identify tool call messages
  isToolError?: boolean; // Flag to identify tool error messages
  isToolProcessing?: boolean; // Flag to identify processing tool calls
}

interface ArchitectChatRequest {
  message: string;
  // History is no longer sent from client
}

// Define a more specific interface for tool calls
interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  result?: string;
}

interface ArchitectChatResponse {
  response: string;
  tool_calls?: ToolCall[]; // Using the defined ToolCall type
}

interface ArchitectChatProps {
  projectId: string;
  isMinimized: boolean;
  onMinimizeToggle: () => void;
  onClose: () => void;
}

export function ArchitectChat({
  projectId,
  isMinimized,
  onMinimizeToggle,
  onClose,
}: ArchitectChatProps) {
  const auth = useAuth();
  const [messages, setMessages] = useState<ArchitectChatHistoryItem[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingHistory, setIsFetchingHistory] = useState(true);
  const [isClearing, setIsClearing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isProcessingTools, setIsProcessingTools] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // State for pagination
  const [isLoadingOlder, setIsLoadingOlder] = useState(false);
  const [hasMoreOlderMessages, setHasMoreOlderMessages] = useState(true); // Assume true initially
  const [oldestMessageIdCursor, setOldestMessageIdCursor] = useState<
    string | null
  >(null);

  // Add a status text to show during tool processing
  const [toolStatus, setToolStatus] = useState<string | null>(null);

  // Auto-scroll to bottom with improved reliability
  const scrollToBottom = useCallback(() => {
    if (isMinimized) return;

    // Use requestAnimationFrame for smoother scrolling after DOM updates
    requestAnimationFrame(() => {
      if (messagesEndRef.current) {
        messagesEndRef.current.scrollIntoView({
          behavior: "smooth",
          block: "end",
        });
      }

      // Fallback method using ScrollArea viewport
      if (scrollAreaRef.current) {
        const viewport = scrollAreaRef.current.querySelector<HTMLElement>(
          "[data-radix-scroll-area-viewport]"
        );
        if (viewport) {
          viewport.scrollTop = viewport.scrollHeight;
        }
      }
    });
  }, [isMinimized]);

  // Fetch history on initial load and when auth changes
  useEffect(() => {
    const fetchHistory = async () => {
      if (!auth.isAuthenticated || !auth.user?.id_token) {
        setIsFetchingHistory(false);
        return; // Don't fetch if not authenticated
      }
      setIsFetchingHistory(true);
      setError(null);
      try {
        // When endpoint exists, uncomment below:
        // The backend currently returns the array directly, not nested under 'history'
        // For pagination, we'll assume the API can take 'limit' and 'before_id'
        const apiUrl = `/projects/${projectId}/architect/chat-history?limit=${MESSAGE_PAGE_SIZE}`;
        // For subsequent fetches of older messages, we'd add `&before_id=${oldestMessageIdCursor}`
        // For initial fetch, no `before_id` is needed.

        const historyResponse = await fetchApi<ArchitectChatHistoryItem[]>( // Expect a direct array now
          apiUrl,
          { method: "GET" },
          auth.user.id_token
        );

        // Add unique IDs to messages for animation
        const messagesWithIds = (historyResponse || []).map((msg, index) => ({
          ...msg,
          // Ensure ID for new messages is unique and if msg.id exists, use it.
          // This is important if actual message objects from backend have stable IDs.
          // For now, we generate one if not present, but for pagination cursors, backend IDs are better.
          id: msg.id || `msg-${Date.now()}-${index}`,
        }));
        setMessages(messagesWithIds); // REMOVED .reverse() - backend provides chronological order

        if (messagesWithIds.length > 0) {
          setOldestMessageIdCursor(messagesWithIds[0].id!); // Oldest is now the first (correct for chronological)
        }

        setHasMoreOlderMessages(messagesWithIds.length === MESSAGE_PAGE_SIZE);

        // console.log(
        //   "ArchitectChat: History fetching placeholder - GET endpoint needed."
        // ); // Keep this commented or remove if endpoint exists
      } catch (err) {
        console.error("Failed to fetch Architect chat history:", err);
        toast.error("Failed to load chat history.");
        setError("Could not load previous conversation.");
      } finally {
        setIsFetchingHistory(false);
      }
    };

    fetchHistory();
  }, [auth.isAuthenticated, auth.user?.id_token, projectId]);

  // Scroll when messages update or loading state changes
  useEffect(() => {
    if (!isLoading && !isFetchingHistory) {
      // Add a small delay to ensure DOM has updated completely
      setTimeout(scrollToBottom, 100);
    }
  }, [messages, scrollToBottom, isLoading, isFetchingHistory]);

  // Also scroll when the component becomes visible from minimized state
  useEffect(() => {
    if (!isMinimized) {
      setTimeout(scrollToBottom, 300); // delay for the animation to complete
    }
  }, [isMinimized, scrollToBottom]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading || !auth.user?.id_token) {
      return;
    }

    const newUserMessage: ArchitectChatHistoryItem = {
      role: "user",
      content: inputMessage.trim(),
      id: `user-${Date.now()}`,
    };
    // Optimistically update UI
    setMessages((prev) => [...prev, newUserMessage]);
    setInputMessage("");
    setIsLoading(true);
    setError(null);
    setToolStatus(null);

    try {
      const requestBody: ArchitectChatRequest = {
        message: newUserMessage.content,
        // chatHistory removed
      };

      const response = await fetchApi<ArchitectChatResponse>(
        `/projects/${projectId}/architect/chat`,
        {
          method: "POST",
          body: JSON.stringify(requestBody),
        },
        auth.user.id_token
      );

      const assistantMessage: ArchitectChatHistoryItem = {
        role: "assistant",
        content: response.response,
        id: `assistant-${Date.now()}`,
      };

      // Update message list with the actual response
      const updatedMessages = [
        ...messages.slice(0, -1),
        newUserMessage,
        assistantMessage,
      ];
      setMessages(updatedMessages);

      // Handle tool calls if present
      if (response.tool_calls && response.tool_calls.length > 0) {
        console.log("Architect requested tool calls:", response.tool_calls);

        // Show tool processing indicator
        setIsProcessingTools(true);

        // Create a copy of messages that we'll modify as tools are processed
        let currentMessages = [...updatedMessages];

        try {
          // For each tool call, add a message showing the tool usage
          for (const [index, toolCall] of response.tool_calls.entries()) {
            setToolStatus(
              `Processing tool: ${toolCall.name} (${index + 1}/${
                response.tool_calls.length
              })`
            );

            // Add a "processing" message that will be updated later
            const processingId = `tool-call-${Date.now()}-${index}`;
            const processingMessage: ArchitectChatHistoryItem = {
              role: "assistant",
              content:
                `**Tool Called: ${toolCall.name}**\n\n` +
                `**Arguments:**\n\`\`\`json\n${JSON.stringify(
                  toolCall.args,
                  null,
                  2
                )}\n\`\`\`\n` +
                `\n_Processing..._`,
              id: processingId,
              isToolCall: true,
              isToolProcessing: true,
            };

            currentMessages = [...currentMessages, processingMessage];
            setMessages(currentMessages);

            // Allow UI to update before simulating tool execution
            await new Promise((resolve) => setTimeout(resolve, 100));
            scrollToBottom();

            try {
              // Simulate tool execution with a delay
              // In a real implementation, you would actually call the tool here
              // and update the message with the result
              await new Promise((resolve) => setTimeout(resolve, 1000));

              // Update the processing message with the "result"
              const resultMessage: ArchitectChatHistoryItem = {
                role: "assistant",
                content:
                  `**Tool Called: ${toolCall.name}**\n\n` +
                  `**Arguments:**\n\`\`\`json\n${JSON.stringify(
                    toolCall.args,
                    null,
                    2
                  )}\n\`\`\`\n` +
                  (toolCall.result
                    ? `\n**Result:**\n${toolCall.result}`
                    : `\n**Result:**\n_Tool execution completed successfully._`),
                id: processingId,
                isToolCall: true,
                isToolProcessing: false,
              };

              // Replace the processing message with the result
              const msgIndex = currentMessages.findIndex(
                (msg) => msg.id === processingId
              );
              if (msgIndex !== -1) {
                currentMessages = [
                  ...currentMessages.slice(0, msgIndex),
                  resultMessage,
                  ...currentMessages.slice(msgIndex + 1),
                ];
                setMessages(currentMessages);
                scrollToBottom();
              }
            } catch (singleToolErr) {
              console.error(
                `Error processing tool ${toolCall.name}:`,
                singleToolErr
              );

              // Update the message to show the error for this specific tool
              const errorMessage: ArchitectChatHistoryItem = {
                role: "assistant",
                content:
                  `**Tool Error: ${toolCall.name}**\n\n` +
                  `Failed to process this tool call. The operation could not be completed.`,
                id: processingId,
                isToolCall: true,
                isToolError: true,
              };

              // Replace the processing message with the error
              const msgIndex = currentMessages.findIndex(
                (msg) => msg.id === processingId
              );
              if (msgIndex !== -1) {
                currentMessages = [
                  ...currentMessages.slice(0, msgIndex),
                  errorMessage,
                  ...currentMessages.slice(msgIndex + 1),
                ];
                setMessages(currentMessages);
                scrollToBottom();
              }
            }
          }
        } catch (toolErr) {
          console.error("Error processing all tool calls:", toolErr);
          const errorMessage: ArchitectChatHistoryItem = {
            role: "assistant",
            content:
              "**Error:** Failed to process one or more tool calls. Please try again.",
            id: `tool-error-${Date.now()}`,
            isToolCall: true,
            isToolError: true,
          };
          setMessages([...currentMessages, errorMessage]);
        } finally {
          setIsProcessingTools(false);
          setToolStatus(null);
        }
      }
    } catch (err: unknown) {
      console.error("Architect chat error:", err);
      const message =
        err instanceof Error
          ? err.message
          : "Failed to get response from Architect.";
      setError(message);
      toast.error(`Architect Chat Error: ${message}`);
      // Revert optimistic update on error
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setIsLoading(false);
      scrollToBottom(); // Ensure scroll after response/error
    }
  };

  const handleClearHistory = async () => {
    if (!auth.user?.id_token || isClearing) {
      return;
    }
    setIsClearing(true);
    setError(null);
    try {
      await fetchApi(
        `/projects/${projectId}/architect/chat-history`,
        { method: "DELETE" },
        auth.user.id_token
      );
      setMessages([]); // Clear messages locally
      toast.success("Architect chat history cleared.");
    } catch (err) {
      console.error("Failed to clear Architect chat history:", err);
      const message =
        err instanceof Error ? err.message : "Could not clear history.";
      setError(message);
      toast.error(`Error: ${message}`);
    } finally {
      setIsClearing(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault(); // Prevent newline
      handleSendMessage();
    }
  };

  const handleLoadOlderMessages = async () => {
    if (
      !auth.isAuthenticated ||
      !auth.user?.id_token ||
      isLoadingOlder ||
      !hasMoreOlderMessages ||
      !oldestMessageIdCursor
    ) {
      return;
    }

    setIsLoadingOlder(true);
    setError(null);

    // Store current scroll height and top position to restore later
    const scrollableView = scrollAreaRef.current?.querySelector<HTMLElement>(
      "[data-radix-scroll-area-viewport]"
    );
    const oldScrollHeight = scrollableView?.scrollHeight || 0;
    const oldScrollTop = scrollableView?.scrollTop || 0;

    try {
      let apiUrl = `/projects/${projectId}/architect/chat-history?limit=${MESSAGE_PAGE_SIZE}`;
      if (oldestMessageIdCursor) {
        apiUrl += `&before_id=${oldestMessageIdCursor}`;
      }

      const olderMessagesResponse = await fetchApi<ArchitectChatHistoryItem[]>(
        apiUrl,
        { method: "GET" },
        auth.user.id_token
      );

      const olderMessagesWithIds = (olderMessagesResponse || []).map(
        (msg, index) => ({
          ...msg,
          id: msg.id || `msg-old-${Date.now()}-${index}`,
        })
      );

      if (olderMessagesWithIds.length > 0) {
        setMessages((prevMessages) => [
          ...olderMessagesWithIds,
          ...prevMessages,
        ]);
        setOldestMessageIdCursor(olderMessagesWithIds[0].id!); // New oldest message
        setHasMoreOlderMessages(
          olderMessagesWithIds.length === MESSAGE_PAGE_SIZE
        );

        // Attempt to restore scroll position
        if (scrollableView) {
          // Wait for DOM update
          requestAnimationFrame(() => {
            const newScrollHeight = scrollableView.scrollHeight;
            scrollableView.scrollTop =
              oldScrollTop + (newScrollHeight - oldScrollHeight);
          });
        }
      } else {
        setHasMoreOlderMessages(false); // No more messages found
      }
    } catch (err) {
      console.error("Failed to fetch older Architect chat messages:", err);
      toast.error("Failed to load older messages.");
      // setError("Could not load older messages."); // Optionally set an error message
    } finally {
      setIsLoadingOlder(false);
    }
  };

  return (
    <TooltipProvider>
      <div
        className={cn(
          "fixed bottom-5 right-5 z-50 flex flex-col border rounded-lg bg-background shadow-lg transition-all duration-300 ease-in-out overflow-hidden",
          isMinimized
            ? "h-[60px] w-[300px]"
            : "h-[calc(100vh-120px)] max-h-[85vh] w-[600px]"
        )}
      >
        <div className="flex items-center justify-between p-3 border-b bg-muted/40 flex-shrink-0">
          <div className="flex items-center">
            <Sparkles className="h-5 w-5 mr-2 text-primary" />
            <h3 className="text-lg font-semibold">Architect Chat</h3>
          </div>
          <div className="flex items-center space-x-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onMinimizeToggle}
                  className="text-muted-foreground hover:bg-accent h-7 w-7"
                >
                  {isMinimized ? (
                    <Square className="h-3 w-3" />
                  ) : (
                    <Minus className="h-3 w-3" />
                  )}
                  <span className="sr-only">
                    {isMinimized ? "Maximize" : "Minimize"} Chat
                  </span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>{isMinimized ? "Maximize" : "Minimize"} Chat</p>
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleClearHistory}
                  disabled={isClearing || messages.length === 0 || isMinimized}
                  className="text-muted-foreground hover:text-destructive h-7 w-7"
                >
                  {isClearing ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>Clear Chat History</p>
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onClose}
                  className="text-muted-foreground hover:bg-destructive hover:text-destructive-foreground h-7 w-7"
                >
                  <X className="h-4 w-4" />
                  <span className="sr-only">Close Chat</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>Close Chat</p>
              </TooltipContent>
            </Tooltip>
          </div>
        </div>

        {!isMinimized && (
          <>
            <ScrollArea
              className="flex-grow p-4 overflow-y-auto overflow-x-hidden"
              ref={scrollAreaRef}
              scrollHideDelay={100}
            >
              {isFetchingHistory ? (
                <div className="flex justify-center items-center h-full">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <div className="space-y-4 mb-4 relative">
                  {/* Button to load older messages */}
                  {hasMoreOlderMessages && (
                    <div className="flex justify-center py-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleLoadOlderMessages}
                        disabled={isLoadingOlder}
                        className="text-sm"
                      >
                        {isLoadingOlder ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Loading...
                          </>
                        ) : (
                          "Load Older Messages"
                        )}
                      </Button>
                    </div>
                  )}
                  <AnimatePresence initial={false}>
                    {messages.map((msg, index) => (
                      <motion.div
                        key={msg.id || index}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.3 }}
                        className={cn(
                          "flex items-start gap-3 w-full",
                          msg.role === "user" ? "justify-end" : ""
                        )}
                      >
                        {msg.role === "assistant" && (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <div
                                className={cn(
                                  "p-2 rounded-full flex-shrink-0",
                                  msg.isToolCall
                                    ? msg.isToolError
                                      ? "bg-destructive/10 text-destructive"
                                      : "bg-amber-100 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400"
                                    : "bg-primary/10 text-primary"
                                )}
                              >
                                {msg.isToolCall ? (
                                  msg.isToolError ? (
                                    <AlertTriangle className="h-5 w-5" />
                                  ) : (
                                    <Wrench className="h-5 w-5" />
                                  )
                                ) : (
                                  <Bot className="h-5 w-5" />
                                )}
                              </div>
                            </TooltipTrigger>
                            <TooltipContent>
                              {msg.isToolCall
                                ? msg.isToolError
                                  ? "Tool Error"
                                  : msg.isToolProcessing
                                  ? "Processing Tool Call"
                                  : "Tool Result"
                                : "Architect"}
                            </TooltipContent>
                          </Tooltip>
                        )}
                        <div
                          className={cn(
                            "p-3 rounded-lg max-w-[75%] shadow-sm break-words overflow-hidden",
                            msg.role === "user"
                              ? "bg-primary text-primary-foreground"
                              : msg.isToolCall
                              ? msg.isToolError
                                ? "bg-destructive/10 border border-destructive/20"
                                : msg.isToolProcessing
                                ? "bg-amber-50/80 dark:bg-amber-900/10 border border-amber-200/50 dark:border-amber-800/30"
                                : "bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/50"
                              : "bg-muted/80 border border-muted-foreground/10"
                          )}
                        >
                          <div className="overflow-hidden max-w-full">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                // eslint-disable-next-line @typescript-eslint/no-unused-vars
                                p: ({ node, ...props }) => (
                                  <p
                                    className="mb-2 last:mb-0 break-words"
                                    {...props}
                                  />
                                ),
                                // eslint-disable-next-line @typescript-eslint/no-unused-vars
                                a: ({ node, ...props }) => (
                                  <a
                                    className="text-primary underline hover:no-underline break-words break-all max-w-full inline-block"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    {...props}
                                  />
                                ),
                                // eslint-disable-next-line @typescript-eslint/no-unused-vars
                                code: ({ className, children, ...props }) => {
                                  const codeString = String(children).replace(
                                    /\n$/,
                                    ""
                                  );

                                  // Simple heuristic: if code contains newlines, it's likely a block
                                  const isInlineCode =
                                    !codeString.includes("\n");

                                  return isInlineCode ? (
                                    <code
                                      className="bg-muted-foreground/10 px-1 py-0.5 rounded text-sm whitespace-normal break-all"
                                      {...props}
                                    >
                                      {children}
                                    </code>
                                  ) : (
                                    <div className="bg-muted-foreground/10 p-2 rounded-md my-2 overflow-x-auto max-w-full">
                                      <code
                                        className="text-sm font-mono whitespace-pre"
                                        {...props}
                                      >
                                        {children}
                                      </code>
                                    </div>
                                  );
                                },
                                // eslint-disable-next-line @typescript-eslint/no-unused-vars
                                pre: ({ node, ...props }) => (
                                  <pre
                                    className="overflow-x-auto p-0 my-2"
                                    {...props}
                                  />
                                ),
                                // eslint-disable-next-line @typescript-eslint/no-unused-vars
                                table: ({ node, ...props }) => (
                                  <div className="overflow-x-auto my-2">
                                    <table
                                      className="w-full border-collapse"
                                      {...props}
                                    />
                                  </div>
                                ),
                                // eslint-disable-next-line @typescript-eslint/no-unused-vars
                                ul: ({ node, ...props }) => (
                                  <ul
                                    className="list-disc pl-6 my-2"
                                    {...props}
                                  />
                                ),
                                // eslint-disable-next-line @typescript-eslint/no-unused-vars
                                ol: ({ node, ...props }) => (
                                  <ol
                                    className="list-decimal pl-6 my-2"
                                    {...props}
                                  />
                                ),
                              }}
                            >
                              {msg.content}
                            </ReactMarkdown>
                          </div>
                        </div>
                        {msg.role === "user" && (
                          <div className="p-2 rounded-full bg-muted/80 flex-shrink-0">
                            <User className="h-5 w-5 text-muted-foreground" />
                          </div>
                        )}
                      </motion.div>
                    ))}
                  </AnimatePresence>

                  {isProcessingTools && toolStatus && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="flex justify-center items-center py-2 mt-2"
                    >
                      <div
                        className="flex items-center gap-2 px-3 py-1.5 bg-amber-50 dark:bg-amber-900/20 
                              text-amber-700 dark:text-amber-300 rounded-full text-sm border border-amber-200 dark:border-amber-800/50"
                      >
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>{toolStatus}</span>
                      </div>
                    </motion.div>
                  )}

                  {isLoading && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="flex items-start gap-3"
                    >
                      <div className="p-2 rounded-full bg-primary/10 text-primary">
                        <Bot className="h-5 w-5" />
                      </div>
                      <div className="p-3 rounded-lg bg-muted/80 border border-muted-foreground/10">
                        <div className="flex items-center space-x-2">
                          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                          <span className="text-sm text-muted-foreground">
                            Thinking...
                          </span>
                        </div>
                      </div>
                    </motion.div>
                  )}

                  {error && !isFetchingHistory && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                    >
                      <Alert variant="destructive" className="mt-4">
                        <AlertTriangle className="h-4 w-4" />
                        <AlertTitle>Chat Error</AlertTitle>
                        <AlertDescription>{error}</AlertDescription>
                      </Alert>
                    </motion.div>
                  )}

                  {messages.length === 0 &&
                    !isLoading &&
                    !isFetchingHistory && (
                      <div className="text-center text-muted-foreground py-10">
                        <Sparkles className="h-10 w-10 mx-auto mb-4 text-primary/50" />
                        <p>Start the conversation with the Architect.</p>
                        <p className="text-sm mt-2">
                          Ask questions about your project or get creative
                          assistance.
                        </p>
                      </div>
                    )}

                  {/* Invisible element to scroll to */}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </ScrollArea>

            <div className="border-t p-3 flex items-center gap-2 bg-background flex-shrink-0">
              <Textarea
                placeholder="Ask the Architect... (Shift+Enter for newline)"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
                className="flex-grow resize-none min-h-[40px] max-h-[150px] overflow-y-auto pr-12 rounded-md border focus-visible:ring-1 focus-visible:ring-ring"
                disabled={isLoading || isFetchingHistory || isProcessingTools}
              />
              <Button
                type="button"
                onClick={handleSendMessage}
                disabled={
                  isLoading ||
                  !inputMessage.trim() ||
                  isFetchingHistory ||
                  isProcessingTools
                }
                size="icon"
                className="absolute right-5 bottom-[18px] h-8 w-8"
              >
                {isLoading || isProcessingTools ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <SendHorizonal className="h-4 w-4" />
                )}
                <span className="sr-only">Send message</span>
              </Button>
            </div>
          </>
        )}
      </div>
    </TooltipProvider>
  );
}

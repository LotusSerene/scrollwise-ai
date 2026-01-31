"use client"; // Make this a client component to handle state and effects
import React, { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "next/navigation"; // Import useParams
import { Button } from "@/components/ui/button";
import {
  List,
  Plus,
  Upload,
  Download,
  Save,
  Trash2,
  Loader2,
  Pencil,
  Wand2,
  AlertTriangle,
  StickyNote,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { fetchApi, extractTextFromFile } from "@/lib/api";
import RichTextEditor from "@/components/RichTextEditor";
import { Input } from "@/components/ui/input"; // Import Input for new chapter title
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth
import { toast } from "sonner";
// Add imports for dropdown components
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
// Import marked for Markdown conversion
import { marked } from "marked";
// Import turndown for HTML to Markdown conversion
import TurndownService from "turndown";
import { type Editor } from "@tiptap/core";
import jsPDF from "jspdf";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { Notepad } from "@/components/Notepad";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

// Interface for Chapter data (match backend structure)
interface Chapter {
  id: string;
  title: string;
  content?: string; // Content might be fetched separately
  chapter_number?: number;
  // Add other fields if needed (word_count, etc.)
}

// New interfaces for the folder structure
interface ChapterItem {
  id: string;
  type: "chapter";
  title: string;
}

interface FolderItem {
  id: string;
  type: "folder";
  title: string;
  children: (FolderItem | ChapterItem)[];
}

type StructureItem = FolderItem | ChapterItem;

interface ProjectStructureResponse {
  project_structure: StructureItem[];
}

interface CodexItem {
  id: string;
  name: string;
  type: string;
}

interface ProactiveSuggestion {
  suggestion: string;
  confidence: number;
}

// Add this component before the EditorPage function
interface ChapterStructureRendererProps {
  items: (FolderItem | ChapterItem)[];
  handleSelectChapter: (chapterId: string, token: string | undefined) => void;
  selectedChapter: Chapter | null;
  isLoadingChapterContent: boolean;
  isDeleting: boolean;
  isAddingChapter: boolean;
  authToken: string | undefined;
  handleExtractFolderItems?: (folderId: string) => void;
  isExtracting: boolean;
}

const ChapterStructureRenderer: React.FC<ChapterStructureRendererProps> = ({
  items,
  handleSelectChapter,
  selectedChapter,
  isLoadingChapterContent,
  isDeleting,
  isAddingChapter,
  authToken,
  handleExtractFolderItems,
  isExtracting,
}) => {
  const [expandedFolders, setExpandedFolders] = useState<
    Record<string, boolean>
  >({});

  const toggleFolder = (folderId: string) => {
    setExpandedFolders((prev) => ({
      ...prev,
      [folderId]: !prev[folderId],
    }));
  };

  const renderItems = (structureItems: (FolderItem | ChapterItem)[]) => {
    return structureItems.map((item) => {
      if (item.type === "chapter") {
        return (
          <button
            key={item.id}
            onClick={() => handleSelectChapter(item.id, authToken)}
            disabled={
              (isLoadingChapterContent && selectedChapter?.id === item.id) ||
              isDeleting ||
              isAddingChapter
            }
            className={`block w-full text-left px-3 py-2 rounded-md text-sm truncate cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-wait
                      ${
                        selectedChapter?.id === item.id
                          ? isLoadingChapterContent
                            ? "text-muted-foreground cursor-wait"
                            : "bg-primary text-primary-foreground"
                          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                      }`}
            title={item.title || "Chapter"}
          >
            {isLoadingChapterContent && selectedChapter?.id === item.id && (
              <Loader2 className="h-4 w-4 animate-spin inline mr-2" />
            )}
            {item.title || "Chapter"}
          </button>
        );
      } else if (item.type === "folder") {
        const isExpanded = expandedFolders[item.id] === true; // Default to collapsed

        return (
          <div key={item.id} className="space-y-1">
            <div className="flex items-center w-full">
              <button
                onClick={() => toggleFolder(item.id)}
                className="flex-1 flex items-center text-left px-3 py-2 rounded-l-md text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              >
                <span className="mr-2">
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </span>
                <span className="truncate" title={item.title}>
                  {item.title}
                </span>
              </button>

              {handleExtractFolderItems && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleExtractFolderItems(item.id);
                  }}
                  disabled={isExtracting}
                  className="px-2 py-2 rounded-r-md text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground disabled:opacity-50"
                  title="Extract codex items from this folder"
                >
                  {isExtracting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Wand2 className="h-4 w-4" />
                  )}
                </button>
              )}
            </div>

            {isExpanded && item.children && item.children.length > 0 && (
              <div className="pl-4 border-l border-border ml-3 space-y-1">
                {renderItems(item.children)}
              </div>
            )}
          </div>
        );
      }
      return null;
    });
  };

  return renderItems(items);
};

// Remove params from function signature
export default function EditorPage(/* { params }: EditorPageProps */) {
  const params = useParams<{ projectId: string }>(); // Use the hook
  const projectId = params?.projectId; // Access directly from the hook's return value
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<Chapter | null>(null);
  const [currentContent, setCurrentContent] = useState<string>(""); // State for editor content
  const [isLoadingChapters, setIsLoadingChapters] = useState(true);
  const [isLoadingChapterContent, setIsLoadingChapterContent] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isAddingChapter, setIsAddingChapter] = useState(false);
  const [newChapterTitle, setNewChapterTitle] = useState("");
  const [showAddChapterInput, setShowAddChapterInput] = useState(false);
  const importFileInputRef = React.useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  // State for inline title editing
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [currentChapterTitle, setCurrentChapterTitle] = useState("");
  // Use a ref to track if the component is mounted, preventing state updates after unmount
  const isMounted = useRef(true);
  const auth = useAuth(); // Use the hook
  const [isImporting, setIsImporting] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [codexItems, setCodexItems] = useState<CodexItem[]>([]);
  const [proactiveSuggestions, setProactiveSuggestions] = useState<
    ProactiveSuggestion[]
  >([]);
  const [isAssistantLoading, setIsAssistantLoading] = useState(false);
  const [notepadContent, setNotepadContent] = useState<string>("");
  const [isNotepadVisible, setIsNotepadVisible] = useState<boolean>(false);
  const editorRef = useRef<Editor | null>(null);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [projectStructure, setProjectStructure] =
    useState<ProjectStructureResponse | null>(null);
  // Add states for batch upload progress tracking
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isBatchImporting, setIsBatchImporting] = useState(false);
  const [totalFiles, setTotalFiles] = useState(0);
  const [processedFiles, setProcessedFiles] = useState(0);

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  useEffect(() => {
    const loadCodexItems = async (token: string) => {
      if (!projectId) return;
      try {
        const response = await fetchApi<CodexItem[]>(
          `/projects/${projectId}/codex-items/`,
          {},
          token
        );
        // Assuming the response is an array of items with { id, name }
        if (Array.isArray(response)) {
          setCodexItems(
            response.map((item) => ({
              id: item.id,
              name: item.name,
              type: item.type,
            }))
          );
        }
      } catch (err) {
        console.error("Failed to load codex items:", err);
        // Handle error silently or show a toast
      }
    };

    if (auth.isAuthenticated && auth.user?.id_token) {
      loadCodexItems(auth.user.id_token);
    }
  }, [projectId, auth.isAuthenticated, auth.user?.id_token]);

  // Adjusted handleSelectChapter: Needs token
  const handleSelectChapter = useCallback(
    async (chapterId: string, token: string | undefined) => {
      if (!token) {
        setError("Authentication token is missing.");
        setIsLoadingChapterContent(false); // Ensure loading state is reset
        return;
      }
      // If chapter is already selected or content is currently loading for it, do nothing
      if (selectedChapter?.id === chapterId) {
        // If content is still loading for the already selected chapter, don't interrupt
        if (isLoadingChapterContent) return;
        // If it's selected and not loading, maybe force reload? For now, just return.
        return;
      }

      setIsLoadingChapterContent(true);
      setError(null);
      setCurrentContent("");
      // Set temporary states indicating loading
      setSelectedChapter({
        id: chapterId,
        title: "Loading...",
      });
      setCurrentChapterTitle("Loading..."); // Match selectedChapter initial state

      // Token is passed as argument
      try {
        const chapterData = await fetchApi<Chapter>(
          `/projects/${projectId}/chapters/${chapterId}`,
          {},
          token
        );

        // Check if component is still mounted and if selection target hasn't changed
        if (isMounted.current) {
          setSelectedChapter((prev) => {
            if (prev?.id === chapterId) {
              // Only update if the selection target is still this chapter
              setCurrentContent(chapterData.content ?? ""); // Set content alongside chapter
              // Initialize title editing state for the selected chapter
              setCurrentChapterTitle(chapterData.title); // Use the fetched chapterData.title
              setIsEditingTitle(false); // Ensure edit mode is off initially
              return chapterData;
            }
            return prev; // Otherwise, keep the state (another selection might have started)
          });
        }
      } catch (err: unknown) {
        if (!isMounted.current) return; // Check mount status before setting state on error
        console.error(`Failed to load chapter ${chapterId}:`, err);
        const message =
          err instanceof Error ? err.message : "An unknown error occurred";
        setError(`Failed to load chapter content: ${message}`);
        // Clear selection only if the error corresponds to the current selection attempt
        setSelectedChapter((prev) => {
          if (prev?.id === chapterId) {
            setCurrentChapterTitle(""); // Clear title on error for this chapter
            return null; // Clear selection fully on error
          }
          return prev;
        });
      } finally {
        // Set loading false only if component is mounted and the current selected chapter matches the one we tried to load
        if (isMounted.current) {
          setSelectedChapter((prev) => {
            if (prev?.id === chapterId) {
              setIsLoadingChapterContent(false);
            }
            return prev;
          });
        }
      }
    },
    [projectId, selectedChapter?.id, isLoadingChapterContent]
  );

  // Effect 1: Load only chapter list on mount or projectId/auth change
  useEffect(() => {
    const loadChapters = async (token: string | undefined) => {
      if (!token) {
        setError("Authentication token is missing.");
        setIsLoadingChapters(false);
        return;
      }
      setIsLoadingChapters(true);
      setError(null);
      setSelectedChapter(null); // Clear selection when project changes
      setCurrentContent("");
      try {
        // First, try to fetch the new structured format
        const structureResponse = await fetchApi<ProjectStructureResponse>(
          `/projects/${projectId}/structure`,
          {},
          token
        );

        if (!isMounted.current) return;

        if (
          structureResponse &&
          Array.isArray(structureResponse.project_structure)
        ) {
          // Add this line:
          setProjectStructure(structureResponse);

          // We have the new structure format, flatten it into a sorted chapter list
          const flattenedChapters: Chapter[] = [];

          // Recursive function to flatten the structure
          const flattenStructure = (items: StructureItem[]) => {
            items.forEach((item) => {
              if (item.type === "chapter") {
                flattenedChapters.push({
                  id: item.id,
                  title: item.title,
                });
              } else if (item.type === "folder" && item.children) {
                // Process children of this folder
                flattenStructure(item.children);
              }
            });
          };

          // Start flattening from the root
          flattenStructure(structureResponse.project_structure);

          setChapters(flattenedChapters);
        } else {
          // Fall back to the old endpoint if structure is not available
          const chaptersResponse = await fetchApi<{ chapters: Chapter[] }>(
            `/projects/${projectId}/chapters`,
            {},
            token
          );

          if (!isMounted.current) return;

          if (!chaptersResponse || !chaptersResponse.chapters) {
            throw new Error("Invalid response from server");
          }

          const sortedChapters = chaptersResponse.chapters.sort(
            (a, b) =>
              (a.chapter_number ?? Infinity) - (b.chapter_number ?? Infinity)
          );
          setChapters(sortedChapters);
        }
      } catch (err: unknown) {
        if (!isMounted.current) return;
        console.error("Failed to load chapters:", err);
        const message =
          err instanceof Error ? err.message : "An unknown error occurred";
        setError(`Failed to load chapters: ${message}`);

        // Try the fallback endpoint if the structure endpoint failed
        try {
          const chaptersResponse = await fetchApi<{ chapters: Chapter[] }>(
            `/projects/${projectId}/chapters`,
            {},
            token
          );

          if (!isMounted.current) return;

          if (!chaptersResponse || !chaptersResponse.chapters) {
            throw new Error("Invalid response from server");
          }

          const sortedChapters = chaptersResponse.chapters.sort(
            (a, b) =>
              (a.chapter_number ?? Infinity) - (b.chapter_number ?? Infinity)
          );
          setChapters(sortedChapters);
          setError(null); // Clear error if fallback succeeded
        } catch (fallbackErr) {
          if (!isMounted.current) return;
          console.error("Fallback also failed:", fallbackErr);
        }
      } finally {
        if (isMounted.current) {
          setIsLoadingChapters(false);
        }
      }
    };

    if (!auth.isLoading && auth.isAuthenticated && auth.user?.id_token) {
      loadChapters(auth.user.id_token);
    } else if (!auth.isLoading && !auth.isAuthenticated) {
      setError("Authentication required to load chapters.");
      setIsLoadingChapters(false);
    }
  }, [projectId, auth.isLoading, auth.isAuthenticated, auth.user?.id_token]);

  // Effect 2: Select the first chapter once the chapter list is loaded
  useEffect(() => {
    if (
      !isLoadingChapters &&
      chapters.length > 0 &&
      !selectedChapter &&
      !isLoadingChapterContent
    ) {
      const firstChapter = chapters[0];
      if (firstChapter && auth.isAuthenticated && auth.user?.id_token) {
        handleSelectChapter(firstChapter.id, auth.user.id_token);
      }
    }
  }, [
    chapters,
    isLoadingChapters,
    selectedChapter,
    handleSelectChapter,
    isLoadingChapterContent,
    auth.isAuthenticated,
    auth.user?.id_token,
  ]);

  if (!projectId) {
    return <div>Invalid Project ID.</div>;
  }

  const handleSaveChanges = async () => {
    if (!selectedChapter) return;
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to save changes.");
      return;
    }
    const contentToSave = currentContent;
    setIsSaving(true);
    setError(null);
    const token = auth.user.id_token;

    const finalTitle = currentChapterTitle.trim() || selectedChapter.title;

    try {
      await fetchApi(
        `/projects/${projectId}/chapters/${selectedChapter.id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            title: finalTitle,
            content: contentToSave,
          }),
        },
        token
      );

      if (!isMounted.current) return;

      setSelectedChapter((prev) =>
        prev ? { ...prev, title: finalTitle, content: contentToSave } : null
      );
      setChapters((prevChapters) =>
        prevChapters.map((chapter) =>
          chapter.id === selectedChapter.id
            ? { ...chapter, title: finalTitle }
            : chapter
        )
      );
      setIsEditingTitle(false);

      console.log("Changes saved successfully");
    } catch (err: unknown) {
      console.error("Failed to save chapter:", err);
      const message =
        err instanceof Error ? err.message : "An unknown error occurred";
      setError(`Failed to save changes: ${message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const toggleAddChapterInput = () => {
    setShowAddChapterInput((prev) => !prev);
    setNewChapterTitle("");
    setError(null);
  };

  const handleAddChapter = async () => {
    if (!newChapterTitle.trim()) {
      setError("Please enter a title for the new chapter.");
      return;
    }
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to add chapter.");
      return;
    }
    setIsAddingChapter(true);
    setError(null);
    const token = auth.user.id_token;

    try {
      const newChapter = await fetchApi<Chapter>(
        `/projects/${projectId}/chapters`,
        {
          method: "POST",
          body: JSON.stringify({
            title: newChapterTitle,
            content: "",
            // Add to the end of the structure by default
            append_to_structure: true,
          }),
        },
        token
      );

      if (!newChapter) {
        throw new Error("Invalid response from server");
      }

      setShowAddChapterInput(false);
      setNewChapterTitle("");

      setChapters((prevChapters) => {
        const updatedChapters = [...prevChapters, newChapter];
        return updatedChapters.sort(
          (a, b) =>
            (a.chapter_number ?? Infinity) - (b.chapter_number ?? Infinity)
        );
      });

      // Also update the project structure to include the new chapter
      setProjectStructure((prevStructure) => {
        if (!prevStructure) {
          // Fallback in case structure isn't loaded yet
          return {
            project_structure: [
              { id: newChapter.id, type: "chapter", title: newChapter.title },
            ],
          };
        }
        const newStructureItem: ChapterItem = {
          id: newChapter.id,
          type: "chapter",
          title: newChapter.title,
        };
        return {
          ...prevStructure,
          project_structure: [
            ...prevStructure.project_structure,
            newStructureItem,
          ],
        };
      });

      if (auth.isAuthenticated && auth.user?.id_token) {
        handleSelectChapter(newChapter.id, token);
      }

      toast.success("Chapter created successfully");
    } catch (err) {
      if (!isMounted.current) return;
      console.error("Failed to add chapter:", err);
      const message =
        err instanceof Error ? err.message : "Unknown error occurred";
      setError(`Failed to add chapter: ${message}`);
      toast.error("Failed to create chapter");
    } finally {
      if (isMounted.current) {
        setIsAddingChapter(false);
      }
    }
  };

  const handleDeleteChapter = async () => {
    if (!selectedChapter) return;
    const chapterToDelete = selectedChapter;

    if (
      !confirm(
        `Are you sure you want to delete chapter "${chapterToDelete.title}"?`
      )
    ) {
      return;
    }
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to delete chapter.");
      return;
    }
    setIsDeleting(true);
    setError(null);
    const token = auth.user.id_token;
    try {
      await fetchApi(
        `/projects/${projectId}/chapters/${chapterToDelete.id}`,
        {
          method: "DELETE",
        },
        token
      );

      if (!isMounted.current) return;

      setProjectStructure((prevStructure) => {
        if (!prevStructure) return null;

        const removeChapterRecursively = (
          items: StructureItem[]
        ): StructureItem[] => {
          return items
            .map((item) => {
              if (item.id === chapterToDelete.id) {
                return null; // Filter this chapter out
              }
              if (item.type === "folder") {
                return {
                  ...item,
                  children: removeChapterRecursively(item.children),
                };
              }
              return item;
            })
            .filter(Boolean) as StructureItem[];
        };

        const newStructure = removeChapterRecursively(
          prevStructure.project_structure
        );
        return { project_structure: newStructure };
      });

      setSelectedChapter(null);
      setCurrentContent("");
      setChapters((prevChapters) =>
        prevChapters.filter((c) => c.id !== chapterToDelete.id)
      );

      console.log("Chapter deleted successfully");
    } catch (err: unknown) {
      if (!isMounted.current) return;
      console.error("Failed to delete chapter:", err);
      const message =
        err instanceof Error ? err.message : "An unknown error occurred";
      setError(`Failed to delete chapter: ${message}`);
    } finally {
      if (isMounted.current) {
        setIsDeleting(false);
      }
    }
  };

  const handleContentChange = (htmlContent: string) => {
    setCurrentContent(htmlContent);
  };

  const handleImportClick = () => {
    importFileInputRef.current?.click();
  };

  const importFileAsNewChapter = async (file: File) => {
    if (!auth.isAuthenticated || !auth.user?.id_token || !projectId) {
      setError("Authentication required to import chapter.");
      toast.error("Authentication required.");
      return;
    }

    setIsImporting(true);
    setError(null);

    try {
      const title = file.name.replace(/\.[^/.]+$/, "");

      let finalContent = "";
      if (
        file.name.endsWith(".md") ||
        file.type === "text/markdown" ||
        file.type.startsWith("text/")
      ) {
        const textContent = await file.text();
        if (file.name.endsWith(".md") || file.type === "text/markdown") {
          finalContent = marked.parse(textContent, { async: false }) as string;
        } else {
          finalContent = `<p>${textContent
            .replace(/\n\n/g, "</p><p>")
            .replace(/\n/g, "<br/>")}</p>`;
        }
      } else {
        const result = await extractTextFromFile(
          projectId,
          file,
          auth.user.id_token
        );
        if (!result.text) {
          throw new Error("Failed to extract text from file.");
        }
        finalContent = `<p>${result.text
          .replace(/\n\n/g, "</p><p>")
          .replace(/\n/g, "<br/>")}</p>`;
      }

      const token = auth.user.id_token;
      const newChapter = await fetchApi<Chapter>(
        `/projects/${projectId}/chapters`,
        {
          method: "POST",
          body: JSON.stringify({
            title: title,
            content: finalContent,
            // Add to the end of the structure by default
            append_to_structure: true,
          }),
        },
        token
      );

      if (!newChapter) {
        throw new Error("Invalid response from server when creating chapter.");
      }

      setChapters((prevChapters) => {
        const updatedChapters = [...prevChapters, newChapter];
        return updatedChapters.sort(
          (a, b) =>
            (a.chapter_number ?? Infinity) - (b.chapter_number ?? Infinity)
        );
      });

      // Don't automatically select the chapter when batch importing
      if (!isBatchImporting) {
        handleSelectChapter(newChapter.id, token);
        toast.success(`Successfully imported and created chapter "${title}"`);
      }

      return newChapter;
    } catch (error) {
      console.error("File import error:", error);
      const message = error instanceof Error ? error.message : "Unknown error";
      setError(`Failed to import file: ${message}`);
      if (!isBatchImporting) {
        toast.error("Import failed. Please try again.");
      }
      throw error;
    } finally {
      if (!isBatchImporting) {
        setIsImporting(false);
      }
    }
  };

  const handleFileImport = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const validTypes = [
      "text/plain",
      "text/markdown",
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/rtf",
      "text/rtf",
      "application/epub+zip",
    ];

    // Check if we have multiple files
    if (files.length > 1) {
      setIsBatchImporting(true);
      setTotalFiles(files.length);
      setProcessedFiles(0);
      setUploadProgress(0);

      const validFiles: File[] = [];
      const invalidFiles: string[] = [];

      // First validate all files
      Array.from(files).forEach((file) => {
        const isValidExtension = /\.(txt|md|pdf|docx|rtf|epub)$/i.test(
          file.name
        );
        const isValidMime = validTypes.includes(file.type);

        if (isValidMime || isValidExtension) {
          validFiles.push(file);
        } else {
          invalidFiles.push(file.name);
        }
      });

      // Show warning for invalid files
      if (invalidFiles.length > 0) {
        toast.warning(
          `${invalidFiles.length} files were skipped due to unsupported format.`
        );
      }

      // If no valid files, stop processing
      if (validFiles.length === 0) {
        setIsBatchImporting(false);
        event.target.value = "";
        return;
      }

      // Process all valid files
      let successCount = 0;
      let failCount = 0;

      try {
        // Process files sequentially
        for (let i = 0; i < validFiles.length; i++) {
          try {
            await importFileAsNewChapter(validFiles[i]);
            successCount++;
          } catch (error) {
            console.error(`Error importing ${validFiles[i].name}:`, error);
            failCount++;
          }

          // Update progress
          setProcessedFiles(i + 1);
          setUploadProgress(Math.round(((i + 1) / validFiles.length) * 100));
        }

        // Summary notification
        toast.success(`Successfully imported ${successCount} chapters`);
        if (failCount > 0) {
          toast.error(`Failed to import ${failCount} files`);
        }
      } catch (error) {
        console.error("Batch import error:", error);
        toast.error("Error during batch import");
      } finally {
        setIsBatchImporting(false);
        setIsImporting(false);
        event.target.value = "";
      }
    } else {
      // Single file import (existing functionality)
      const file = files[0];

      const isValidExtension = /\.(txt|md|pdf|docx|rtf|epub)$/i.test(file.name);
      const isValidMime = validTypes.includes(file.type);

      if (!isValidMime && !isValidExtension) {
        setError(
          `Invalid file type. Supported formats: TXT, MD, PDF, DOCX, RTF, EPUB.`
        );
        toast.error("Invalid file type.");
        event.target.value = "";
        return;
      }

      importFileAsNewChapter(file);
      event.target.value = "";
    }
  };

  const handleTextAction = async (action: string, customPrompt?: string) => {
    if (!editorRef.current || !selectedChapter) return;
    const { from, to } = editorRef.current.state.selection;
    const selectedText = editorRef.current.state.doc.textBetween(from, to);

    if (!selectedText) {
      toast.info("Please select text to perform an action.");
      return;
    }

    setIsActionLoading(true);
    const toastId = toast.loading(`Performing action: ${action}...`);

    try {
      const response = await fetchApi<{ modified_text: string }>(
        `/projects/${projectId}/chapters/${selectedChapter.id}/text-action`,
        {
          method: "POST",
          body: JSON.stringify({
            action,
            selected_text: selectedText,
            full_chapter_content: currentContent,
            custom_prompt: customPrompt,
          }),
        },
        auth.user?.id_token
      );

      editorRef.current.chain().focus().deleteSelection().insertContent(response.modified_text).run();
      toast.success("Text successfully modified.", { id: toastId });
    } catch (error) {
      console.error(`Error during ${action}:`, error);
      const message = error instanceof Error ? error.message : "Unknown error";
      toast.error(`Action failed: ${message}`, { id: toastId });
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleExport = async (format: "txt" | "html" | "md" | "pdf") => {
    if (format === "pdf") {
      if (chapters.length === 0) {
        alert("No chapters to export.");
        return;
      }

      try {
        const doc = new jsPDF();
        let yPosition = 20;

        doc.setFontSize(20);
        doc.text("Project Chapters", 105, yPosition, { align: "center" });
        yPosition += 30;
        doc.setFontSize(12);

        for (const chapter of chapters) {
          doc.setFont("helvetica", "bold");
          const chapterTitle =
            chapter.title ||
            (chapter.chapter_number !== undefined
              ? `Chapter ${chapter.chapter_number}`
              : "Untitled Chapter");
          doc.text(chapterTitle, 15, yPosition);
          doc.setFont("helvetica", "normal");
          yPosition += 10;

          let content = chapter.content;
          if (!content) {
            const token = auth.user?.id_token;
            if (!token) {
              throw new Error("Authentication token missing for PDF export.");
            }
            const chapterData = await fetchApi<Chapter>(
              `/projects/${projectId}/chapters/${chapter.id}`,
              {},
              token
            );
            content = chapterData.content || "";
          }

          const plainText = content
            .replace(/<\/p>\s*<p>/gi, "\n\n")
            .replace(/<br\s*\/?>/gi, "\n")
            .replace(/<[^>]+>/g, "");

          const lines = doc.splitTextToSize(plainText, 180);
          doc.text(lines, 15, yPosition);
          yPosition += lines.length * 7 + 15;

          if (yPosition > 270) {
            doc.addPage();
            yPosition = 20;
          }
        }

        doc.save(`project_${projectId}_chapters.pdf`);
      } catch (error) {
        console.error("Failed to generate PDF:", error);
        setError("Failed to generate PDF. Please try again.");
      }
      return;
    }

    if (!selectedChapter) {
      alert("Please select a chapter to export in this format.");
      return;
    }

    let contentToExport = currentContent;
    let fileExtension = format;
    let mimeType = "text/html";

    if (format === "txt") {
      contentToExport = contentToExport
        .replace(/<\/p>\s*<p>/gi, "\n\n")
        .replace(/<br\s*\/?>/gi, "\n")
        .replace(/<[^>]+>/g, "");
      fileExtension = "txt";
      mimeType = "text/plain";
    } else if (format === "md") {
      try {
        const turndownService = new TurndownService();
        contentToExport = turndownService.turndown(currentContent);
        fileExtension = "md";
        mimeType = "text/markdown";
      } catch (error) {
        console.error("Markdown conversion error:", error);
        setError(
          "Failed to convert to Markdown. Please try again or use another format."
        );
        return;
      }
    }

    const blob = new Blob([contentToExport], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const fileName = `${
      selectedChapter.title || "chapter"
    }.${fileExtension}`.replace(/[^a-z0-9.\-_]/gi, "_");
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleExtractCodexItems = async () => {
    if (!selectedChapter || !auth.user?.id_token) return;

    const toastId = toast.loading(
      "Extracting codex items from this chapter..."
    );
    setIsExtracting(true);
    setError(null);
    const token = auth.user.id_token;

    try {
      const result = await fetchApi<{ items: Record<string, unknown>[] }>(
        `/projects/${projectId}/chapters/extract-from-chapters`,
        {
          method: "POST",
          body: JSON.stringify({
            chapter_ids: [selectedChapter.id],
          }),
        },
        token
      );

      if (!result?.items) {
        throw new Error("Invalid response from server");
      }

      toast.success(
        `Successfully extracted ${result.items.length} codex items from this chapter.`,
        { id: toastId }
      );
    } catch (error) {
      console.error("Error extracting codex items:", error);
      const message =
        error instanceof Error ? error.message : "An unknown error occurred.";
      toast.error(`Failed to extract codex items: ${message}`, { id: toastId });
    } finally {
      setIsExtracting(false);
    }
  };

  const handleProactiveAssist = async () => {
    if (!auth.user?.id_token) return;
    setIsAssistantLoading(true);

    const toastId = toast.loading("Analyzing recent content...");

    let recentChaptersContent = "";
    try {
      // Fetch the most recent 3 chapters that might have content
      const recentChapterMetas = chapters.slice(-3);
      const chapterPromises = recentChapterMetas.map((c) =>
        fetchApi<Chapter>(
          `/projects/${projectId}/chapters/${c.id}`,
          {},
          auth.user?.id_token
        )
      );
      const recentFullChapters = await Promise.all(chapterPromises);
      recentChaptersContent = recentFullChapters
        .map((c) => c.content || "")
        .join("\n\n");
      toast.success("Analysis complete. Getting suggestions...", {
        id: toastId,
      });
    } catch (error) {
      console.error("Failed to fetch recent chapter content:", error);
      toast.error(
        "Could not load recent chapter content for proactive assistance.",
        { id: toastId }
      );
      setIsAssistantLoading(false);
      return;
    }

    try {
      const response = await fetchApi<{ suggestions: ProactiveSuggestion[] }>(
        `/projects/${projectId}/proactive-assist`,
        {
          method: "POST",
          body: JSON.stringify({
            recent_chapters_content: recentChaptersContent,
            notepad_content: notepadContent,
          }),
        },
        auth.user.id_token
      );
      setProactiveSuggestions(response.suggestions);
      toast.success(
        `Received ${response.suggestions.length} new suggestion(s).`,
        { id: toastId }
      );
    } catch (error) {
      console.error("Error getting proactive suggestions:", error);
      toast.error("Failed to get suggestions from the assistant.", {
        id: toastId,
      });
    } finally {
      setIsAssistantLoading(false);
    }
  };

  const isLoading = isLoadingChapters;

  // Toggle notepad visibility
  const toggleNotepad = () => {
    setIsNotepadVisible((prev) => !prev);
  };

  // Add a function to collect all chapter IDs in a folder recursively
  const collectChapterIds = (
    items: StructureItem[],
    folderId: string
  ): string[] => {
    const chapterIds: string[] = [];

    const processItems = (
      structureItems: StructureItem[],
      currentFolderId: string
    ) => {
      for (const item of structureItems) {
        if (item.type === "folder") {
          if (item.id === currentFolderId) {
            // If this is the target folder, collect all chapter IDs within it
            collectAllChaptersInFolder(item.children, chapterIds);
            return true; // Found and processed the folder
          }

          // Check this folder's children recursively
          if (processItems(item.children, currentFolderId)) {
            return true; // Found in a child folder
          }
        }
      }
      return false; // Folder not found in this branch
    };

    const collectAllChaptersInFolder = (
      items: StructureItem[],
      ids: string[]
    ) => {
      for (const item of items) {
        if (item.type === "chapter") {
          ids.push(item.id);
        } else if (item.type === "folder") {
          collectAllChaptersInFolder(item.children, ids);
        }
      }
    };

    processItems(items, folderId);
    return chapterIds;
  };

  // Add a function to extract codex items from a folder
  const handleExtractFolderItems = async (folderId: string) => {
    if (!auth.user?.id_token || !projectStructure) return;

    const chapterIds = collectChapterIds(
      projectStructure.project_structure,
      folderId
    );

    if (chapterIds.length === 0) {
      toast.error("No chapters found in this folder.");
      return;
    }

    setIsExtracting(true);

    const toastId = toast.loading(
      `Extracting codex items from ${chapterIds.length} chapters...`
    );

    try {
      const result = await fetchApi<{ items: Record<string, unknown>[] }>(
        `/projects/${projectId}/chapters/extract-from-chapters`,
        {
          method: "POST",
          body: JSON.stringify({
            chapter_ids: chapterIds,
          }),
        },
        auth.user.id_token
      );

      if (!result?.items) {
        throw new Error("Invalid response from server");
      }

      toast.success(
        `Successfully extracted ${result.items.length} codex items from ${chapterIds.length} chapters.`,
        { id: toastId }
      );
    } catch (error) {
      console.error("Error extracting codex items from folder:", error);
      const message =
        error instanceof Error ? error.message : "An unknown error occurred.";
      toast.error(`Failed to extract codex items: ${message}`, { id: toastId });
    } finally {
      setIsExtracting(false);
    }
  };

  return (
    <div
      className={`flex flex-1 overflow-hidden bg-background ${
        error ? "pt-12" : ""
      }`}
    >
      <ResizablePanelGroup direction="horizontal" className="flex flex-1">
        <ResizablePanel defaultSize={20} minSize={15} maxSize={30}>
          <aside className="h-full w-full border-r border-border bg-card p-4 overflow-y-auto flex flex-col shrink-0">
            <div className="flex justify-between items-center mb-4 flex-wrap">
              <h2 className="text-lg font-semibold flex items-center gap-2 text-foreground">
                <List className="h-5 w-5 text-primary" /> Chapters
              </h2>
              <div className="flex items-center space-x-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-muted-foreground hover:text-accent-foreground hover:bg-accent"
                  onClick={handleImportClick}
                  disabled={isLoadingChapterContent || isImporting}
                  title="Import Chapter(s) (TXT, MD, PDF, DOCX, RTF, EPUB)"
                >
                  {isImporting ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Upload className="h-5 w-5" />
                  )}
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-muted-foreground hover:text-accent-foreground hover:bg-accent"
                      disabled={isLoadingChapters || chapters.length === 0}
                      title="Export Chapter"
                    >
                      <Download className="h-5 w-5" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onClick={() => handleExport("txt")}
                      disabled={!selectedChapter}
                    >
                      Export as Text (.txt)
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => handleExport("html")}
                      disabled={!selectedChapter}
                    >
                      Export as HTML (.html)
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => handleExport("md")}
                      disabled={!selectedChapter}
                    >
                      Export as Markdown (.md)
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleExport("pdf")}>
                      Export All Chapters as PDF
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-muted-foreground hover:text-accent-foreground hover:bg-accent"
                  onClick={toggleAddChapterInput}
                  disabled={isLoading || isAddingChapter}
                  title="Add New Chapter"
                >
                  <Plus className="h-5 w-5" />
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-muted-foreground hover:text-accent-foreground hover:bg-accent"
                      disabled={isSaving || isExtracting}
                      title="AI Assistant"
                    >
                      {isExtracting ? (
                        <Loader2 className="h-5 w-5 animate-spin" />
                      ) : (
                        <Wand2 className="h-5 w-5" />
                      )}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onClick={handleExtractCodexItems}
                      disabled={isExtracting || !selectedChapter}
                    >
                      {isExtracting ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Extracting...
                        </>
                      ) : (
                        "Extract Codex Items from Chapter"
                      )}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        if (projectStructure?.project_structure?.length) {
                          const allChapterIds: string[] = [];
                          const collectAllIds = (items: StructureItem[]) => {
                            for (const item of items) {
                              if (item.type === "chapter") {
                                allChapterIds.push(item.id);
                              } else if (item.type === "folder") {
                                collectAllIds(item.children);
                              }
                            }
                          };
                          collectAllIds(projectStructure.project_structure);

                          if (allChapterIds.length === 0) {
                            toast.error("No chapters found in the project.");
                            return;
                          }

                          setIsExtracting(true);
                          const toastId = toast.loading(
                            `Extracting codex items from all ${allChapterIds.length} chapters...`
                          );

                          fetchApi<{ items: Record<string, unknown>[] }>(
                            `/projects/${projectId}/chapters/extract-from-chapters`,
                            {
                              method: "POST",
                              body: JSON.stringify({
                                chapter_ids: allChapterIds,
                              }),
                            },
                            auth.user?.id_token
                          )
                            .then((result) => {
                              if (!result?.items) {
                                throw new Error("Invalid response from server");
                              }
                              toast.success(
                                `Successfully extracted ${result.items.length} codex items from all chapters.`,
                                { id: toastId }
                              );
                            })
                            .catch((error) => {
                              console.error(
                                "Error extracting codex items:",
                                error
                              );
                              const message =
                                error instanceof Error
                                  ? error.message
                                  : "An unknown error occurred.";
                              toast.error(
                                `Failed to extract codex items: ${message}`,
                                { id: toastId }
                              );
                            })
                            .finally(() => {
                              setIsExtracting(false);
                            });
                        } else {
                          toast.error("Project structure not loaded.");
                        }
                      }}
                      disabled={
                        isExtracting ||
                        !projectStructure?.project_structure?.length
                      }
                    >
                      {isExtracting ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Extracting...
                        </>
                      ) : (
                        "Extract Codex Items from All Chapters"
                      )}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
              <input
                type="file"
                ref={importFileInputRef}
                onChange={handleFileImport}
                accept=".txt,.md,.pdf,.docx,.rtf,.epub,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/rtf,text/rtf,application/epub+zip"
                style={{ display: "none" }}
                multiple
              />
            </div>
            <div className="mb-4 text-xs text-muted-foreground bg-muted p-2 rounded-md">
              <p>
                Chapters are displayed in the order defined in the Story
                Outliner.
              </p>
              <p className="mt-1">
                Use the Outliner to organize chapters into folders or reorder
                them.
              </p>
            </div>
            {showAddChapterInput && (
              <div className="mb-4 space-y-2 border-b border-border pb-4">
                <Input
                  type="text"
                  placeholder="New chapter title..."
                  value={newChapterTitle}
                  onChange={(e) => setNewChapterTitle(e.target.value)}
                  className="h-9 text-sm"
                  disabled={isAddingChapter}
                  autoFocus
                />
                <div className="flex justify-end gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={toggleAddChapterInput}
                    disabled={isAddingChapter}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleAddChapter}
                    disabled={isAddingChapter || !newChapterTitle.trim()}
                    className="min-w-[60px]"
                  >
                    {isAddingChapter ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      "Add"
                    )}
                  </Button>
                </div>
              </div>
            )}
            {isLoadingChapters ? (
              <div className="flex justify-center items-center h-40">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : (
              <div className="space-y-1">
                {projectStructure ? (
                  <ChapterStructureRenderer
                    items={projectStructure.project_structure || []}
                    handleSelectChapter={handleSelectChapter}
                    selectedChapter={selectedChapter}
                    isLoadingChapterContent={isLoadingChapterContent}
                    isDeleting={isDeleting}
                    isAddingChapter={isAddingChapter}
                    authToken={auth.user?.id_token}
                    handleExtractFolderItems={handleExtractFolderItems}
                    isExtracting={isExtracting}
                  />
                ) : (
                  chapters.map((chapter) => (
                    <button
                      key={chapter.id}
                      onClick={() =>
                        handleSelectChapter(chapter.id, auth.user?.id_token)
                      }
                      disabled={
                        (isLoadingChapterContent &&
                          selectedChapter?.id === chapter.id) ||
                        isDeleting ||
                        isAddingChapter
                      }
                      className={`block w-full text-left px-3 py-2 rounded-md text-sm truncate cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-wait
                                 ${
                                   selectedChapter?.id === chapter.id
                                     ? isLoadingChapterContent
                                       ? "text-muted-foreground cursor-wait"
                                       : "bg-primary text-primary-foreground"
                                     : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                                 }`}
                      title={
                        chapter.title ||
                        `Chapter ${chapter.chapter_number || "N/A"}`
                      }
                    >
                      {isLoadingChapterContent &&
                        selectedChapter?.id === chapter.id && (
                          <Loader2 className="h-4 w-4 animate-spin inline mr-2" />
                        )}
                      {chapter.title ||
                        `Chapter ${chapter.chapter_number || "N/A"}`}
                    </button>
                  ))
                )}
              </div>
            )}
          </aside>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize={80}>
          <div className="h-full flex flex-col">
            <main className="flex-1 p-6 overflow-y-auto overflow-x-hidden bg-background flex flex-col">
              {proactiveSuggestions.length > 0 && (
                <div className="proactive-assistant-panel bg-card border-b border-border p-4 mb-4 rounded-md">
                  <h3 className="text-lg font-semibold mb-2">
                    Proactive Assistant
                  </h3>
                  <ul>
                    {proactiveSuggestions.map((suggestion, index) => (
                      <li
                        key={index}
                        className="mb-2 p-2 border border-border rounded-md"
                      >
                        <p>{suggestion.suggestion}</p>
                        <p className="text-sm text-muted-foreground">
                          Confidence: {suggestion.confidence.toFixed(2)}
                        </p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {selectedChapter ? (
                <>
                  <div className="flex justify-between items-center mb-4 sticky top-0 bg-background py-2 z-10 border-b border-border">
                    <div className="flex items-center gap-2 flex-1 min-w-0 mr-2">
                      {isEditingTitle ? (
                        <Input
                          type="text"
                          value={currentChapterTitle}
                          onChange={(e) =>
                            setCurrentChapterTitle(e.target.value)
                          }
                          onBlur={() => setIsEditingTitle(false)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              setIsEditingTitle(false);
                            }
                            if (e.key === "Escape") {
                              setCurrentChapterTitle(selectedChapter.title);
                              setIsEditingTitle(false);
                            }
                          }}
                          className="text-lg font-semibold h-9 flex-1"
                          autoFocus
                          disabled={isSaving || isLoadingChapterContent}
                        />
                      ) : (
                        <h2
                          className="text-lg font-semibold truncate text-foreground flex-1 min-w-0"
                          title={currentChapterTitle}
                        >
                          {currentChapterTitle ||
                            `Chapter ${
                              selectedChapter.chapter_number || "N/A"
                            }`}
                        </h2>
                      )}
                      {!isEditingTitle && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setIsEditingTitle(true)}
                          disabled={isLoadingChapterContent || isSaving}
                          className="text-muted-foreground hover:text-accent-foreground hover:bg-accent shrink-0"
                          title="Edit Title"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Button
                        variant={isNotepadVisible ? "secondary" : "ghost"}
                        size="icon"
                        onClick={toggleNotepad}
                        title={
                          isNotepadVisible ? "Hide Notepad" : "Show Notepad"
                        }
                        className="text-muted-foreground hover:text-accent-foreground"
                      >
                        <StickyNote className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={handleDeleteChapter}
                        disabled={isDeleting || isLoadingChapterContent}
                        title="Delete Current Chapter"
                      >
                        {isDeleting ? (
                          <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                        ) : (
                          <Trash2 className="h-4 w-4 mr-1.5" />
                        )}
                        {isDeleting ? "Deleting..." : "Delete"}
                      </Button>
                      <Button
                        variant="default"
                        size="sm"
                        onClick={handleSaveChanges}
                        disabled={isSaving || isLoadingChapterContent}
                        title="Save Changes to Chapter"
                      >
                        {isSaving ? (
                          <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                        ) : (
                          <Save className="h-4 w-4 mr-1.5" />
                        )}
                        {isSaving ? "Saving..." : "Save"}
                      </Button>
                    </div>
                  </div>
                  <div className="flex-1 flex flex-col min-h-0">
                    {isLoadingChapterContent ? (
                      <div className="flex-1 flex justify-center items-center">
                        <Loader2 className="h-8 w-8 animate-spin text-primary" />
                      </div>
                    ) : (
                      <RichTextEditor
                        ref={editorRef}
                        content={currentContent}
                        onChange={handleContentChange}
                        onSave={handleSaveChanges}
                        editable={!isSaving}
                        codexItems={codexItems}
                        onTextAction={handleTextAction}
                        isActionLoading={isActionLoading}
                      />
                    )}
                  </div>
                </>
              ) : (
                <div className="flex-1 flex justify-center items-center">
                  {isLoading ? (
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  ) : (
                    <p className="text-muted-foreground">
                      {chapters.length > 0
                        ? "Select a chapter to start editing."
                        : "Create a chapter to begin."}
                    </p>
                  )}
                </div>
              )}
            </main>

            {/* Notepad as a slide-out panel */}
            {isNotepadVisible && (
              <div className="border-t border-border h-[300px]">
                <Notepad
                  notepadContent={notepadContent}
                  setNotepadContent={setNotepadContent}
                  onProactiveAssist={handleProactiveAssist}
                  isProactiveAssistLoading={isAssistantLoading}
                />
              </div>
            )}
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>

      {error && (
        <div className="absolute top-0 left-0 right-0 z-20 p-3 bg-destructive/90 border-b border-destructive text-destructive-foreground text-sm flex items-center justify-between gap-2 shadow-lg">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            <span>{error}</span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setError(null)}
            className="text-destructive-foreground hover:bg-destructive/20"
          >
            Close
          </Button>
        </div>
      )}

      {/* Batch import progress indicator */}
      {isBatchImporting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-[300px]">
            <CardHeader>
              <CardTitle>Importing Files...</CardTitle>
            </CardHeader>
            <CardContent>
              <Progress value={uploadProgress} className="h-2 mb-2" />
              <p className="text-sm text-center">
                {processedFiles} of {totalFiles} files ({uploadProgress}%)
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

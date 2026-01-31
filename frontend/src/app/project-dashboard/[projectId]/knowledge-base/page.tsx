"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import {
  PlusCircle,
  Upload,
  Search,
  Edit,
  Trash2,
  Download,
  MoreVertical,
  FileText,
  FileJson,
  FileSpreadsheet,
  X,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { fetchApi, fetchFileApi } from "@/lib/api";
import { toast } from "sonner";
import { AddManualEntryModal } from "@/components/AddManualEntryModal";
import { useAuth } from "@/components/MockAuthProvider";
import { KnowledgeBaseItemDisplay } from "@/types/knowledgebaseDisplay";
import { Progress } from "@/components/ui/progress";
import { Checkbox } from "@/components/ui/checkbox";

// Define expected response structure from batch upload endpoint
interface BatchUploadResponse {
  message: string;
  successful: number;
  failed: number;
  items: Array<{
    filename: string;
    success: boolean;
    error?: string;
    id?: string;
  }>;
}

export default function KnowledgeBasePage() {
  const params = useParams();
  const projectId = params?.projectId as string;
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const [items, setItems] = useState<KnowledgeBaseItemDisplay[]>([]);
  const [isAddEntryModalOpen, setIsAddEntryModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [filteredItems, setFilteredItems] = useState<
    KnowledgeBaseItemDisplay[]
  >([]);
  const [editingItem, setEditingItem] =
    useState<KnowledgeBaseItemDisplay | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [isBatchUploading, setIsBatchUploading] = useState(false);
  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const auth = useAuth();

  const fetchKnowledgeBaseItems = useCallback(
    async (token?: string | null) => {
      if (!projectId) return;

      const authToken = token || auth.user?.id_token;
      if (!authToken) {
        setError("Authentication required to fetch knowledge base items.");
        setIsLoading(false);
        return;
      }

      try {
        setIsLoading(true);
        const response = await fetchApi<KnowledgeBaseItemDisplay[]>(
          `/projects/${projectId}/knowledge-base/`,
          {},
          authToken
        );
        setItems(response);
        applySearchFilter(response, searchTerm);
        setError(null);
      } catch (err) {
        console.error("Failed to fetch knowledge base items:", err);
        const message =
          err instanceof Error ? err.message : "An unknown error occurred";
        setError(`Failed to load knowledge base: ${message}`);
        toast.error(`Error loading knowledge base: ${message}`);
      } finally {
        setIsLoading(false);
      }
    },
    [projectId, auth.user?.id_token, searchTerm]
  );

  useEffect(() => {
    fetchKnowledgeBaseItems();
  }, [fetchKnowledgeBaseItems]);

  const applySearchFilter = (
    items: KnowledgeBaseItemDisplay[],
    term: string
  ) => {
    if (!term.trim()) {
      setFilteredItems(items);
      return;
    }

    const lowercaseTerm = term.toLowerCase();
    const filtered = items.filter(
      (item) =>
        item.name.toLowerCase().includes(lowercaseTerm) ||
        (item.content?.toLowerCase() || "").includes(lowercaseTerm)
    );
    setFilteredItems(filtered);
  };

  useEffect(() => {
    applySearchFilter(items, searchTerm);
  }, [items, searchTerm]);

  const handleSelectItem = (id: string, isSelected: boolean) => {
    setSelectedItems((prev) =>
      isSelected ? [...prev, id] : prev.filter((itemId) => itemId !== id)
    );
  };

  const handleSelectAll = (isSelected: boolean) => {
    if (isSelected) {
      setSelectedItems(filteredItems.map((item) => item.id));
    } else {
      setSelectedItems([]);
    }
  };

  const handleFileClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    if (!auth.user?.id_token) {
      toast.error("Authentication required to upload files");
      return;
    }

    try {
      // Multiple files selected - use batch upload
      if (files.length > 1) {
        setIsBatchUploading(true);
        setUploadProgress(0);
        const formData = new FormData();

        // Add all files to the form data
        Array.from(files).forEach((file) => {
          formData.append("files", file);
        });

        // Start progress simulation for better UX
        const progressInterval = setInterval(() => {
          setUploadProgress((prev) => Math.min(95, prev + 5));
        }, 300);

        // Upload to batch endpoint
        const response = await fetchApi<BatchUploadResponse>(
          `/projects/${projectId}/knowledge-base/batch`,
          {
            method: "POST",
            body: formData,
          },
          auth.user?.id_token
        );

        // Complete the progress
        clearInterval(progressInterval);
        setUploadProgress(100);

        toast.success(`Successfully uploaded ${response.successful} files`);
        if (response.failed > 0) {
          toast.warning(`Failed to upload ${response.failed} files`);
        }

        fetchKnowledgeBaseItems(auth.user?.id_token);
      }
      // Single file - use existing endpoint
      else {
        setIsUploading(true);
        setUploadProgress(0);
        const file = files[0];
        const formData = new FormData();
        formData.append("file", file);
        formData.append(
          "metadata_str",
          JSON.stringify({ filename: file.name })
        );

        // Start progress simulation for better UX
        const progressInterval = setInterval(() => {
          setUploadProgress((prev) => Math.min(95, prev + 5));
        }, 300);

        await fetchApi(
          `/projects/${projectId}/knowledge-base/`,
          {
            method: "POST",
            body: formData,
          },
          auth.user?.id_token
        );

        // Complete the progress
        clearInterval(progressInterval);
        setUploadProgress(100);

        toast.success("File uploaded successfully");
        fetchKnowledgeBaseItems(auth.user?.id_token);
      }
    } catch (error) {
      console.error("Failed to upload file:", error);
      toast.error("Failed to upload file");
    } finally {
      setIsUploading(false);
      setIsBatchUploading(false);
      setUploadProgress(0);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleDeleteItem = async (itemId: string) => {
    if (!auth.user?.id_token) {
      toast.error("Authentication required to delete items");
      return;
    }

    try {
      await fetchApi(
        `/projects/${projectId}/knowledge-base/${itemId}`,
        {
          method: "DELETE",
        },
        auth.user?.id_token
      );
      toast.success("Item deleted successfully");
      fetchKnowledgeBaseItems(auth.user?.id_token);
      if (editingItem?.id === itemId) {
        setEditingItem(null);
      }
    } catch (err) {
      console.error("Failed to delete item:", err);
      const message =
        err instanceof Error ? err.message : "An unknown error occurred";
      toast.error(`Failed to delete item: ${message}`);
    }
  };

  const handleDeleteSelected = async () => {
    if (!auth.user?.id_token) {
      toast.error("Authentication required to delete items.");
      return;
    }
    if (selectedItems.length === 0) {
      toast.info("No items selected for deletion.");
      return;
    }

    try {
      await fetchApi(
        `/projects/${projectId}/knowledge-base/batch-delete`,
        {
          method: "DELETE",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ embedding_ids: selectedItems }),
        },
        auth.user.id_token
      );

      toast.success(`Successfully deleted ${selectedItems.length} item(s).`);
      setSelectedItems([]);
      fetchKnowledgeBaseItems(auth.user.id_token);
    } catch (err) {
      console.error("Failed to delete selected items:", err);
      const message =
        err instanceof Error ? err.message : "An unknown error occurred";
      toast.error(`Failed to delete selected items: ${message}`);
    }
  };

  const handleExportAll = async (format: "csv" | "json" | "txt") => {
    if (!auth.user?.id_token) {
      toast.error("Authentication required to export data.");
      return;
    }

    toast.info(`Exporting all items as ${format.toUpperCase()}...`);

    try {
      const { blob } = await fetchFileApi(
        `/projects/${projectId}/knowledge-base/export?format=${format}`,
        {
          method: "GET",
        },
        auth.user.id_token
      );

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = `knowledge-base-export.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast.success("Export completed successfully.");
    } catch (err) {
      console.error(`Failed to export as ${format}:`, err);
      const message =
        err instanceof Error ? err.message : "An unknown error occurred";
      toast.error(`Export failed: ${message}`);
    }
  };

  const exportItemAsFile = async (item: KnowledgeBaseItemDisplay) => {
    if (!auth.user?.id_token) {
      toast.error("Authentication required to export file");
      return;
    }

    try {
      const { blob } = await fetchFileApi(
        `/projects/${projectId}/knowledge-base/export?embedding_id=${item.id}&format=txt`,
        {
          method: "GET",
        },
        auth.user?.id_token
      );

      // Create a download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = `${item.name || "export"}.txt`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast.success("File exported successfully");
    } catch (err) {
      console.error("Failed to export file:", err);
      const message =
        err instanceof Error ? err.message : "An unknown error occurred";
      toast.error(`Failed to export file: ${message}`);
    }
  };

  if (!projectId) {
    return (
      <div className="flex items-center justify-center h-full">
        Invalid Project ID.
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4 md:p-6 lg:p-8">
      <header className="flex flex-col md:flex-row justify-between md:items-center mb-6 gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Knowledge Base</h1>
          <p className="text-muted-foreground">
            Manage your project&apos;s knowledge base items.
          </p>
        </div>
      </header>

      <div className="flex flex-col space-y-4 md:flex-row md:space-y-0 md:space-x-4 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search knowledge base..."
            className="pl-10"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="flex space-x-2">
          {selectedItems.length > 0 && (
            <Button variant="destructive" onClick={handleDeleteSelected}>
              <Trash2 className="mr-2 h-4 w-4" />
              Delete ({selectedItems.length})
            </Button>
          )}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">
                <PlusCircle className="mr-2 h-4 w-4" />
                Add Item
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleFileClick}>
                <Upload className="mr-2 h-4 w-4" />
                Upload File(s)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setIsAddEntryModalOpen(true)}>
                <Edit className="mr-2 h-4 w-4" />
                Manual Entry
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">
                <Download className="mr-2 h-4 w-4" />
                Export All
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleExportAll("txt")}>
                <FileText className="mr-2 h-4 w-4" />
                Export as TXT
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExportAll("json")}>
                <FileJson className="mr-2 h-4 w-4" />
                Export as JSON
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExportAll("csv")}>
                <FileSpreadsheet className="mr-2 h-4 w-4" />
                Export as CSV
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <input
            type="file"
            className="sr-only"
            ref={fileInputRef}
            onChange={handleFileUpload}
            disabled={isLoading || isUploading}
            multiple
          />
        </div>
      </div>

      {error && (
        <div className="p-4 mb-4 text-sm text-red-700 bg-red-100 rounded-lg">
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center p-8">
          <div className="flex flex-col items-center space-y-2">
            <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-primary"></div>
            <p className="text-sm text-muted-foreground">
              Loading knowledge base...
            </p>
          </div>
        </div>
      ) : filteredItems.length > 0 ? (
        <>
          <div className="flex items-center gap-2 mb-4 p-2 rounded-md bg-muted/50">
            <Checkbox
              id="select-all"
              checked={
                selectedItems.length > 0 &&
                selectedItems.length === filteredItems.length
              }
              onCheckedChange={handleSelectAll}
              disabled={filteredItems.length === 0}
            />
            <label
              htmlFor="select-all"
              className="text-sm font-medium text-muted-foreground"
            >
              Select All ({selectedItems.length} selected)
            </label>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredItems.map((item) => (
              <Card
                key={item.id}
                className={`transition-all duration-200 ease-in-out ${
                  selectedItems.includes(item.id)
                    ? "border-primary shadow-lg"
                    : "hover:border-muted-foreground/20"
                }`}
              >
                <CardHeader className="p-4 pb-2">
                  <div className="flex justify-between items-start gap-2">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <Checkbox
                        checked={selectedItems.includes(item.id)}
                        onCheckedChange={(checked) =>
                          handleSelectItem(item.id, !!checked)
                        }
                        onClick={(e) => e.stopPropagation()}
                        aria-label={`Select ${item.name}`}
                      />
                      <CardTitle
                        className="text-base truncate cursor-pointer"
                        onClick={() => setEditingItem(item)}
                      >
                        {item.name || "Untitled"}
                      </CardTitle>
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 shrink-0"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation();
                            exportItemAsFile(item);
                          }}
                        >
                          <Download className="mr-2 h-4 w-4" />
                          Export as .txt
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteItem(item.id);
                          }}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                  <CardDescription className="text-xs pl-10">
                    {item.created_at
                      ? new Date(item.created_at).toLocaleString()
                      : ""}
                  </CardDescription>
                </CardHeader>
                <CardContent
                  className="p-4 pt-0 pl-14 cursor-pointer"
                  onClick={() => setEditingItem(item)}
                >
                  <p className="text-sm text-muted-foreground line-clamp-3">
                    {item.content}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      ) : (
        <div className="flex flex-col items-center justify-center p-16 text-center border-2 border-dashed rounded-lg">
          <p className="mb-4 text-lg text-muted-foreground">
            {searchTerm
              ? "No items found matching your search."
              : "Your knowledge base is empty."}
          </p>
          <Button onClick={handleFileClick}>
            <Upload className="mr-2 h-4 w-4" />
            Upload Your First File
          </Button>
        </div>
      )}

      {/* Show detailed view when an item is selected */}
      {editingItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <Card className="w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
            <CardHeader className="pb-2">
              <div className="flex justify-between items-center">
                <CardTitle>{editingItem.name || "Untitled"}</CardTitle>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setEditingItem(null)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <CardDescription>
                {editingItem.created_at
                  ? new Date(editingItem.created_at).toLocaleString()
                  : ""}
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-auto flex-1">
              <pre className="text-sm whitespace-pre-wrap">
                {editingItem.content}
              </pre>
            </CardContent>
          </Card>
        </div>
      )}

      {isAddEntryModalOpen && (
        <AddManualEntryModal
          isOpen={isAddEntryModalOpen}
          onOpenChange={() => setIsAddEntryModalOpen(false)}
          onSubmit={async (content, metadata) => {
            if (!auth.user?.id_token) {
              toast.error("Authentication required to add entry");
              return;
            }
            try {
              await fetchApi(
                `/projects/${projectId}/knowledge-base/`,
                {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json",
                  },
                  body: JSON.stringify({
                    content_type_form: "manual_text",
                    text_content_form: content,
                    metadata_str_form: JSON.stringify(metadata),
                  }),
                },
                auth.user.id_token
              );
              toast.success("Manual entry added successfully");
              fetchKnowledgeBaseItems();
            } catch (error) {
              console.error("Failed to add manual entry:", error);
              toast.error("Failed to add manual entry");
              throw error; // Re-throw to let the modal know the submission failed
            }
          }}
        />
      )}

      {/* Upload progress indicator */}
      {(isUploading || isBatchUploading) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-[300px]">
            <CardHeader>
              <CardTitle>
                {isBatchUploading ? "Uploading Files..." : "Uploading File..."}
              </CardTitle>
              <CardDescription>
                Please wait while we process your files.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Progress value={uploadProgress} className="h-2 mb-2" />
              <p className="text-sm text-center text-muted-foreground">
                {uploadProgress}%
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

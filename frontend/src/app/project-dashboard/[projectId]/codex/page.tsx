"use client";

import React, { useState, useEffect, use } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Plus,
  Trash2,
  Loader2,
  Search,
  AlertTriangle,
  Edit,
  Wand2,
} from "lucide-react";
import { fetchApi } from "@/lib/api"; // Uncommented for delete functionality
import { CodexEntry, CodexItemType, WorldbuildingSubtype } from "@/types"; // Import shared type
import { CodexEntryForm } from "@/components/CodexEntryForm"; // Import the form component
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth
import { toast } from "sonner";


// Helper to format enum keys for display (Duplicate from form, consider moving to utils)
function formatEnumKey(key: string): string {
  // Find the key corresponding to the enum value
  const enumKey = (
    Object.keys(CodexItemType) as Array<keyof typeof CodexItemType>
  ).find((k) => CodexItemType[k] === key);
  if (!enumKey) return key; // Fallback if not found
  return enumKey
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/(?:^|\s)\S/g, (a) => a.toUpperCase());
}

// // Define the structure of a Codex entry (adjust based on backend)
// interface CodexEntry {
//     id: string;
//     title: string;
//     category?: string; // Example field
//     tags?: string[];   // Example field
//     content_summary?: string; // Example field
//     // Add other relevant fields: created_at, updated_at, etc.
// }

// // --- Helper Function to get Auth Token (Placeholder) ---
// const getAuthToken = (): string | null => {
//     console.warn("Codex Page: Auth token retrieval not implemented yet. API calls might fail.");
// // --- End Placeholder ---

export default function CodexPage(props: {
  params: Promise<{ projectId: string }>;
}) {
  const params = use(props.params);
  const { projectId } = params;
  const [codexEntries, setCodexEntries] = useState<CodexEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedEntryIds, setSelectedEntryIds] = useState<Set<string>>(
    new Set()
  );
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [entryToEdit, setEntryToEdit] = useState<CodexEntry | null>(null);
  const [isDeleting, setIsDeleting] = useState(false); // Added state for deleting
  const auth = useAuth(); // Use the hook
  // --- Add state for user subscription ---
  const [isProUser] = useState(true);
  const [userSubLoading, setUserSubLoading] = useState(false);
  // --- End state for user subscription ---

  useEffect(() => {
    // Move fetchCodexEntries inside useEffect
    const fetchCodexEntries = async (token: string | undefined) => {
      if (!token) {
        setError("Authentication token is missing.");
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetchApi<CodexEntry[]>(
          `/projects/${projectId}/codex-items`,
          {},
          token
        );

        // Use actual fetched data if endpoint works
        if (response && Array.isArray(response)) {
          setCodexEntries(response);
        } else {
          console.log(
            "Codex fetching endpoint might not be ready or returned unexpected data, using placeholder data."
          );
          // Add back the placeholder data
          setCodexEntries([
            {
              id: "1",
              name: "Character A",
              title: "Character A",
              description: "Main character description...",
              content: "Main character description...",
              type: CodexItemType.CHARACTER,
              tags: ["Protagonist", "Human"],
            },
            {
              id: "3",
              name: "Item Y",
              title: "Item Y",
              description: "An ancient powerful item...",
              content: "An ancient powerful item...",
              type: CodexItemType.ITEM,
              tags: ["Magic", "Artifact"],
            },
            {
              id: "4",
              name: "Ancient History",
              title: "Ancient History",
              description: "Details about the old times...",
              content: "Details about the old times...",
              type: CodexItemType.WORLDBUILDING,
              subtype: WorldbuildingSubtype.HISTORY,
              tags: ["Lore"],
            },
          ]);
        }
      } catch (err: unknown) {
        console.error("Failed to load codex entries:", err);
        const message =
          err instanceof Error ? err.message : "An unknown error occurred";
        setError(`Failed to load codex entries: ${message}`);
        setCodexEntries([]); // Clear entries on error
        // ... existing error handling ...
      } finally {
        setIsLoading(false);
      }
    };


    // Rest of useEffect remains the same
    if (!auth.isLoading && auth.isAuthenticated && auth.user?.id_token) {
      fetchCodexEntries(auth.user.id_token);
    } else if (!auth.isLoading && !auth.isAuthenticated) {
      setError("Authentication required to view codex.");
      setIsLoading(false);
      setUserSubLoading(false);
    }
  }, [projectId, auth.isLoading, auth.isAuthenticated, auth.user?.id_token]);

  const filteredEntries = codexEntries.filter(
    (entry) =>
      entry.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      entry.type?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      entry.tags?.some((tag) =>
        tag.toLowerCase().includes(searchTerm.toLowerCase())
      )
  );

  const handleAddEntry = () => {
    setEntryToEdit(null);
    setIsFormOpen(true);
  };

  const handleEntryAdded = (newEntry: CodexEntry) => {
    // Add the new entry to the start of the list for immediate visibility
    // Make sure the added entry has all fields needed for display (name, description, type, tags etc.)
    const displayEntry: CodexEntry = {
      id: newEntry.id,
      name: newEntry.name,
      title: newEntry.name, // Use name as title for display consistency
      description: newEntry.description,
      content: newEntry.description, // Use description as content for display consistency
      type: newEntry.type,
      subtype: newEntry.subtype,
      tags: newEntry.tags || [], // Ensure tags array exists
    };
    setCodexEntries((prevEntries) => [displayEntry, ...prevEntries]);
  };

  const handleEditClick = (entry: CodexEntry) => {
    setEntryToEdit(entry);
    setIsFormOpen(true);
  };

  const handleEntryUpdated = (updatedEntry: CodexEntry) => {
    setCodexEntries((prevEntries) =>
      prevEntries.map((entry) =>
        entry.id === updatedEntry.id ? updatedEntry : entry
      )
    );
    setEntryToEdit(null);
  };

  // Implemented Delete Handler
  const handleDeleteSelected = async () => {
    if (selectedEntryIds.size === 0) return;

    const count = selectedEntryIds.size;
    const confirmation = window.confirm(
      `Are you sure you want to delete ${count} selected ${count > 1 ? "entries" : "entry"
      }?`
    );

    if (!confirmation) return;
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to delete entries.");
      return;
    }

    setIsDeleting(true);
    setError(null);
    const token = auth.user.id_token; // Get token
    const idsToDelete = Array.from(selectedEntryIds);
    const failedDeletes: string[] = [];
    let successCount = 0;

    try {
      // Call delete endpoint for each selected ID
      for (const idToDelete of idsToDelete) {
        try {
          await fetchApi(
            `/projects/${projectId}/codex-items/${idToDelete}`, // Use single-item delete endpoint
            {
              method: "DELETE",
            },
            token
          );
          successCount++;
        } catch (loopError) {
          console.error(
            `Failed to delete codex item ${idToDelete}:`,
            loopError
          );
          failedDeletes.push(idToDelete);
        }
      }

      // Update state on success (filter out successfully deleted items)
      const successfullyDeletedIds = idsToDelete.filter(
        (id) => !failedDeletes.includes(id)
      );
      if (successfullyDeletedIds.length > 0) {
        setCodexEntries((prevEntries) =>
          prevEntries.filter(
            (entry) => !successfullyDeletedIds.includes(entry.id)
          )
        );
      }
      setSelectedEntryIds(new Set()); // Clear selection

      if (failedDeletes.length > 0) {
        setError(
          `Failed to delete ${failedDeletes.length} out of ${count} selected entries. Please try again.`
        );
        console.log("Failed IDs:", failedDeletes);
      } else {
        console.log(`${successCount} entries deleted successfully.`);
      }
    } catch (err: unknown) {
      console.error("Failed to delete codex entries:", err);
      const message =
        err instanceof Error ? err.message : "An unknown error occurred";
      setError(`Failed to delete entries: ${message}`);
    } finally {
      setIsDeleting(false);
    }
  };

  // Selection handling
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedEntryIds(new Set(filteredEntries.map((entry) => entry.id)));
    } else {
      setSelectedEntryIds(new Set());
    }
  };

  const handleSelectRow = (entryId: string, checked: boolean) => {
    const newSelectedIds = new Set(selectedEntryIds);
    if (checked) {
      newSelectedIds.add(entryId);
    } else {
      newSelectedIds.delete(entryId);
    }
    setSelectedEntryIds(newSelectedIds);
  };

  const isAllSelected =
    filteredEntries.length > 0 &&
    selectedEntryIds.size === filteredEntries.length;
  // const isIndeterminate = selectedEntryIds.size > 0 && selectedEntryIds.size < filteredEntries.length; // Placeholder for indeterminate checkbox state

  // Add this new function to handle extraction from all chapters
  const handleExtractFromAllChapters = async () => {
    if (!auth.user?.id_token) {
      toast.error("Authentication is required to perform this action.");
      return;
    }

    const toastId = toast.loading(
      "Extracting codex items from all chapters..."
    );
    setIsLoading(true);
    setError(null);
    const token = auth.user.id_token;

    try {
      const result = await fetchApi<{ items: unknown[] }>(
        `/projects/${projectId}/chapters/extract-all-codex-items`,
        {
          method: "POST",
        },
        token
      );

      if (!result || !Array.isArray(result.items)) {
        throw new Error("Invalid response from server when extracting items.");
      }

      // Refresh the codex entries to show the newly extracted items
      const updatedResponse = await fetchApi<CodexEntry[]>(
        `/projects/${projectId}/codex-items`,
        {},
        token
      );

      if (updatedResponse && Array.isArray(updatedResponse)) {
        setCodexEntries(updatedResponse);
      } else {
        throw new Error(
          "Items were extracted, but the codex list could not be refreshed."
        );
      }

      toast.success(
        `Successfully extracted and refreshed ${result.items.length} codex items.`,
        { id: toastId }
      );
    } catch (error) {
      console.error("Error extracting codex items from all chapters:", error);
      const message =
        error instanceof Error ? error.message : "An unknown error occurred.";
      toast.error(`Extraction failed: ${message}`, { id: toastId });
      setError(`Extraction failed: ${message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    // Use theme background, adjust padding
    <div className="p-0 md:p-6 flex flex-col h-full bg-background">
      {/* Header/Toolbar */}
      <div className="flex items-center justify-between mb-4 gap-4 px-6 md:px-0">
        {/* Apply display font and theme text color */}
        <h2 className="text-2xl font-semibold text-foreground font-display">
          Codex
        </h2>
        <div className="flex items-center gap-2 flex-1 justify-end">
          {/* Filter Input - Apply theme styles */}
          <div className="relative max-w-xs w-full">
            <Search className="absolute left-2.5 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Filter by name, type, tags..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              // Input inherits theme styles
              className="pl-8 h-9 text-sm"
            />
          </div>
          {/* Action Buttons - Apply theme styles */}
          <Button
            variant="destructive" // Use destructive variant
            size="sm"
            onClick={handleDeleteSelected}
            disabled={selectedEntryIds.size === 0 || isDeleting}
            className="disabled:opacity-50 disabled:cursor-not-allowed min-w-[160px]" // Keep min-width
          >
            {isDeleting ? (
              <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4 mr-1.5" />
            )}
            {isDeleting
              ? "Deleting..."
              : `Delete Selected (${selectedEntryIds.size})`}
          </Button>
          <Button
            variant="outline"
            onClick={handleExtractFromAllChapters}
            disabled={isLoading}
          >
            <Wand2 className="h-4 w-4 mr-2" />
            Extract From Chapters
          </Button>
          <Button size="sm" onClick={handleAddEntry} disabled={isLoading}>
            <Plus className="h-4 w-4 mr-1.5" />
            Add Entry
          </Button>
        </div>
      </div>
      {/* Error Display - Apply theme styles */}
      {error && (
        <div className="mb-4 mx-6 md:mx-0 p-3 bg-destructive/90 border border-destructive text-destructive-foreground text-sm rounded-md flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            <span>{error}</span>
          </div>
          <Button
            variant="ghost" // Ghost for close button
            size="sm"
            onClick={() => setError(null)}
            className="text-destructive-foreground hover:bg-destructive/20 p-1 h-auto"
          >
            Dismiss
          </Button>
        </div>
      )}
      {/* Codex Table Container - Apply theme styles */}
      <div className="flex-1 overflow-auto border border-border rounded-lg bg-card mx-6 md:mx-0">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            {/* Use primary color for loader */}
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        ) : (
          <Table>
            {/* Style TableHeader */}
            <TableHeader className="sticky top-0 bg-card z-10">
              {/* Style TableRow border */}
              <TableRow className="border-border">
                {/* Style TableHead */}
                <TableHead className="w-[50px]">
                  <Checkbox
                    checked={isAllSelected}
                    onCheckedChange={handleSelectAll}
                    aria-label="Select all rows"
                  // Checkbox inherits theme styles
                  // Add indeterminate state visual if possible or needed
                  />
                </TableHead>
                <TableHead className="w-[30%] text-foreground">Name</TableHead>
                <TableHead className="w-[20%] text-foreground">Type</TableHead>
                <TableHead className="w-[20%] text-foreground">Tags</TableHead>
                <TableHead className="text-foreground">Description</TableHead>
                <TableHead className="w-[80px] text-right text-foreground">
                  Actions
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredEntries.length > 0 ? (
                filteredEntries.map((entry) => (
                  // Style TableRow border and hover/selected states
                  <TableRow
                    key={entry.id}
                    className="border-border hover:bg-accent/50 data-[state=selected]:bg-primary/10"
                    data-state={
                      selectedEntryIds.has(entry.id) ? "selected" : undefined
                    }
                  >
                    <TableCell>
                      <Checkbox
                        checked={selectedEntryIds.has(entry.id)}
                        onCheckedChange={(checked) =>
                          handleSelectRow(entry.id, !!checked)
                        }
                        aria-label={`Select row ${entry.name}`}
                      // Checkbox inherits theme styles
                      />
                    </TableCell>
                    {/* Style TableCell text */}
                    <TableCell
                      className="font-medium text-foreground truncate"
                      title={entry.name}
                    >
                      {entry.name}
                    </TableCell>
                    <TableCell
                      className="text-muted-foreground truncate"
                      title={
                        entry.subtype
                          ? `${formatEnumKey(entry.type)} (${formatEnumKey(
                            entry.subtype
                          )})`
                          : formatEnumKey(entry.type)
                      }
                    >
                      {formatEnumKey(entry.type) || "-"}
                      {entry.subtype && (
                        <span className="text-xs ml-1">
                          ({formatEnumKey(entry.subtype)})
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground truncate">
                      {entry.tags?.join(", ") || "-"}
                    </TableCell>
                    <TableCell
                      className="text-muted-foreground truncate"
                      title={entry.description}
                    >
                      {entry.description
                        ? `${entry.description.substring(0, 75)}${entry.description.length > 75 ? "..." : ""
                        }`
                        : "-"}
                    </TableCell>
                    <TableCell className="text-right">
                      {/* Style action button */}
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleEditClick(entry)}
                        className="text-muted-foreground hover:text-primary hover:bg-accent h-7 w-7"
                        title="Edit Entry"
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow className="border-border hover:bg-transparent">
                  <TableCell
                    colSpan={6}
                    className="h-24 text-center text-muted-foreground"
                  >
                    {searchTerm
                      ? "No entries match your filter."
                      : "No codex entries found. Add one to get started!"}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </div>
      {/* Add/Edit Entry Dialog - Assuming CodexEntryForm uses themed components */}
      <CodexEntryForm
        projectId={projectId}
        isOpen={isFormOpen}
        onOpenChange={setIsFormOpen}
        onEntryAdded={handleEntryAdded}
        onEntryUpdated={handleEntryUpdated}
        entryToEdit={entryToEdit}
        // --- Pass isProUser and loading state ---
        isProUser={isProUser}
        userSubLoading={userSubLoading}
      // --- End pass isProUser ---
      />
    </div>
  );
}

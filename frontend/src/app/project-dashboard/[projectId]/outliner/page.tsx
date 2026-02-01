"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { useAuth } from "@/components/MockAuthProvider";
import { fetchApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Check,
  X,
  Loader2,
  Save,
  Edit3,
  Trash2,
  FolderPlus,
} from "lucide-react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { toast } from "sonner";

const generateUniqueId = () =>
  `temp-id-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

// --- Frontend Data Structure ---
interface ChapterItem {
  id: string;
  type: "chapter";
  title: string;
  structure_item_id?: string; // Parent folder ID for backend association
}

interface FolderItem {
  id: string;
  type: "folder";
  title: string;
  description?: string;
  children: (FolderItem | ChapterItem)[];
}

type StructureItem = FolderItem | ChapterItem;

interface ProjectStructureApiResponse {
  project_structure: StructureItem[];
}

// --- Backend Data Structure ---
// Update these interfaces to match what the backend expects
interface BackendFolderItem {
  id: string;
  name: string;
  title: string;
  type: string; // "folder", "act", "stage", or "substage"
  description: string;
  children: BackendStructureItem[];
}

interface BackendChapterItem {
  id: string;
  type: "chapter";
  title: string;
  name: string;
  structure_item_id?: string; // Parent folder ID
  children?: BackendStructureItem[]; // Empty array for consistency
}

type BackendStructureItem = BackendFolderItem | BackendChapterItem;

// Helper to find an item and its parent
const findItemRecursive = (
  items: StructureItem[],
  itemId: string,
  parent: FolderItem | null = null
): { item: StructureItem; parent: FolderItem | null } | null => {
  for (const item of items) {
    if (item.id === itemId) return { item, parent };
    if (item.type === "folder") {
      const found = findItemRecursive(item.children, itemId, item);
      if (found) return found;
    }
  }
  return null;
};

// --- Sortable Item Component ---
const SortableItem: React.FC<{
  item: StructureItem;
  renderItems: (
    items: StructureItem[],
    parentId: string | null
  ) => React.ReactNode;
  onDeleteItem: (itemId: string) => void;
  onRenameItem: (itemId: string, newTitle: string) => void;
  onUpdateDescription?: (itemId: string, newDescription: string) => void;
  handleAddFolder: (parentId: string | null) => void;
}> = ({
  item,
  renderItems,
  onDeleteItem,
  onRenameItem,
  onUpdateDescription,
  handleAddFolder,
}) => {
    const {
      attributes,
      listeners,
      setNodeRef,
      transform,
      transition,
      isDragging,
    } = useSortable({ id: item.id });

    const [isExpanded, setIsExpanded] = useState(false);
    const [isEditingTitle, setIsEditingTitle] = useState(false);
    const [editedTitle, setEditedTitle] = useState(item.title);
    const [editedDescription, setEditedDescription] = useState(
      item.type === "folder" ? item.description || "" : ""
    );

    const style = {
      transform: CSS.Transform.toString(transform),
      transition,
      opacity: isDragging ? 0.5 : 1,
    };

    const isFolder = item.type === "folder";

    const handleTitleConfirm = () => {
      onRenameItem(item.id, editedTitle);
      setIsEditingTitle(false);
    };

    const handleTitleCancel = () => {
      setEditedTitle(item.title);
      setIsEditingTitle(false);
    };

    const handleDescriptionChange = (
      e: React.ChangeEvent<HTMLTextAreaElement>
    ) => {
      setEditedDescription(e.target.value);
    };

    // Auto-save description on blur
    const handleDescriptionBlur = () => {
      if (
        isFolder &&
        onUpdateDescription &&
        editedDescription !== item.description
      ) {
        onUpdateDescription(item.id, editedDescription);
        toast.success(`Description for "${item.title}" updated.`);
      }
    };

    return (
      <div ref={setNodeRef} style={style} className="mb-2 group">
        <div
          className={`flex items-center p-2 rounded-t-md transition-colors ${isFolder
              ? "bg-slate-100 dark:bg-muted/50 hover:bg-slate-200 dark:hover:bg-muted"
              : "bg-white dark:bg-card hover:bg-slate-50 dark:hover:bg-accent/10"
            } ${isDragging ? "ring-2 ring-primary" : ""} ${isExpanded ? "" : "rounded-b-md"
            }`}
        >
          <button
            {...attributes}
            {...listeners}
            className="cursor-grab p-1 mr-2 text-muted-foreground hover:text-foreground"
            aria-label="Drag to reorder"
            title="Drag to reorder"
          >
            {/* Drag Handle Icon */}
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M9 5a1 1 0 1 0 0 2 1 1 0 0 0 0-2zM9 12a1 1 0 1 0 0 2 1 1 0 0 0 0-2zM9 19a1 1 0 1 0 0 2 1 1 0 0 0 0-2zM15 5a1 1 0 1 0 0 2 1 1 0 0 0 0-2zM15 12a1 1 0 1 0 0 2 1 1 0 0 0 0-2zM15 19a1 1 0 1 0 0 2 1 1 0 0 0 0-2z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>

          {isFolder && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1 mr-2"
              aria-label={isExpanded ? "Collapse" : "Expand"}
            >
              <svg
                className={`w-4 h-4 transition-transform ${isExpanded ? "rotate-90" : ""
                  }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M9 5l7 7-7 7"
                ></path>
              </svg>
            </button>
          )}

          {isEditingTitle ? (
            <div className="flex-grow flex items-center">
              <input
                type="text"
                value={editedTitle}
                onChange={(e) => setEditedTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleTitleConfirm();
                  if (e.key === "Escape") handleTitleCancel();
                }}
                autoFocus
                className="flex-grow p-1 border rounded-md"
              />
              <Button
                size="icon"
                variant="ghost"
                className="h-7 w-7 ml-1"
                onClick={handleTitleConfirm}
              >
                <Check size={16} />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                className="h-7 w-7"
                onClick={handleTitleCancel}
              >
                <X size={16} />
              </Button>
            </div>
          ) : (
            <span
              className={`flex-grow ${isFolder ? "font-semibold" : ""
                } cursor-pointer`}
              onClick={() => isFolder && setIsExpanded(!isExpanded)}
              onDoubleClick={() => setIsEditingTitle(true)}
              title={
                isFolder
                  ? "Click to expand/collapse, double-click to edit title"
                  : "Double-click to edit title"
              }
            >
              {item.title}
            </span>
          )}

          <div className="flex items-center opacity-0 group-hover:opacity-100 transition-opacity ml-2">
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7"
              onClick={() => setIsEditingTitle(true)}
              title="Edit title"
            >
              <Edit3 size={16} />
            </Button>
            {isFolder && (
              <Button
                size="icon"
                variant="ghost"
                className="h-7 w-7"
                onClick={() => handleAddFolder(item.id)}
                title="Add folder to this folder"
              >
                <FolderPlus size={16} />
              </Button>
            )}
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 text-destructive hover:text-destructive"
              onClick={() => onDeleteItem(item.id)}
              title="Delete item"
            >
              <Trash2 size={16} />
            </Button>
          </div>
        </div>
        {isFolder && isExpanded && (
          <div className="pl-6 pt-2 pb-2 bg-slate-50 dark:bg-muted/20 rounded-b-md">
            <div className="mb-2">
              <label className="text-sm font-medium text-muted-foreground">
                Description
              </label>
              <textarea
                value={editedDescription}
                onChange={handleDescriptionChange}
                onBlur={handleDescriptionBlur}
                className="w-full p-2 border rounded-md mt-1 text-sm bg-white dark:bg-background dark:border-input"
                placeholder="Add a description for this folder..."
                rows={2}
              />
            </div>
            <div className="ml-4 border-l-2 border-slate-200 dark:border-border pl-4">
              {renderItems((item as FolderItem).children, item.id)}
              <div className="mt-2 flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleAddFolder(item.id)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <FolderPlus size={16} className="mr-2" />
                  Add Folder
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

// --- Main Page Component ---
export default function StoryOutlinerPage() {
  const params = useParams();
  const projectId = params?.projectId as string;
  const auth = useAuth();

  const [structure, setStructure] = useState<StructureItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const fetchStructure = useCallback(
    async (token: string) => {
      if (!projectId) return;
      setIsLoading(true);
      try {
        const response = await fetchApi<ProjectStructureApiResponse>(
          `/projects/${projectId}/structure`,
          {},
          token
        );
        setStructure(response?.project_structure || []);
      } catch (error) {
        console.error("Failed to fetch project outliner structure:", error);
        toast.error("Failed to load story outliner.");
      } finally {
        setIsLoading(false);
      }
    },
    [projectId]
  );

  useEffect(() => {
    if (auth.isAuthenticated && auth.user?.id_token) {
      fetchStructure(auth.user.id_token);
    } else if (!auth.isLoading && !auth.isAuthenticated) {
      toast.error("Authentication required.");
      setIsLoading(false);
    }
  }, [
    auth.isAuthenticated,
    auth.isLoading,
    auth.user?.id_token,
    fetchStructure,
  ]);

  const toBackendStructure = (items: StructureItem[]): BackendStructureItem[] =>
    items.map((item) => {
      if (item.type === "folder") {
        const folder = item as FolderItem;
        return {
          id: folder.id,
          name: folder.title,
          title: folder.title,
          type: "folder",
          description: folder.description || "",
          children: toBackendStructure(folder.children),
        } as BackendFolderItem;
      }
      // chapter
      const chapter = item as ChapterItem;
      return {
        id: chapter.id,
        type: "chapter",
        title: chapter.title,
        name: chapter.title,
      } as BackendChapterItem;
    });

  const handleSaveStructure = async () => {
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      toast.error("Authentication required to save.");
      return;
    }
    setIsSaving(true);

    const backendStructure = toBackendStructure(structure);

    try {
      await fetchApi(
        `/projects/${projectId}/structure`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_structure: backendStructure,
          }),
        },
        auth.user.id_token
      );
      toast.success("Outliner saved successfully!");
      // Refetch to get permanent IDs from the backend and see the updated state
      fetchStructure(auth.user.id_token);
    } catch (error) {
      console.error("Failed to save outliner structure:", error);
      toast.error("Failed to save outliner.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleAddFolder = (parentId: string | null = null) => {
    const newFolder: FolderItem = {
      id: generateUniqueId(),
      type: "folder",
      title: "New Folder",
      children: [],
    };

    if (parentId === null) {
      setStructure((prev) => [...prev, newFolder]);
    } else {
      // Logic to add to a sub-folder
      setStructure((prev) => {
        const newStructure = JSON.parse(JSON.stringify(prev));
        const result = findItemRecursive(newStructure, parentId);
        if (result && result.item.type === "folder") {
          // Only allow adding folders inside other folders
          (result.item as FolderItem).children.push(newFolder);
        } else {
          toast.error("Can only add folders to other folders.");
        }
        return newStructure;
      });
    }
  };

  const handleDeleteItem = async (itemId: string) => {
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      toast.error("Authentication required to delete items.");
      return;
    }
    const token = auth.user.id_token;

    // Find the item to be deleted to get its title for the confirmation dialog
    const tempFindStructure = JSON.parse(JSON.stringify(structure));
    const itemSearchResult = findItemRecursive(tempFindStructure, itemId);

    if (!itemSearchResult) {
      toast.error("Could not find the item to delete.");
      return;
    }
    const { item } = itemSearchResult;
    const itemTitle = item.title;
    const itemType = item.type;

    // Collect chapter IDs that need to be deleted from the database
    const chapterIdsToDelete: string[] = [];
    const collectChapterIds = (currentItem: StructureItem) => {
      if (currentItem.type === "chapter") {
        if (!currentItem.id.startsWith("temp-id-")) {
          chapterIdsToDelete.push(currentItem.id);
        }
      } else if (currentItem.type === "folder") {
        (currentItem as FolderItem).children.forEach(collectChapterIds);
      }
    };
    collectChapterIds(item);

    // Confirmation dialog
    const confirmationMessage =
      itemType === "folder"
        ? `Are you sure you want to delete the folder "${itemTitle}" and all of its contents (${chapterIdsToDelete.length} chapters)? This action also saves the outliner and cannot be undone.`
        : `Are you sure you want to delete the chapter "${itemTitle}"? This action also saves the outliner and cannot be undone.`;

    if (!confirm(confirmationMessage)) {
      return;
    }

    const toastId = toast.loading(`Deleting ${itemType} "${itemTitle}"...`);

    try {
      // Step 1: Delete all associated chapters from the database
      if (chapterIdsToDelete.length > 0) {
        const deletePromises = chapterIdsToDelete.map((chapterId) =>
          fetchApi(
            `/projects/${projectId}/chapters/${chapterId}`,
            { method: "DELETE" },
            token
          )
        );
        await Promise.all(deletePromises);
        toast.info(
          `Deleted ${chapterIdsToDelete.length} chapter(s) from database.`,
          { id: toastId }
        );
      }

      // Step 2: Compute the new structure after removing the item
      const newStructure = JSON.parse(JSON.stringify(structure));
      const searchResultForUpdate = findItemRecursive(newStructure, itemId);
      if (!searchResultForUpdate) {
        throw new Error("Item disappeared during deletion process.");
      }
      const container = searchResultForUpdate.parent
        ? searchResultForUpdate.parent.children
        : newStructure;
      const itemIndex = container.findIndex(
        (i: StructureItem) => i.id === itemId
      );
      if (itemIndex > -1) {
        container.splice(itemIndex, 1);
      }

      // Step 3: Save the updated structure to the backend
      toast.info("Saving updated outliner structure...", { id: toastId });
      const backendStructure = toBackendStructure(newStructure);
      await fetchApi(
        `/projects/${projectId}/structure`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project_structure: backendStructure }),
        },
        token
      );

      // Step 4: If all backend operations are successful, update the UI state
      setStructure(newStructure);

      toast.success(
        `${itemType.charAt(0).toUpperCase() + itemType.slice(1)
        } "${itemTitle}" deleted successfully.`,
        { id: toastId }
      );
    } catch (err) {
      console.error("Failed to delete item(s):", err);
      const message =
        err instanceof Error ? err.message : "An unknown error occurred.";
      toast.error(`Failed to delete: ${message}`, { id: toastId });
      // On error, refetch the structure to ensure UI consistency with the backend state
      if (auth.user?.id_token) fetchStructure(auth.user.id_token);
    }
  };

  const handleRenameItem = (itemId: string, newTitle: string) => {
    setStructure((prev) => {
      const newStructure = JSON.parse(JSON.stringify(prev));
      const itemSearchResult = findItemRecursive(newStructure, itemId);

      if (itemSearchResult) {
        itemSearchResult.item.title = newTitle;
      }

      return newStructure;
    });
  };

  const handleUpdateDescription = (itemId: string, newDescription: string) => {
    setStructure((prev) => {
      const newStructure = JSON.parse(JSON.stringify(prev));
      const itemSearchResult = findItemRecursive(newStructure, itemId);

      if (itemSearchResult && itemSearchResult.item.type === "folder") {
        (itemSearchResult.item as FolderItem).description = newDescription;
      }

      return newStructure;
    });
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (!over || active.id === over.id) {
      return;
    }

    setStructure((prevStructure) => {
      const newStructure = JSON.parse(JSON.stringify(prevStructure));

      // Find the active item and its parent
      const activeItemSearchResult = findItemRecursive(
        newStructure,
        active.id as string
      );
      if (!activeItemSearchResult) return prevStructure;

      const { item: activeItem, parent: activeParent } = activeItemSearchResult;
      const activeType = activeItem.type;

      // Remove the active item from its original position
      const sourceContainer = activeParent
        ? activeParent.children
        : newStructure;
      const activeIndex = sourceContainer.findIndex(
        (i: StructureItem) => i.id === active.id
      );
      sourceContainer.splice(activeIndex, 1);

      // Find the over item and its parent
      const overItemSearchResult = findItemRecursive(
        newStructure,
        over.id as string
      );

      if (!overItemSearchResult) {
        // If target not found, add to root as fallback
        newStructure.push(activeItem);
        return newStructure;
      }

      const { item: overItem, parent: overParent } = overItemSearchResult;
      const overType = overItem.type;

      // Handle dropping based on item types
      if (overType === "folder") {
        // Add item to the folder's children
        const targetFolder = overItem as FolderItem;

        // For chapters being moved to folders, add a success message with item type
        if (activeType === "chapter") {
          // For chapters, set the structure_item_id to the folder's id in the frontend model
          // This ensures proper serialization when sending to backend
          (activeItem as ChapterItem).structure_item_id = targetFolder.id;
          toast.success(`Moved chapter to "${targetFolder.title}" folder`);
        } else {
          toast.success(`Moved folder to "${targetFolder.title}" folder`);
        }

        targetFolder.children.push(activeItem);
      } else if (overType === "chapter") {
        // Dropping next to a chapter (at the same level)
        const targetContainer = overParent ? overParent.children : newStructure;
        const overIndex = targetContainer.findIndex(
          (i: StructureItem) => i.id === over.id
        );

        // If moving to a folder's children, update the structure_item_id
        if (activeType === "chapter" && overParent) {
          (activeItem as ChapterItem).structure_item_id = overParent.id;
        } else if (activeType === "chapter") {
          // If moving to root level, remove the structure_item_id
          (activeItem as ChapterItem).structure_item_id = undefined;
        }

        // Insert the active item at the same level as the chapter
        targetContainer.splice(overIndex, 0, activeItem);
      }

      return newStructure;
    });
  };

  // This renderItems function renders structure items recursively
  const renderItems = (
    items: StructureItem[],
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    parentId: string | null = null
  ) => {
    return items.map((item) => (
      <SortableItem
        key={item.id}
        item={item}
        renderItems={renderItems}
        onDeleteItem={handleDeleteItem}
        onRenameItem={handleRenameItem}
        onUpdateDescription={handleUpdateDescription}
        handleAddFolder={handleAddFolder}
      />
    ));
  };

  if (isLoading) {
    return <div className="p-6">Loading Story Outliner...</div>;
  }

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Story Outliner</h1>
        <div className="flex space-x-2">
          <Button
            variant="outline"
            onClick={() => handleAddFolder(null)}
            className="flex items-center"
            disabled={isLoading || isSaving}
          >
            <FolderPlus size={16} className="mr-2" />
            Add Folder
          </Button>
          <Button
            onClick={handleSaveStructure}
            className="flex items-center"
            disabled={isLoading || isSaving}
          >
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save size={16} className="mr-2" />
                Save
              </>
            )}
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-10">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={structure.map((item) => item.id)}
            strategy={verticalListSortingStrategy}
          >
            {renderItems(structure, null)}
          </SortableContext>
        </DndContext>
      )}
    </div>
  );
}

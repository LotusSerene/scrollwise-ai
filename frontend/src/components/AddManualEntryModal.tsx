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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import type { KnowledgeBaseItemDisplay } from "@/types/knowledgebaseDisplay";

// Define a more specific type for metadata if possible, or use Record<string, unknown>
// Using unknown is slightly better than any as it forces type checks later.
// type ManualMetadata = Record<string, string | number | boolean | string[] | number[] | boolean[]>;
type ManualMetadata = Record<string, unknown>;

interface AddManualEntryModalProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit?: (content: string, metadata: ManualMetadata) => Promise<void>;
  onUpdate?: (
    embeddingId: string,
    content: string,
    metadata: ManualMetadata
  ) => Promise<void>;
  itemToEdit?: KnowledgeBaseItemDisplay | null;
  // projectId prop removed as it's not used directly in the modal logic
}

export function AddManualEntryModal({
  isOpen,
  onOpenChange,
  onSubmit,
  onUpdate,
  itemToEdit,
}: AddManualEntryModalProps) {
  const [content, setContent] = useState("");
  const [metadataInput, setMetadataInput] = useState("{}"); // Store as JSON string
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isEditMode = !!itemToEdit;

  // Use useEffect to pre-fill form when in edit mode and modal opens
  useEffect(() => {
    if (isEditMode && isOpen) {
      setContent(itemToEdit.content || ""); // Use existing content or empty string
      setMetadataInput(
        itemToEdit.metadata
          ? JSON.stringify(itemToEdit.metadata, null, 2)
          : "{}"
      ); // Use existing metadata or empty object
    } else if (!isOpen) {
      // Reset form when modal closes
      setContent("");
      setMetadataInput("{}");
    }
  }, [itemToEdit, isEditMode, isOpen]);

  const handleSubmitOrUpdate = async () => {
    let parsedMetadata: ManualMetadata = {};
    try {
      parsedMetadata = JSON.parse(metadataInput || "{}"); // Default to empty object if input is empty
      if (
        typeof parsedMetadata !== "object" ||
        parsedMetadata === null ||
        Array.isArray(parsedMetadata)
      ) {
        throw new Error("Metadata must be a valid JSON object.");
      }
    } catch (error) {
      toast.error("Invalid JSON format for metadata.");
      console.error("Metadata parse error:", error);
      return;
    }

    if (!content.trim()) {
      toast.error("Content cannot be empty.");
      return;
    }

    setIsSubmitting(true);
    try {
      if (isEditMode && onUpdate && itemToEdit.embedding_id) {
        // Call onUpdate if in edit mode and function is provided
        await onUpdate(itemToEdit.embedding_id, content, parsedMetadata);
      } else if (!isEditMode && onSubmit) {
        // Call onSubmit if in add mode and function is provided
        await onSubmit(content, parsedMetadata);
      } else {
        // Should not happen if props are correctly passed
        toast.error("Configuration error: No submit handler available.");
        console.error(
          "No onSubmit or onUpdate handler provided appropriately."
        );
      }

      // Clear form and close modal on success (handled by onOpenChange)
      onOpenChange(false); // Close modal on success
    } catch (error) {
      // Error toast is likely handled in the onSubmit/onUpdate function passed from parent
      console.error("Submission failed:", error);
      // Keep modal open on error
    } finally {
      setIsSubmitting(false);
    }
  };

  // Close modal without submitting, reset fields
  const handleClose = (open: boolean) => {
    // Reset happens in useEffect now when isOpen becomes false
    onOpenChange(open);
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      {/* Apply theme styles to DialogContent */}
      <DialogContent className="sm:max-w-[600px] bg-card border-border text-card-foreground rounded-lg">
        <DialogHeader>
          {/* Apply theme styles */}
          <DialogTitle className="text-primary font-display">
            {isEditMode ? "Edit" : "Add Manual"} Knowledge Base Entry
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">
            {isEditMode
              ? "Modify the text content and optional JSON metadata."
              : "Enter the text content and optional JSON metadata for the new knowledge base item."}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-start gap-4">
            {/* Apply theme styles */}
            <Label
              htmlFor="content"
              className="text-right pt-2 text-foreground"
            >
              Content
            </Label>
            {/* Textarea inherits theme styles */}
            <Textarea
              id="content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="col-span-3 h-40 resize-none" // Removed explicit bg/border
              placeholder="Paste or type the text content here..."
              disabled={isSubmitting}
            />
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            {/* Apply theme styles */}
            <Label htmlFor="metadata" className="text-right text-foreground">
              Metadata (JSON)
            </Label>
            {/* Input inherits theme styles */}
            <Input
              id="metadata"
              value={metadataInput}
              onChange={(e) => setMetadataInput(e.target.value)}
              className="col-span-3" // Removed explicit bg/border
              placeholder='e.g., {"source": "manual", "tags": ["important"]}'
              disabled={isSubmitting}
            />
          </div>
          {/* Apply theme styles */}
          <p className="text-xs text-muted-foreground col-start-2 col-span-3">
            Enter metadata as a valid JSON object. This can be used for
            filtering during retrieval.
          </p>
        </div>
        <DialogFooter>
          {/* Buttons inherit theme styles */}
          <Button
            variant="outline"
            onClick={() => handleClose(false)}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmitOrUpdate}
            disabled={isSubmitting || !content.trim()}
            // Removed explicit bg/hover classes
          >
            {isSubmitting
              ? isEditMode
                ? "Updating..."
                : "Adding..."
              : isEditMode
              ? "Update Entry"
              : "Add Entry"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

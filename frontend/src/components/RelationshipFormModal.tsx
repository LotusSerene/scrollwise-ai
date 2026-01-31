"use client";

import React, { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, AlertTriangle, UserPlus } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { CodexEntry, Relationship } from "@/types";
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth

// Zod schema for validation
const relationshipSchema = z
  .object({
    character_id: z
      .string()
      .min(1, { message: "Please select the first character." }),
    related_character_id: z
      .string()
      .min(1, { message: "Please select the second character." }),
    relationship_type: z
      .string()
      .min(1, { message: "Relationship type is required." })
      .max(100, "Type cannot exceed 100 characters."),
    description: z
      .string()
      .max(500, "Description cannot exceed 500 characters.")
      .optional(),
  })
  .refine((data) => data.character_id !== data.related_character_id, {
    message: "Characters cannot have a relationship with themselves.",
    path: ["related_character_id"], // Apply error to the second character field
  });

type RelationshipFormValues = z.infer<typeof relationshipSchema>;

interface RelationshipFormModalProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  projectId: string;
  characters: CodexEntry[]; // List of characters for dropdowns
  relationshipToEdit?: Relationship | null;
  onSaveComplete: () => void; // Callback after successful save/update
}

export function RelationshipFormModal({
  isOpen,
  onOpenChange,
  projectId,
  characters,
  relationshipToEdit,
  onSaveComplete,
}: RelationshipFormModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isEditMode = !!relationshipToEdit;
  const auth = useAuth(); // Use the hook

  const form = useForm<RelationshipFormValues>({
    resolver: zodResolver(relationshipSchema),
    defaultValues: {
      character_id: "",
      related_character_id: "",
      relationship_type: "",
      description: "",
    },
  });

  // Populate form when editing
  useEffect(() => {
    if (isOpen && relationshipToEdit) {
      form.reset({
        character_id: relationshipToEdit.character_id,
        related_character_id: relationshipToEdit.related_character_id,
        relationship_type: relationshipToEdit.relationship_type,
        description: relationshipToEdit.description || "",
      });
    } else if (!isOpen) {
      form.reset(); // Reset form on close
      setError(null);
    }
  }, [isOpen, relationshipToEdit, form]);

  const onSubmit = async (values: RelationshipFormValues) => {
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to save relationship.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    const token = auth.user.id_token; // Get token

    // Prepare payload (matches backend dictionary structure for create/update)
    const payload = {
      character_id: values.character_id,
      related_character_id: values.related_character_id,
      relationship_type: values.relationship_type,
      description: values.description || null, // Send null if empty
    };

    try {
      if (isEditMode && relationshipToEdit) {
        // --- Edit Mode --- (PUT request)
        await fetchApi<Relationship>( // Expect updated relationship back?
          `/projects/${projectId}/relationships/${relationshipToEdit.id}`,
          {
            method: "PUT",
            body: JSON.stringify(payload),
          },
          token
        );
      } else {
        // --- Add Mode --- (POST request)
        await fetchApi<{ id: string }>( // Expect new ID back
          `/projects/${projectId}/relationships`,
          {
            method: "POST",
            body: JSON.stringify(payload),
          },
          token
        );
      }

      onSaveComplete(); // Trigger refresh
      onOpenChange(false); // Close modal
    } catch (err: unknown) {
      console.error(
        `Failed to ${isEditMode ? "update" : "create"} relationship:`,
        err
      );
      const message =
        err instanceof Error ? err.message : "An unknown error occurred";
      setError(
        `Failed to ${isEditMode ? "update" : "create"} relationship: ${message}`
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      {/* Apply theme styles to DialogContent */}
      <DialogContent className="sm:max-w-[600px] bg-card border-border text-card-foreground rounded-lg">
        <DialogHeader>
          {/* Apply theme styles to DialogTitle and DialogDescription */}
          <DialogTitle className="flex items-center gap-2 text-foreground font-display">
            {/* Use primary color for icon */}
            <UserPlus className="h-5 w-5 text-primary" />
            {isEditMode
              ? "Edit Character Relationship"
              : "Add New Relationship"}
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Define the connection between two characters.
          </DialogDescription>
        </DialogHeader>

        {/* Apply theme styles to error message */}
        {error && (
          <div className="mb-4 p-3 bg-destructive/10 border border-destructive text-destructive-foreground text-sm rounded-md flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="space-y-4 py-4"
          >
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="character_id"
                render={({ field }) => (
                  <FormItem>
                    {/* Apply theme style to FormLabel */}
                    <FormLabel className="text-foreground">Character 1</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                      value={field.value}
                      disabled={isSubmitting || isEditMode} // Disable if editing
                    >
                      <FormControl>
                        {/* SelectTrigger inherits theme styles */}
                        <SelectTrigger className="">
                          <SelectValue placeholder="Select character" />
                        </SelectTrigger>
                      </FormControl>
                      {/* Apply theme styles to SelectContent/Item */}
                      <SelectContent className="bg-popover border-border text-popover-foreground">
                        {characters.map((char) => (
                          <SelectItem
                            key={char.id}
                            value={char.id}
                            className="hover:bg-accent focus:bg-accent"
                          >
                            {char.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {/* Apply theme style to FormMessage */}
                    <FormMessage className="text-destructive" />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="related_character_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-foreground">Character 2</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                      value={field.value}
                      disabled={isSubmitting || isEditMode} // Disable if editing
                    >
                      <FormControl>
                        <SelectTrigger className="">
                          <SelectValue placeholder="Select character" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent className="bg-popover border-border text-popover-foreground">
                        {characters.map((char) => (
                          <SelectItem
                            key={char.id}
                            value={char.id}
                            className="hover:bg-accent focus:bg-accent"
                          >
                            {char.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage className="text-destructive" />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="relationship_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-foreground">Relationship Type</FormLabel>
                  <FormControl>
                    {/* Input inherits theme styles */}
                    <Input
                      placeholder="E.g., Allies, Rivals, Siblings, Mentor/Mentee..."
                      {...field}
                      className=""
                      disabled={isSubmitting}
                    />
                  </FormControl>
                  <FormMessage className="text-destructive" />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-foreground">Description (Optional)</FormLabel>
                  <FormControl>
                    {/* Textarea inherits theme styles */}
                    <Textarea
                      placeholder="Describe the nature or history of their relationship..."
                      {...field}
                      className="min-h-[100px]"
                      disabled={isSubmitting}
                    />
                  </FormControl>
                  <FormMessage className="text-destructive" />
                </FormItem>
              )}
            />

            <DialogFooter>
              {/* Buttons inherit theme styles */}
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={isSubmitting}
                // Default variant inherits theme styles
              >
                {isSubmitting && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {isSubmitting
                  ? isEditMode
                    ? "Saving..."
                    : "Adding..."
                  : isEditMode
                  ? "Save Changes"
                  : "Add Relationship"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

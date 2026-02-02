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
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, AlertTriangle, Sparkles } from "lucide-react";
import { fetchApi } from "@/lib/api";
import {
  CodexEntry,
  CodexItemType,
  WorldbuildingSubtype,
  CharacterVoiceProfileData,
} from "@/types";
import { useAuth } from "@/components/MockAuthProvider";

// Helper to format enum keys for display
function formatEnumKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/(?:^|\s)\S/g, (a) => a.toUpperCase());
}

// --- Zod schema for Voice Profile (all fields optional) ---
const voiceProfileSchema = z
  .object({
    vocabulary: z.string().optional(),
    sentence_structure: z.string().optional(),
    speech_patterns_tics: z.string().optional(),
    tone: z.string().optional(),
    habits_mannerisms: z.string().optional(),
  })
  .optional();
// --- End Zod schema for Voice Profile ---

// Updated Zod schema for validation, matching backend CodexItemCreate
const codexEntrySchema = z
  .object({
    name: z
      .string()
      .min(1, { message: "Name is required." })
      .max(100, { message: "Name must be 100 characters or less." }),
    type: z.nativeEnum(CodexItemType, { required_error: "Type is required." }),
    subtype: z.string().optional(),
    description: z.string().min(1, { message: "Description is required." }),
    voice_profile: voiceProfileSchema,
  })
  .refine(
    (data) => {
      if (data.type === CodexItemType.WORLDBUILDING) {
        return !!data.subtype;
      }
      return true;
    },
    {
      message: "Subtype is required for Worldbuilding entries.",
      path: ["subtype"],
    }
  );

type CodexEntryFormValues = z.infer<typeof codexEntrySchema>;

interface CodexEntryFormProps {
  projectId: string;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  onEntryAdded: (newEntry: CodexEntry) => void;
  onEntryUpdated: (updatedEntry: CodexEntry) => void;
  entryToEdit?: CodexEntry | null;
  isProUser: boolean;
  userSubLoading: boolean;
}

// --- Define Payload type ---
interface CodexItemPayload {
  name: string;
  description: string;
  type: CodexItemType;
  subtype?: WorldbuildingSubtype | string | null;
  voice_profile?: CharacterVoiceProfileData | null;
}
// --- End Payload type ---

export function CodexEntryForm({
  projectId,
  isOpen,
  onOpenChange,
  onEntryAdded,
  onEntryUpdated,
  entryToEdit,
  isProUser,
  userSubLoading,
}: CodexEntryFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isEditMode = !!entryToEdit;
  const auth = useAuth();

  const form = useForm<CodexEntryFormValues>({
    resolver: zodResolver(codexEntrySchema),
    defaultValues: {
      name: "",
      type: undefined,
      subtype: "",
      description: "",
      voice_profile: {
        vocabulary: "",
        sentence_structure: "",
        speech_patterns_tics: "",
        tone: "",
        habits_mannerisms: "",
      },
    },
  });

  useEffect(() => {
    if (isOpen && entryToEdit) {
      form.reset({
        name: entryToEdit.name,
        description: entryToEdit.description || entryToEdit.content || "",
        type: entryToEdit.type,
        subtype: entryToEdit.subtype || "",
        voice_profile: entryToEdit.voice_profile || {
          vocabulary: "",
          sentence_structure: "",
          speech_patterns_tics: "",
          tone: "",
          habits_mannerisms: "",
        },
      });
    } else if (!isOpen) {
      form.reset({
        name: "",
        type: undefined,
        subtype: "",
        description: "",
        voice_profile: {
          vocabulary: "",
          sentence_structure: "",
          speech_patterns_tics: "",
          tone: "",
          habits_mannerisms: "",
        },
      });
      setError(null);
    }
  }, [isOpen, entryToEdit, form]);

  const selectedType = form.watch("type");

  const onSubmit = async (values: CodexEntryFormValues) => {
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to save codex entry.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    const token = auth.user.id_token;

    const payload: CodexItemPayload = {
      name: values.name,
      description: values.description,
      type: values.type,
      subtype:
        values.type === CodexItemType.WORLDBUILDING ? values.subtype : null,
    };

    if (values.type === CodexItemType.CHARACTER && isProUser) {
      const voiceProfilePayload: CharacterVoiceProfileData = {};
      let hasVoiceData = false;
      if (values.voice_profile) {
        for (const key in values.voice_profile) {
          const typedKey = key as keyof CharacterVoiceProfileData;
          if (
            values.voice_profile[typedKey] &&
            values.voice_profile[typedKey]?.trim() !== ""
          ) {
            voiceProfilePayload[typedKey] = values.voice_profile[typedKey];
            hasVoiceData = true;
          } else {
            voiceProfilePayload[typedKey] = undefined;
          }
        }
      }
      if (hasVoiceData) {
        payload.voice_profile = voiceProfilePayload;
      }
    }

    try {
      if (isEditMode && entryToEdit) {
        // Make the PUT request to update the entry
        await fetchApi<unknown>( // Use <unknown> for PUT response as we won't use its body directly
          `/projects/${projectId}/codex-items/${entryToEdit.id}`,
          {
            method: "PUT",
            body: JSON.stringify(payload),
          },
          token
        );

        // After successful PUT, fetch the definitive updated entry using GET
        const freshUpdatedEntry = await fetchApi<CodexEntry>(
          `/projects/${projectId}/codex-items/${entryToEdit.id}`,
          {}, // Empty options for GET request
          token
        );

        if (!freshUpdatedEntry) {
          throw new Error("Failed to fetch the updated entry after PUT.");
        }

        // Call onEntryUpdated with the fresh data from GET
        onEntryUpdated(freshUpdatedEntry);
      } else {
        const creationResponse = await fetchApi<{
          id: string;
          message?: string;
          embedding_id?: string;
          voice_profile?: CharacterVoiceProfileData | null;
        }>(
          `/projects/${projectId}/codex-items`,
          {
            method: "POST",
            body: JSON.stringify(payload),
          },
          token
        );
        const newItemId = creationResponse?.id;
        if (!newItemId) {
          throw new Error(
            "Invalid response received after creating entry (missing ID)."
          );
        }
        const callbackData: CodexEntry = {
          id: newItemId,
          name: payload.name,
          title: payload.name,
          description: payload.description,
          content: payload.description,
          type: payload.type,
          subtype: payload.subtype,
          tags: [],
          voice_profile:
            creationResponse.voice_profile ||
            (payload.voice_profile as CharacterVoiceProfileData) ||
            null,
        };
        onEntryAdded(callbackData);
      }

      onOpenChange(false);
    } catch (err: unknown) {
      console.error(
        `Failed to ${isEditMode ? "update" : "create"} codex entry:`,
        err
      );
      const message =
        err instanceof Error ? err.message : "An unknown error occurred";
      setError(
        `Failed to ${isEditMode ? "update" : "create"} entry: ${message}`
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (isSubmitting) return;
    form.reset();
    setError(null);
    onOpenChange(false);
  };

  const renderVoiceProfileFields = () => {
    if (userSubLoading) {
      return (
        <div className="mt-4 p-4 border border-dashed border-border rounded-md text-center">
          <Loader2 className="h-5 w-5 animate-spin inline-block mr-2 text-muted-foreground" />
          <span className="text-muted-foreground text-sm">
            Checking Pro status...
          </span>
        </div>
      );
    }
    if (selectedType === CodexItemType.CHARACTER) {
      if (isProUser) {
        return (
          <div className="mt-4 p-4 border border-dashed border-purple-500/50 rounded-md bg-purple-500/5">
            <div className="flex items-center mb-3">
              <Sparkles className="h-5 w-5 mr-2 text-purple-500" />
              <h4 className="font-semibold text-purple-600">
                Character Voice Profile
              </h4>
            </div>
            <div className="space-y-4">
              <FormField
                control={form.control}
                name="voice_profile.vocabulary"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-sm">Vocabulary</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Common words, jargon, formality level (e.g., 'uses archaic terms', 'speaks formally')"
                        {...field}
                        className="min-h-[60px]"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="voice_profile.sentence_structure"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-sm">
                      Sentence Structure
                    </FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Typical length, complexity (e.g., 'short, choppy sentences', 'long, flowing prose')"
                        {...field}
                        className="min-h-[60px]"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="voice_profile.speech_patterns_tics"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-sm">
                      Speech Patterns/Tics
                    </FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Filler words, repeated phrases, accent hints (e.g., 'often says \'you know\'', 'slight lisp')"
                        {...field}
                        className="min-h-[60px]"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="voice_profile.tone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-sm">Tone</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Default emotional state and how it shifts (e.g., 'sarcastic but kind', 'generally cheerful')"
                        {...field}
                        className="min-h-[60px]"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="voice_profile.habits_mannerisms"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-sm">Habits/Mannerisms</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Associated non-verbal actions or verbal habits (e.g., 'taps fingers when thinking', 'always clears throat before speaking')"
                        {...field}
                        className="min-h-[60px]"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          </div>
        );
      } else {
        return (
          <div className="mt-4 p-4 border border-dashed border-border rounded-md text-center bg-muted/50">
            <Sparkles className="h-5 w-5 mr-2 text-muted-foreground inline-block" />
            <span className="text-muted-foreground text-sm">
              Unlock advanced Character Voice Profiles with a Pro subscription!
            </span>
          </div>
        );
      }
    }
    return null;
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[600px] bg-card border-border text-card-foreground rounded-lg">
        <DialogHeader>
          <DialogTitle className="text-foreground font-display">
            {isEditMode ? "Edit Codex Entry" : "Add New Codex Entry"}
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">
            {isEditMode
              ? "Update the details of your codex entry."
              : "Add a new entry to your project codex."}
          </DialogDescription>
        </DialogHeader>
        {error && (
          <div className="my-3 p-3 bg-destructive/90 border border-destructive text-destructive-foreground text-sm rounded-md flex items-center">
            <AlertTriangle className="h-4 w-4 mr-2" />
            {error}
          </div>
        )}
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="E.g., Aragorn, The One Ring"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Type</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    defaultValue={field.value}
                    value={field.value}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select a codex type" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {Object.entries(CodexItemType).map(([key, value]) => (
                        <SelectItem key={value} value={value}>
                          {formatEnumKey(key)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            {selectedType === CodexItemType.WORLDBUILDING && (
              <FormField
                control={form.control}
                name="subtype"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Subtype (for Worldbuilding)</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                      value={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select a subtype" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {Object.entries(WorldbuildingSubtype).map(
                          ([key, value]) => (
                            <SelectItem key={value} value={value}>
                              {formatEnumKey(key)}
                            </SelectItem>
                          )
                        )}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Detailed description of the codex item."
                      {...field}
                      className="min-h-[100px]"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {renderVoiceProfileFields()}

            <DialogFooter className="pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={handleClose}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={isSubmitting}
                className="min-w-[100px]"
              >
                {isSubmitting ? (
                  <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                ) : (
                  "Save"
                )}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose, // Import DialogClose
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Loader2, Trash2, Pencil, PlusCircle } from "lucide-react"; // Added icons
import { fetchApi } from "@/lib/api";
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth

// Zod schema for preset data validation
const presetFormSchema = z.object({
  name: z.string().min(1, "Preset name is required."),
  plot: z.string().optional(),
  writingStyle: z.string().optional(),
  numChapters: z.coerce.number().int().positive().optional(), // Use coerce for string->number conversion
  wordCount: z.coerce.number().int().positive().optional(),
  styleGuide: z.string().optional(),
  additionalInstructions: z.string().optional(),
});

type PresetFormData = z.infer<typeof presetFormSchema>;

// Define the structure for a preset (matching expected backend 'data' structure)
export interface Preset {
  id: string;
  name: string;
  data: {
    plot?: string;
    writingStyle?: string;
    numChapters?: number;
    wordCount?: number;
    // Flattened instruction fields
    styleGuide?: string;
    additionalInstructions?: string;
    // Also allow for nested instructions structure from backend
    instructions?: {
      styleGuide?: string;
      additionalInstructions?: string;
      wordCount?: number;
      [key: string]: string | number | boolean | undefined; // More specific than 'any'
    };
  };
}

// Map Preset to PresetFormData for editing (updated for flattened structure)
const mapPresetToFormData = (preset: Preset): PresetFormData => ({
  name: preset.name,
  plot: preset.data.plot || "",
  writingStyle: preset.data.writingStyle || "",
  numChapters: preset.data.numChapters,
  // Check if data has nested instructions or direct fields
  wordCount:
    preset.data.wordCount || preset.data.instructions?.wordCount || undefined,
  styleGuide:
    preset.data.styleGuide || preset.data.instructions?.styleGuide || "",
  additionalInstructions:
    preset.data.additionalInstructions ||
    preset.data.instructions?.additionalInstructions ||
    "",
});

// Define interfaces for the request bodies based on backend models
// Use specific optional fields instead of { [key: string]: any }
interface PresetCreateData {
  plot?: string;
  writingStyle?: string;
  numChapters?: number;
  wordCount?: number;
  styleGuide?: string;
  additionalInstructions?: string;
}

// Interface for the actual body sent by frontend (create)
interface PresetCreatePayloadFrontend {
  name: string;
  data: PresetCreateData;
}

interface PresetUpdateInstructions {
  styleGuide?: string;
  additionalInstructions?: string;
  wordCount?: number; // Assuming wordCount goes here for update
}
interface PresetUpdateData {
  // Corresponds to ChapterGenerationRequest
  numChapters?: number;
  plot?: string;
  writingStyle?: string;
  instructions: PresetUpdateInstructions; // Use the specific type
}
interface PresetUpdatePayload {
  name: string;
  data: PresetUpdateData;
}

interface PresetManagerProps {
  projectId: string;
  onPresetSelect: (presetData: Preset["data"]) => void;
}

export default function PresetManager({
  projectId,
  onPresetSelect,
}: PresetManagerProps) {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [isPresetsLoading, setIsPresetsLoading] = useState<boolean>(false);
  const [presetsError, setPresetsError] = useState<string | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState<boolean>(false);
  const [editingPreset, setEditingPreset] = useState<Preset | null>(null); // null for create, Preset object for edit
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [crudError, setCrudError] = useState<string | null>(null);
  const auth = useAuth(); // Use the hook

  const form = useForm<PresetFormData>({
    resolver: zodResolver(presetFormSchema),
    defaultValues: {
      // Initialize with empty/default values
      name: "",
      plot: "",
      writingStyle: "",
      numChapters: undefined,
      wordCount: undefined,
      styleGuide: "",
      additionalInstructions: "",
    },
  });

  // Memoize fetchPresets to avoid re-renders
  const fetchPresets = useCallback(
    async (token: string | undefined) => {
      if (!token) {
        setPresetsError("Authentication token is missing.");
        setIsPresetsLoading(false);
        return;
      }
      // Use projectId from props
      if (!projectId) {
        setPresetsError("Project ID is missing.");
        setIsPresetsLoading(false);
        return;
      }

      setIsPresetsLoading(true);
      setPresetsError(null);
      try {
        const response = await fetchApi<{ presets: Preset[] }>(
          `/projects/${projectId}/presets`, // Use projectId here
          { method: "GET" },
          token
        );

        // Normalize preset data structure to handle both nested and flat formats
        const normalizedPresets = response.presets.map((preset) => {
          // Create a normalized copy of the preset
          const normalizedPreset = { ...preset };

          // If the preset has data.instructions, flatten it for frontend use
          if (preset.data?.instructions) {
            normalizedPreset.data = {
              ...preset.data,
              // Flatten instructions fields to top level
              styleGuide:
                preset.data.instructions.styleGuide || preset.data.styleGuide,
              additionalInstructions:
                preset.data.instructions.additionalInstructions ||
                preset.data.additionalInstructions,
              wordCount:
                preset.data.instructions.wordCount || preset.data.wordCount,
            };
          }

          return normalizedPreset;
        });

        setPresets(normalizedPresets || []);
      } catch (err) {
        console.error("Failed to fetch presets:", err);
        setPresetsError(
          err instanceof Error ? err.message : "Failed to load presets."
        );
      } finally {
        setIsPresetsLoading(false);
      }
    },
    [projectId, setPresets, setPresetsError, setIsPresetsLoading]
  );

  // Fetch presets on component mount or when auth/projectId changes
  useEffect(() => {
    if (!auth.isLoading && auth.isAuthenticated && auth.user?.id_token) {
      fetchPresets(auth.user.id_token);
    } else if (!auth.isLoading && !auth.isAuthenticated) {
      setPresetsError("Authentication required to load presets.");
      // Set loading false here too
      setIsPresetsLoading(false);
    }
    // Depend on auth state, projectId, and the memoized fetchPresets
  }, [
    auth.isLoading,
    auth.isAuthenticated,
    auth.user?.id_token,
    projectId,
    fetchPresets, // Add fetchPresets to dependencies
  ]);

  // Handle preset selection from the dropdown
  const handlePresetSelectChange = (presetId: string) => {
    const selectedPreset = presets.find((p) => p.id === presetId);
    if (selectedPreset) {
      onPresetSelect(selectedPreset.data);
      // Optionally reset the select trigger value if needed, or manage externally
    }
  };

  // Open dialog for creating a new preset
  const handleCreatePreset = () => {
    setEditingPreset(null);
    form.reset({
      // Reset form to defaults for creation
      name: "",
      plot: "",
      writingStyle: "",
      numChapters: undefined,
      wordCount: undefined,
      styleGuide: "",
      additionalInstructions: "",
    });
    setCrudError(null);
    setIsDialogOpen(true);
  };

  // Open dialog for editing an existing preset
  const handleEditPreset = (preset: Preset) => {
    setEditingPreset(preset);
    form.reset(mapPresetToFormData(preset)); // Populate form with preset data
    setCrudError(null);
    setIsDialogOpen(true);
  };

  // Handle deleting a preset
  const handleDeletePreset = async (presetId: string) => {
    if (!confirm("Are you sure you want to delete this preset?")) {
      return;
    }
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setCrudError("Authentication required to delete preset.");
      return;
    }
    setIsSubmitting(true); // Use submitting state for delete as well
    setCrudError(null);
    const token = auth.user.id_token; // Get token
    try {
      await fetchApi(
        `/projects/${projectId}/presets/${presetId}`,
        { method: "DELETE" },
        token // Pass token
      );
      // Optimistic UI update or refetch
      setPresets(presets.filter((p) => p.id !== presetId));
      // If the deleted preset was selected in the parent form, maybe clear it?
      // This depends on desired UX. For now, just remove from list.
      if (auth.isAuthenticated && auth.user?.id_token) {
        fetchPresets(auth.user.id_token); // Refetch after successful delete
      }
    } catch (err) {
      console.error("Failed to delete preset:", err);
      setCrudError(
        err instanceof Error ? err.message : "Failed to delete preset."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle form submission (Create or Update)
  const onSubmit = async (
    formData: PresetFormData,
    e?: React.BaseSyntheticEvent
  ) => {
    // Stop event propagation if an event was passed
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }

    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setCrudError("Authentication required to save preset.");
      return;
    }
    setIsSubmitting(true);
    setCrudError(null);
    const token = auth.user.id_token; // Get token

    // Use the Frontend create payload type here
    let requestBody: PresetCreatePayloadFrontend | PresetUpdatePayload;
    let url: string;
    let method: "POST" | "PUT";

    if (editingPreset) {
      // --- Prepare body for UPDATE (PUT) ---
      method = "PUT";
      url = `/projects/${projectId}/presets/${editingPreset.id}`;
      requestBody = {
        name: formData.name,
        data: {
          // Ensure all required fields are present for ChapterGenerationRequest
          numChapters: formData.numChapters || 1, // Default to 1 if undefined
          plot: formData.plot || "", // Default to empty string if undefined
          writingStyle: formData.writingStyle || "", // Default to empty string if undefined
          instructions: {
            // Instructions dictionary
            styleGuide: formData.styleGuide || "",
            additionalInstructions: formData.additionalInstructions || "",
            wordCount: formData.wordCount || 0, // Default to 0 if undefined
          },
        },
      };
    } else {
      // --- Prepare body for CREATE (POST) ---
      method = "POST";
      url = `/projects/${projectId}/presets`;
      requestBody = {
        name: formData.name,
        data: {
          // Flatten data into Dict[str, Any]
          plot: formData.plot,
          writingStyle: formData.writingStyle,
          numChapters: formData.numChapters,
          wordCount: formData.wordCount,
          // Flatten instructions directly into the data dict
          styleGuide: formData.styleGuide,
          additionalInstructions: formData.additionalInstructions,
        },
      };
      // Filter out undefined/empty optional fields from data
      // Now we can safely access keys because requestBody.data is PresetCreateData
      // Ensure we are only doing this for the CREATE case
      if (method === "POST") {
        const createData = requestBody.data as PresetCreateData; // Type assertion for safety
        Object.keys(createData).forEach((key) => {
          const typedKey = key as keyof PresetCreateData; // Type assertion
          if (
            createData[typedKey] === undefined ||
            createData[typedKey] === ""
          ) {
            delete createData[typedKey];
          }
        });
      }
    }

    console.log(
      "Sending request:",
      method,
      url,
      JSON.stringify(requestBody, null, 2)
    ); // Log the request

    try {
      const savedPreset = await fetchApi<Preset>(
        url,
        {
          method: method,
          body: JSON.stringify(requestBody), // Use the correctly structured body
        },
        token // Pass token
      );

      // Update local state optimistically or refetch
      if (editingPreset) {
        setPresets(
          presets.map((p) => (p.id === savedPreset.id ? savedPreset : p))
        );
      } else {
        setPresets([...presets, savedPreset]);
      }
      setIsDialogOpen(false); // Close dialog on success
      if (auth.isAuthenticated && auth.user?.id_token) {
        fetchPresets(auth.user.id_token); // Refetch after successful create/update
      }
    } catch (err) {
      console.error(
        `Failed to ${editingPreset ? "update" : "create"} preset:`,
        err
      );
      setCrudError(
        err instanceof Error
          ? err.message
          : `Failed to ${editingPreset ? "update" : "create"} preset.`
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Load Preset Dropdown */}
      <div className="space-y-2">
        <Label htmlFor="preset-select" className="text-foreground">
          Load Preset (Optional)
        </Label>
        {isPresetsLoading ? (
          <div className="flex items-center space-x-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Loading presets...</span>
          </div>
        ) : presetsError ? (
          <p className="text-sm text-destructive">Error: {presetsError}</p>
        ) : (
          <Select
            onValueChange={handlePresetSelectChange}
            disabled={presets.length === 0}
          >
            <SelectTrigger id="preset-select">
              <SelectValue
                placeholder={
                  presets.length > 0
                    ? "Select a preset to load..."
                    : "No presets available"
                }
              />
            </SelectTrigger>
            <SelectContent>
              {presets.map((preset) => (
                <SelectItem key={preset.id} value={preset.id}>
                  {preset.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* Manage Presets Button & Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogTrigger asChild>
          <Button variant="outline" size="sm">
            <PlusCircle className="mr-2 h-4 w-4" /> Manage Presets
          </Button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>
              {editingPreset ? "Edit Preset" : "Create New Preset"}
            </DialogTitle>
            <DialogDescription>
              {editingPreset
                ? "Modify the details of this preset."
                : "Save the current generation settings as a new preset."}
            </DialogDescription>
          </DialogHeader>

          {/* Preset Form */}
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit((data, event) =>
                onSubmit(data, event)
              )}
              className="space-y-4 py-4"
            >
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Preset Name</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., Epic Fantasy Tone" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Grouping other fields - adjust layout as needed */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="numChapters"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Number of Chapters</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min="1"
                          placeholder="Default: 1"
                          {...field}
                          onChange={(event) =>
                            field.onChange(+event.target.value)
                          }
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="wordCount"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Approx. Words/Chapter</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min="50"
                          placeholder="e.g., 1500"
                          {...field}
                          onChange={(event) =>
                            field.onChange(+event.target.value)
                          }
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="plot"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Plot / Scene Outline</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Preset plot outline..."
                        className="min-h-[80px]"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="writingStyle"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Writing Style</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Preset writing style description..."
                        className="min-h-[80px]"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="styleGuide"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Style Guide / Rules</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Preset style guide rules..."
                        className="min-h-[80px]"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="additionalInstructions"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Other Instructions</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Other preset instructions..."
                        className="min-h-[80px]"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {crudError && (
                <p className="text-sm text-destructive">{crudError}</p>
              )}

              <DialogFooter>
                <DialogClose asChild>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={isSubmitting}
                  >
                    Cancel
                  </Button>
                </DialogClose>
                <Button
                  type="submit"
                  disabled={isSubmitting}
                  onClick={(e) => {
                    // Prevent event from propagating up
                    e.stopPropagation();
                  }}
                >
                  {isSubmitting && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  {editingPreset ? "Save Changes" : "Create Preset"}
                </Button>
              </DialogFooter>
            </form>
          </Form>

          {/* List existing presets for editing/deleting inside the dialog */}
          <div className="mt-6 border-t pt-4 space-y-3">
            <div className="flex justify-between items-center">
              <h4 className="text-sm font-medium text-muted-foreground">
                Existing Presets
              </h4>
              {/* Add Button to trigger create mode */}
              <Button
                variant="outline"
                size="sm"
                onClick={handleCreatePreset}
                disabled={isSubmitting}
              >
                <PlusCircle className="mr-2 h-4 w-4" /> New
              </Button>
            </div>
            {isPresetsLoading ? (
              <div className="flex items-center space-x-2 text-muted-foreground text-sm">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Loading...</span>
              </div>
            ) : presetsError ? (
              <p className="text-sm text-destructive">
                Error loading presets: {presetsError}
              </p>
            ) : presets.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No presets saved yet.
              </p>
            ) : (
              <ul className="space-y-2 max-h-48 overflow-y-auto">
                {presets.map((preset) => (
                  <li
                    key={preset.id}
                    className="flex justify-between items-center text-sm p-2 border rounded"
                  >
                    <span>{preset.name}</span>
                    <div className="space-x-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleEditPreset(preset)}
                        disabled={isSubmitting}
                      >
                        <Pencil className="h-4 w-4" />
                        <span className="sr-only">Edit</span>
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDeletePreset(preset.id)}
                        disabled={isSubmitting}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                        <span className="sr-only">Delete</span>
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

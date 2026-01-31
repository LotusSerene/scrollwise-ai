"use client";

import React, { useState, useEffect, use } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { Textarea } from "@/components/ui/textarea";
import { Loader2, AlertTriangle, Sparkles, Wand2 } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { CodexItemType, WorldbuildingSubtype } from "@/types"; // Ensure types are imported
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth

// Helper to format enum keys for display
function formatEnumKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/(?:^|\s)\S/g, (a) => a.toUpperCase());
}

// Zod schema for the generation request form, based on CodexItemGenerateRequest
const generationSchema = z
  .object({
    codex_type: z.nativeEnum(CodexItemType, {
      required_error: "Please select a codex type.",
    }),
    subtype: z.string().optional(),
    description: z
      .string()
      .min(10, {
        message: "Please provide a more detailed description (min 10 chars).",
      })
      .max(1000, { message: "Description cannot exceed 1000 characters." }),
  })
  .refine(
    (data) => {
      // Subtype is required only if type is Worldbuilding
      if (data.codex_type === CodexItemType.WORLDBUILDING) {
        return !!data.subtype;
      }
      return true;
    },
    {
      message: "Subtype is required for Worldbuilding entries.",
      path: ["subtype"], // Apply error to subtype field
    }
  );

type GenerationFormValues = z.infer<typeof generationSchema>;

// Ensure this interface is present
interface GenerationResponse {
  message: string;
  item: {
    name: string;
    description: string;
  };
  id: string;
  embedding_id: string | null;
}

// Using correct Next.js 15 App Router page props type
type PageProps = {
  params: Promise<{
    projectId: string;
  }>;
  searchParams?: Promise<{ [key: string]: string | string[] | undefined }>;
};

// Client component wrapper that will use React hooks
function CodexGenerationClient({ projectId }: { projectId: string }) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generatedItem, setGeneratedItem] = useState<
    GenerationResponse["item"] | null
  >(null);
  const [newItemId, setNewItemId] = useState<string | null>(null);
  const auth = useAuth(); // Use the hook

  const form = useForm<GenerationFormValues>({
    resolver: zodResolver(generationSchema),
    defaultValues: {
      codex_type: undefined,
      subtype: "",
      description: "",
    },
  });

  const selectedType = form.watch("codex_type");

  const onSubmit = async (values: GenerationFormValues) => {
    setIsGenerating(true);
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to generate codex entry.");
      return;
    }
    setError(null);
    setGeneratedItem(null);
    setNewItemId(null);
    const token = auth.user.id_token; // Get token

    const payload = {
      ...values,
      // Ensure subtype is only sent when type is Worldbuilding
      subtype:
        values.codex_type === CodexItemType.WORLDBUILDING
          ? values.subtype
          : null,
    };

    try {
      const response = await fetchApi<GenerationResponse>(
        `/projects/${projectId}/codex/generate`,
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
        token
      );

      console.log("Generation successful:", response);
      setGeneratedItem(response.item);
      setNewItemId(response.id);
      // Optionally reset form? Or keep values? Keeping for now.
      // form.reset();
    } catch (err: unknown) {
      console.error("Failed to generate codex item:", err);
      const message =
        err instanceof Error ? err.message : "An unknown error occurred";
      setError(`Generation failed: ${message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    // Adjust container padding if needed, remove explicit container class if layout provides it
    <section className="py-8">
      {/* Apply theme styles to Card */}
      <Card className="w-full max-w-2xl mx-auto bg-card border-border rounded-lg">
        <CardHeader>
          {/* Apply theme styles to CardTitle and CardDescription */}
          <CardTitle className="flex items-center gap-2 text-foreground font-display">
            {/* Use primary color for icon */}
            <Wand2 className="h-6 w-6 text-primary" />
            Generate New Codex Entry
          </CardTitle>
          <CardDescription className="text-muted-foreground">
            Describe the kind of codex entry you want to create, and the AI will
            generate the details.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Apply theme styles to error message */}
          {error && (
            <div className="mb-4 p-3 bg-destructive/10 border border-destructive text-destructive-foreground text-sm rounded-md flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              <FormField
                control={form.control}
                name="codex_type"
                render={({ field }) => (
                  <FormItem>
                    {/* Apply theme style to FormLabel */}
                    <FormLabel className="text-foreground">
                      Codex Type
                    </FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                      value={field.value}
                      disabled={isGenerating}
                    >
                      <FormControl>
                        {/* SelectTrigger inherits theme styles */}
                        <SelectTrigger className="">
                          <SelectValue placeholder="Select the type of item" />
                        </SelectTrigger>
                      </FormControl>
                      {/* Apply theme styles to SelectContent and SelectItem */}
                      <SelectContent className="bg-popover border-border text-popover-foreground">
                        {Object.entries(CodexItemType).map(([key, value]) => (
                          <SelectItem
                            key={value}
                            value={value}
                            className="hover:bg-accent focus:bg-accent"
                          >
                            {formatEnumKey(key)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {/* Apply theme style to FormMessage */}
                    <FormMessage className="text-destructive" />
                  </FormItem>
                )}
              />

              {selectedType === CodexItemType.WORLDBUILDING && (
                <FormField
                  control={form.control}
                  name="subtype"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-foreground">
                        Worldbuilding Subtype
                      </FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                        value={field.value}
                        disabled={isGenerating}
                      >
                        <FormControl>
                          <SelectTrigger className="">
                            <SelectValue placeholder="Select a worldbuilding subtype" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent className="bg-popover border-border text-popover-foreground">
                          {Object.entries(WorldbuildingSubtype).map(
                            ([key, value]) => (
                              <SelectItem
                                key={value}
                                value={value}
                                className="hover:bg-accent focus:bg-accent"
                              >
                                {formatEnumKey(key)}
                              </SelectItem>
                            )
                          )}
                        </SelectContent>
                      </Select>
                      <FormMessage className="text-destructive" />
                    </FormItem>
                  )}
                />
              )}

              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-foreground">
                      Generation Prompt / Description
                    </FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Describe the core idea for the codex entry. For example: 'A cynical, chain-smoking detective in a neon-drenched cyberpunk city' or 'A magical sword forged from starlight, hidden in an ancient ruin'."
                        {...field}
                        // Textarea inherits theme styles
                        className="min-h-[150px]"
                        disabled={isGenerating}
                      />
                    </FormControl>
                    <FormMessage className="text-destructive" />
                  </FormItem>
                )}
              />

              {/* Apply theme styles to Button */}
              <Button type="submit" disabled={isGenerating} className="w-full">
                {isGenerating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    {/* Use primary color for icon */}
                    <Sparkles className="mr-2 h-4 w-4 text-primary-foreground" />
                    Generate Entry
                  </>
                )}
              </Button>
            </form>
          </Form>
        </CardContent>
        {/* Apply theme styles to CardFooter and generated item display */}
        {generatedItem && (
          <CardFooter className="flex flex-col items-start gap-4 border-t border-border pt-6">
            {/* Use primary color for heading */}
            <h3 className="text-lg font-semibold text-primary font-display">
              Generated Item:
            </h3>
            {/* Use accent background for result box */}
            <div className="p-4 bg-accent/50 rounded-md w-full border border-border/50">
              {/* Use theme text colors */}
              <p className="font-medium text-foreground">
                Name: {generatedItem.name}
              </p>
              <p className="mt-2 text-muted-foreground">
                Description: {generatedItem.description}
              </p>
              {newItemId && (
                <p className="text-xs text-muted-foreground/80 mt-3">
                  Database ID: {newItemId}
                </p>
              )}
            </div>
          </CardFooter>
        )}
      </Card>
    </section>
  );
}

// Main page component that handles the async params
export default function CodexGenerationPage(props: PageProps) {
  const params = use(props.params);
  // Use a state to store the projectId
  const [projectId, setProjectId] = useState<string | null>(null);

  // Use useEffect to handle the async operation
  useEffect(() => {
    const fetchParams = async () => {
      const { projectId } = await params;
      setProjectId(projectId);
    };
    fetchParams();
  }, [params]);

  // Render the client component only when projectId is available
  if (!projectId) return null;

  // Render the client component with the extracted projectId
  return <CodexGenerationClient projectId={projectId} />;
}

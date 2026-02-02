// frontend/src/app/project-dashboard/[projectId]/settings/page.tsx
"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { fetchApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Loader2, AlertTriangle, Trash2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/components/MockAuthProvider";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { useProject } from "@/contexts/ProjectContext"; // Import the context hook

// Define the form schema for editing project details
const projectSettingsSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters.").max(100),
  description: z
    .string()
    .max(500, "Description cannot exceed 500 characters.")
    .optional(),
  target_word_count: z.coerce // Use coerce for number conversion from input
    .number()
    .int()
    .min(0, "Target word count cannot be negative.")
    .optional()
    .nullable(), // Allow null for empty input
});

type ProjectSettingsFormData = z.infer<typeof projectSettingsSchema>;

// Type for the project data fetched from API (adjust based on actual API response)
interface ProjectData {
  id: string;
  name: string;
  description: string | null;
  universe_id: string | null;
  target_word_count: number | null;
  architect_mode_enabled: boolean;
  // Add other fields if needed
}

interface UserDetails {
  id: string;
  subscription_plan: string | null;
  subscription_status: string | null;
  // ... other user fields
}

export default function ProjectSettingsPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.projectId as string;
  const auth = useAuth();
  const { project, setProject, isLoading: isProjectLoading } = useProject(); // Use context

  const [userDetails, setUserDetails] = useState<UserDetails | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);

  const form = useForm<ProjectSettingsFormData>({
    resolver: zodResolver(projectSettingsSchema),
    defaultValues: {
      name: "",
      description: "",
      target_word_count: null, // Default to null
    },
  });

  const isProUser = useCallback(() => {
    return true; // Always pro in local version
  }, []);

  // Fetch project data on mount or auth change
  useEffect(() => {
    const fetchUserData = async (token: string | undefined) => {
      if (!token) return;
      try {
        const userData = await fetchApi<UserDetails>("/users/me", {}, token);
        setUserDetails(userData);
      } catch (err) {
        console.error("Failed to fetch user details:", err);
      }
    };
    // Fetch only when authenticated
    if (!auth.isLoading && auth.isAuthenticated && auth.user?.id_token) {
      if (!userDetails) {
        fetchUserData(auth.user.id_token);
      }
    } else if (!auth.isLoading && !auth.isAuthenticated) {
      setError("Authentication required to view project settings.");
    }
  }, [auth, userDetails]);

  // Effect to sync form with project context
  useEffect(() => {
    if (project) {
      form.reset({
        name: project.name || "",
        description: project.description || "",
        target_word_count: project.target_word_count ?? null,
      });
    }
  }, [project, form]);

  // Add check for projectId after hooks
  if (!projectId) {
    return <div>Invalid Project ID.</div>;
  }

  // Handle form submission for updating project details
  const onSubmit = async (values: ProjectSettingsFormData) => {
    if (!project) return;
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to save settings.");
      return;
    }
    const toastId = toast.loading("Saving project settings...");
    setIsSaving(true);
    setError(null);
    const token = auth.user.id_token; // Get token
    try {
      // Ensure target_word_count is sent as null if empty/optional
      const payload = {
        name: values.name,
        description: values.description || null, // Ensure null if empty
        target_word_count: values.target_word_count ?? null, // Ensure null if empty/undefined
        universe_id: project.universe_id, // Keep existing universe_id
      };
      // Assume the backend PUT endpoint returns the updated project data
      const updatedProject = await fetchApi<ProjectData>(
        `/projects/${projectId}`,
        {
          method: "PUT",
          body: JSON.stringify(payload),
        },
        token // Pass token
      );
      toast.success("Project settings updated successfully!", { id: toastId });
      // Update state and form with the response from the PUT request
      setProject(updatedProject); // Update context
      form.reset({
        name: updatedProject.name || "",
        description: updatedProject.description || "",
        target_word_count: updatedProject.target_word_count ?? null, // Use nullish coalescing
      });
    } catch (err: unknown) {
      // Use unknown
      console.error("Failed to update project settings:", err);
      const message =
        err instanceof Error ? err.message : "Failed to save settings.";
      setError(message);
      toast.error(`Failed to save settings: ${message}`, { id: toastId });
    } finally {
      setIsSaving(false);
    }
  };

  // Handle project deletion
  const handleDeleteProject = async () => {
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to delete project.");
      return;
    }
    const toastId = toast.loading("Deleting project...");
    setIsDeleting(true);
    setError(null);
    const token = auth.user.id_token; // Get token
    try {
      await fetchApi(
        `/projects/${projectId}`,
        { method: "DELETE" },
        token // Pass token
      );
      toast.success("Project deleted successfully!", { id: toastId });
      router.push("/dashboard"); // Redirect to dashboard after deletion
    } catch (err: unknown) {
      // Use unknown
      console.error("Failed to delete project:", err);
      const message =
        err instanceof Error ? err.message : "Failed to delete project.";
      setError(message);
      toast.error(`Failed to delete project: ${message}`, { id: toastId });
      setIsDeleting(false); // Re-enable button on error
    }
    // No finally block needed here as we navigate away on success
  };

  // Handle toggle change
  const handleArchitectToggle = async (enabled: boolean) => {
    if (!project || !auth.user?.id_token) return;

    // Prevent non-pro users from enabling
    if (enabled && !isProUser()) {
      toast.error("Architect Mode requires a Pro subscription to enable.");
      return;
    }

    const toastId = toast.loading("Updating Architect Mode...");
    setIsUpdating(true);
    const originalState = project.architect_mode_enabled;
    // Optimistically update UI via context
    setProject({ ...project, architect_mode_enabled: enabled });

    try {
      await fetchApi(
        `/projects/${projectId}/settings/architect`,
        {
          method: "PUT",
          body: JSON.stringify({ enabled }),
        },
        auth.user.id_token
      );
      toast.success(
        `Architect Mode successfully ${enabled ? "enabled" : "disabled"}.`,
        { id: toastId }
      );
      // No longer need router.refresh()
    } catch (err: unknown) {
      console.error("Failed to update Architect mode:", err);
      const message =
        err instanceof Error ? err.message : "An unknown error occurred.";
      toast.error(`Failed to update Architect Mode: ${message}`, {
        id: toastId,
      });
      // Revert optimistic update on error via context
      setProject({ ...project, architect_mode_enabled: originalState });
    } finally {
      setIsUpdating(false);
    }
  };

  if (isProjectLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-1/3" />
        <Skeleton className="h-8 w-1/2" />
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-1/4 mb-2" />
            <Skeleton className="h-4 w-3/4" />
          </CardHeader>
          <CardContent className="space-y-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error && !project) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!project) {
    // Should be covered by loading/error states, but good fallback
    return <div className="text-center py-10">Project data not available.</div>;
  }

  return (
    <div className="space-y-8 max-w-3xl mx-auto pb-24">
      <h2 className="text-2xl font-semibold tracking-tight text-foreground">
        Project Settings
      </h2>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Architect Mode
          </CardTitle>
          <CardDescription>
            Enable the advanced AI Architect for this project, providing
            enhanced planning, generation tools, and project management
            capabilities.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center space-x-3 rounded-md border border-border p-4 bg-background/30">
            <Switch
              id="architect-mode"
              checked={project.architect_mode_enabled}
              onCheckedChange={handleArchitectToggle}
              disabled={
                isUpdating || (!isProUser() && !project.architect_mode_enabled)
              }
              aria-readonly={isUpdating}
            />
            <Label
              htmlFor="architect-mode"
              className={`flex-grow cursor-pointer ${isUpdating ? "opacity-50" : ""
                }`}
            >
              {project.architect_mode_enabled
                ? "Architect Mode Enabled"
                : "Architect Mode Disabled"}
            </Label>
            {isUpdating && (
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            )}
          </div>
        </CardContent>
      </Card>

      {/* Edit Project Form */}
      <Card>
        <CardHeader>
          <CardTitle>Project Details</CardTitle>
          <CardDescription>
            Update your project&apos;s name, description, and target word count.
          </CardDescription>{" "}
          {/* Fixed quote */}
        </CardHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <CardContent className="space-y-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Project Name</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="Your Project Name"
                        {...field}
                        disabled={isSaving}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="A brief description of your project..."
                        {...field}
                        value={field.value ?? ""}
                        disabled={isSaving}
                        rows={3}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="target_word_count"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Target Word Count</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        placeholder="e.g., 80000"
                        {...field}
                        // Handle null/undefined for the input value
                        value={field.value ?? ""}
                        onChange={(e) => {
                          const value = e.target.value;
                          // Allow empty string, otherwise convert to number or null
                          field.onChange(value === "" ? null : Number(value));
                        }}
                        disabled={isSaving}
                        min="0"
                      />
                    </FormControl>
                    <FormDescription>
                      Set a goal for your project&apos;s length (optional).{" "}
                      {/* Fixed quote */}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
            <CardFooter className="border-t px-6 py-4">
              <Button type="submit" disabled={isSaving}>
                {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save Changes
              </Button>
            </CardFooter>
          </form>
        </Form>
      </Card>

      {/* Danger Zone */}
      <Card className="border-destructive">
        <CardHeader>
          <CardTitle className="text-destructive">Danger Zone</CardTitle>
          <CardDescription>
            Permanent actions that cannot be undone.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex justify-between items-center p-4 border rounded-md border-destructive/50 bg-destructive/5">
            <div>
              <h4 className="font-semibold">Delete this project</h4>
              <p className="text-sm text-muted-foreground">
                Once deleted, all associated data (chapters, codex items, etc.)
                will be permanently removed.
              </p>
            </div>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" disabled={isDeleting}>
                  {isDeleting ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="mr-2 h-4 w-4" />
                  )}
                  Delete Project
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This action cannot be undone. This will permanently delete
                    the project
                    <span className="font-semibold"> {project.name} </span>
                    and all its associated data from our servers.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel disabled={isDeleting}>
                    Cancel
                  </AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleDeleteProject}
                    disabled={isDeleting}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    {isDeleting && (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    Yes, delete project
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

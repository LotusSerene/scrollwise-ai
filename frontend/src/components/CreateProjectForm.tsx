"use client";

import React, { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
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
import { Loader2, AlertTriangle, CircleDashed } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth

// Define the Universe type (simplified)
interface Universe {
  id: string;
  name: string;
}

// Define the form schema using Zod, including universeId
const formSchema = z.object({
  name: z
    .string()
    .min(2, {
      message: "Project name must be at least 2 characters.",
    })
    .max(100, {
      message: "Project name must not exceed 100 characters.",
    }),
  description: z
    .string()
    .max(500, {
      message: "Description must not exceed 500 characters.",
    })
    .optional(),
  universeId: z.string().optional(), // Optional string for universe ID
});

type FormData = z.infer<typeof formSchema>;

// Define Project type for onSuccess callback (matching backend)
interface Project {
  id: string;
  name: string;
  description: string | null;
  universe_id: string | null;
  // Add other fields if returned by backend
}

interface CreateProjectFormProps {
  onSuccess: (newProject: Project) => void; // Use specific Project type
  onCancel: () => void;
  defaultUniverseId?: string | null; // Add optional prop for pre-selection
}

export function CreateProjectForm({
  onSuccess,
  onCancel,
  defaultUniverseId, // Destructure the new prop
}: CreateProjectFormProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingUniverses, setIsFetchingUniverses] = useState(true); // State for universe fetch
  const [error, setError] = useState<string | null>(null);
  const [universes, setUniverses] = useState<Universe[]>([]); // State for universes
  const auth = useAuth(); // Use the hook

  // Fetch universes on component mount or auth change
  useEffect(() => {
    const fetchUniverses = async (token: string | undefined) => {
      if (!token) {
        setError("Authentication token is missing for fetching universes.");
        setIsFetchingUniverses(false);
        return;
      }
      setIsFetchingUniverses(true);
      // Token is passed as argument
      try {
        // Assuming fetchApi returns the array directly based on dashboard page
        const fetchedUniverses = await fetchApi<Universe[]>(
          "/universes",
          {},
          token
        );
        setUniverses(fetchedUniverses || []); // Ensure it's an array
      } catch (err) {
        console.error("Failed to fetch universes:", err);
        // Optionally set an error state specific to universes fetch
        setError(
          "Could not load universes. You can still create standalone projects."
        );
      } finally {
        setIsFetchingUniverses(false);
      }
    };

    // Fetch only when authenticated
    if (!auth.isLoading && auth.isAuthenticated && auth.user?.id_token) {
      fetchUniverses(auth.user.id_token);
    } else if (!auth.isLoading && !auth.isAuthenticated) {
      setError("Authentication required to list universes.");
      setIsFetchingUniverses(false);
    }
    // Depend on auth state
  }, [auth.isLoading, auth.isAuthenticated, auth.user?.id_token]);

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      description: "",
      // Set default universe based on prop, otherwise 'none'
      universeId: defaultUniverseId ?? "none",
    },
  });

  async function onSubmit(values: FormData) {
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to create project.");
      return;
    }
    setIsLoading(true);
    setError(null);
    const token = auth.user.id_token; // Get token

    try {
      // Backend expects name, description, user_id (from token), universe_id (optional)
      const payload = {
        name: values.name,
        description: values.description || null,
        // Send null if universeId is "none" or undefined, otherwise send the ID
        universe_id:
          values.universeId && values.universeId !== "none"
            ? values.universeId
            : null,
      };

      // Assuming fetchApi returns an object with a 'project' key
      const result = await fetchApi<{ project: Project }>(
        "/projects",
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
        token
      );

      console.log("Project creation successful:", result);
      if (result.project) {
        onSuccess(result.project); // Pass the specific project data back
      } else {
        throw new Error("Project data missing in API response.");
      }
    } catch (err) {
      // Use unknown type for better error handling
      console.error("Project creation failed:", err);
      let message = "Failed to create project. Please try again.";
      if (err instanceof Error) {
        message = err.message;
      }
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Project Name</FormLabel>
              <FormControl>
                <Input
                  placeholder="My Awesome Novel"
                  {...field}
                  disabled={isLoading || isFetchingUniverses}
                />
              </FormControl>
              <FormDescription>
                Give your project a distinct name.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="universeId"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Universe (Optional)</FormLabel>
              <Select
                onValueChange={field.onChange}
                // Use the form's current value for defaultValue/value management
                value={field.value}
                // Disable if fetching, loading, OR if a defaultUniverseId was provided
                disabled={isLoading || isFetchingUniverses || !!defaultUniverseId}
              >
                <FormControl>
                  <SelectTrigger
                    className={isFetchingUniverses ? "text-gray-500" : ""}
                  >
                    {isFetchingUniverses ? (
                      <div className="flex items-center gap-2">
                        <CircleDashed className="h-4 w-4 animate-spin" />{" "}
                        Loading Universes...
                      </div>
                    ) : (
                      <SelectValue placeholder="Select a universe (optional)" />
                    )}
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="none">-- Standalone Project --</SelectItem>
                  {universes.map((universe) => (
                    <SelectItem key={universe.id} value={universe.id}>
                      {universe.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormDescription>
                Assign this project to an existing universe or leave it
                standalone.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description (Optional)</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="A brief summary of your project..."
                  className="resize-none"
                  {...field}
                  value={field.value ?? ""}
                  disabled={isLoading || isFetchingUniverses}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {error && (
          <div className="flex items-center gap-2 text-sm text-red-500 bg-red-500/10 p-3 rounded-md">
            <AlertTriangle className="h-4 w-4" />
            <span>{error}</span>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-4">
          <Button
            type="button"
            variant="ghost"
            onClick={onCancel}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={isLoading || isFetchingUniverses}
            className="min-w-[100px]"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              "Create Project"
            )}
          </Button>
        </div>
      </form>
    </Form>
  );
}

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
import { Edit } from "lucide-react"; // Changed icon
import { fetchApi } from "@/lib/api";
import { toast } from "sonner";

// Interface (could be shared)
interface Location {
  id: string;
  name: string;
  description: string;
  coordinates?: string;
}

// Zod schema (same as AddLocationForm)
const formSchema = z.object({
  name: z
    .string()
    .min(1, "Location name is required.")
    .max(100, "Name too long"),
  description: z.string().min(1, "Description is required."),
  coordinates: z.string().optional(),
});

type LocationFormValues = z.infer<typeof formSchema>;

interface EditLocationFormProps {
  projectId: string;
  location: Location; // The location to edit
  onLocationUpdated: () => void; // Callback after successful update
  onCancel: () => void; // Callback to close modal without saving
  token: string | null; // Receive token directly
}

export function EditLocationForm({
  projectId,
  location,
  onLocationUpdated,
  onCancel,
  token, // Use the passed token
}: EditLocationFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<LocationFormValues>({
    resolver: zodResolver(formSchema),
    // Pre-populate with existing location data
    defaultValues: {
      name: location.name,
      description: location.description,
      coordinates: location.coordinates || "",
    },
  });

  // Reset form if the location prop changes
  useEffect(() => {
    form.reset({
      name: location.name,
      description: location.description,
      coordinates: location.coordinates || "",
    });
  }, [location, form]);

  async function onSubmit(values: LocationFormValues) {
    if (!token) {
      toast.error("Authentication token is missing. Cannot update location.");
      return;
    }
    setIsSubmitting(true);
    // Use the token passed via props
    try {
      // Construct the payload for the API
      const payload = {
        name: values.name,
        description: values.description,
        coordinates: values.coordinates || null, // Send null if empty
      };

      // Make PUT request to update the specific location
      await fetchApi(
        `/projects/${projectId}/locations/${location.id}`,
        {
          method: "PUT",
          body: JSON.stringify(payload),
          headers: {
            "Content-Type": "application/json",
          },
        },
        token
      );

      toast.success("Location updated successfully.");
      onLocationUpdated(); // Refresh list and close modal
    } catch (error) {
      console.error("Failed to update location:", error);
      const errorMsg =
        error instanceof Error ? error.message : "Please try again.";
      toast.error(`Failed to update location: ${errorMsg}`);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        {/* Name */}
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Location Name</FormLabel>
              <FormControl>
                <Input
                  placeholder="e.g., The Whispering Caves, Capital City Market"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Description */}
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Describe the location's key features, atmosphere, etc..."
                  className="resize-y min-h-[100px]"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Coordinates (Optional) */}
        <FormField
          control={form.control}
          name="coordinates"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Coordinates (Optional)</FormLabel>
              <FormControl>
                <Input
                  placeholder="e.g., 45.67 N, 12.34 E or map grid reference"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                Geographic coordinates or map reference, if applicable.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="flex justify-end space-x-2 pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={isSubmitting}
            className="bg-green-600 hover:bg-green-700"
          >
            {isSubmitting ? "Saving..." : "Save Changes"}
            <Edit className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </form>
    </Form>
  );
}

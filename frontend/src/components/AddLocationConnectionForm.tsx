"use client";

import React, { useState } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { PlusCircle } from "lucide-react"; // Icons for location connection
import { fetchApi } from "@/lib/api";
import { toast } from "sonner";

// Interface for location (could be shared)
interface Location {
  id: string;
  name: string;
}

// Zod schema for location connection form validation
const formSchema = z
  .object({
    location1_id: z.string().min(1, "First location selection is required."),
    location2_id: z.string().min(1, "Second location selection is required."),
    connection_type: z
      .string()
      .min(1, "Connection type is required.")
      .max(100, "Type too long"),
    description: z.string().min(1, "Description is required."),
    travel_route: z.string().optional(),
    cultural_exchange: z.string().optional(),
  })
  .refine((data) => data.location1_id !== data.location2_id, {
    message: "Cannot connect a location to itself.",
    path: ["location2_id"],
  });

type LocationConnectionFormValues = z.infer<typeof formSchema>;

interface AddLocationConnectionFormProps {
  projectId: string;
  locations: Location[]; // List of available locations
  onConnectionAdded: () => void; // Callback to refresh list/close modal
  onCancel: () => void; // Callback to close modal without saving
  token: string | null; // Receive token directly
}

export function AddLocationConnectionForm({
  projectId,
  locations,
  onConnectionAdded,
  onCancel,
  token, // Use the passed token
}: AddLocationConnectionFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<LocationConnectionFormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      location1_id: "",
      location2_id: "",
      connection_type: "",
      description: "",
      travel_route: "",
      cultural_exchange: "",
    },
  });

  async function onSubmit(values: LocationConnectionFormValues) {
    if (!token) {
      toast.error("Authentication token is missing. Cannot add connection.");
      return;
    }
    setIsSubmitting(true);
    // Use the token passed via props
    try {
      // Construct the payload for the API
      const payload = {
        location1_id: values.location1_id,
        location2_id: values.location2_id,
        connection_type: values.connection_type,
        description: values.description,
        travel_route: values.travel_route || null, // Send null if optional fields are empty
        cultural_exchange: values.cultural_exchange || null,
      };

      // Make POST request to create the new location connection
      // Assuming endpoint is /projects/{projectId}/locations/connections
      await fetchApi<{ connection_id: string }>(
        `/projects/${projectId}/locations/connections`,
        {
          method: "POST",
          body: JSON.stringify(payload),
          headers: {
            "Content-Type": "application/json",
          },
        },
        token
      );

      toast.success("Location connection added successfully.");
      onConnectionAdded(); // Refresh list and close modal
    } catch (error) {
      console.error("Failed to add location connection:", error);
      const errorMsg =
        error instanceof Error ? error.message : "Please try again.";
      toast.error(`Failed to add location connection: ${errorMsg}`);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        {/* Select Location 1 */}
        <FormField
          control={form.control}
          name="location1_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>First Location</FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Select the first location" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {locations.map((location) => (
                    <SelectItem key={location.id} value={location.id}>
                      {location.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Select Location 2 */}
        <FormField
          control={form.control}
          name="location2_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Second Location</FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Select the second location" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {locations.map((location) => (
                    <SelectItem key={location.id} value={location.id}>
                      {location.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Connection Type */}
        <FormField
          control={form.control}
          name="connection_type"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Connection Type</FormLabel>
              <FormControl>
                <Input
                  placeholder="e.g., Geographic Proximity, Trade Route, Political Alliance"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                How are these locations related?
              </FormDescription>
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
                  placeholder="Describe the connection between the locations..."
                  className="resize-y min-h-[80px]"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Travel Route (Optional) */}
        <FormField
          control={form.control}
          name="travel_route"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Travel Route (Optional)</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Describe the typical travel route, time, methods, dangers..."
                  className="resize-y min-h-[60px]"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                Details about how one travels between these locations.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Cultural Exchange (Optional) */}
        <FormField
          control={form.control}
          name="cultural_exchange"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Cultural Exchange (Optional)</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Describe any cultural interactions, influences, or differences..."
                  className="resize-y min-h-[60px]"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                Information on cultural dynamics between the locations.
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
            className="bg-purple-600 hover:bg-purple-700"
          >
            {isSubmitting ? "Adding..." : "Add Connection"}
            <PlusCircle className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </form>
    </Form>
  );
}

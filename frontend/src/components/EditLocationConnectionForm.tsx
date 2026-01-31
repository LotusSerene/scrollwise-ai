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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Save } from "lucide-react"; // Icon for saving changes
import { fetchApi } from "@/lib/api";
import { toast } from "sonner";

// Interface for Location (could be shared)
interface Location {
  id: string;
  name: string;
}

// Interface for the connection data being edited
interface LocationConnection {
  id: string;
  location1_id: string;
  location2_id: string;
  connection_type: string;
  description: string;
  travel_route?: string | null;
  cultural_exchange?: string | null;
}

// Zod schema (same validation logic as Add form)
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

interface EditLocationConnectionFormProps {
  projectId: string;
  locations: Location[];
  connection: LocationConnection; // The connection data to edit
  onConnectionUpdated: () => void; // Callback after successful update
  onCancel: () => void;
  token: string | null; // Receive token directly
}

export function EditLocationConnectionForm({
  projectId,
  locations,
  connection,
  onConnectionUpdated,
  onCancel,
  token, // Use the passed token
}: EditLocationConnectionFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<LocationConnectionFormValues>({
    resolver: zodResolver(formSchema),
    // Pre-populate the form with existing connection data
    defaultValues: {
      location1_id: connection.location1_id,
      location2_id: connection.location2_id,
      connection_type: connection.connection_type,
      description: connection.description,
      travel_route: connection.travel_route || "", // Handle null by defaulting to empty string
      cultural_exchange: connection.cultural_exchange || "",
    },
  });

  // Optional: Reset form if the connection prop changes (e.g., editing a different connection)
  useEffect(() => {
    form.reset({
      location1_id: connection.location1_id,
      location2_id: connection.location2_id,
      connection_type: connection.connection_type,
      description: connection.description,
      travel_route: connection.travel_route || "",
      cultural_exchange: connection.cultural_exchange || "",
    });
  }, [connection, form]);

  async function onSubmit(values: LocationConnectionFormValues) {
    if (!token) {
      toast.error("Authentication token is missing. Cannot update connection.");
      return;
    }
    setIsSubmitting(true);
    // Use the token passed via props
    try {
      const payload = {
        location1_id: values.location1_id,
        location2_id: values.location2_id,
        connection_type: values.connection_type,
        description: values.description,
        travel_route: values.travel_route || null,
        cultural_exchange: values.cultural_exchange || null,
      };

      // Make PUT request to update the connection
      await fetchApi(
        `/projects/${projectId}/locations/connections/${connection.id}`,
        {
          method: "PUT",
          body: JSON.stringify(payload),
          headers: {
            "Content-Type": "application/json",
          },
        },
        token
      );

      toast.success("Location connection updated successfully.");
      onConnectionUpdated();
    } catch (error) {
      console.error("Failed to update location connection:", error);
      const errorMsg =
        error instanceof Error ? error.message : "Please try again.";
      toast.error(`Failed to update location connection: ${errorMsg}`);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        {/* Location 1 Select */}
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

        {/* Location 2 Select */}
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

        {/* Connection Type Input */}
        <FormField
          control={form.control}
          name="connection_type"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Connection Type</FormLabel>
              <FormControl>
                <Input
                  placeholder="e.g., Geographic Proximity, Trade Route"
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

        {/* Description Textarea */}
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Describe the connection..."
                  className="resize-y min-h-[80px]"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Travel Route Textarea (Optional) */}
        <FormField
          control={form.control}
          name="travel_route"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Travel Route (Optional)</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Describe travel details..."
                  className="resize-y min-h-[60px]"
                  {...field}
                  value={field.value ?? ""}
                />
              </FormControl>
              <FormDescription>
                How one travels between these locations.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Cultural Exchange Textarea (Optional) */}
        <FormField
          control={form.control}
          name="cultural_exchange"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Cultural Exchange (Optional)</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Describe cultural dynamics..."
                  className="resize-y min-h-[60px]"
                  {...field}
                  value={field.value ?? ""}
                />
              </FormControl>
              <FormDescription>
                Cultural interactions between locations.
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
            {isSubmitting ? "Saving..." : "Save Changes"}
            <Save className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </form>
    </Form>
  );
}

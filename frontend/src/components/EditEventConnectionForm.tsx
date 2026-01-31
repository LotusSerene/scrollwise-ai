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
import { Edit } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { toast } from "sonner";

// Interfaces (could be shared)
interface Event {
  id: string;
  title: string;
}

interface EventConnection {
  id: string;
  event1_id: string;
  event2_id: string;
  event1_title?: string; // Optional, might not be present in connection data initially
  event2_title?: string;
  connection_type: string;
  description: string;
  impact: string;
}

// Zod schema for connection form validation
const formSchema = z
  .object({
    event1_id: z.string().min(1, "First event selection is required."),
    event2_id: z.string().min(1, "Second event selection is required."),
    connection_type: z
      .string()
      .min(1, "Connection type is required.")
      .max(100, "Type too long"),
    description: z.string().min(1, "Description is required."),
    impact: z.string().min(1, "Impact description is required."),
  })
  .refine((data) => data.event1_id !== data.event2_id, {
    message: "Cannot connect an event to itself.",
    path: ["event2_id"],
  });

type ConnectionFormValues = z.infer<typeof formSchema>;

interface EditEventConnectionFormProps {
  projectId: string;
  events: Event[]; // List of available events
  connection: EventConnection; // The connection to edit
  onConnectionUpdated: () => void; // Callback to refresh list/close modal
  onCancel: () => void; // Callback to close modal without saving
  token: string | null; // Receive token directly
}

export function EditEventConnectionForm({
  projectId,
  events,
  connection,
  onConnectionUpdated,
  onCancel,
  token, // Use the passed token
}: EditEventConnectionFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<ConnectionFormValues>({
    resolver: zodResolver(formSchema),
    // Pre-populate the form with existing connection data
    defaultValues: {
      event1_id: connection.event1_id,
      event2_id: connection.event2_id,
      connection_type: connection.connection_type,
      description: connection.description,
      impact: connection.impact,
    },
  });

  // Reset form if the connection prop changes (e.g., opening modal for a different connection)
  useEffect(() => {
    form.reset({
      event1_id: connection.event1_id,
      event2_id: connection.event2_id,
      connection_type: connection.connection_type,
      description: connection.description,
      impact: connection.impact,
    });
  }, [connection, form]);

  async function onSubmit(values: ConnectionFormValues) {
    if (!token) {
      toast.error("Authentication token is missing. Cannot update connection.");
      return;
    }
    setIsSubmitting(true);
    // Use the token passed via props
    try {
      // Construct the payload for the API
      const payload = {
        event1_id: values.event1_id,
        event2_id: values.event2_id,
        connection_type: values.connection_type,
        description: values.description,
        impact: values.impact,
      };

      // Make PUT request to update the specific connection
      await fetchApi(
        `/projects/${projectId}/events/connections/${connection.id}`,
        {
          method: "PUT",
          body: JSON.stringify(payload),
          headers: {
            "Content-Type": "application/json",
          },
        },
        token
      );

      toast.success("Event connection updated successfully.");
      onConnectionUpdated(); // Refresh list and close modal
    } catch (error) {
      console.error("Failed to update event connection:", error);
      const errorMsg =
        error instanceof Error ? error.message : "Please try again.";
      toast.error(`Failed to update connection: ${errorMsg}`);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        {/* Select Event 1 */}
        <FormField
          control={form.control}
          name="event1_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>First Event</FormLabel>
              <Select
                onValueChange={field.onChange}
                defaultValue={field.value} // Set default value from pre-population
              >
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Select the first event" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {events.map((event) => (
                    <SelectItem key={event.id} value={event.id}>
                      {event.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Select Event 2 */}
        <FormField
          control={form.control}
          name="event2_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Second Event</FormLabel>
              <Select
                onValueChange={field.onChange}
                defaultValue={field.value} // Set default value from pre-population
              >
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Select the second event" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {events.map((event) => (
                    <SelectItem key={event.id} value={event.id}>
                      {event.title}
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
                  placeholder="e.g., Cause & Effect, Temporal Sequence"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                How are these events related? (e.g., Causality, Precedes,
                Follows)
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
                  placeholder="Describe the connection between the events..."
                  className="resize-y min-h-[80px]"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Impact */}
        <FormField
          control={form.control}
          name="impact"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Impact</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Describe the impact or significance of this connection..."
                  className="resize-y min-h-[80px]"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                What is the consequence or importance of this link?
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
            className="bg-cyan-600 hover:bg-cyan-700"
          >
            {isSubmitting ? "Saving..." : "Save Changes"}
            <Edit className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </form>
    </Form>
  );
}

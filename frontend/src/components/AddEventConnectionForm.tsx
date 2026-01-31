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
import { Link2 } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { toast } from "sonner";

// Re-use Event interface (or import from a shared types file)
interface Event {
  id: string;
  title: string;
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
    // Prevent selecting the same event twice
    message: "Cannot connect an event to itself.",
    path: ["event2_id"], // Show error message under the second select
  });

type ConnectionFormValues = z.infer<typeof formSchema>;

interface AddEventConnectionFormProps {
  projectId: string;
  events: Event[]; // Pass the list of available events
  onConnectionAdded: () => void; // Callback to refresh the list
  onCancel: () => void; // Callback to close the dialog/form
  getAuthToken: () => string | null; // Function to get auth token
}

export function AddEventConnectionForm({
  projectId,
  events,
  onConnectionAdded,
  onCancel,
  getAuthToken,
}: AddEventConnectionFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<ConnectionFormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      event1_id: "",
      event2_id: "",
      connection_type: "",
      description: "",
      impact: "",
    },
  });

  async function onSubmit(values: ConnectionFormValues) {
    setIsSubmitting(true);
    const token = getAuthToken();
    try {
      // Construct the payload for the API
      const payload = {
        event1_id: values.event1_id,
        event2_id: values.event2_id,
        connection_type: values.connection_type,
        description: values.description,
        impact: values.impact,
      };

      await fetchApi<{ connection_id: string }>(
        `/projects/${projectId}/events/connections`,
        {
          method: "POST",
          body: JSON.stringify(payload),
          // Ensure headers are set if backend expects application/json
          headers: {
            "Content-Type": "application/json",
          },
        },
        token
      );

      toast.success("Event connection created successfully.");
      onConnectionAdded(); // Refresh list and close modal
      form.reset();
    } catch (error) {
      console.error("Failed to create event connection:", error);
      // Check if error response has more details
      const errorMsg =
        error instanceof Error ? error.message : "Please try again.";
      toast.error(`Failed to create connection: ${errorMsg}`);
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
              <Select onValueChange={field.onChange} defaultValue={field.value}>
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
              <Select onValueChange={field.onChange} defaultValue={field.value}>
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
            {isSubmitting ? "Adding..." : "Add Connection"}
            <Link2 className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </form>
    </Form>
  );
}

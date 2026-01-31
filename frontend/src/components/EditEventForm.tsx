"use client";

import React, { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Button } from "@/components/ui/button";
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
import { Pencil } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { toast } from "sonner";

// Reusable Event interface (could be moved to a types file later)
interface Event {
  id: string;
  title: string;
  description: string;
  date: string;
  character_id?: string;
  location_id?: string;
}

// Zod schema for form validation (same as AddEventForm)
const formSchema = z.object({
  title: z.string().min(1, "Title is required").max(255, "Title too long"),
  description: z.string().min(1, "Description is required"),
  date: z.string().refine((date) => !isNaN(Date.parse(date)), {
    message: "Invalid date format",
  }),
});

type EventFormValues = z.infer<typeof formSchema>;

interface EditEventFormProps {
  projectId: string;
  event: Event; // Pass the event data to pre-populate
  onEventUpdated: () => void; // Callback to refresh the list
  onCancel: () => void; // Callback to close the dialog/form
  token: string | null; // Receive token directly
}

export function EditEventForm({
  projectId,
  event,
  onEventUpdated,
  onCancel,
  token, // Use the passed token
}: EditEventFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<EventFormValues>({
    resolver: zodResolver(formSchema),
    // Pre-populate form with existing event data
    defaultValues: {
      title: event.title,
      description: event.description,
      // Format date for the input type="date"
      date: new Date(event.date).toISOString().split("T")[0],
    },
  });

  // Reset form if the event prop changes (e.g., opening modal for a different event)
  useEffect(() => {
    form.reset({
      title: event.title,
      description: event.description,
      date: new Date(event.date).toISOString().split("T")[0],
    });
  }, [event, form]);

  async function onSubmit(values: EventFormValues) {
    if (!token) {
      toast.error("Authentication token is missing. Cannot update event.");
      return;
    }
    setIsSubmitting(true);
    // Use the token passed via props
    try {
      const updatedEventData = {
        ...values,
        date: new Date(values.date).toISOString(),
      };

      await fetchApi<Event>( // Expect updated event data back
        `/projects/${projectId}/events/${event.id}`,
        {
          method: "PUT",
          body: JSON.stringify(updatedEventData),
        },
        token
      );

      toast.success(`Event "${values.title}" updated successfully.`);
      onEventUpdated(); // Refresh list and close modal
    } catch (error) {
      console.error("Failed to update event:", error);
      toast.error("Failed to update event. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        {/* Form fields are the same as AddEventForm */}
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Title</FormLabel>
              <FormControl>
                <Input placeholder="e.g., The Coronation" {...field} />
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
                  placeholder="Describe the event..."
                  className="resize-y min-h-[100px]"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="date"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Date</FormLabel>
              <FormControl>
                <Input type="date" {...field} />
              </FormControl>
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
            className="bg-blue-600 hover:bg-blue-700"
          >
            {isSubmitting ? "Updating..." : "Update Event"}
            <Pencil className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </form>
    </Form>
  );
}

"use client";

import React, { useState } from "react";
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
import { Calendar } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { toast } from "sonner";

// Zod schema for form validation
const formSchema = z.object({
  title: z.string().min(1, "Title is required").max(255, "Title too long"),
  description: z.string().min(1, "Description is required"),
  date: z.string().refine((date) => !isNaN(Date.parse(date)), {
    message: "Invalid date format",
  }),
});

type EventFormValues = z.infer<typeof formSchema>;

interface AddEventFormProps {
  projectId: string;
  onEventAdded: () => void; // Callback to refresh the list
  onCancel: () => void; // Callback to close the dialog/form
  token: string | null; // Receive token directly
}

export function AddEventForm({
  projectId,
  onEventAdded,
  onCancel,
  token, // Use the passed token
}: AddEventFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<EventFormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      title: "",
      description: "",
      date: new Date().toISOString().split("T")[0], // Default to today
    },
  });

  async function onSubmit(values: EventFormValues) {
    if (!token) {
      toast.error("Authentication token is missing. Cannot add event.");
      return;
    }
    setIsSubmitting(true);
    // Use the token passed via props
    try {
      // Convert date string to ISO 8601 format for backend
      const eventData = {
        ...values,
        date: new Date(values.date).toISOString(),
      };

      await fetchApi<{ event_id: string }>(
        `/projects/${projectId}/events`,
        {
          method: "POST",
          body: JSON.stringify(eventData),
        },
        token
      );

      toast.success(`Event "${values.title}" added successfully.`);
      onEventAdded(); // Refresh the list in the parent component
      form.reset(); // Reset form after successful submission
    } catch (error) {
      console.error("Failed to create event:", error);
      toast.error("Failed to create event. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
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
                {/* Basic date input, consider using a Date Picker component later */}
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
            // Removed explicit background classes to use default theme style
          >
            {isSubmitting ? "Adding..." : "Add Event"}
            <Calendar className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </form>
    </Form>
  );
}

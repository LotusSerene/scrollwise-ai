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
import { Input } from "@/components/ui/input";
import { Loader2, AlertTriangle } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth

// Define the form schema using Zod
const formSchema = z.object({
  name: z
    .string()
    .min(2, {
      message: "Universe name must be at least 2 characters.",
    })
    .max(100, {
      message: "Universe name must not exceed 100 characters.",
    }),
  // Universes might not need a description at creation based on backend route
});

type FormData = z.infer<typeof formSchema>;

// Define the expected shape of the created universe
interface CreatedUniverse {
  id: string;
  name: string;
}

interface CreateUniverseFormProps {
  onSuccess: (newUniverse: CreatedUniverse) => void; // Use the specific type
  onCancel: () => void; // Callback to close the dialog
}

export function CreateUniverseForm({
  onSuccess,
  onCancel,
}: CreateUniverseFormProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const auth = useAuth(); // Use the hook

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
    },
  });

  async function onSubmit(values: FormData) {
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      setError("Authentication required to create universe.");
      return;
    }
    setIsLoading(true);
    setError(null);
    const token = auth.user.id_token; // Get token

    try {
      // Backend expects just the name for universe creation
      const payload = {
        name: values.name,
      };

      // The backend returns { id: string, name: string } on success
      const newUniverse = await fetchApi<CreatedUniverse>(
        "/universes",
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
        token
      );

      console.log("Universe creation successful:", newUniverse);
      onSuccess(newUniverse); // Pass the newly created universe data back
    } catch (err: unknown) {
      console.error("Universe creation failed:", err);
      let errorMessage = "Failed to create universe. Please try again.";
      if (err instanceof Error) {
        errorMessage = err.message;
      } else if (
        typeof err === "object" &&
        err !== null &&
        "message" in err &&
        typeof err.message === "string"
      ) {
        errorMessage = err.message;
      }
      setError(errorMessage);
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
              <FormLabel>Universe Name</FormLabel>
              <FormControl>
                <Input placeholder="Eldoria" {...field} disabled={isLoading} />
              </FormControl>
              <FormDescription>
                Give your universe a unique name.
              </FormDescription>
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
          <Button type="submit" disabled={isLoading} className="min-w-[100px]">
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              "Create Universe"
            )}
          </Button>
        </div>
      </form>
    </Form>
  );
}

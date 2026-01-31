"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import Link from "next/link";

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
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
import { fetchApi } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth
import { Feather, ArrowLeft } from "lucide-react";

interface Universe {
  id: string;
  name: string;
  description: string | null;
}

export default function UniverseSettingsPage() {
  const params = useParams();
  const router = useRouter();
  const universeId = params?.universeId as string;
  const auth = useAuth();

  const [universe, setUniverse] = useState<Universe | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const fetchUniverse = async (token: string | undefined) => {
      if (!token) {
        toast.error("Authentication required to load universe details.");
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      try {
        const fetchedUniverse = await fetchApi<Universe>(
          `/universes/${universeId}`,
          {}, // Add empty options
          token // Pass token
        );
        if (fetchedUniverse) {
          setUniverse(fetchedUniverse);
          setName(fetchedUniverse.name);
          setDescription(fetchedUniverse.description || "");
        } else {
          throw new Error("Universe data not received");
        }
      } catch (error) {
        console.error("Error fetching universe:", error);
        toast.error("Failed to load universe details.");
        // Optional: Redirect if universe not found or error
        // router.push('/dashboard');
      } finally {
        setIsLoading(false);
      }
    };

    // Fetch only when authenticated
    if (
      universeId &&
      !auth.isLoading &&
      auth.isAuthenticated &&
      auth.user?.id_token
    ) {
      fetchUniverse(auth.user.id_token);
    } else if (universeId && !auth.isLoading && !auth.isAuthenticated) {
      toast.error("Authentication required.");
      setIsLoading(false);
    }
    // Depend on auth state and universeId
  }, [universeId, auth.isLoading, auth.isAuthenticated, auth.user?.id_token]);

  // Add check for universeId after hooks
  if (!universeId) {
    return <div>Invalid Universe ID.</div>;
  }

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      toast.error("Authentication required to update universe.");
      return;
    }
    setIsSaving(true);
    const token = auth.user.id_token; // Get token
    try {
      await fetchApi(
        `/universes/${universeId}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ name, description }),
        },
        token // Pass token
      );
      toast.success("Universe details updated.");
      // Optionally refetch or update local state if needed
      setUniverse((prev) => (prev ? { ...prev, name, description } : null));
    } catch (error) {
      console.error("Error updating universe:", error);
      toast.error("Failed to update universe.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      toast.error("Authentication required to delete universe.");
      return;
    }
    setIsDeleting(true);
    const token = auth.user.id_token; // Get token
    try {
      await fetchApi(
        `/universes/${universeId}`,
        { method: "DELETE" },
        token // Pass token
      );
      toast.success("Universe deleted.");
      router.push("/dashboard"); // Redirect after deletion
    } catch (error) {
      console.error("Error deleting universe:", error);
      toast.error(
        "Failed to delete universe. Make sure it doesn't contain any projects."
      );
    } finally {
      setIsDeleting(false);
    }
  };

  if (isLoading) {
    return <div>Loading universe settings...</div>; // Replace with a proper skeleton loader if available
  }

  if (!universe) {
    return <div>Universe not found or could not be loaded.</div>;
  }

  return (
    <div className="container mx-auto p-4 py-8">
      {/* Back button */}
      <div className="mb-8">
        <Link href={`/universe/${universeId}`}>
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Universe
          </Button>
        </Link>
      </div>

      {/* Centered card with max width */}
      <div className="max-w-2xl mx-auto">
        <Card>
          <CardHeader>
            <CardTitle>Universe Settings</CardTitle>
            <CardDescription>
              Manage details for the universe: {universe.name}
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleUpdate}>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="name" className="text-sm font-medium">
                  Name
                </label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  disabled={isSaving}
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="description" className="text-sm font-medium">
                  Description
                </label>
                <Textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Enter a description for the universe (optional)"
                  disabled={isSaving}
                  rows={4}
                />
              </div>
            </CardContent>
            <CardFooter className="flex justify-between">
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive" disabled={isDeleting}>
                    {isDeleting ? "Deleting..." : "Delete Universe"}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>
                      Are you absolutely sure?
                    </AlertDialogTitle>
                    <AlertDialogDescription>
                      This action cannot be undone. This will permanently delete
                      the universe
                      <strong> {universe.name}</strong>. Make sure no projects
                      are linked to this universe before deleting.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel disabled={isDeleting}>
                      Cancel
                    </AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleDelete}
                      disabled={isDeleting}
                    >
                      {isDeleting ? "Deleting..." : "Yes, delete universe"}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
              <Button type="submit" disabled={isSaving}>
                {isSaving ? "Saving..." : "Save Changes"}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>

      <div className="w-full max-w-md mx-auto h-px bg-border/50 relative my-8">
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-background px-6">
          <Feather className="h-4 w-4 text-primary/40" />
        </div>
      </div>
      <footer className="text-center text-sm text-muted-foreground">
        &copy; {new Date().getFullYear()} ScrollWise. All rights reserved.
      </footer>
    </div>
  );
}

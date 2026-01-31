// frontend/src/app/universe/[universeId]/page.tsx
"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { fetchApi } from "@/lib/api";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { CreateProjectForm } from "@/components/CreateProjectForm";
import {
  Loader2,
  AlertTriangle,
  ArrowLeft,
  Plus,
  BookOpen,
  Settings,
  Feather,
} from "lucide-react";
import { useAuth } from "@/components/MockAuthProvider";

// Define types
interface UniverseDetails {
  id: string;
  name: string;
  description?: string;
}

interface Project {
  id: string;
  name: string;
  description?: string | null;
  universe_id?: string | null;
}

interface KnowledgeBaseItem {
  id: string;
  type: string;
  name: string;
  content?: string;
}

export default function UniverseDetailPage() {
  const params = useParams();
  const universeId = params?.universeId as string;
  const { user, isLoading: authIsLoading, isAuthenticated } = useAuth();

  const [universe, setUniverse] = useState<UniverseDetails | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [knowledgeBase, setKnowledgeBase] = useState<
    Record<string, KnowledgeBaseItem[]>
  >({});
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isFetchingProjects, setIsFetchingProjects] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isCreateProjectDialogOpen, setIsCreateProjectDialogOpen] =
    useState(false);

  const fetchProjects = useCallback(
    async (token: string | undefined) => {
      if (!universeId || !token) {
        setError(
          (prevError) =>
            prevError || "Authentication token missing for projects."
        );
        setIsFetchingProjects(false);
        return;
      }
      setIsFetchingProjects(true);
      // Token is passed as argument
      try {
        const projectsResponse = await fetchApi<{ projects: Project[] }>(
          `/universes/${universeId}/projects`,
          {},
          token
        );
        // Removed specific logging
        setProjects(projectsResponse.projects || []); // Simplified back
      } catch (err) {
        console.error("Error fetching projects:", err); // Keep error log
        setError((prevError) => prevError || "Failed to load projects.");
      } finally {
        setIsFetchingProjects(false);
      }
    },
    [universeId]
  ); // Keep universeId dependency

  useEffect(() => {
    if (!universeId) return;
    const fetchInitialData = async (token: string | undefined) => {
      if (!token) {
        setError("Authentication required to load universe data.");
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      setError(null);
      setProjects([]);
      setKnowledgeBase({});
      // Token is passed as argument
      try {
        const [universeDetails, kbResponse] = await Promise.all([
          fetchApi<UniverseDetails>(`/universes/${universeId}`, {}, token),
          fetchApi<Record<string, KnowledgeBaseItem[]>>(
            `/universes/${universeId}/knowledge-base`,
            {},
            token
          ),
          fetchProjects(token), // Pass token to fetchProjects
        ]);
        setUniverse(universeDetails);
        setKnowledgeBase(kbResponse || {});
      } catch (err: unknown) {
        console.error("Error fetching initial universe data:", err);
        const errorMessage =
          err instanceof Error ? err.message : "Failed to load universe data.";
        setError(errorMessage);
        setUniverse(null);
      } finally {
        setIsLoading(false);
      }
    };
    // Fetch only when authenticated
    if (!authIsLoading && isAuthenticated && user?.id_token) {
      fetchInitialData(user.id_token);
    } else if (!authIsLoading && !isAuthenticated) {
      setError("Authentication required.");
      setIsLoading(false);
    }
    // Depend on auth state, universeId, and fetchProjects
  }, [
    universeId,
    fetchProjects,
    authIsLoading,
    isAuthenticated,
    user?.id_token,
  ]);

  // Add check for universeId AFTER hooks
  if (!universeId) {
    return <div>Invalid Universe ID.</div>;
  }

  const handleCreateProjectSuccess = (newProject: Project) => {
    console.log("Project created:", newProject); // Keep this log for now
    setIsCreateProjectDialogOpen(false);
    // Refresh projects list only if authenticated
    if (isAuthenticated && user?.id_token) {
      fetchProjects(user.id_token);
    }
  };

  const handleCreateProjectCancel = () => {
    setIsCreateProjectDialogOpen(false);
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <Loader2 className="h-16 w-16 animate-spin text-primary" />
      </div>
    );
  }

  if (error && !universe) {
    return (
      <div className="container mx-auto px-6 py-12 text-center">
        <AlertTriangle className="h-12 w-12 mx-auto mb-4 text-destructive" />
        <h2 className="text-2xl font-semibold mb-4 text-destructive-foreground">
          Error Loading Universe
        </h2>
        <p className="text-muted-foreground mb-6">{error}</p>
        <Link href="/dashboard">
          <Button variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
          </Button>
        </Link>
      </div>
    );
  }

  if (!universe) {
    return (
      <div className="container mx-auto px-6 py-12 text-center">
        <h2 className="text-2xl font-semibold mb-4">Universe Not Found</h2>
        <p className="text-muted-foreground mb-6">
          The requested universe could not be found.
        </p>
        <Link href="/dashboard">
          <Button variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
          </Button>
        </Link>
      </div>
    );
  }

  // Calculate total count manually
  const totalKnowledgeBaseItems = Object.values(knowledgeBase).reduce(
    (count, items) => count + items.length,
    0
  );

  // Removed render log

  return (
    // Added more vertical padding
    <div className="container mx-auto px-6 py-16">
      {/* Link container */}
      <div className="flex justify-between items-center mb-10">
        <Link href="/dashboard" className="inline-block">
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
          </Button>
        </Link>
        {/* Settings Button */}
        <Link href={`./${universeId}/settings`} className="inline-block">
          <Button variant="outline" size="sm">
            <Settings className="mr-2 h-4 w-4" /> Settings
          </Button>
        </Link>
      </div>
      {/* Centered Title and Description */}
      <div className="text-center mb-16">
        {" "}
        {/* Increased bottom margin */}
        <h1 className="text-4xl md:text-5xl font-bold mb-3">
          {universe.name}
        </h1>{" "}
        {/* Adjusted margin */}
        <p className="text-lg md:text-xl text-muted-foreground max-w-3xl mx-auto">
          {universe.description || "No description provided."}
        </p>
      </div>
      {/* Display non-fatal errors */}
      {error && (
        <div className="mb-6 text-destructive bg-destructive/10 p-3 rounded-md">
          {error}
        </div>
      )}
      {/* Grid layout with increased gap */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
        {/* Projects Section - Added background, padding, rounded corners */}
        <section className="bg-card p-6 rounded-lg shadow-sm">
          {/* Header with border */}
          <div className="flex justify-between items-center mb-6 border-b border-border pb-3">
            {" "}
            {/* Adjusted spacing */}
            <h2 className="text-2xl font-semibold">
              Projects ({projects.length})
            </h2>
            <Dialog
              open={isCreateProjectDialogOpen}
              onOpenChange={setIsCreateProjectDialogOpen}
            >
              <DialogTrigger asChild>
                <Button size="sm" variant="secondary">
                  {" "}
                  {/* Changed variant */}
                  <Plus className="mr-2 h-4 w-4" /> Create Project
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[525px]">
                <DialogHeader>
                  <DialogTitle className="text-foreground font-display">
                    Create New Project in &ldquo;{universe.name}&rdquo;
                  </DialogTitle>
                </DialogHeader>
                <CreateProjectForm
                  onSuccess={handleCreateProjectSuccess}
                  onCancel={handleCreateProjectCancel}
                  defaultUniverseId={universeId}
                />
              </DialogContent>
            </Dialog>
          </div>
          {/* Project List */}
          {isFetchingProjects ? (
            <div className="flex justify-center items-center py-6">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : projects.length > 0 ? (
            <div className="space-y-4">
              {projects.map((project) => (
                // Added hover effect to project cards
                <Card
                  key={project.id}
                  className="transition-all hover:shadow-md hover:border-primary/30 border border-transparent"
                >
                  <CardHeader>
                    <CardTitle>
                      <Link
                        href={`/project-dashboard/${project.id}`}
                        className="hover:underline text-primary" // Added primary color link
                      >
                        {project.name}
                      </Link>
                    </CardTitle>
                    <CardDescription className="line-clamp-2 pt-1">
                      {" "}
                      {/* Added padding top */}
                      {project.description || "No description."}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Link href={`/project-dashboard/${project.id}`}>
                      <Button variant="outline" size="sm">
                        {" "}
                        {/* Changed variant */}
                        Open Project
                      </Button>
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-center py-4">
              {" "}
              {/* Centered text */}
              No projects have been added to this universe yet.
            </p>
          )}
        </section>

        {/* Knowledge Base Section - Added background, padding, rounded corners */}
        <section className="bg-card p-6 rounded-lg shadow-sm">
          {/* Header with border */}
          <div className="flex justify-between items-center mb-6 border-b border-border pb-3">
            {" "}
            {/* Adjusted spacing */}
            <h2 className="text-2xl font-semibold flex items-center">
              <BookOpen className="mr-3 h-6 w-6 text-primary" />{" "}
              {/* Added Icon */}
              Knowledge Base ({totalKnowledgeBaseItems})
            </h2>
            {/* Placeholder for future 'Add Entry' button */}
          </div>
          {/* KB List */}
          {totalKnowledgeBaseItems > 0 ? (
            <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2">
              {" "}
              {/* Added max height and scroll */}
              {/* Iterate through projects (projectId) and then items */}
              {Object.entries(knowledgeBase).map(([projectId, items]) =>
                items.map((item) => (
                  // Wrap Card with Link using projectId
                  <Link
                    key={item.id}
                    // Update href to use project-based route
                    href={`/project/${projectId}/codex/${item.id}`}
                    passHref
                  >
                    <Card className="transition-all hover:shadow-md hover:border-primary/30 border border-transparent cursor-pointer">
                      {" "}
                      {/* Added cursor-pointer */}
                      <CardHeader>
                        <CardTitle className="text-lg">{item.name}</CardTitle>{" "}
                        {/* Slightly smaller title */}
                        <CardDescription className="text-sm capitalize pt-1">
                          {" "}
                          {/* Added padding top */}
                          Type: {item.type}
                        </CardDescription>
                      </CardHeader>
                      {item.content && (
                        <CardContent>
                          <p className="text-sm text-muted-foreground line-clamp-2">
                            {item.content}
                          </p>
                        </CardContent>
                      )}
                    </Card>
                  </Link>
                ))
              )}
            </div>
          ) : (
            <div className="text-center py-6">
              <p className="text-muted-foreground">
                No knowledge base entries found for this universe.
              </p>
            </div>
          )}
        </section>
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

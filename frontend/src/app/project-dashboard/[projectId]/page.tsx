"use client";

import React, { useState, useEffect, use } from "react";
import {
  BookCopy,
  FileText,
  Sparkles,
  BookOpen,
  AlertTriangle,
  PenSquare,
  BookOpenText,
} from "lucide-react";
import { fetchApi } from "@/lib/api";
import { notFound } from "next/navigation";
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth
import { ProjectProgressCircle } from "@/components/ProjectProgressCircle";
import { TargetWordCountForm } from "@/components/TargetWordCountForm";
import Link from "next/link";
import { Button } from "@/components/ui/button";

// Type matching backend Project response (including stats)
interface Project {
  id: string;
  name: string;
  description: string;
  universe_id: string | null;
  target_word_count?: number;
  chapter_count?: number;
  word_count?: number;
  // Add other relevant fields
}

// Define Props type for the page component
interface ProjectDashboardPageProps {
  params: Promise<{
    projectId: string;
  }>;
}

// Fetch project details - needs token passed in
async function getProjectDetails(
  id: string,
  token: string | undefined
): Promise<Project | null> {
  if (!token) {
    console.error(`Error fetching project ${id}: Auth token is missing.`);
    return null; // Cannot fetch without a token
  }
  try {
    const projectData = await fetchApi<Project>(
      `/projects/${id}?t=${Date.now()}`, // Add cache-busting param
      {
        cache: "no-store",
        next: { tags: ["project"] }, // Add revalidation tag
      },
      token
    );
    return projectData;
  } catch (error: unknown) {
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    if (
      errorMessage.includes("404") ||
      errorMessage.toLowerCase().includes("not found")
    ) {
      return null;
    }
    console.error(`Error fetching project ${id}:`, error);
    return null; // Treat other errors as not found for simplicity here
  }
}

export default function ProjectDashboardPage(props: ProjectDashboardPageProps) {
  const params = use(props.params);
  const auth = useAuth(); // Use auth hook
  const projectId = params.projectId;
  const [project, setProject] = useState<Project | null>(null); // State for project data
  const [isLoadingProject, setIsLoadingProject] = useState(true); // State for project loading
  const [error, setError] = useState<string | null>(null); // State for errors

  useEffect(() => {
    const fetchProject = async () => {
      if (auth.isAuthenticated && auth.user?.id_token) {
        setIsLoadingProject(true);
        setError(null);
        try {
          const fetchedProject = await getProjectDetails(
            projectId,
            auth.user.id_token
          );
          if (fetchedProject) {
            setProject(fetchedProject);
          } else {
            // Project not found or other fetch error handled in getProjectDetails
            setError("Project not found or could not be loaded.");
            setProject(null); // Ensure project state is null if fetch fails
          }
        } catch (err) {
          console.error("Error fetching project details:", err);
          setError("Failed to load project details.");
          setProject(null);
        } finally {
          setIsLoadingProject(false);
        }
      } else if (!auth.isLoading && !auth.isAuthenticated) {
        // If auth is loaded but user is not authenticated
        setIsLoadingProject(false);
        setProject(null);
        // Optionally set an error or rely on the later check
      }
      // If auth.isLoading is true, we wait for the next effect trigger when auth state changes
    };

    fetchProject();
  }, [auth.isAuthenticated, auth.isLoading, auth.user?.id_token, projectId]); // Dependencies for the effect

  // Handle loading states
  if (auth.isLoading || (auth.isAuthenticated && isLoadingProject)) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-4">
            <div className="absolute inset-0 rounded-full border-t-2 border-primary animate-spin"></div>
            <div className="absolute inset-2 rounded-full border-r-2 border-primary/30 animate-pulse"></div>
          </div>
          <p className="text-muted-foreground animate-pulse">
            Loading project details...
          </p>
        </div>
      </div>
    );
  }

  // Handle not authenticated state after loading
  if (!auth.isAuthenticated) {
    return (
      <div className="bg-card/50 border border-border rounded-lg p-8 text-center max-w-md mx-auto mt-12 shadow-sm">
        <BookOpen className="h-12 w-12 mx-auto mb-4 text-primary/50" />
        <h2 className="text-xl font-semibold mb-3 text-foreground font-display">
          Authentication Required
        </h2>
        <p className="text-muted-foreground mb-6">
          Please log in to view the project dashboard.
        </p>
        <Button
          onClick={() => auth.signinRedirect()}
          className="bg-primary hover:bg-primary/90"
        >
          Sign In
        </Button>
      </div>
    );
  }

  // Handle error state
  if (error) {
    if (error.includes("not found")) {
      notFound();
    }
    return (
      <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-8 text-center max-w-md mx-auto mt-12">
        <AlertTriangle className="h-12 w-12 mx-auto mb-4 text-destructive" />
        <h2 className="text-xl font-semibold mb-3 text-destructive-foreground">
          Error Loading Project
        </h2>
        <p className="text-muted-foreground mb-6">{error}</p>
        <Link href="/dashboard">
          <Button
            variant="outline"
            className="border-destructive/30 text-destructive hover:bg-destructive/10"
          >
            Return to Dashboard
          </Button>
        </Link>
      </div>
    );
  }

  // Handle project not found after loading and authentication
  if (!project) {
    notFound();
  }

  const currentWords = project.word_count ?? 0;
  const targetWords = project.target_word_count ?? 0;
  const chapters = project.chapter_count ?? 0;

  return (
    <section className="grid grid-cols-1 md:grid-cols-3 gap-8 animate-in fade-in-50 slide-in-from-bottom-5 duration-500">
      {/* Progress Card */}
      <div className="md:col-span-1 bg-card border border-border rounded-lg shadow-sm hover:shadow-md transition-all duration-300 overflow-hidden relative group">
        {/* Decorative elements */}
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-primary/5 rounded-full blur-2xl opacity-70 group-hover:opacity-100 transition-opacity"></div>
        <div className="absolute top-0 left-0 w-8 h-8 border-t border-l border-primary/20"></div>
        <div className="absolute top-0 right-0 w-8 h-8 border-t border-r border-primary/20"></div>
        <div className="absolute bottom-0 right-0 w-8 h-8 border-b border-r border-primary/20"></div>
        <div className="absolute bottom-0 left-0 w-8 h-8 border-b border-l border-primary/20"></div>

        <div className="p-6 flex flex-col items-center justify-center relative z-10">
          {/* Header */}
          <h2 className="text-xl font-semibold mb-6 text-center font-display text-primary relative">
            Word Count Progress
            <span className="block h-1 w-12 bg-primary/30 mx-auto mt-2 rounded-full"></span>
          </h2>

          {/* Progress Circle */}
          <div className="transform hover:scale-105 transition-transform duration-300">
            <ProjectProgressCircle
              currentWords={currentWords}
              targetWords={targetWords}
            />
          </div>

          {/* Target Word Count Form */}
          <div className="w-full mt-6 border-t border-border/40 pt-6">
            <TargetWordCountForm
              projectId={projectId}
              initialTarget={targetWords}
            />
          </div>
        </div>
      </div>

      {/* Stats and Details Card */}
      <div className="md:col-span-2 bg-card border border-border rounded-lg shadow-sm hover:shadow-md transition-all duration-300 relative overflow-hidden group">
        {/* Decorative elements */}
        <div className="absolute -bottom-24 -left-24 w-64 h-64 bg-primary/5 rounded-full blur-3xl opacity-70 group-hover:opacity-100 transition-opacity"></div>
        <div className="absolute top-0 left-0 w-8 h-8 border-t border-l border-primary/20"></div>
        <div className="absolute top-0 right-0 w-8 h-8 border-t border-r border-primary/20"></div>
        <div className="absolute bottom-0 right-0 w-8 h-8 border-b border-r border-primary/20"></div>
        <div className="absolute bottom-0 left-0 w-8 h-8 border-b border-l border-primary/20"></div>

        <div className="p-6 relative z-10">
          {/* Header */}
          <h2 className="text-xl font-semibold mb-6 font-display text-primary flex items-center">
            Project Overview
            <span className="block h-1 w-12 bg-primary/30 ml-3 rounded-full"></span>
          </h2>

          {/* Stats */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 text-center">
            {/* Chapters */}
            <div className="bg-accent/30 p-5 rounded-lg border border-border/50 shadow-sm hover:shadow transition-all duration-300 hover:border-primary/20 transform hover:-translate-y-1 group">
              <div className="rounded-full w-12 h-12 mx-auto mb-3 bg-primary/10 flex items-center justify-center">
                <BookCopy className="h-6 w-6 text-primary/70 group-hover:text-primary transition-colors duration-300" />
              </div>
              <p className="text-3xl font-bold text-foreground mb-1">
                {chapters}
              </p>
              <p className="text-sm text-muted-foreground">Chapters</p>
            </div>

            {/* Words */}
            <div className="bg-accent/30 p-5 rounded-lg border border-border/50 shadow-sm hover:shadow transition-all duration-300 hover:border-primary/20 transform hover:-translate-y-1 group">
              <div className="rounded-full w-12 h-12 mx-auto mb-3 bg-primary/10 flex items-center justify-center">
                <FileText className="h-6 w-6 text-primary/70 group-hover:text-primary transition-colors duration-300" />
              </div>
              <p className="text-3xl font-bold text-foreground mb-1">
                {currentWords.toLocaleString()}
              </p>
              <p className="text-sm text-muted-foreground">Total Words</p>
            </div>
          </div>

          {/* Project Details */}
          <div className="mt-8 border-t border-border/40 pt-6">
            <h3 className="text-lg font-semibold mb-4 text-foreground/90 font-display flex items-center">
              <Sparkles className="h-4 w-4 mr-2 text-primary/70" />
              Project Details
            </h3>
            <div className="bg-accent/20 p-5 rounded-lg border border-border/30">
              <div className="flex flex-col gap-4">
                <div>
                  <span className="text-sm text-muted-foreground block mb-1">
                    Name:
                  </span>
                  <p className="font-medium text-foreground">{project.name}</p>
                </div>

                {project.description && (
                  <div>
                    <span className="text-sm text-muted-foreground block mb-1">
                      Description:
                    </span>
                    <p className="text-sm text-foreground/80">
                      {project.description}
                    </p>
                  </div>
                )}

                {project.universe_id && (
                  <div>
                    <span className="text-sm text-muted-foreground block mb-1">
                      Universe:
                    </span>
                    <Link
                      href={`/universe/${project.universe_id}`}
                      className="text-sm text-primary font-medium hover:underline flex items-center"
                    >
                      <BookOpen className="h-4 w-4 mr-1" />
                      Connected to Universe
                    </Link>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href={`/project-dashboard/${projectId}/editor`}>
              <Button
                variant="outline"
                className="border-primary/20 hover:border-primary/50"
              >
                <PenSquare className="h-4 w-4 mr-2" />
                Open Editor
              </Button>
            </Link>

            <Link href={`/project-dashboard/${projectId}/codex`}>
              <Button
                variant="outline"
                className="border-primary/20 hover:border-primary/50"
              >
                <BookOpenText className="h-4 w-4 mr-2" />
                View Codex
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

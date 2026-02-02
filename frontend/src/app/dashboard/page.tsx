"use client"; // Required for state and interactions

import React, { useState, useMemo, useEffect, useCallback } from "react"; // Added useCallback
import { Button } from "@/components/ui/button";
import Link from "next/link";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  PlusCircle,
  BookOpen,
  LayoutGrid,
  Globe,
  FolderKanban,
  ChevronDown,
  Loader2,
  AlertTriangle,
  Settings,
  FileText,
  BookCopy,
  Feather,
  Archive,
  ScrollText,
  Home,
  MessageSquare,
} from "lucide-react"; // Added Feather, Archive, ScrollText, Home, MessageSquare, X icons
import { fetchApi } from "@/lib/api";
import { CreateProjectForm } from "@/components/CreateProjectForm";
import { CreateUniverseForm } from "@/components/CreateUniverseForm";
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth
import { useOnboarding } from "@/contexts/OnboardingContext";
import { useRouter } from "next/navigation"; // Import useRouter for redirect

// Define types matching backend response structure (adjust as needed based on actual API)
interface Project {
  id: string;
  name: string;
  description: string | null;
  universe_id: string | null;
  target_word_count?: number;
  chapter_count?: number;
  word_count?: number;
}

interface Universe {
  id: string;
  name: string;
  description?: string;
  project_count?: number;
  entry_count?: number;
}

// Interface for User details including onboarding status
interface UserDetails {
  id: string;
  email: string;
  has_completed_onboarding: boolean;
  // Add other fields if needed
}

// Frontend combined type
interface CreativeItem {
  id: string;
  name: string;
  description: string;
  type: string;
  category: "Project" | "Universe";
}

type FilterType = "all" | "projects" | "universes";


export default function DashboardPage() {
  const [activeFilter, setActiveFilter] = useState<FilterType>("all");
  const [projects, setProjects] = useState<Project[]>([]);
  const [universes, setUniverses] = useState<Universe[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isCreateProjectDialogOpen, setIsCreateProjectDialogOpen] =
    useState(false);
  const [isCreateUniverseDialogOpen, setIsCreateUniverseDialogOpen] =
    useState(false); // State for Universe dialog
  const [isApiKeySet, setIsApiKeySet] = useState(true); // State for API key status
  // No longer need userDetails state here if only used for onboarding flag
  // const [userDetails, setUserDetails] = useState<UserDetails | null>(null); // State for user details

  const auth = useAuth(); // Use the hook
  const router = useRouter(); // Use the router hook
  const { isOnboardingActive, currentStep, nextStep, setCurrentProjectId } = useOnboarding();


  // Fetch user details and main dashboard data
  const fetchData = useCallback(async (token: string | undefined) => {
    if (!token) {
      setError("Authentication token is missing. Cannot fetch data.");
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);

    try {
      // Fetch user details first to check onboarding status
      const fetchedUserDetails = await fetchApi<UserDetails>(
        "/users/me",
        {},
        token
      );
      // Use the fetched details directly here without setting separate state
      if (
        fetchedUserDetails &&
        fetchedUserDetails.has_completed_onboarding === false
      ) {
      }

      // Fetch projects and universes
      const results = await Promise.allSettled([
        fetchApi<{ projects: Project[] }>("/projects", {}, token),
        fetchApi<Universe[]>("/universes", {}, token),
        fetchApi<{ isSet: boolean }>("/settings/api-key", {}, token),
      ]);

      let fetchedProjects: Project[] = [];
      let fetchedUniverses: Universe[] = [];
      let fetchError: string | null = null;
      let apiKeyStatus = true;

      if (results[0].status === "fulfilled") {
        fetchedProjects = results[0].value?.projects || [];
      } else {
        console.error("Failed to fetch projects:", results[0].reason);
        fetchError = `Failed to load projects: ${results[0].reason.message || "Unknown error"
          }`;
      }

      if (results[1].status === "fulfilled") {
        fetchedUniverses = results[1].value || [];
      } else {
        console.error("Failed to fetch universes:", results[1].reason);
        const universeError = `Failed to load universes: ${results[1].reason.message || "Unknown error"
          }`;
        fetchError = fetchError
          ? `${fetchError}; ${universeError}`
          : universeError;
      }

      if (results[2].status === "fulfilled") {
        apiKeyStatus = results[2].value?.isSet ?? false;
      } else {
        console.error("Failed to fetch API key status:", results[2].reason);
        // You might want to handle this error, but for now, we'll assume the key is not set
        apiKeyStatus = false;
      }

      setProjects(fetchedProjects);
      setUniverses(fetchedUniverses);
      setIsApiKeySet(apiKeyStatus);
      setError(fetchError);
    } catch (err: unknown) {
      console.error("Error fetching dashboard data:", err);
      let message = "An unexpected error occurred while fetching data.";
      if (err instanceof Error) {
        message = err.message;
      }
      setError(message);
      setProjects([]);
      setUniverses([]);
      // setUserDetails(null); // No longer needed
    } finally {
      setIsLoading(false);
      // If user details fetch failed but project/universe succeeded, we might not have checked onboarding
    }
  }, []); // router is not needed in dependency array as it's stable

  useEffect(() => {
    // Check auth state from useAuth
    if (!auth.isLoading) {
      // Wait until auth state is determined
      if (auth.isAuthenticated && auth.user?.id_token) {
        console.log("DashboardPage: User authenticated, fetching data...");
        fetchData(auth.user.id_token); // Fetch data only if authenticated and token exists
      } else {
        console.error(
          "DashboardPage: User not authenticated or token missing."
        );
        setError("Authentication required. Redirecting to login...");
        setIsLoading(false);
        // Redirect to login page after a short delay
        setTimeout(() => router.push("/"), 2000); // Redirect to home/login page
      }
    }
    // Dependency array: react to changes in auth state
  }, [auth.isLoading, auth.isAuthenticated, auth.user, fetchData, router]);

  const allItems = useMemo((): CreativeItem[] => {
    const mappedProjects = projects.map((p) => ({
      id: p.id,
      name: p.name,
      description: p.description || "No description provided.",
      type: p.universe_id ? "Story (within Universe)" : "Standalone Project",
      category: "Project" as const,
    }));

    const mappedUniverses = universes.map((u) => ({
      id: u.id,
      name: u.name,
      description:
        u.description || "A collection of interconnected projects and lore.",
      type: "Worldbuilding",
      category: "Universe" as const,
    }));

    return [...mappedProjects, ...mappedUniverses].sort((a, b) =>
      a.name.localeCompare(b.name)
    ); // Sort alphabetically
  }, [projects, universes]);

  const filteredItems = useMemo(() => {
    if (activeFilter === "projects") {
      return allItems.filter((item) => item.category === "Project");
    }
    if (activeFilter === "universes") {
      return allItems.filter((item) => item.category === "Universe");
    }
    return allItems;
  }, [activeFilter, allItems]);

  const handleProjectCreated = (newProject: Project) => {
    console.log("New project created:", newProject);
    setProjects((prev) =>
      [...prev, newProject].sort((a, b) => a.name.localeCompare(b.name))
    ); // Add and sort
    setIsCreateProjectDialogOpen(false);
    setActiveFilter("projects");

    // If user is in onboarding and on the "create first project" step, advance to next step and navigate to project
    if (isOnboardingActive && currentStep === 5) { // Step 5 is "create-first-project"
      // Set the project ID for the onboarding context
      setCurrentProjectId(newProject.id);
      // Navigate to the project dashboard
      router.push(`/project-dashboard/${newProject.id}`);
      // Advance to the next step
      nextStep();
    }
  };

  // Handler for successful universe creation
  const handleUniverseCreated = (newUniverse: Universe) => {
    console.log("New universe created:", newUniverse);
    setUniverses((prev) =>
      [...prev, newUniverse].sort((a, b) => a.name.localeCompare(b.name))
    ); // Add and sort
    setIsCreateUniverseDialogOpen(false); // Close dialog
    setActiveFilter("universes"); // Switch filter to show universes
  };



  return (
    <>
      {/* Conditionally render the Onboarding Guide */}
      {/* Apply theme background and foreground */}
      <div className="min-h-screen flex bg-background text-foreground antialiased relative">
        {/* Vintage paper texture overlay - CSS only version */}
        <div
          aria-hidden="true"
          className="absolute inset-0 opacity-10 pointer-events-none z-0 bg-gradient-to-br from-amber-50/20 via-amber-100/10 to-amber-50/20"
          style={{
            backdropFilter: "brightness(1.02)",
          }}
        />

        {/* Vignette effect */}
        <div
          aria-hidden="true"
          className="absolute inset-0 pointer-events-none z-0"
          style={{
            boxShadow: "inset 0 0 200px rgba(0,0,0,0.2)",
          }}
        />

        {/* Sidebar - Apply card background, border and vintage styling */}
        <aside className="w-64 flex-shrink-0 bg-card p-4 border-r border-border flex flex-col z-10 relative">
          {/* Decorative corner flourish - CSS only version */}
          <div
            aria-hidden="true"
            className="absolute top-0 left-0 w-12 h-12 opacity-20 pointer-events-none border-t border-l border-primary/30"
            style={{
              borderTopWidth: "2px",
              borderLeftWidth: "2px",
              borderTopLeftRadius: "0.25rem",
            }}
          />

          <div className="mb-8">
            {/* Apply display font with vintage styling */}
            <h2 className="text-2xl font-semibold text-center font-display text-foreground tracking-wider relative">
              <ScrollText className="h-5 w-5 text-primary/60 absolute -left-1 top-1" />
              ScrollWise
            </h2>

            {/* Decorative divider */}
            <div className="flex items-center justify-center w-full my-4">
              <div className="flex-grow h-px bg-border/70"></div>
              <Feather className="mx-4 text-primary/60 h-4 w-4" />
              <div className="flex-grow h-px bg-border/70"></div>
            </div>
          </div>

          <nav className="flex-grow space-y-2">
            {/* Update filter button styles with vintage hover effects */}
            <button
              onClick={() => setActiveFilter("all")}
              className={`w-full justify-start px-3 py-2 rounded-md text-sm font-medium flex items-center gap-2 transition-all ${activeFilter === "all"
                ? "bg-primary text-primary-foreground shadow-sm" // Active state
                : "text-muted-foreground hover:text-accent-foreground hover:bg-primary/5" // Default/Hover state
                }`}
            >
              <LayoutGrid className="h-5 w-5" /> All Items
            </button>

            <button
              onClick={() => setActiveFilter("projects")}
              className={`w-full justify-start px-3 py-2 rounded-md text-sm font-medium flex items-center gap-2 transition-all ${activeFilter === "projects"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-accent-foreground hover:bg-primary/5"
                }`}
            >
              <FolderKanban className="h-5 w-5" /> Projects
            </button>

            <button
              onClick={() => setActiveFilter("universes")}
              className={`w-full justify-start px-3 py-2 rounded-md text-sm font-medium flex items-center gap-2 transition-all ${activeFilter === "universes"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-accent-foreground hover:bg-primary/5"
                }`}
            >
              <Globe className="h-5 w-5" /> Universes
            </button>

            {/* Settings Link - Apply theme styles with vintage hover */}
            <Link
              href="/settings"
              className={`w-full justify-start px-3 py-2 rounded-md text-sm font-medium flex items-center gap-2 transition-all text-muted-foreground hover:text-accent-foreground hover:bg-primary/5`}
            >
              <Settings className="h-5 w-5" /> Settings
            </Link>

            {/* Back to Landing Page Link - Apply theme styles with vintage hover */}
            <Link
              href="/"
              className={`w-full justify-start px-3 py-2 rounded-md text-sm font-medium flex items-center gap-2 transition-all text-muted-foreground hover:text-accent-foreground hover:bg-primary/5`}
            >
              <Home className="h-5 w-5" /> Back
            </Link>
          </nav>

          {/* Decorative bottom element */}
          <div className="pt-6 opacity-60">
            <div className="w-full h-px bg-border/50"></div>
            <div className="flex justify-center mt-2">
              <Feather className="h-4 w-4 text-muted-foreground/40" />
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-8 overflow-y-auto z-10 relative">

          {!isApiKeySet && (
            <div className="relative bg-red-50 border-l-4 border-red-400 p-4 mb-6 rounded-r-lg shadow-md">
              <div className="flex">
                <div className="py-1">
                  <AlertTriangle className="h-6 w-6 text-red-500 mr-4" />
                </div>
                <div>
                  <p className="font-bold text-red-800">
                    API Key Not Set
                  </p>
                  <p className="text-sm text-red-700">
                    You need to set your Google AI Studio API key to enable all features. It&apos;s free!
                  </p>
                  <Link href="/settings" passHref>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-2 border-red-300 text-red-700 hover:bg-red-100 hover:text-red-800"
                    >
                      Go to Settings
                    </Button>
                  </Link>
                </div>
              </div>
            </div>
          )}
          <header className="mb-10 flex flex-col md:flex-row justify-between items-center gap-4">
            {/* Apply display font with vintage styling */}
            <div className="relative">
              <h1 className="text-3xl md:text-4xl font-bold tracking-wide font-display text-foreground/95 leading-tight animate-fade-in">
                {activeFilter === "projects"
                  ? "Your Projects"
                  : activeFilter === "universes"
                    ? "Your Universes"
                    : "Your Creative Dashboard"}
              </h1>

              {/* Decorative underline */}
              <div className="w-24 h-1 bg-primary/30 mt-2 rounded-full animate-fade-in animation-delay-200"></div>

              {/* Ink splatter decoration - CSS only version */}
              <div
                aria-hidden="true"
                className="absolute -right-16 -top-6 w-24 h-24 opacity-10 pointer-events-none bg-primary/40 rounded-full blur-lg"
              />
            </div>

            {/* --- Create New Dropdown with vintage styling --- */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                {/* Use primary button style with vintage effects */}
                <Button
                  size="lg"
                  className="group bg-primary text-primary-foreground hover:bg-primary/90 rounded-md border border-primary/20 shadow-sm hover:shadow transition-all overflow-hidden relative create-new-button"
                >
                  <span className="relative z-10">
                    <PlusCircle className="mr-2 h-5 w-5 inline-block" /> Create
                    New <ChevronDown className="ml-1 h-5 w-5 inline-block" />
                  </span>
                  <span className="absolute inset-0 bg-primary/90 scale-x-0 group-hover:scale-x-100 origin-left transition-transform duration-500"></span>
                </Button>
              </DropdownMenuTrigger>

              {/* Style dropdown content with vintage aesthetic */}
              <DropdownMenuContent className="w-56 bg-popover border-border text-popover-foreground shadow-md animate-fade-in">
                <DropdownMenuLabel className="text-muted-foreground font-display tracking-wide">
                  Create a new...
                </DropdownMenuLabel>

                <DropdownMenuSeparator className="bg-border" />

                {/* Style dropdown items with vintage hover */}
                <DropdownMenuItem
                  className="hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground transition-colors create-project-button"
                  onSelect={(e) => {
                    e.preventDefault();
                    setIsCreateProjectDialogOpen(true);
                  }}
                >
                  <FolderKanban className="mr-2 h-4 w-4" />
                  <span>Project</span>
                </DropdownMenuItem>

                <DropdownMenuItem
                  className="hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground transition-colors"
                  onSelect={(e) => {
                    e.preventDefault();
                    setIsCreateUniverseDialogOpen(true);
                  }}
                >
                  <Globe className="mr-2 h-4 w-4" />
                  <span>Universe</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </header>

          {/* --- Content Display Section --- */}
          <section>
            {isLoading ? (
              <div className="flex justify-center items-center h-64">
                {/* Use primary color for loader */}
                <Loader2 className="h-12 w-12 animate-spin text-primary" />
              </div>
            ) : error ? (
              // Style error state with destructive colors and vintage paper
              <div className="text-center py-16 px-6 bg-destructive/10 rounded-lg border border-dashed border-destructive text-destructive-foreground/80 relative overflow-hidden">
                {/* Add vintage texture - CSS only version */}
                <div
                  aria-hidden="true"
                  className="absolute inset-0 opacity-5 bg-gradient-to-br from-amber-50/10 via-amber-100/5 to-amber-50/10"
                />

                <AlertTriangle className="h-10 w-10 mx-auto mb-4 text-destructive animate-fade-in" />

                <h2 className="text-2xl font-semibold mb-4 font-display tracking-wide leading-tight relative z-10 animate-fade-in animation-delay-100">
                  Error Loading Data
                </h2>

                <p className="mb-6 animate-fade-in animation-delay-200">
                  {error}
                </p>

                <p className="text-sm text-destructive-foreground/60 animate-fade-in animation-delay-300">
                  (Ensure the backend server is running and accessible at{" "}
                  {process.env.NEXT_PUBLIC_BACKEND_URL}. Authentication might be
                  required.)
                </p>
              </div>
            ) : filteredItems.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 gap-6">
                {filteredItems.map((item, index) => {
                  const projectData =
                    item.category === "Project"
                      ? projects.find((p) => p.id === item.id)
                      : null;
                  const universeData =
                    item.category === "Universe"
                      ? universes.find((u) => u.id === item.id)
                      : null;

                  return (
                    // Style cards with theme colors and vintage hover
                    <Card
                      key={item.id}
                      className={`relative overflow-hidden transition-all duration-300 hover:shadow-lg transform hover:-translate-y-1 bg-card border border-border text-card-foreground animate-slide-up ${index === 0
                        ? "animation-delay-100"
                        : index === 1
                          ? "animation-delay-200"
                          : index === 2
                            ? "animation-delay-300"
                            : "animation-delay-500"
                        }`}
                    >
                      {/* Decorative corner flourishes - CSS only version */}
                      <div
                        aria-hidden="true"
                        className="absolute top-0 left-0 w-8 h-8 opacity-30 pointer-events-none transition-opacity duration-300 group-hover:opacity-60 border-t border-l border-primary/30"
                        style={{
                          borderTopWidth: "2px",
                          borderLeftWidth: "2px",
                          borderTopLeftRadius: "0.25rem",
                        }}
                      />
                      <div
                        aria-hidden="true"
                        className="absolute top-0 right-0 w-8 h-8 opacity-30 pointer-events-none transition-opacity duration-300 group-hover:opacity-60 border-t border-r border-primary/30"
                        style={{
                          borderTopWidth: "2px",
                          borderRightWidth: "2px",
                          borderTopRightRadius: "0.25rem",
                        }}
                      />
                      <div
                        aria-hidden="true"
                        className="absolute bottom-0 right-0 w-8 h-8 opacity-30 pointer-events-none transition-opacity duration-300 group-hover:opacity-60 border-b border-r border-primary/30"
                        style={{
                          borderBottomWidth: "2px",
                          borderRightWidth: "2px",
                          borderBottomRightRadius: "0.25rem",
                        }}
                      />
                      <div
                        aria-hidden="true"
                        className="absolute bottom-0 left-0 w-8 h-8 opacity-30 pointer-events-none transition-opacity duration-300 group-hover:opacity-60 border-b border-l border-primary/30"
                        style={{
                          borderBottomWidth: "2px",
                          borderLeftWidth: "2px",
                          borderBottomLeftRadius: "0.25rem",
                        }}
                      />

                      <CardHeader>
                        {/* Apply display font to title with vintage styling */}
                        <CardTitle className="text-xl font-semibold mb-1 line-clamp-2 font-display tracking-wide leading-tight">
                          {item.name}
                        </CardTitle>

                        {/* Use accent color for type with vintage styling */}
                        <CardDescription className="text-sm text-primary font-medium flex items-center gap-1">
                          {item.category === "Project" ? (
                            <FolderKanban className="h-3.5 w-3.5" />
                          ) : (
                            <Globe className="h-3.5 w-3.5" />
                          )}
                          {item.type}
                        </CardDescription>
                      </CardHeader>

                      <CardContent className="flex-grow flex flex-col justify-between">
                        {/* Use muted foreground for description */}
                        <p className="text-muted-foreground text-sm line-clamp-3 mb-4">
                          {item.description}
                        </p>

                        {/* Style stats section with vintage divider */}
                        <div className="mt-auto pt-4 border-t border-border/50 text-xs text-muted-foreground space-y-1">
                          {item.category === "Project" && projectData && (
                            <>
                              <div className="flex items-center gap-1.5">
                                <FileText className="h-3.5 w-3.5" />
                                <span>
                                  {projectData.word_count?.toLocaleString() ??
                                    0}{" "}
                                  Words
                                </span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <BookCopy className="h-3.5 w-3.5" />
                                <span>
                                  {projectData.chapter_count ?? 0} Chapters
                                </span>
                              </div>
                            </>
                          )}
                          {item.category === "Universe" && universeData && (
                            <>
                              <div className="flex items-center gap-1.5">
                                <FolderKanban className="h-3.5 w-3.5" />
                                <span>
                                  {universeData.project_count ?? 0} Projects
                                </span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <LayoutGrid className="h-3.5 w-3.5" />
                                <span>
                                  {universeData.entry_count ?? 0} Codex Entries
                                </span>
                              </div>
                            </>
                          )}
                        </div>
                      </CardContent>

                      <CardFooter>
                        <Link
                          href={
                            item.category === "Project"
                              ? `/project-dashboard/${item.id}`
                              : `/universe/${item.id}` // Assuming a different route for universe details
                          }
                          passHref
                          legacyBehavior // Still needed for Button inside Link
                          className="w-full"
                        >
                          {/* Style card button with vintage effects */}
                          <Button
                            variant="outline"
                            size="sm"
                            className="w-full group border-border hover:bg-accent hover:text-accent-foreground hover:border-primary/50 rounded-md relative overflow-hidden"
                          >
                            <span className="relative z-10">
                              {item.category === "Project"
                                ? "Open Dashboard"
                                : "Open Universe"}
                            </span>{" "}
                            <BookOpen className="ml-2 h-4 w-4 group-hover:text-primary transition-colors relative z-10" />
                            <span className="absolute inset-0 bg-primary/5 scale-x-0 group-hover:scale-x-100 origin-left transition-transform duration-500"></span>
                          </Button>
                        </Link>
                      </CardFooter>
                    </Card>
                  );
                })}
              </div>
            ) : (
              // --- Empty State with vintage styling --- //
              <div className="text-center mt-10 py-16 px-6 bg-card/50 rounded-lg border border-dashed border-border relative overflow-hidden animate-fade-in">
                {/* Add vintage texture - CSS only version */}
                <div
                  aria-hidden="true"
                  className="absolute inset-0 opacity-5 bg-gradient-to-br from-amber-50/10 via-amber-100/5 to-amber-50/10"
                />

                {/* Decorative icon */}
                <Archive className="h-12 w-12 mx-auto mb-6 text-muted-foreground/40" />

                <h2 className="text-2xl font-semibold mb-4 text-muted-foreground font-display tracking-wide leading-tight">
                  No {activeFilter !== "all" ? activeFilter : "items"} found!
                </h2>

                <p className="text-muted-foreground mb-8">
                  Ready to start your next masterpiece? Create your first{" "}
                  {activeFilter === "universes" ? "universe" : "project"}.
                </p>

                {/* Use themed dropdown with vintage styling */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      size="lg"
                      className="group bg-primary text-primary-foreground hover:bg-primary/90 rounded-md border border-primary/20 shadow-sm hover:shadow transition-all relative overflow-hidden"
                    >
                      <span className="relative z-10">
                        <PlusCircle className="mr-2 h-5 w-5 inline-block" />{" "}
                        Create New{" "}
                        <ChevronDown className="ml-1 h-5 w-5 inline-block" />
                      </span>
                      <span className="absolute inset-0 bg-primary/90 scale-x-0 group-hover:scale-x-100 origin-left transition-transform duration-500"></span>
                    </Button>
                  </DropdownMenuTrigger>

                  <DropdownMenuContent className="w-56 bg-popover border-border text-popover-foreground shadow-md">
                    <DropdownMenuLabel className="text-muted-foreground font-display tracking-wide">
                      Create a new...
                    </DropdownMenuLabel>

                    <DropdownMenuSeparator className="bg-border" />

                    <DropdownMenuItem
                      className="hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground transition-colors"
                      onSelect={(e) => {
                        e.preventDefault();
                        setIsCreateProjectDialogOpen(true);
                      }}
                    >
                      <FolderKanban className="mr-2 h-4 w-4" />
                      <span>Project</span>
                    </DropdownMenuItem>

                    <DropdownMenuItem
                      className="hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground transition-colors"
                      onSelect={(e) => {
                        e.preventDefault();
                        setIsCreateUniverseDialogOpen(true);
                      }}
                    >
                      <Globe className="mr-2 h-4 w-4" />
                      <span>Universe</span>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            )}
          </section>
        </main>

        {/* --- Create Project Dialog - Apply vintage styling --- */}
        <Dialog
          open={isCreateProjectDialogOpen}
          onOpenChange={setIsCreateProjectDialogOpen}
        >
          <DialogContent className="sm:max-w-[425px] bg-card border-border text-card-foreground rounded-lg shadow-lg">
            {/* Decorative corner flourishes - CSS only version */}
            <div
              aria-hidden="true"
              className="absolute top-0 left-0 w-8 h-8 opacity-30 pointer-events-none border-t border-l border-primary/30"
              style={{
                borderTopWidth: "2px",
                borderLeftWidth: "2px",
                borderTopLeftRadius: "0.25rem",
              }}
            />
            <div
              aria-hidden="true"
              className="absolute top-0 right-0 w-8 h-8 opacity-30 pointer-events-none border-t border-r border-primary/30"
              style={{
                borderTopWidth: "2px",
                borderRightWidth: "2px",
                borderTopRightRadius: "0.25rem",
              }}
            />

            <DialogHeader>
              <DialogTitle className="text-foreground font-display tracking-wide leading-tight">
                Create New Project
              </DialogTitle>

              <DialogDescription className="text-muted-foreground">
                Enter the details for your new project below. Click create when
                you&apos;re done.
              </DialogDescription>
            </DialogHeader>

            {/* Assuming CreateProjectForm uses themed components internally */}
            <CreateProjectForm
              onSuccess={handleProjectCreated}
              onCancel={() => setIsCreateProjectDialogOpen(false)}
            />
          </DialogContent>
        </Dialog>

        {/* --- Create Universe Dialog - Apply vintage styling --- */}
        <Dialog
          open={isCreateUniverseDialogOpen}
          onOpenChange={setIsCreateUniverseDialogOpen}
        >
          <DialogContent className="sm:max-w-[425px] bg-card border-border text-card-foreground rounded-lg shadow-lg">
            {/* Decorative corner flourishes - CSS only version */}
            <div
              aria-hidden="true"
              className="absolute top-0 left-0 w-8 h-8 opacity-30 pointer-events-none border-t border-l border-primary/30"
              style={{
                borderTopWidth: "2px",
                borderLeftWidth: "2px",
                borderTopLeftRadius: "0.25rem",
              }}
            />
            <div
              aria-hidden="true"
              className="absolute top-0 right-0 w-8 h-8 opacity-30 pointer-events-none border-t border-r border-primary/30"
              style={{
                borderTopWidth: "2px",
                borderRightWidth: "2px",
                borderTopRightRadius: "0.25rem",
              }}
            />

            <DialogHeader>
              <DialogTitle className="text-foreground font-display tracking-wide leading-tight">
                Create New Universe
              </DialogTitle>

              <DialogDescription className="text-muted-foreground">
                Enter the name for your new universe. Click create when done.
              </DialogDescription>
            </DialogHeader>

            {/* Assuming CreateUniverseForm uses themed components internally */}
            <CreateUniverseForm
              onSuccess={handleUniverseCreated}
              onCancel={() => setIsCreateUniverseDialogOpen(false)}
            />
          </DialogContent>
        </Dialog>
      </div>{" "}
      {/* End of main layout div */}
      {/* Define our CSS animations */}
      <style jsx global>{`
        @keyframes fade-in {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }

        @keyframes slide-up {
          from {
            transform: translateY(20px);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }

        .animate-fade-in {
          animation: fade-in 1.5s ease-out forwards;
        }

        .animate-slide-up {
          animation: slide-up 0.7s ease-out forwards;
        }

        .animation-delay-100 {
          animation-delay: 100ms;
        }

        .animation-delay-200 {
          animation-delay: 200ms;
        }

        .animation-delay-300 {
          animation-delay: 300ms;
        }

        .animation-delay-500 {
          animation-delay: 500ms;
        }
      `}</style>
    </>
  );
}

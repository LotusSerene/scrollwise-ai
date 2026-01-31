"use client"; // Needed for hooks like usePathname and client components like Tabs

import React, { useState, useEffect, use } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList } from "@/components/ui/tabs";
import {
  ArrowLeft,
  BookOpenText,
  Library,
  Wand2,
  PenSquare,
  Users,
  CalendarDays,
  Database,
  ListChecks,
  Sparkles,
  Settings,
  LayoutDashboard,
  Milestone,
} from "lucide-react";
import { fetchApi } from "@/lib/api";
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth
import { ArchitectChat } from "@/components/ArchitectChat"; // Import ArchitectChat component
import { Skeleton } from "@/components/ui/skeleton"; // Import Skeleton for loading
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ProjectProvider, useProject } from "@/contexts/ProjectContext"; // Import context

interface Project {
  id: string;
  name: string;
  architect_mode_enabled: boolean; // Need this field
  // Add other fields if needed
}

function ProjectLayoutContent({
  children,
  projectId,
}: {
  children: React.ReactNode;
  projectId: string;
}) {
  const pathname = usePathname();
  const { project, setProject, isLoading, setIsLoading } = useProject();
  const auth = useAuth();
  // Architect Chat State
  const [isArchitectChatOpen, setIsArchitectChatOpen] = useState(false);
  const [isArchitectChatMinimized, setIsArchitectChatMinimized] =
    useState(false);

  // Determine active tab based on current path
  let activeTab = "overview"; // Default
  const basePath = `/project-dashboard/${projectId}`;

  // Use startsWith for routes with potential sub-paths
  if (pathname?.startsWith(`${basePath}/editor`)) {
    activeTab = "editor";
  } else if (pathname?.startsWith(`${basePath}/codex/generate`)) {
    activeTab = "codex-generate";
  } else if (pathname?.startsWith(`${basePath}/codex`)) {
    activeTab = "codex";
  } else if (pathname?.startsWith(`${basePath}/journeys`)) {
    activeTab = "journeys";
  } else if (pathname?.startsWith(`${basePath}/relationships`)) {
    activeTab = "relationships";
  } else if (pathname?.startsWith(`${basePath}/timeline`)) {
    activeTab = "timeline";
  } else if (pathname?.startsWith(`${basePath}/outliner`)) {
    activeTab = "outliner";
  } else if (pathname?.startsWith(`${basePath}/generate`)) {
    activeTab = "generate";
  } else if (pathname?.startsWith(`${basePath}/knowledge-base`)) {
    activeTab = "knowledge-base";
  } else if (pathname?.startsWith(`${basePath}/validity`)) {
    activeTab = "validity";
  } else if (pathname?.startsWith(`${basePath}/query`)) {
    activeTab = "query";
  } else if (pathname?.startsWith(`${basePath}/settings`)) {
    activeTab = "settings";
  } else if (pathname === basePath || pathname === `${basePath}/`) {
    activeTab = "overview";
  }

  useEffect(() => {
    const fetchProjectData = async (token: string) => {
      if (!projectId) return;
      if (!token) {
        setProject(null);
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      try {
        const projectData = await fetchApi<Project>(
          `/projects/${projectId}`,
          {},
          token
        );
        setProject(projectData);
      } catch (error) {
        console.error("Failed to fetch project data:", error);
        setProject(null);
      } finally {
        setIsLoading(false);
      }
    };

    if (!auth.isLoading && auth.isAuthenticated && auth.user?.id_token) {
      // Fetch only if project data is not already loaded
      if (!project || project.id !== projectId) {
        fetchProjectData(auth.user.id_token);
      } else {
        setIsLoading(false); // Already loaded
      }
    } else if (!auth.isLoading && !auth.isAuthenticated) {
      setProject(null);
      setIsLoading(false);
    }
  }, [
    projectId,
    auth.isLoading,
    auth.isAuthenticated,
    auth.user?.id_token,
    setProject,
    setIsLoading,
    project,
  ]);

  const navItems = [
    {
      name: "Overview",
      href: `${basePath}`,
      icon: <LayoutDashboard className="h-4 w-4 mr-2" />,
      key: "overview",
    },
    {
      name: "Editor",
      href: `${basePath}/editor`,
      icon: <PenSquare className="h-4 w-4 mr-2" />,
      key: "editor",
    },
    {
      name: "Codex",
      href: `${basePath}/codex`,
      icon: <BookOpenText className="h-4 w-4 mr-2" />,
      key: "codex",
    },
    {
      name: "Generate Codex",
      href: `${basePath}/codex/generate`,
      icon: <Sparkles className="h-4 w-4 mr-2" />,
      key: "codex-generate",
    },
    {
      name: "Journeys",
      href: `${basePath}/journeys`,
      icon: <Users className="h-4 w-4 mr-2" />,
      key: "journeys",
    },
    {
      name: "Relationships",
      href: `${basePath}/relationships`,
      icon: <Users className="h-4 w-4 mr-2" />,
      key: "relationships",
    },
    {
      name: "Timeline",
      href: `${basePath}/timeline`,
      icon: <CalendarDays className="h-4 w-4 mr-2" />,
      key: "timeline",
    },
    {
      name: "Outliner",
      href: `${basePath}/outliner`,
      icon: <Milestone className="h-4 w-4 mr-2" />,
      key: "outliner",
    },
    {
      name: "Knowledge Base",
      href: `${basePath}/knowledge-base`,
      icon: <Library className="h-4 w-4 mr-2" />,
      key: "knowledge-base",
    },
    {
      name: "Validity",
      href: `${basePath}/validity`,
      icon: <ListChecks className="h-4 w-4 mr-2" />,
      key: "validity",
    },
    {
      name: "Query AI",
      href: `${basePath}/query`,
      icon: <Database className="h-4 w-4 mr-2" />,
      key: "query",
    },
    {
      name: "Generate Chapters",
      href: `${basePath}/generate`,
      icon: <Wand2 className="h-4 w-4 mr-2" />,
      key: "generate",
    },
    {
      name: "Settings",
      href: `${basePath}/settings`,
      icon: <Settings className="h-4 w-4 mr-2" />,
      key: "settings",
    },
  ];

  // Toggle Architect Chat window
  const toggleArchitectChat = () => {
    setIsArchitectChatOpen((prev) => !prev);
    if (isArchitectChatOpen) {
      // Reset minimized state when closing
      setIsArchitectChatMinimized(false);
    }
  };

  const handleArchitectMinimizeToggle = () => {
    setIsArchitectChatMinimized((prev) => !prev);
  };

  // Handle loading and auth states
  if (auth.isLoading || isLoading) {
    return (
      <div className="flex h-screen bg-background">
        <div className="m-auto text-center">
          <div className="relative w-16 h-16 mx-auto mb-4">
            <div className="absolute inset-0 rounded-full border-t-2 border-primary animate-spin"></div>
            <div className="absolute inset-2 rounded-full border-r-2 border-primary/30 animate-pulse"></div>
          </div>
          <p className="text-muted-foreground animate-pulse">
            {auth.isLoading ? "Authenticating..." : "Loading Project..."}
          </p>
        </div>
      </div>
    );
  }

  const renderLoadingSkeleton = () => (
    <div className="p-6 md:p-8 relative z-10">
      <header className="mb-8 flex flex-col sm:flex-row sm:items-center gap-4 border-b border-border/40 pb-6">
        <Skeleton className="h-10 w-10 rounded-md" />
        <div className="flex-1">
          <Skeleton className="h-8 w-48 rounded-md" />
        </div>
        <Skeleton className="h-6 w-24 rounded-md hidden md:block" />
      </header>
      <Tabs defaultValue="overview" className="mb-8 relative">
        <TabsList className="bg-card/80 border border-border shadow-md backdrop-blur-sm flex flex-wrap justify-center h-auto py-2 px-3 rounded-xl overflow-hidden relative project-dashboard-tabs">
          {navItems.map((item) => (
            <Skeleton key={item.key} className="h-8 w-24 rounded-md m-1" />
          ))}
        </TabsList>
      </Tabs>
      <main>
        <Skeleton className="h-64 w-full rounded-lg" />
      </main>
    </div>
  );

  if (isLoading) {
    return renderLoadingSkeleton();
  }

  if (!project) {
    return (
      <div className="p-6 md:p-8">
        <header className="mb-8 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="outline" size="icon" className="h-10 w-10" asChild>
              <Link href="/dashboard">
                <ArrowLeft className="h-5 w-5" />
              </Link>
            </Button>
            <h1 className="text-2xl font-bold tracking-tight text-destructive">
              Project Not Found or Access Denied
            </h1>
          </div>
        </header>
        <p className="text-muted-foreground">
          The project could not be loaded. It may have been deleted, or you may
          not have permission to view it.
        </p>
      </div>
    );
  }

  const coreNav = navItems.filter(
    (i) =>
      !["journeys", "relationships", "timeline", "outliner"].includes(i.key)
  );
  const worldEngineNav = navItems.filter((i) =>
    ["journeys", "relationships", "timeline", "outliner"].includes(i.key)
  );

  return (
    <TooltipProvider delayDuration={150}>
      <div className="min-h-screen bg-background text-foreground flex flex-col relative">
        <main className="flex-1 p-6 md:p-8 relative z-10">
          <header className="mb-8 flex flex-col sm:flex-row sm:items-center gap-4 border-b border-border/40 pb-6">
            <Button
              variant="outline"
              size="icon"
              className="h-10 w-10 hidden sm:inline-flex"
              asChild
            >
              <Link href="/dashboard">
                <ArrowLeft className="h-5 w-5" />
              </Link>
            </Button>
            <div className="flex-1">
              <h1 className="text-2xl font-bold tracking-tight">
                {project.name}
              </h1>
            </div>
            {project.architect_mode_enabled && (
              <Button
                variant="default"
                className="bg-gradient-to-r from-primary to-primary/80 text-primary-foreground shadow-lg hover:shadow-xl transition-shadow"
                onClick={toggleArchitectChat}
              >
                <Sparkles className="h-4 w-4 mr-2" />
                Architect
              </Button>
            )}
          </header>

          <Tabs
            defaultValue={activeTab}
            value={activeTab}
            className="mb-8 relative"
          >
            <TabsList className="bg-card/80 border border-border shadow-md backdrop-blur-sm flex flex-wrap justify-center h-auto py-2 px-3 rounded-xl overflow-hidden relative project-dashboard-tabs">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Link
                    href={`${basePath}`}
                    className={cn(
                      "flex items-center justify-center px-4 py-1.5 text-sm font-medium rounded-md transition-all outline-none",
                      "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                      activeTab === "overview"
                        ? "bg-primary text-primary-foreground shadow-sm"
                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                    )}
                  >
                    <LayoutDashboard className="h-4 w-4" />
                  </Link>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Overview</p>
                </TooltipContent>
              </Tooltip>

              <div className="h-6 w-px bg-border/60 mx-2"></div>

              {coreNav.slice(1, 3).map((item) => (
                <Tooltip key={item.key}>
                  <TooltipTrigger asChild>
                    <Link
                      href={item.href}
                      className={cn(
                        "flex items-center justify-center px-4 py-1.5 text-sm font-medium rounded-md transition-all outline-none",
                        "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                        activeTab === item.key
                          ? "bg-primary text-primary-foreground shadow-sm"
                          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                        item.key === "codex" ? "codex-tab-trigger" : "",
                        item.key === "editor" ? "editor-tab-trigger" : ""
                      )}
                    >
                      {React.cloneElement(item.icon, {
                        className: "h-4 w-4",
                      })}
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{item.name}</p>
                  </TooltipContent>
                </Tooltip>
              ))}

              <div className="h-6 w-px bg-border/60 mx-2"></div>

              {worldEngineNav.map((item) => (
                <Tooltip key={item.key}>
                  <TooltipTrigger asChild>
                    <Link
                      href={item.href}
                      className={cn(
                        "flex items-center justify-center px-4 py-1.5 text-sm font-medium rounded-md transition-all outline-none",
                        "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                        activeTab === item.key
                          ? "bg-primary text-primary-foreground shadow-sm"
                          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                        item.key === "outliner" ? "outliner-tab-trigger" : ""
                      )}
                    >
                      {React.cloneElement(item.icon, {
                        className: "h-4 w-4",
                      })}
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{item.name}</p>
                  </TooltipContent>
                </Tooltip>
              ))}

              <div className="h-6 w-px bg-border/60 mx-2"></div>

              {navItems
                .filter(
                  (i) =>
                    ![
                      "overview",
                      "editor",
                      "codex",
                      ...worldEngineNav.map((w) => w.key),
                    ].includes(i.key)
                )
                .map((item) => (
                  <Tooltip key={item.key}>
                    <TooltipTrigger asChild>
                      <Link
                        href={item.href}
                        className={cn(
                          "flex items-center justify-center px-4 py-1.5 text-sm font-medium rounded-md transition-all outline-none",
                          "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                          activeTab === item.key
                            ? "bg-primary text-primary-foreground shadow-sm"
                            : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                          item.key === "query" ? "query-tab-trigger" : "",
                          item.key === "generate" ? "generate-tab-trigger" : ""
                        )}
                      >
                        {React.cloneElement(item.icon, {
                          className: "h-4 w-4",
                        })}
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>{item.name}</p>
                    </TooltipContent>
                  </Tooltip>
                ))}
            </TabsList>
          </Tabs>

          <main>{children}</main>
        </main>
        {project.architect_mode_enabled && isArchitectChatOpen && (
          <ArchitectChat
            projectId={projectId}
            isMinimized={isArchitectChatMinimized}
            onClose={toggleArchitectChat}
            onMinimizeToggle={handleArchitectMinimizeToggle}
          />
        )}
        <div
          aria-hidden="true"
          className="absolute inset-0 -z-10 h-full w-full bg-background bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:14px_24px]"
        ></div>
        <div
          aria-hidden="true"
          className="absolute left-0 top-0 -z-10 h-1/3 w-full bg-gradient-to-b from-primary/10 to-transparent"
        ></div>
      </div>
    </TooltipProvider>
  );
}

export default function ProjectDashboardLayout(props: {
  children: React.ReactNode;
  params: Promise<{ projectId: string }>;
}) {
  const params = use(props.params);
  const { projectId } = params;

  return (
    <ProjectProvider>
      <ProjectLayoutContent projectId={projectId}>
        {props.children}
      </ProjectLayoutContent>
    </ProjectProvider>
  );
}
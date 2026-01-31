"use client";

import React, { useEffect, useState } from "react";
import { useOnboarding } from "@/contexts/OnboardingContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  ArrowRight,
  X,
  ChevronRight,
  ChevronLeft,
} from "lucide-react";
import { usePathname } from "next/navigation";

interface OnboardingStep {
  id: string;
  title: string;
  description: string;
  target: string; // CSS selector for the element to highlight
  position: "top" | "bottom" | "left" | "right" | "center";
  action?: () => void; // Optional action to perform when step is shown
  waitForElement?: boolean; // Wait for element to exist before showing step
  page?: string; // Which page this step should be shown on
}

const onboardingSteps: OnboardingStep[] = [
  {
    id: "dashboard-welcome",
    title: "Welcome to Your Dashboard! 👋",
    description: "This is your creative command center where you can see all your projects and universes at a glance. Let's explore the key features together!",
    target: "main",
    position: "center",
    page: "/dashboard",
  },
  {
    id: "sidebar-navigation",
    title: "Navigation Sidebar",
    description: "Use this sidebar to filter between all items, projects only, or universes only. You can also access settings and return to the home page from here.",
    target: "aside",
    position: "right",
    page: "/dashboard",
  },
  {
    id: "create-new",
    title: "Create New Content",
    description: "Click here to create your first project or universe. Projects are individual stories, while universes can contain multiple related projects sharing the same world.",
    target: ".create-new-button",
    position: "bottom",
    waitForElement: true,
    page: "/dashboard",
  },
  {
    id: "projects-vs-universes",
    title: "Projects vs Universes",
    description: "Projects are standalone stories or books. Universes are collections of related projects that share characters, locations, and lore. Start with a project for your first story!",
    target: "main",
    position: "center",
    page: "/dashboard",
  },
  {
    id: "project-overview",
    title: "Project Cards",
    description: "This is where your project cards will appear, showing progress, word count, and chapter count. Since you don't have any projects yet, let's create your first one! Click the 'Create New' button to get started.",
    target: ".grid",
    position: "center",
    waitForElement: false,
    page: "/dashboard",
  },
  {
    id: "create-first-project",
    title: "Create Your First Project! 🚀",
    description: "Now it's time to create your first project! Click the 'Create New' button and choose 'Project' to start your writing journey. Once you create a project, the tour will continue in your project workspace.",
    target: ".create-new-button",
    position: "bottom",
    waitForElement: true,
    page: "/dashboard",
  },
  {
    id: "project-dashboard-intro",
    title: "Project Dashboard Overview",
    description: "Welcome to your project workspace! This is where the magic happens. You can see your progress and access all the powerful writing tools.",
    target: "main",
    position: "center",
    page: "project-dashboard",
  },
  {
    id: "project-tabs",
    title: "Project Navigation Tabs",
    description: "These tabs give you access to all project features. Each icon represents a different aspect of your story creation process. Let's explore the key ones!",
    target: ".project-dashboard-tabs",
    position: "bottom",
    waitForElement: true,
    page: "project-dashboard",
  },
  {
    id: "editor-tab",
    title: "Smart Editor ✍️",
    description: "Your main writing workspace with AI assistance. Use @ to mention codex entries (like @CharacterName), and access AI tools for rewriting, expanding, and improving your text. Click 'Next' to see the editor!",
    target: ".editor-tab-trigger",
    position: "bottom",
    waitForElement: true,
    page: "project-dashboard",
  },
  {
    id: "editor-demo",
    title: "Editor Workspace",
    description: "Here's your writing environment! You can write chapters, use AI assistance, and organize your content. The editor provides real-time word counts and smart suggestions.",
    target: "main",
    position: "center",
    waitForElement: false,
    page: "project-dashboard-editor",
  },
  {
    id: "codex-tab",
    title: "Codex System 📚",
    description: "Your story bible! Manage characters, locations, items, and lore. The AI can automatically extract these from your writing or you can create them manually. Click 'Next' to explore!",
    target: ".codex-tab-trigger",
    position: "bottom",
    waitForElement: true,
    page: "project-dashboard",
  },
  {
    id: "codex-demo",
    title: "Codex Management",
    description: "This is where you manage your story's world-building elements. Create characters, locations, items, and lore entries. The AI can help extract these from your writing automatically!",
    target: "main",
    position: "center",
    waitForElement: false,
    page: "project-dashboard-codex",
  },
  {
    id: "generate-tab",
    title: "Chapter Generation 🤖",
    description: "Let AI help write your story! Generate entire chapters based on your plot, writing style, and existing content. Check the history tab to see past generations. Click 'Next' to see it!",
    target: ".generate-tab-trigger",
    position: "bottom",
    waitForElement: true,
    page: "project-dashboard",
  },
  {
    id: "generate-demo",
    title: "AI Chapter Generation",
    description: "Here you can generate entire chapters using AI! Provide prompts, set the tone, and let the AI help write your story. You can also view generation history and refine results.",
    target: "main",
    position: "center",
    waitForElement: false,
    page: "project-dashboard-generate",
  },
  {
    id: "query-tab",
    title: "AI Knowledge Assistant 💬",
    description: "Chat with your story! Ask questions about characters, plot points, or get writing suggestions based on your existing content and codex. Click 'Next' to try it!",
    target: ".query-tab-trigger",
    position: "bottom",
    waitForElement: true,
    page: "project-dashboard",
  },
  {
    id: "query-demo",
    title: "AI Story Assistant",
    description: "This is your AI-powered story assistant! Ask questions about your characters, plot, or get writing suggestions. The AI knows your entire story and codex.",
    target: "main",
    position: "center",
    waitForElement: false,
    page: "project-dashboard-query",
  },
  {
    id: "outliner-feature",
    title: "Project Structure & Outliner 📋",
    description: "Organize your story with folders, acts, stages, and chapters. Drag and drop to reorder, and use the folder system to keep everything organized. Click 'Next' to see the outliner!",
    target: ".outliner-tab-trigger",
    position: "bottom",
    waitForElement: true,
    page: "project-dashboard",
  },
  {
    id: "outliner-demo",
    title: "Story Structure",
    description: "Here's your story outliner! Organize chapters into acts and stages, create folders for different story arcs, and drag-and-drop to reorder your content.",
    target: "main",
    position: "center",
    waitForElement: false,
    page: "project-dashboard-outliner",
  },
  {
    id: "back-to-overview",
    title: "Tour Complete! 🎉",
    description: "Congratulations! You've explored all the key features of ScrollWise. You're now ready to start writing your story. Return to the project overview to begin!",
    target: "main",
    position: "center",
    waitForElement: false,
    page: "project-dashboard",
  },
  {
    id: "completion",
    title: "You're All Set! 🎉",
    description: "You now know the key features of ScrollWise. Start by creating your first project, then build your codex and begin writing. The AI is here to help every step of the way!",
    target: "main",
    position: "center",
    page: "/dashboard",
  },
];

export function OnboardingOverlay() {
  const {
    isOnboardingActive,
    currentStep,
    totalSteps,
    nextStep,
    prevStep,
    completeOnboarding,
    currentProjectId,
    setCurrentProjectId,
  } = useOnboarding();

  const [highlightedElement, setHighlightedElement] = useState<Element | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });
  const [isElementReady, setIsElementReady] = useState(false);
  const pathname = usePathname();

  const currentStepData = onboardingSteps[currentStep];

  // Check if current step should be shown on current page
  const shouldShowStep = React.useCallback(() => {
    if (!currentStepData?.page) return true;

    if (currentStepData.page === "/dashboard") {
      return pathname === "/dashboard";
    }

    if (currentStepData.page === "project-dashboard") {
      return pathname ? pathname.includes("/project-dashboard/") && !pathname.includes("/editor") && !pathname.includes("/codex") && !pathname.includes("/generate") && !pathname.includes("/query") && !pathname.includes("/outliner") : false;
    }

    if (currentStepData.page === "project-dashboard-editor") {
      return pathname ? pathname.includes("/project-dashboard/") && pathname.includes("/editor") : false;
    }

    if (currentStepData.page === "project-dashboard-codex") {
      return pathname ? pathname.includes("/project-dashboard/") && pathname.includes("/codex") : false;
    }

    if (currentStepData.page === "project-dashboard-generate") {
      return pathname ? pathname.includes("/project-dashboard/") && pathname.includes("/generate") : false;
    }

    if (currentStepData.page === "project-dashboard-query") {
      return pathname ? pathname.includes("/project-dashboard/") && pathname.includes("/query") : false;
    }

    if (currentStepData.page === "project-dashboard-outliner") {
      return pathname ? pathname.includes("/project-dashboard/") && pathname.includes("/outliner") : false;
    }

    return pathname === currentStepData.page;
  }, [currentStepData, pathname]);

  // Track when we're on the wrong page and show loading briefly


  useEffect(() => {
    if (!isOnboardingActive || !currentStepData) return;

    // Track project ID when we're in a project dashboard
    if (pathname && pathname.includes("/project-dashboard/")) {
      const pathParts = pathname.split('/');
      const projectIdFromPath = pathParts[2];
      if (projectIdFromPath && projectIdFromPath !== currentProjectId) {
        setCurrentProjectId(projectIdFromPath);
      }
    }

    // Reset element ready state when step changes
    setIsElementReady(false);

    // Reset retry counter for new step
    (window as Window & { __onboardingRetryCount?: number }).__onboardingRetryCount = 0;

    const findAndHighlightElement = () => {
      // Handle multiple selectors separated by comma
      const selectors = currentStepData.target.split(',').map(s => s.trim());
      let element: Element | null = null;

      for (const selector of selectors) {
        element = document.querySelector(selector);
        if (element) break;
      }

      if (element) {
        setHighlightedElement(element);
        setIsElementReady(true);

        // Calculate tooltip position
        const rect = element.getBoundingClientRect();
        const scrollTop = window.scrollY || document.documentElement.scrollTop;
        const scrollLeft = window.scrollX || document.documentElement.scrollLeft;

        let x = 0;
        let y = 0;

        switch (currentStepData.position) {
          case "top":
            x = rect.left + scrollLeft + rect.width / 2;
            y = rect.top + scrollTop - 20;
            break;
          case "bottom":
            x = rect.left + scrollLeft + rect.width / 2;
            y = rect.bottom + scrollTop + 20;
            break;
          case "left":
            x = rect.left + scrollLeft - 20;
            y = rect.top + scrollTop + rect.height / 2;
            break;
          case "right":
            x = rect.right + scrollLeft + 20;
            y = rect.top + scrollTop + rect.height / 2;
            break;
          case "center":
            x = window.innerWidth / 2;
            y = window.innerHeight / 2;
            break;
        }

        setTooltipPosition({ x, y });

        // Scroll element into view
        element.scrollIntoView({
          behavior: "smooth",
          block: "center",
          inline: "center",
        });
      } else if (currentStepData.waitForElement) {
        // If element doesn't exist and we should wait, try again (but limit retries)
        setIsElementReady(false);
        const retryCount = (window as Window & { __onboardingRetryCount?: number }).__onboardingRetryCount || 0;
        if (retryCount < 10) { // Max 10 retries (5 seconds)
          (window as Window & { __onboardingRetryCount?: number }).__onboardingRetryCount = retryCount + 1;
          setTimeout(findAndHighlightElement, 500);
        } else {
          // Give up waiting and show in center
          (window as Window & { __onboardingRetryCount?: number }).__onboardingRetryCount = 0;
          setHighlightedElement(null);
          setIsElementReady(true);
          setTooltipPosition({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
        }
      } else {
        // If element doesn't exist but we don't need to wait, show in center
        setHighlightedElement(null);
        setIsElementReady(true);
        setTooltipPosition({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
      }
    };

    // Execute any step action with a delay to ensure UI is ready
    if (currentStepData.action) {
      setTimeout(() => {
        currentStepData.action!();
      }, 1000); // 1 second delay to let user see the step first
    }

    // Delay to ensure DOM is ready - longer delay for page navigation
    const delay = shouldShowStep() ? 100 : 500; // Wait longer if page needs to load
    setTimeout(findAndHighlightElement, delay);
  }, [isOnboardingActive, currentStep, currentStepData, pathname, currentProjectId, setCurrentProjectId, shouldShowStep]);

  if (!isOnboardingActive || !currentStepData || !isElementReady || !shouldShowStep()) {
    return null;
  }

  return (
    <>
      {/* Overlay */}
      <div className="fixed inset-0 bg-black/50 z-[9998] pointer-events-none animate-in fade-in duration-300">
        {/* Highlight cutout */}
        {highlightedElement && (
          <div
            className="absolute border-2 border-primary rounded-lg shadow-lg pointer-events-none animate-pulse transition-all duration-300"
            style={{
              left: highlightedElement.getBoundingClientRect().left - 4,
              top: highlightedElement.getBoundingClientRect().top - 4,
              width: highlightedElement.getBoundingClientRect().width + 8,
              height: highlightedElement.getBoundingClientRect().height + 8,
              boxShadow: "0 0 0 9999px rgba(0, 0, 0, 0.5), 0 0 20px rgba(var(--primary), 0.5)",
            }}
          />
        )}
      </div>

      {/* Tooltip */}
      <Card
        className="fixed z-[9999] w-80 max-w-[90vw] bg-card border-border shadow-xl pointer-events-auto animate-in slide-in-from-bottom-4 duration-300"
        style={{
          left: Math.min(Math.max(tooltipPosition.x - 160, 20), window.innerWidth - 340),
          top: Math.min(Math.max(tooltipPosition.y - 100, 20), window.innerHeight - 200),
          transform: currentStepData.position === "center" ? "translate(-50%, -50%)" : "none",
        }}
      >
        <CardContent className="p-6">
          {/* Header */}
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-foreground mb-2">
                {currentStepData.title}
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {currentStepData.description}
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={completeOnboarding}
              className="ml-2 h-8 w-8 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Progress */}
          <div className="mb-4">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
              <span>Step {currentStep + 1} of {totalSteps}</span>
              <span>{Math.round(((currentStep + 1) / totalSteps) * 100)}%</span>
            </div>
            <div className="w-full bg-accent rounded-full h-2">
              <div
                className="bg-primary h-2 rounded-full transition-all duration-300"
                style={{ width: `${((currentStep + 1) / totalSteps) * 100}%` }}
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between">
            <Button
              variant="outline"
              size="sm"
              onClick={prevStep}
              disabled={currentStep === 0}
              className="flex items-center"
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Previous
            </Button>

            <Button
              onClick={nextStep}
              size="sm"
              className="flex items-center bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {currentStep === totalSteps - 1 ? (
                <>
                  Complete
                  <ArrowRight className="h-4 w-4 ml-1" />
                </>
              ) : (
                <>
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </>
  );
}

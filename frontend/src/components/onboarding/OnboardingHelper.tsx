"use client";

import React from "react";
import { useOnboarding } from "@/contexts/OnboardingContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePathname } from "next/navigation";
import { Sparkles } from "lucide-react";

export function OnboardingHelper() {
  const { isOnboardingActive, currentStep, currentProjectId, setCurrentProjectId } = useOnboarding();
  const pathname = usePathname();

  // Track when user enters a project dashboard
  React.useEffect(() => {
    if (pathname && pathname.includes("/project-dashboard/")) {
      const pathParts = pathname.split('/');
      const projectIdFromPath = pathParts[2];
      if (projectIdFromPath) {
        setCurrentProjectId(projectIdFromPath);
      }
    }
  }, [pathname, setCurrentProjectId]);

  // Show helper when user is on dashboard during onboarding and needs to create/select a project
  // Show at step 6 (create-first-project) or steps 7-19 if no project is selected
  const shouldShowHelper = 
    isOnboardingActive && 
    ((currentStep === 6 && pathname === "/dashboard") || 
     (currentStep >= 7 && currentStep <= 19 && !currentProjectId && pathname === "/dashboard"));

  if (!shouldShowHelper) return null;

  return (
    <Card className="fixed bottom-4 right-4 w-80 z-[9997] bg-card border-primary/20 shadow-xl">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          Continue Your Tour
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          {currentStep === 6 
            ? "Great! Now it's time to create your first project to continue the tour. Once you create a project, we'll explore all the powerful features inside!"
            : "The onboarding tour needs you to be in a project dashboard. Please create a new project or open an existing one to continue."
          }
        </p>
        
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium text-foreground">Next steps:</p>
          <div className="text-xs text-muted-foreground space-y-1">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 bg-primary rounded-full"></div>
              Click the &quot;Create New&quot; button above
            </div>
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 bg-primary rounded-full"></div>
              Select &quot;Project&quot; from the dropdown
            </div>
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 bg-primary rounded-full"></div>
              Fill in your project details and create it
            </div>
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 bg-primary rounded-full"></div>
              The tour will automatically continue in your new project!
            </div>
          </div>
        </div>

        <div className="pt-2 border-t border-border/50">
          <p className="text-xs text-muted-foreground">
            💡 Tip: You can also open an existing project if you have one.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

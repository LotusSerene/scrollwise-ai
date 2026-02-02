"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useAuth } from "@/components/MockAuthProvider";
import { fetchApi } from "@/lib/api";
import { useRouter, usePathname } from "next/navigation";

interface OnboardingContextType {
  isOnboardingActive: boolean;
  currentStep: number;
  totalSteps: number;
  showWelcome: boolean;
  currentProjectId: string | null;
  startOnboarding: () => void;
  nextStep: () => void;
  prevStep: () => void;
  skipOnboarding: () => void;
  completeOnboarding: () => void;
  setCurrentStep: (step: number) => void;
  setShowWelcome: (show: boolean) => void;
  restartOnboarding: () => void;
  navigateToStep: (step: number) => void;
  setCurrentProjectId: (projectId: string | null) => void;
}

const OnboardingContext = createContext<OnboardingContextType | undefined>(
  undefined
);

export function useOnboarding() {
  const context = useContext(OnboardingContext);
  if (context === undefined) {
    throw new Error("useOnboarding must be used within an OnboardingProvider");
  }
  return context;
}

interface OnboardingProviderProps {
  children: React.ReactNode;
}

export function OnboardingProvider({ children }: OnboardingProviderProps) {
  const [isOnboardingActive, setIsOnboardingActive] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [showWelcome, setShowWelcome] = useState(false);
  const [hasCheckedOnboarding, setHasCheckedOnboarding] = useState(false);
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const auth = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const totalSteps = 20;

  const getTargetPageForStep = useCallback((step: number): string => {
    const stepData = [
      { page: "/dashboard" }, // 0 - dashboard-welcome
      { page: "/dashboard" }, // 1 - sidebar-navigation
      { page: "/dashboard" }, // 2 - create-new
      { page: "/dashboard" }, // 3 - projects-vs-universes
      { page: "/dashboard" }, // 4 - project-overview
      { page: "/dashboard" }, // 5 - create-first-project
      { page: "project-dashboard" }, // 6 - project-dashboard-intro
      { page: "project-dashboard" }, // 7 - project-tabs
      { page: "project-dashboard" }, // 8 - editor-tab (showing the tab, not navigating yet)
      { page: "project-dashboard-editor" }, // 9 - editor-demo (now navigate to editor)
      { page: "project-dashboard" }, // 10 - codex-tab (back to main, showing codex tab)
      { page: "project-dashboard-codex" }, // 11 - codex-demo (navigate to codex)
      { page: "project-dashboard" }, // 12 - generate-tab (back to main, showing generate tab)
      { page: "project-dashboard-generate" }, // 13 - generate-demo (navigate to generate)
      { page: "project-dashboard" }, // 14 - query-tab (back to main, showing query tab)
      { page: "project-dashboard-query" }, // 15 - query-demo (navigate to query)
      { page: "project-dashboard" }, // 16 - outliner-feature (back to main, showing outliner tab)
      { page: "project-dashboard-outliner" }, // 17 - outliner-demo (navigate to outliner)
      { page: "project-dashboard" }, // 18 - back-to-overview (back to main)
      { page: "/dashboard" }, // 19 - completion
    ];
    return stepData[step]?.page || "/dashboard";
  }, []);

  const markOnboardingComplete = useCallback(async () => {
    if (auth.user?.id_token) {
      try {
        await fetchApi("/users/me/onboarding-complete", { method: "PUT" }, auth.user.id_token);
      } catch (error) {
        console.error("Failed to mark onboarding as complete:", error);
      }
    }
  }, [auth.user?.id_token]);

  const completeOnboarding = useCallback(async () => {
    setIsOnboardingActive(false);
    setCurrentStep(0);
    setCurrentProjectId(null);
    await markOnboardingComplete();
  }, [markOnboardingComplete]);

  const nextStep = useCallback(() => {
    if (currentStep < totalSteps - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      completeOnboarding();
    }
  }, [currentStep, totalSteps, completeOnboarding]);

  const prevStep = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  }, [currentStep]);

  const navigateToStep = useCallback((step: number) => {
    setCurrentStep(step);
  }, []);

  useEffect(() => {
    const checkOnboardingStatus = async () => {
      if (!auth.isLoading && auth.isAuthenticated && auth.user?.id_token && !hasCheckedOnboarding) {
        try {
          const userDetails = await fetchApi<{ has_completed_onboarding: boolean }>("/users/me", {}, auth.user.id_token);
          if (userDetails && !userDetails.has_completed_onboarding) {
            setShowWelcome(true);
          }
          setHasCheckedOnboarding(true);
        } catch (error) {
          console.error("Failed to check onboarding status:", error);
          setHasCheckedOnboarding(true);
        }
      }
    };
    checkOnboardingStatus();
  }, [auth.isLoading, auth.isAuthenticated, auth.user?.id_token, hasCheckedOnboarding]);

  useEffect(() => {
    if (isOnboardingActive && pathname?.includes("/project-dashboard/")) {
      const projectIdFromPath = pathname.split('/')[2];
      if (projectIdFromPath && projectIdFromPath !== currentProjectId) {
        setCurrentProjectId(projectIdFromPath);
      }
    }
  }, [isOnboardingActive, pathname, currentProjectId]);

  // Central navigation handler effect - only runs when step or projectId changes
  useEffect(() => {
    if (!isOnboardingActive) return;

    const targetPage = getTargetPageForStep(currentStep);
    let targetPath: string | null = null;

    if (currentStep >= 7 && currentStep <= 19) {
      if (!currentProjectId) {
        console.log(`[Onboarding] Step ${currentStep}: Waiting for project ID...`);
        // Navigate back to dashboard if we don't have a project ID
        targetPath = "/dashboard";
      } else {
        targetPath = `/project-dashboard/${currentProjectId}`;
        if (targetPage === "project-dashboard-editor") targetPath += "/editor";
        else if (targetPage === "project-dashboard-codex") targetPath += "/codex";
        else if (targetPage === "project-dashboard-generate") targetPath += "/generate";
        else if (targetPage === "project-dashboard-query") targetPath += "/query";
        else if (targetPage === "project-dashboard-outliner") targetPath += "/outliner";
      }
    } else {
      targetPath = "/dashboard";
    }

    // Navigate to the target path if we're not already there
    // We remove pathname from dependencies to avoid "trapping" the user
    // if they manually navigate during a tour.
    const currentPath = window.location.pathname;
    if (targetPath && currentPath !== targetPath) {
      // Use replace for tour steps to avoid polluting history stack
      router.replace(targetPath);
    }
  }, [isOnboardingActive, currentStep, currentProjectId, getTargetPageForStep, router]);


  const startOnboarding = () => {
    setShowWelcome(false);
    setIsOnboardingActive(true);
    setCurrentStep(0);
  };

  const skipOnboarding = async () => {
    setShowWelcome(false);
    setIsOnboardingActive(false);
    await markOnboardingComplete();
  };

  const restartOnboarding = () => {
    setIsOnboardingActive(true);
    setCurrentStep(0);
    setShowWelcome(false);
    setCurrentProjectId(null);
  };

  const value: OnboardingContextType = {
    isOnboardingActive,
    currentStep,
    totalSteps,
    showWelcome,
    currentProjectId,
    startOnboarding,
    nextStep,
    prevStep,
    skipOnboarding,
    completeOnboarding,
    setCurrentStep: navigateToStep,
    setShowWelcome,
    restartOnboarding,
    navigateToStep,
    setCurrentProjectId,
  };

  return (
    <OnboardingContext.Provider value={value}>
      {children}
    </OnboardingContext.Provider>
  );
}

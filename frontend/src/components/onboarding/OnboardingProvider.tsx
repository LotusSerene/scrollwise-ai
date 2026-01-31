"use client";

import React from "react";
import { OnboardingProvider as ContextProvider } from "@/contexts/OnboardingContext";
import { WelcomeModal } from "./WelcomeModal";
import { OnboardingOverlay } from "./OnboardingOverlay";
import { OnboardingHelper } from "./OnboardingHelper";

interface OnboardingProviderProps {
  children: React.ReactNode;
}

export function OnboardingProvider({ children }: OnboardingProviderProps) {
  return (
    <ContextProvider>
      {children}
      <WelcomeModal />
      <OnboardingOverlay />
      <OnboardingHelper />
    </ContextProvider>
  );
}

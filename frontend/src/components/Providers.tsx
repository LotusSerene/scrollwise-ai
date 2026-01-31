"use client"; // This component uses client-side context

import React from "react";
import { ThemeProvider } from "@/components/ThemeProvider";
import { AuthProvider } from "@/components/MockAuthProvider";
import { Toaster } from "@/components/ui/sonner";
import { OnboardingProvider } from "@/components/onboarding/OnboardingProvider";

export function Providers({ children }: { children: React.ReactNode }) {
  // Config is no longer needed for mock auth
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      <AuthProvider>
        <OnboardingProvider>
          {children}
        </OnboardingProvider>
      </AuthProvider>
      <Toaster />
    </ThemeProvider>
  );
}

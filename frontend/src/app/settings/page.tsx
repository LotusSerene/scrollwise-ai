"use client"; // Required for using hooks like useAuth and useState

import React, { useState, useEffect } from "react"; // Import useState and useEffect
import { useAuth } from "@/components/MockAuthProvider"; // Import useAuth from react-oidc-context
import { useRouter } from "next/navigation"; // Use useRouter for client-side navigation
import Link from "next/link";
import { fetchApi } from "@/lib/api"; // Assuming api lib is in src/lib
import { Button } from "@/components/ui/button"; // Assuming shadcn/ui
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"; // Assuming shadcn/ui
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"; // Assuming shadcn/ui
import {
  Terminal,
  Loader2,
  ArrowLeft,
  Palette,
  CheckCircle,
  Sun,
  Moon,
  Sparkles,
  Feather,
  BookOpen,
} from "lucide-react"; // Added Loader2, ArrowLeft, Palette, and BookOpen icons
import { SettingsForm } from "@/components/SettingsForm"; // Import the SettingsForm
import { ModeToggle } from "@/components/ThemeToggle"; // Import the ModeToggle component
import { useTheme } from "next-themes"; // Import useTheme
import { toast } from "sonner";
import { useOnboarding } from "@/contexts/OnboardingContext"; // Import onboarding context

// Define a more complete interface for the user data from /users/me
interface UserDetails {
  id: string;
  email: string;
  subscription_plan: string | null; // The plan name (free, pro, etc.)
  subscription_status: string | null; // The status (active, canceled, etc.)
  subscription_renews_at: string | null; // Date when subscription renews
  has_completed_onboarding: boolean; // Added onboarding flag
  // Other fields returned by the backend
}

export default function SettingsPage() {
  const {
    user,
    isAuthenticated,
    isLoading: authLoading,
  } = useAuth(); // Use the hook
  const router = useRouter();
  const { theme } = useTheme(); // Get current theme
  const { restartOnboarding } = useOnboarding(); // Get onboarding functions
  const [userDetails, setUserDetails] = useState<UserDetails | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [isLoadingData, setIsLoadingData] = useState<boolean>(true);
  const [isProUser, setIsProUser] = useState<boolean>(true); // Pro by default in local version

  useEffect(() => {
    // Handle authentication state
    if (!authLoading && !isAuthenticated) {
      // router.push("/api/auth/login"); // Redirect to login if not authenticated
      // Let the component render the unauthenticated state instead
      setIsLoadingData(false);
      return;
    }

    // Fetch user details only if authenticated and token is available
    if (isAuthenticated && user?.id_token) {
      const accessToken = user.id_token;
      const fetchUserDetails = async () => {
        setIsLoadingData(true);
        setFetchError(null);
        try {
          // Call the new /users/me endpoint
          const data = await fetchApi<UserDetails>(
            "/users/me", // Changed from /users/me/plan
            { method: "GET" },
            accessToken
          );
          setUserDetails(data);
          // Determine if the user is 'pro'
          const proStatus =
            data?.subscription_plan?.toLowerCase() === "pro" &&
            data?.subscription_status?.toLowerCase() === "active";
          setIsProUser(proStatus);
          toast.success("Account details loaded", {
            description: "Your information has been successfully retrieved.",
          });
        } catch (error) {
          console.error("Failed to fetch user details:", error);
          const errorMessage =
            error instanceof Error
              ? error.message
              : "An unknown error occurred while fetching your account details.";
          setFetchError(errorMessage);
          toast.error("Failed to Load Details", {
            description: errorMessage,
          });
          setIsProUser(false); // Assume not pro on error
        } finally {
          setIsLoadingData(false);
        }
      };

      fetchUserDetails();
    } else if (!authLoading && !user?.id_token) {
      const errorMessage =
        "Authentication token not found. Please try signing out and back in.";
      setFetchError(errorMessage);
      toast.error("Authentication Error", {
        description: errorMessage,
      });
      setIsLoadingData(false);
      setIsProUser(false);
    }
    // If auth is still loading, the effect will re-run.
  }, [isAuthenticated, authLoading, user, router]); // Removed signinRedirect dependency

  // Show loading state while checking auth or fetching data
  if (authLoading || isLoadingData) {
    return (
      <div className="container mx-auto px-4 py-8 flex justify-center items-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="ml-3 text-muted-foreground">Loading account details...</p>
      </div>
    );
  }


  // Main content render
  return (
    <div className="container mx-auto px-4 md:px-8 py-8 space-y-8 bg-background/50 relative">
      {/* Paper texture overlay - CSS only version */}
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

      {/* Header with Back Button and Title */}
      <div className="flex items-center justify-center relative mb-10 animate-in fade-in-50 duration-700 z-10">
        {/* Back button with enhanced styling */}
        <Link href="/dashboard" passHref legacyBehavior>
          <Button
            variant="outline"
            size="icon"
            className="absolute left-0 top-1/2 -translate-y-1/2 group border-border hover:bg-accent hover:text-accent-foreground hover:border-primary/50 rounded-md transition-all duration-300"
          >
            <ArrowLeft className="h-5 w-5 transition-transform group-hover:-translate-x-1" />
          </Button>
        </Link>
        {/* Centered Title with decoration */}
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-primary font-display relative inline-block">
            Account Settings
            <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-20 h-1 bg-primary/50 rounded-full"></span>
          </h1>
          <p className="text-muted-foreground mt-2 max-w-xl">
            Manage your account details, preferences, and model settings
          </p>
        </div>
      </div>

      {/* Centered Content Area using Flexbox */}
      <div className="flex flex-col items-center space-y-8 relative z-10">
        {/* User Information Card with animation */}
        <Card className="w-full max-w-2xl mx-auto overflow-hidden border-border hover:shadow-md transition-all animate-in fade-in-50 slide-in-from-bottom-5 duration-500 fill-mode-both">
          <CardHeader className="border-b border-border/50 bg-muted/20">
            <CardTitle className="flex items-center gap-2">
              <svg
                className="h-5 w-5 text-primary"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                />
              </svg>
              Your Information
            </CardTitle>
            <CardDescription>
              Details associated with your account.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5 pt-6">
            <div className="flex flex-col sm:flex-row border border-border/40 rounded-lg overflow-hidden divide-y sm:divide-y-0 sm:divide-x divide-border/40">
              <div className="flex-1 p-4 bg-muted/10">
                <p className="text-sm font-medium text-muted-foreground mb-1.5">
                  Email
                </p>
                <p className="font-medium flex items-center">
                  <svg
                    className="h-4 w-4 mr-2 text-primary/70"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                    />
                  </svg>
                  {userDetails?.email ||
                    user?.profile?.email ||
                    "Not available"}
                </p>
              </div>
              <div className="flex-1 p-4">
                <p className="text-sm font-medium text-muted-foreground mb-1.5">
                  Current Plan
                </p>
                {fetchError ? (
                  <Alert variant="destructive" className="mt-2">
                    <Terminal className="h-4 w-4" />
                    <AlertTitle>Error Loading Plan</AlertTitle>
                    <AlertDescription>{fetchError}</AlertDescription>
                  </Alert>
                ) : userDetails?.subscription_plan ? (
                  <div className="flex items-center">
                    <div className="mr-3 h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center">
                      <Sparkles className="h-4 w-4 text-primary" />
                    </div>
                    <p className="text-lg font-semibold capitalize">
                      {userDetails.subscription_plan}
                    </p>
                  </div>
                ) : (
                  <div className="flex items-center">
                    <div className="mr-3 h-8 w-8 rounded-full bg-muted flex items-center justify-center">
                      <svg
                        className="h-4 w-4 text-muted-foreground"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                    </div>
                    <p className="text-muted-foreground">
                      Free Plan (or status unknown)
                    </p>
                  </div>
                )}
              </div>
            </div>

            {(userDetails?.subscription_status ||
              userDetails?.subscription_renews_at) && (
                <div className="flex flex-col sm:flex-row border border-border/40 rounded-lg overflow-hidden divide-y sm:divide-y-0 sm:divide-x divide-border/40">
                  {userDetails?.subscription_status && (
                    <div className="flex-1 p-4 bg-muted/10">
                      <p className="text-sm font-medium text-muted-foreground mb-1.5">
                        Subscription Status
                      </p>
                      <p className="font-medium capitalize flex items-center">
                        <svg
                          className="h-4 w-4 mr-2 text-primary/70"
                          xmlns="http://www.w3.org/2000/svg"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                          />
                        </svg>
                        {userDetails.subscription_status}
                      </p>
                    </div>
                  )}
                  {userDetails?.subscription_renews_at && (
                    <div className="flex-1 p-4">
                      <p className="text-sm font-medium text-muted-foreground mb-1.5">
                        Renews
                      </p>
                      <p className="font-medium flex items-center">
                        <svg
                          className="h-4 w-4 mr-2 text-primary/70"
                          xmlns="http://www.w3.org/2000/svg"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                          />
                        </svg>
                        {new Date(
                          userDetails.subscription_renews_at
                        ).toLocaleDateString()}
                      </p>
                    </div>
                  )}
                </div>
              )}
          </CardContent>
        </Card>

        {/* Theme Settings Section with animation */}
        <Card className="w-full max-w-2xl mx-auto overflow-hidden border-border hover:shadow-md transition-shadow animate-in fade-in-50 slide-in-from-bottom-5 duration-500 delay-150 fill-mode-both">
          <CardHeader className="border-b border-border/50 bg-muted/20">
            <CardTitle className="flex items-center gap-2">
              <Palette className="h-5 w-5 text-primary" />
              Theme Settings
            </CardTitle>
            <CardDescription>
              Customize the appearance of ScrollWise.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 pt-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="font-medium text-foreground">Color Theme</p>
                <p className="text-sm text-muted-foreground">
                  Choose between light, dark or system theme
                </p>
              </div>
              <ModeToggle />
            </div>

            {/* Theme preview section */}
            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div
                className={`border rounded-md p-4 ${theme === "light" ? "ring-2 ring-primary" : ""
                  } transition-all duration-300 bg-[oklch(0.98_0.01_90)] relative overflow-hidden`}
              >
                <div className="flex items-center text-[oklch(0.25_0.03_250)] mb-2">
                  <div className="w-4 h-4 rounded-full bg-[oklch(0.65_0.15_80)] mr-2"></div>
                  <span className="font-medium text-sm">Light Theme</span>
                </div>
                <div className="w-full h-2 rounded bg-[oklch(0.85_0.02_90)] mb-1"></div>
                <div className="w-3/4 h-2 rounded bg-[oklch(0.85_0.02_90)] mb-3"></div>
                <div className="w-1/2 h-6 rounded bg-[oklch(0.65_0.15_80)] text-[oklch(0.15_0.03_250)] text-xs flex items-center justify-center">
                  Button
                </div>
                {theme === "light" && (
                  <div className="absolute top-2 right-2">
                    <CheckCircle className="h-4 w-4 text-primary" />
                  </div>
                )}
              </div>

              <div
                className={`border rounded-md p-4 ${theme === "dark" ? "ring-2 ring-primary" : ""
                  } transition-all duration-300 bg-[oklch(0.18_0.03_250)] relative overflow-hidden`}
              >
                <div className="flex items-center text-[oklch(0.95_0.01_90)] mb-2">
                  <div className="w-4 h-4 rounded-full bg-[oklch(0.7_0.15_85)] mr-2"></div>
                  <span className="font-medium text-sm">Dark Theme</span>
                </div>
                <div className="w-full h-2 rounded bg-[oklch(0.35_0.03_250)] mb-1"></div>
                <div className="w-3/4 h-2 rounded bg-[oklch(0.35_0.03_250)] mb-3"></div>
                <div className="w-1/2 h-6 rounded bg-[oklch(0.7_0.15_85)] text-[oklch(0.15_0.03_250)] text-xs flex items-center justify-center">
                  Button
                </div>
                {theme === "dark" && (
                  <div className="absolute top-2 right-2">
                    <CheckCircle className="h-4 w-4 text-primary" />
                  </div>
                )}
              </div>
            </div>

            <div className="pt-2 pb-1 mt-2 border-t border-border/50">
              <p className="text-sm font-medium text-muted-foreground mt-2">
                Active Theme
              </p>
              <p className="font-medium capitalize flex items-center">
                {theme === "light" && (
                  <>
                    <Sun className="h-4 w-4 mr-2 text-amber-500" />
                    Light
                  </>
                )}
                {theme === "dark" && (
                  <>
                    <Moon className="h-4 w-4 mr-2 text-indigo-400" />
                    Dark
                  </>
                )}
                {(theme === "system" || !theme) && (
                  <>
                    <svg
                      className="h-4 w-4 mr-2 text-primary"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                      />
                    </svg>
                    System
                  </>
                )}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Onboarding Section with animation */}
        <Card className="w-full max-w-2xl mx-auto overflow-hidden border-border hover:shadow-md transition-shadow animate-in fade-in-50 slide-in-from-bottom-5 duration-500 delay-250 fill-mode-both">
          <CardHeader className="border-b border-border/50 bg-muted/20">
            <CardTitle className="flex items-center gap-2">
              <svg
                className="h-5 w-5 text-primary"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                />
              </svg>
              Getting Started
            </CardTitle>
            <CardDescription>
              Learn how to use ScrollWise with our interactive guide.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 pt-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="font-medium text-foreground">Interactive Tour</p>
                <p className="text-sm text-muted-foreground">
                  Take a guided tour of ScrollWise features and learn how to create amazing stories
                </p>
              </div>
              <Button
                onClick={() => {
                  restartOnboarding();
                  toast.success("Onboarding tour started!", {
                    description: "Follow the guided tour to learn ScrollWise features.",
                  });
                }}
                variant="outline"
                className="border-primary/20 hover:border-primary/50 hover:bg-primary/5"
              >
                <BookOpen className="h-4 w-4 mr-2" />
                Start Tour
              </Button>
            </div>

            <div className="pt-2 pb-1 mt-2 border-t border-border/50">
              <p className="text-sm font-medium text-muted-foreground mt-2">
                What you&apos;ll learn:
              </p>
              <ul className="text-sm text-muted-foreground mt-2 space-y-1">
                <li className="flex items-center">
                  <div className="w-1.5 h-1.5 bg-primary/60 rounded-full mr-2"></div>
                  Creating projects and organizing with universes
                </li>
                <li className="flex items-center">
                  <div className="w-1.5 h-1.5 bg-primary/60 rounded-full mr-2"></div>
                  Using the smart editor with @ mentions
                </li>
                <li className="flex items-center">
                  <div className="w-1.5 h-1.5 bg-primary/60 rounded-full mr-2"></div>
                  Building your story codex automatically
                </li>
                <li className="flex items-center">
                  <div className="w-1.5 h-1.5 bg-primary/60 rounded-full mr-2"></div>
                  Generating chapters with AI assistance
                </li>
                <li className="flex items-center">
                  <div className="w-1.5 h-1.5 bg-primary/60 rounded-full mr-2"></div>
                  Organizing with the outliner and folder system
                </li>
              </ul>
            </div>
          </CardContent>
        </Card>

        {/* Settings Form Section with animation */}
        <Card className="w-full max-w-2xl mx-auto overflow-hidden border-border hover:shadow-md transition-shadow animate-in fade-in-50 slide-in-from-bottom-5 duration-500 delay-350 fill-mode-both">
          <CardHeader className="border-b border-border/50 bg-muted/20">
            <CardTitle className="flex items-center gap-2">
              <svg
                className="h-5 w-5 text-primary"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2"
                />
              </svg>
              Model Settings
            </CardTitle>
            <CardDescription>
              Configure AI model settings and API keys.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="p-6">
              <SettingsForm isProUser={isProUser} />
            </div>
          </CardContent>
        </Card>

        {/* Footer with subtle separator */}
        <div className="w-full max-w-2xl mx-auto py-6 text-center text-sm text-muted-foreground">
          <div className="w-full h-px bg-border/50 relative mb-6">
            <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-background px-6">
              <Feather className="h-4 w-4 text-primary/40" />
            </div>
          </div>
          &copy; {new Date().getFullYear()} ScrollWise. All rights reserved.
        </div>
      </div>
    </div>
  );
}

"use client";

import React, { useEffect } from "react";
import { useAuth } from "@/components/MockAuthProvider";
import { useRouter } from "next/navigation"; // Use next/navigation for App Router

export default function CallbackPage() {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    // Check if authentication is successful and user data is loaded
    if (!auth.isLoading && auth.isAuthenticated && auth.user) {
      console.log("Callback: Authentication successful, user loaded.");
      // Redirect to the intended page after login (e.g., dashboard or stored path)
      // const intendedPath = sessionStorage.getItem('postLoginRedirect') || '/';
      // sessionStorage.removeItem('postLoginRedirect');
      router.push("/dashboard"); // Redirect to dashboard by default
    } else if (!auth.isLoading && auth.error) {
      // Handle authentication error
      console.error("Callback: Authentication error", auth.error);
      // Redirect to an error page or home with an error message
      router.push("/?error=auth_failed");
    } else if (!auth.isLoading && !auth.isAuthenticated) {
      // This state might occur briefly or if silent renew fails
      console.warn(
        "Callback: Not authenticated after load, redirecting to login..."
      );
      // Optionally redirect back to login or home
      router.push("/");
    }
    // Dependency array: react to changes in auth state
  }, [auth.isLoading, auth.isAuthenticated, auth.user, auth.error, router]);

  // Display a loading indicator while processing
  return (
    <div style={{ padding: "40px", textAlign: "center" }}>
      <h2>Loading session...</h2>
      {/* You can add a spinner component here */}
    </div>
  );
}

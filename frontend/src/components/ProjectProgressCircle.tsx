"use client"; // Mark this as a Client Component

import React from "react";
import { CircularProgressbar, buildStyles } from "react-circular-progressbar";
import "react-circular-progressbar/dist/styles.css";
import { Target } from "lucide-react";

interface ProjectProgressCircleProps {
  currentWords: number;
  targetWords: number;
}

// Helper function to get CSS variable value
const getCssVariable = (variableName: string): string => {
  if (typeof window === "undefined") {
    // Default fallback for SSR or environments without window
    // You might want more robust defaults based on your theme
    if (variableName === "--primary") return "oklch(0.70 0.15 85)"; // Muted Gold/Brass
    if (variableName === "--accent") return "oklch(0.40 0.03 250)"; // Medium Blue-Grey Accent
    if (variableName === "--foreground") return "oklch(0.95 0.01 90)"; // Off-white/Cream
    return "#ffffff"; // Default fallback
  }
  return getComputedStyle(document.documentElement)
    .getPropertyValue(variableName)
    .trim();
};

export function ProjectProgressCircle({
  currentWords,
  targetWords,
}: ProjectProgressCircleProps) {
  const progress =
    targetWords > 0 ? Math.min((currentWords / targetWords) * 100, 100) : 0;

  // Use state to hold computed styles to avoid recomputing on every render unnecessarily
  // and ensure it runs client-side after mount
  const [styles, setStyles] = React.useState({
    textColor: "#ffffff", // Initial default
    pathColor: "#0000ff", // Initial default
    trailColor: "#d1d5db", // Initial default
  });

  React.useEffect(() => {
    // Compute styles only on the client-side after mount
    setStyles({
      textColor: getCssVariable("--foreground"),
      pathColor: getCssVariable("--primary"),
      trailColor: getCssVariable("--accent"), // Using accent for the trail
    });
  }, []); // Empty dependency array ensures this runs once on mount

  if (targetWords <= 0) {
    return (
      // Use muted foreground color
      <div className="text-center text-muted-foreground flex flex-col items-center justify-center h-full my-4">
        {/* Use primary color for icon */}
        <Target className="h-12 w-12 mx-auto mb-4 text-primary" />
        <p>No word count target set.</p>
      </div>
    );
  }

  return (
    <>
      <div className="w-40 h-40 mb-4">
        <CircularProgressbar
          value={progress}
          text={`${Math.round(progress)}%`}
          styles={buildStyles({
            textColor: styles.textColor,
            pathColor: styles.pathColor,
            trailColor: styles.trailColor,
            textSize: "18px",
            pathTransitionDuration: 0.5,
          })}
        />
      </div>
      {/* Use theme text colors */}
      <p className="text-lg text-foreground">
        {currentWords.toLocaleString()} / {targetWords.toLocaleString()}
      </p>
      <p className="text-sm text-muted-foreground">Words Written</p>
    </>
  );
}

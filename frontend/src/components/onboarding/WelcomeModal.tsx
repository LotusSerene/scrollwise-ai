"use client";

import React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useOnboarding } from "@/contexts/OnboardingContext";
import {
  BookOpen,
  Sparkles,
  Users,
  PenTool,
  ArrowRight,
  X,
} from "lucide-react";

export function WelcomeModal() {
  const { showWelcome, startOnboarding, skipOnboarding, setShowWelcome } =
    useOnboarding();

  if (!showWelcome) return null;

  return (
    <Dialog open={showWelcome} onOpenChange={setShowWelcome}>
      <DialogContent className="sm:max-w-[600px] bg-card border-border text-card-foreground rounded-lg shadow-xl">
        {/* Decorative elements */}
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-primary/5 rounded-full blur-2xl opacity-70"></div>
        <div className="absolute top-0 left-0 w-8 h-8 border-t border-l border-primary/20"></div>
        <div className="absolute top-0 right-0 w-8 h-8 border-t border-r border-primary/20"></div>
        <div className="absolute bottom-0 right-0 w-8 h-8 border-b border-r border-primary/20"></div>
        <div className="absolute bottom-0 left-0 w-8 h-8 border-b border-l border-primary/20"></div>

        <DialogHeader className="text-center space-y-4 relative z-10">
          <div className="mx-auto w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-4">
            <BookOpen className="h-8 w-8 text-primary" />
          </div>

          <DialogTitle className="text-2xl font-bold font-display text-foreground">
            Welcome to ScrollWise! ✨
          </DialogTitle>

          <DialogDescription className="text-base text-muted-foreground max-w-md mx-auto leading-relaxed">
            Your AI-powered creative writing companion is ready to help you craft amazing stories.
            Let us show you around!
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-4 my-8 relative z-10">
          <div className="bg-accent/30 p-4 rounded-lg border border-border/50 text-center">
            <Sparkles className="h-6 w-6 text-primary mx-auto mb-2" />
            <h3 className="font-semibold text-sm mb-1">AI Generation</h3>
            <p className="text-xs text-muted-foreground">
              Generate chapters, characters, and worldbuilding elements
            </p>
          </div>

          <div className="bg-accent/30 p-4 rounded-lg border border-border/50 text-center">
            <Users className="h-6 w-6 text-primary mx-auto mb-2" />
            <h3 className="font-semibold text-sm mb-1">Smart Codex</h3>
            <p className="text-xs text-muted-foreground">
              Organize characters, locations, and lore automatically
            </p>
          </div>

          <div className="bg-accent/30 p-4 rounded-lg border border-border/50 text-center">
            <PenTool className="h-6 w-6 text-primary mx-auto mb-2" />
            <h3 className="font-semibold text-sm mb-1">Smart Editor</h3>
            <p className="text-xs text-muted-foreground">
              Write with AI assistance and @ mentions for codex entries
            </p>
          </div>

          <div className="bg-accent/30 p-4 rounded-lg border border-border/50 text-center">
            <BookOpen className="h-6 w-6 text-primary mx-auto mb-2" />
            <h3 className="font-semibold text-sm mb-1">Project Structure</h3>
            <p className="text-xs text-muted-foreground">
              Organize with folders, acts, and chapters
            </p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 pt-4 border-t border-border/50 relative z-10">
          <Button
            onClick={startOnboarding}
            className="flex-1 bg-primary text-primary-foreground hover:bg-primary/90 group"
          >
            <span className="flex items-center justify-center">
              Take the Tour
              <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
            </span>
          </Button>

          <Button
            onClick={skipOnboarding}
            variant="outline"
            className="flex-1 border-border hover:bg-accent hover:text-accent-foreground"
          >
            <span className="flex items-center justify-center">
              Skip for Now
              <X className="ml-2 h-4 w-4" />
            </span>
          </Button>
        </div>

        <p className="text-xs text-muted-foreground text-center mt-4 relative z-10">
          You can restart this tour anytime from Settings
        </p>
      </DialogContent>
    </Dialog>
  );
}

"use client";

import * as React from "react";
import { Moon, Sun, Monitor } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function ModeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="default"
          className="relative h-10 min-w-[2.5rem] px-3 border border-border rounded-lg hover:border-primary/50 transition-all duration-300 hover:shadow-sm overflow-hidden group"
        >
          <span className="sr-only">Toggle theme</span>
          <div className="flex items-center gap-2">
            {theme === "light" && (
              <>
                <Sun className="h-[1.2rem] w-[1.2rem] text-amber-500 transition-transform group-hover:rotate-45" />
                <span className="text-sm hidden md:inline-block">Light</span>
              </>
            )}
            {theme === "dark" && (
              <>
                <Moon className="h-[1.2rem] w-[1.2rem] text-indigo-400 transition-transform group-hover:scale-110" />
                <span className="text-sm hidden md:inline-block">Dark</span>
              </>
            )}
            {(theme === "system" || !theme) && (
              <>
                <Monitor className="h-[1.2rem] w-[1.2rem] text-primary transition-transform group-hover:scale-110" />
                <span className="text-sm hidden md:inline-block">System</span>
              </>
            )}
          </div>
          <div className="absolute inset-0 bg-primary/10 transform scale-x-0 group-hover:scale-x-100 origin-left transition-transform duration-300"></div>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="min-w-[8rem] rounded-lg border border-border/80 shadow-md animate-in fade-in-80 zoom-in-95 p-1"
      >
        <DropdownMenuItem
          onClick={() => setTheme("light")}
          className={`flex items-center gap-2 rounded-md transition-colors duration-200 ${
            theme === "light"
              ? "bg-accent text-accent-foreground font-medium"
              : "hover:bg-accent/80"
          }`}
        >
          <Sun className="h-4 w-4 text-amber-500" />
          <span>Light</span>
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => setTheme("dark")}
          className={`flex items-center gap-2 rounded-md transition-colors duration-200 ${
            theme === "dark"
              ? "bg-accent text-accent-foreground font-medium"
              : "hover:bg-accent/80"
          }`}
        >
          <Moon className="h-4 w-4 text-indigo-400" />
          <span>Dark</span>
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => setTheme("system")}
          className={`flex items-center gap-2 rounded-md transition-colors duration-200 ${
            theme === "system" || !theme
              ? "bg-accent text-accent-foreground font-medium"
              : "hover:bg-accent/80"
          }`}
        >
          <Monitor className="h-4 w-4 text-primary" />
          <span>System</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

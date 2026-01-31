"use client";

import React, { createContext, useContext, useState, ReactNode } from "react";

// Define the shape of the project data
interface Project {
  id: string;
  name: string;
  architect_mode_enabled: boolean;
  // Add other fields as they become necessary to share
  description?: string | null;
  universe_id?: string | null;
  target_word_count?: number | null;
}

// Define the shape of the context
interface ProjectContextType {
  project: Project | null;
  setProject: React.Dispatch<React.SetStateAction<Project | null>>;
  isLoading: boolean;
  setIsLoading: React.Dispatch<React.SetStateAction<boolean>>;
}

// Create the context with a default undefined value
const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

// Create a provider component
export const ProjectProvider = ({ children }: { children: ReactNode }) => {
  const [project, setProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  return (
    <ProjectContext.Provider
      value={{ project, setProject, isLoading, setIsLoading }}
    >
      {children}
    </ProjectContext.Provider>
  );
};

// Create a custom hook for using the context
export const useProject = () => {
  const context = useContext(ProjectContext);
  if (context === undefined) {
    throw new Error("useProject must be used within a ProjectProvider");
  }
  return context;
};

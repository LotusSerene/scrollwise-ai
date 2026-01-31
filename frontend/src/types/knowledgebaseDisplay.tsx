import React from "react";
import {
  FileText,
  BookOpenText,
  Library,
  Database,
  UploadCloud, // Icon for uploaded files
  FileQuestion, // Fallback icon
} from "lucide-react";

// Define the structure based on usage in page.tsx
export interface KnowledgeBaseItemDisplay {
  id: string; // Unique ID from its database table
  db_table: string; // e.g., "chapters", "codex_items", "knowledge_base_items"
  name: string; // Display name or title
  type: string; // e.g., "chapter", "character", "manual_text", "uploaded_file"
  content?: string | null; // Text content snippet
  metadata?: Record<string, unknown> | null; // Metadata object
  created_at?: string | null; // ISO date string
  embedding_id?: string | null; // ID from the vector store
}

// Basic function to get an icon based on the item type or source table
export const getItemIcon = (item: KnowledgeBaseItemDisplay) => {
  const className = "h-5 w-5 text-primary/80 flex-shrink-0";

  if (item.db_table === "chapters") {
    return <BookOpenText className={className} aria-label="Chapter" />;
  }
  if (item.db_table === "codex_items") {
    return <Library className={className} aria-label="Codex Item" />;
  }
  if (item.db_table === "knowledge_base_items") {
    if (item.type === "manual_text") {
      return <FileText className={className} aria-label="Manual Entry" />;
    }
    if (item.type === "uploaded_file") {
      return <UploadCloud className={className} aria-label="Uploaded File" />;
    }
    return <Database className={className} aria-label="Knowledge Base Item" />;
  }

  // Fallback icon
  return <FileQuestion className={className} aria-label="Unknown Item" />;
};

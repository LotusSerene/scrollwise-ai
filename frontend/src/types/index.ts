// Shared type definitions for the frontend

// Based on backend/models.py:CodexItemType, excluding types user specified as separate
export enum CodexItemType {
  CHARACTER = "character",
  WORLDBUILDING = "worldbuilding",
  ITEM = "item",
  LORE = "lore",
  FACTION = "faction",
  LOCATION = "location",
  EVENT = "event",
  RELATIONSHIP = "relationship",
  BACKSTORY = "character_backstory",
}

// Based on backend/models.py:WorldbuildingSubtype
export enum WorldbuildingSubtype {
  HISTORY = "history",
  CULTURE = "culture",
  GEOGRAPHY = "geography",
  OTHER = "other",
}

// --- Add CharacterVoiceProfileData ---
export interface CharacterVoiceProfileData {
  vocabulary?: string;
  sentence_structure?: string;
  speech_patterns_tics?: string;
  tone?: string;
  habits_mannerisms?: string;
}
// --- End CharacterVoiceProfileData ---

// Updated CodexEntry interface
export interface CodexEntry {
  id: string;
  title: string; // Keep title for display? Or rename to name?
  name: string; // Add name to align with backend create model
  type: CodexItemType;
  subtype?: WorldbuildingSubtype | string | null; // Allow string for flexibility if backend adds more, or null
  tags?: string[];
  content?: string; // For description
  description: string; // Add description to align with backend create model
  backstory?: string | null; // Add backstory, explicitly allowing null
  voice_profile?: CharacterVoiceProfileData | null; // Add voice_profile
  // Add other relevant fields: created_at, updated_at, etc. if needed
  user_id?: string; // Optional: if needed for any client-side logic
  project_id?: string; // Optional: if needed for any client-side logic
  created_at?: string; // Optional: store as ISO string
  updated_at?: string; // Optional: store as ISO string
  embedding_id?: string | null; // Optional
}

// You can add other shared interfaces here, e.g., Project, Chapter
export interface Project {
  id: string;
  name: string;
  target_word_count?: number;
  current_word_count?: number;
  // Add other needed fields
}

export interface Chapter {
  id: string;
  title: string;
  content?: string; // Content might be fetched separately
  chapter_number?: number;
  word_count?: number;
  // Add other fields if needed
}

// Character Relationship Type
export interface Relationship {
  id: string;
  character_id: string; // ID of the first character
  related_character_id: string; // ID of the second character
  relationship_type: string;
  description?: string;
  // Add other potential fields from backend like created_at, project_id etc. if needed
}

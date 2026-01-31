from pydantic import BaseModel, Field, EmailStr, model_validator
from typing import List, Dict, Optional, Any, Union, Literal
from enum import Enum
from datetime import datetime


class CodexItemType(str, Enum):
    CHARACTER = "character"
    WORLDBUILDING = "worldbuilding"
    ITEM = "item"
    LORE = "lore"
    FACTION = "faction"
    LOCATION = "location"
    EVENT = "event"
    RELATIONSHIP = "relationship"
    BACKSTORY = "character_backstory"


class CodexExtractionTypes(str, Enum):
    CHARACTER = "character"
    WORLDBUILDING = "worldbuilding"
    ITEM = "item"
    LORE = "lore"
    FACTION = "faction"


class WorldbuildingSubtype(str, Enum):
    HISTORY = "history"
    CULTURE = "culture"
    GEOGRAPHY = "geography"
    OTHER = "other"


# For API responses, to include DB fields like id, created_at, etc.
class CharacterVoiceProfileBase(BaseModel):
    vocabulary: Optional[str] = None
    sentence_structure: Optional[str] = None
    speech_patterns_tics: Optional[str] = None
    tone: Optional[str] = None
    habits_mannerisms: Optional[str] = None


class CharacterVoiceProfileData(CharacterVoiceProfileBase):
    pass  # Used for create/update in API request


class CharacterVoiceProfileResponse(CharacterVoiceProfileBase):
    id: str
    codex_item_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class CodexItemBase(BaseModel):
    name: str = Field(description="Name of the codex item")
    description: str = Field(description="Description of the codex item")
    type: CodexItemType = Field(description="Type of codex item")
    subtype: Optional[WorldbuildingSubtype] = Field(
        None, description="Subtype for worldbuilding items"
    )
    backstory: Optional[str] = None  # Added for characters


# Pydantic model for API responses (including fields from DB like id, created_at)
class CodexItemResponse(CodexItemBase):
    id: str
    user_id: str
    project_id: str
    embedding_id: Optional[str] = None
    created_at: Optional[datetime] = (
        None  # Assuming datetime will be imported or use str
    )
    updated_at: Optional[datetime] = (
        None  # Assuming datetime will be imported or use str
    )
    voice_profile: Optional[CharacterVoiceProfileResponse] = None
    model_config = {"from_attributes": True}  # To create from SQLAlchemy model


class CodexItemCreate(CodexItemBase):
    voice_profile: Optional[CharacterVoiceProfileData] = None


class CodexItemUpdate(CodexItemBase):
    name: Optional[str] = None  # Make fields optional for update
    description: Optional[str] = None
    type: Optional[CodexItemType] = None
    subtype: Optional[WorldbuildingSubtype] = None
    backstory: Optional[str] = None
    voice_profile: Optional[CharacterVoiceProfileData] = None


class CriterionScore(BaseModel):
    score: int = Field(..., ge=1, le=10, description="Score for the criterion (1-10)")
    explanation: str = Field(..., description="Brief explanation for the score")


class ChapterValidation(BaseModel):
    is_valid: bool = Field(..., description="Whether the chapter is valid overall")
    overall_score: int = Field(
        ..., ge=0, le=10, description="Overall score of the chapter"
    )
    criteria_scores: Dict[str, CriterionScore] = Field(
        ..., description="Scores and feedback for each evaluation criterion"
    )
    style_guide_adherence: CriterionScore = Field(
        ..., description="Score and feedback for style guide adherence"
    )
    continuity: CriterionScore = Field(
        ..., description="Score and feedback for continuity with previous chapters"
    )
    areas_for_improvement: List[str] = Field(
        ..., description="List of areas that need improvement"
    )
    general_feedback: str = Field(..., description="Overall feedback on the chapter")


class RelationshipAnalysis(BaseModel):
    character1: str = Field(
        ..., description="Name of the first character in the relationship"
    )
    character2: str = Field(
        ..., description="Name of the second character in the relationship"
    )
    relationship_type: str = Field(
        ..., description="Type of relationship between the characters"
    )
    description: str = Field(
        ..., description="Description of the relationship dynamics"
    )


class RelationshipAnalysisList(BaseModel):
    relationships: List[RelationshipAnalysis] = Field(default_factory=list)

    def deduplicate_relationships(self) -> "RelationshipAnalysisList":
        seen = set()
        unique_relationships = []
        for rel in self.relationships:
            pair = tuple(sorted([rel.character1, rel.character2]))
            if pair not in seen:
                seen.add(pair)
                unique_relationships.append(rel)
        return RelationshipAnalysisList(relationships=unique_relationships)


class EventDescription(BaseModel):
    title: str = Field(..., description="Title of the event")
    description: str = Field(..., description="Description of what happened")
    impact: str = Field(..., description="Impact of the event on the story/characters")
    involved_characters: List[str] = Field(
        default_factory=list, description="Characters involved in the event"
    )
    location: Optional[str] = Field(
        None, description="Location where the event took place"
    )


class EventAnalysis(BaseModel):
    events: List[EventDescription] = Field(default_factory=list)


class LocationConnection(BaseModel):
    location1_id: str
    location2_id: str
    location1_name: str
    location2_name: str
    connection_type: str = Field(
        ..., description="Type of connection between locations"
    )
    description: str = Field(
        ..., description="Description of how the locations are connected"
    )
    travel_route: Optional[str] = Field(
        None, description="Description of travel route between locations"
    )
    cultural_exchange: Optional[str] = Field(
        None, description="Description of cultural exchange between locations"
    )


class LocationConnectionAnalysis(BaseModel):
    connections: List[LocationConnection] = Field(default_factory=list)

    def deduplicate_connections(self) -> "LocationConnectionAnalysis":
        seen = set()
        unique_connections = []
        for conn in self.connections:
            pair = tuple(sorted([conn.location1_id, conn.location2_id]))
            if pair not in seen:
                seen.add(pair)
                unique_connections.append(conn)
        return LocationConnectionAnalysis(connections=unique_connections)


class LocationAnalysis(BaseModel):
    name: str = Field(..., description="Name of the location")
    significance_analysis: str = Field(
        ..., description="Analysis of the location's significance"
    )
    connected_locations: List[str] = Field(
        default_factory=list, description="Names of connected locations"
    )
    notable_events: List[str] = Field(
        default_factory=list, description="Notable events that occurred here"
    )
    character_associations: List[str] = Field(
        default_factory=list, description="Characters associated with this location"
    )


class LocationAnalysisList(BaseModel):
    locations: List[LocationAnalysis] = Field(default_factory=list)


# Renamed from EventConnection to avoid conflict with SQLAlchemy model
class EventConnectionBase(BaseModel):
    id: Optional[str] = None
    event1_id: str
    event2_id: str
    connection_type: str = Field(..., description="Type of connection between events")
    description: str = Field(
        ..., description="Description of how the events are connected"
    )
    impact: str = Field(..., description="Impact or significance of this connection")
    characters_involved: Optional[str] = Field(
        None, description="Characters involved in connecting the events"
    )
    location_relation: Optional[str] = Field(
        None, description="Spatial relationship between events"
    )


class EventConnectionAnalysis(BaseModel):
    connections: List[EventConnectionBase] = Field(default_factory=list)

    def deduplicate_connections(self) -> "EventConnectionAnalysis":
        seen = set()
        unique_connections = []
        for conn in self.connections:
            pair = tuple(sorted([conn.event1_id, conn.event2_id]))
            if pair not in seen:
                seen.add(pair)
                unique_connections.append(conn)
        return EventConnectionAnalysis(connections=unique_connections)


class EventConnectionCreate(BaseModel):
    event1_id: str
    event2_id: str
    connection_type: str
    description: str
    impact: str


class EventConnectionUpdate(BaseModel):
    connection_type: str
    description: str
    impact: str


class UserCreate(BaseModel):
    email: EmailStr
    id: str

    class Config:
        from_attributes = True


class ChapterCreate(BaseModel):
    title: str = Field(..., example="The Beginning")
    content: Optional[str] = Field(None, example="It was a dark and stormy night...")
    structure_item_id: Optional[str] = Field(None, example="act-1-stage-1")
    append_to_structure: bool = Field(
        False, description="Append chapter to the root of the project structure"
    )

    class Config:
        extra = "allow"


class ChapterUpdate(BaseModel):
    title: Optional[str] = None  # Made title optional for updates
    content: Optional[str] = None  # Made content optional for updates
    structure_item_id: Optional[str] = None  # Optional link to project structure


class ChapterBase(BaseModel):
    title: str
    content: Optional[str] = None
    chapter_number: Optional[int] = None
    structure_item_id: Optional[str] = None


class ChapterResponse(ChapterBase):
    id: str
    project_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ModelSettings(BaseModel):
    mainLLM: str
    checkLLM: str
    embeddingsModel: str
    titleGenerationLLM: str
    extractionLLM: str
    knowledgeBaseQueryLLM: str
    temperature: float


class ApiKeyUpdate(BaseModel):
    apiKey: str


class KnowledgeBaseQuery(BaseModel):
    query: str
    chatHistory: List[Dict[str, str]]


class ChatHistoryItem(BaseModel):
    type: str
    content: str

    model_config = {"extra": "allow"}  # Allow extra fields like 'role'

    @model_validator(mode="before")
    @classmethod
    def convert_role_to_type(cls, data):
        if isinstance(data, dict) and "role" in data and "type" not in data:
            data["type"] = data["role"]
        return data


class ChatHistoryRequest(BaseModel):
    chatHistory: List[ChatHistoryItem]


class ChapterGenerationRequest(BaseModel):
    numChapters: int
    plot: str
    writingStyle: str
    instructions: Dict[str, Any]


class PresetCreate(BaseModel):
    name: str
    data: Dict[str, Any]


class PresetUpdate(BaseModel):
    name: str
    data: ChapterGenerationRequest


class GenerationHistoryEntry(BaseModel):
    id: str
    project_id: str
    user_id: str
    timestamp: datetime
    num_chapters: int
    word_count: Optional[int] = None
    plot: str
    writing_style: str
    instructions: Dict[str, Any]

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    universe_id: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    universe_id: Optional[str] = None
    target_word_count: Optional[int] = None


class UniverseCreate(BaseModel):
    name: str


class UniverseUpdate(BaseModel):
    name: str


class UpdateTargetWordCountRequest(BaseModel):
    targetWordCount: int


class BackstoryExtractionRequest(BaseModel):
    character_id: str
    chapter_id: str


class CodexItemGenerateRequest(BaseModel):
    codex_type: str
    subtype: Optional[str] = None
    description: str = Field(..., description="Description to base the codex item on")


class CodexExtraction(BaseModel):
    new_items: List[CodexItemCreate] = Field(
        default_factory=list,
        description="List of newly extracted codex items, using the creation schema.",
    )


class RelationshipUpdate(BaseModel):
    relationship_type: str = Field(..., description="The type of the relationship.")
    description: Optional[str] = Field(
        None, description="Optional description of the relationship."
    )


class LocationConnectionCreate(BaseModel):
    location1_id: str
    location2_id: str
    connection_type: str
    description: str
    travel_route: Optional[str] = None
    cultural_exchange: Optional[str] = None


class GenerationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GenerationStatusResponse(BaseModel):
    status: GenerationStatus
    message: Optional[str] = None
    current_step: Optional[str] = None
    total_steps: Optional[int] = None
    progress_percent: Optional[float] = None
    result_url: Optional[str] = None  # URL to download generated chapter/content
    error_details: Optional[str] = None  # Added for detailed errors


# --- Architect Feature Models ---


class ArchitectChatRequest(BaseModel):
    message: str
    # Optional: Add chat_history if we want to pass it from client,
    # but ArchitectAgent currently loads it from DB
    # chat_history: Optional[List[Dict[str, str]]] = None


class ArchitectChatResponse(BaseModel):
    response: str
    tool_calls: Optional[List[Dict[str, Any]]] = None  # For potential future use


# --- Settings Models ---


class ApiKeyUpdate(BaseModel):
    apiKey: str


# Add new models here
class StructureItemModel(BaseModel):
    id: str
    name: str
    type: Literal[
        "act", "stage", "substage", "folder", "chapter"
    ]  # Added "folder" and "chapter" types
    description: Optional[str] = None
    title: Optional[str] = None  # Added to match frontend expectations
    children: List["StructureItemModel"] = []  # Default to empty list


StructureItemModel.model_rebuild()  # Resolve forward reference for recursive children


# Define a base response model (later we'll use the more specific version)
class ProjectStructureUpdateRequest(BaseModel):
    project_structure: List[StructureItemModel]


class ProactiveSuggestion(BaseModel):
    suggestion: str = Field(description="The suggestion for improving the text.")
    confidence: float = Field(description="The confidence score for the suggestion.")


class ProactiveSuggestionsResponse(BaseModel):
    suggestions: List[ProactiveSuggestion]


class ProactiveAssistRequest(BaseModel):
    recent_chapters_content: str
    notepad_content: str


class TextActionRequest(BaseModel):
    action: str = Field(..., description="The action to perform: 'revise', 'extend', or 'custom'.")
    selected_text: str = Field(..., description="The text selected by the user in the editor.")
    full_chapter_content: str = Field(..., description="The full content of the chapter for context.")
    custom_prompt: Optional[str] = Field(None, description="The custom prompt provided by the user for the 'custom' action.")


class StructureChapterItem(BaseModel):
    id: str
    type: str = "chapter"
    title: str


class StructureFolderItem(BaseModel):
    id: str
    type: str = "folder"
    title: str
    description: Optional[str] = None
    children: List[Union["StructureFolderItem", StructureChapterItem]]


# This is needed for Pydantic to handle the recursive self-reference in StructureFolderItem
StructureFolderItem.model_rebuild()


class ProjectStructureResponse(BaseModel):
    project_structure: List[Union[StructureFolderItem, StructureChapterItem]]

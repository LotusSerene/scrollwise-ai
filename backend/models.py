from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Optional, Any
from enum import Enum


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


class CodexItem(BaseModel):
    name: str = Field(description="Name of the codex item")
    description: str = Field(description="Description of the codex item")
    type: CodexItemType = Field(description="Type of codex item")
    subtype: Optional[WorldbuildingSubtype] = Field(
        None, description="Subtype for worldbuilding items"
    )


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


class CharacterBackstoryExtraction(BaseModel):
    character_id: str = Field(
        ..., description="ID of the character whose backstory is being extracted"
    )
    new_backstory: str = Field(
        ..., description="New backstory content extracted from the chapter"
    )


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


class EventConnection(BaseModel):
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
    connections: List[EventConnection] = Field(default_factory=list)

    def deduplicate_connections(self) -> "EventConnectionAnalysis":
        seen = set()
        unique_connections = []
        for conn in self.connections:
            pair = tuple(sorted([conn.event1_id, conn.event2_id]))
            if pair not in seen:
                seen.add(pair)
                unique_connections.append(conn)
        return EventConnectionAnalysis(connections=unique_connections)


class UserCreate(BaseModel):
    email: EmailStr

    class Config:
        from_attributes = True


class ChapterCreate(BaseModel):
    title: str
    content: str


class ChapterUpdate(BaseModel):
    title: str
    content: str


class CodexItemCreate(BaseModel):
    name: str
    description: str
    type: str
    subtype: Optional[str] = None


class CodexItemUpdate(BaseModel):
    name: str
    description: str
    type: str
    subtype: Optional[str] = None


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
    project_id: str


class PresetUpdate(BaseModel):
    name: str
    data: ChapterGenerationRequest


class ProjectCreate(BaseModel):
    name: str
    description: str
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

from pydantic import BaseModel, Field
from typing import List, Dict, Optional
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
    subtype: Optional[WorldbuildingSubtype] = Field(None, description="Subtype for worldbuilding items")

class CriterionScore(BaseModel):
    score: int = Field(..., ge=1, le=10, description="Score for the criterion (1-10)")
    explanation: str = Field(..., description="Brief explanation for the score")

class ChapterValidation(BaseModel):
    is_valid: bool = Field(..., description="Whether the chapter is valid overall")
    overall_score: int = Field(..., ge=0, le=10, description="Overall score of the chapter")
    criteria_scores: Dict[str, CriterionScore] = Field(..., description="Scores and feedback for each evaluation criterion")
    style_guide_adherence: CriterionScore = Field(..., description="Score and feedback for style guide adherence")
    continuity: CriterionScore = Field(..., description="Score and feedback for continuity with previous chapters")
    areas_for_improvement: List[str] = Field(..., description="List of areas that need improvement")
    general_feedback: str = Field(..., description="Overall feedback on the chapter")



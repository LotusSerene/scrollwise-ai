from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class CodexItem(BaseModel):
    name: str = Field(description="Name of the codex item")
    description: str = Field(description="Description of the codex item")
    type: str = Field(description="Type of codex item")
    subtype: Optional[str] = Field(None, description="Subtype of codex item")

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

# Add other model classes as needed...

import logging
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    DateTime,
    Text,
    JSON,
    UniqueConstraint,
    and_,
    func,
    select,
    delete,
    or_,
    Index,
    update,
    text,
    UUID,
    PickleType,
)
# JSONB is specific to PostgreSQL, use standard JSON for SQLite
JSONB = JSON 
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Use sqlalchemy.orm.declarative_base directly
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    joinedload,
    selectinload,
    aliased,
)
from datetime import datetime, timezone
import json
import os
from dotenv import load_dotenv
import uuid
from typing import Optional, List, Dict, Any
from models import CodexItemType
from enum import Enum
from models import (
    ProjectStructureUpdateRequest,
)  # Add ProjectStructureUpdateRequest
from pydantic import ValidationError  # Add ValidationError
import copy

load_dotenv()

logger = logging.getLogger(__name__)

Base = declarative_base()


# Define Enum for Agent Type
class AgentType(Enum):
    STANDARD = "standard"  # Or perhaps 'query_agent'
    ARCHITECT = "architect"


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True) # "local" or a unique identifier
    email = Column(String, unique=True, index=True, nullable=False)
    api_key = Column(String)  # Encrypted API key
    openrouter_api_key = Column(String)  # Encrypted OpenRouter API Key
    anthropic_api_key = Column(String)  # Encrypted Anthropic API Key
    openai_api_key = Column(String)  # Encrypted OpenAI API Key
    model_settings = Column(JSON, nullable=True)  # Store model preferences as JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    subscription_plan = Column(
        String, nullable=False, default="pro", index=True # Default to pro for local
    )
    subscription_status = Column(
        String, nullable=False, default="active", index=True
    )
    has_completed_onboarding = Column(
        Boolean, nullable=False, default=True, server_default="true" # Skip by default
    )

    projects = relationship(
        "Project", back_populates="user", cascade="all, delete-orphan"
    )

    def to_dict(self):
        """Converts User object to dictionary."""
        return {
            "id": self.id,
            "email": self.email,
            "model_settings": self.model_settings,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "subscription_plan": self.subscription_plan,
            "subscription_status": self.subscription_status,
            "has_completed_onboarding": self.has_completed_onboarding,
        }


class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    universe_id = Column(String, ForeignKey("universes.id"), nullable=True)
    target_word_count = Column(Integer, default=0)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    architect_mode_enabled = Column(Boolean, default=False, nullable=False)
    project_structure = Column(JSONB, nullable=True)  # New field for acts/stages
    # Add the user relationship
    user = relationship("User", back_populates="projects")
    # Add the universe relationship
    universe = relationship("Universe", back_populates="projects")

    # Update relationships to include cascade deletes
    chapters = relationship(
        "Chapter", back_populates="project", cascade="all, delete-orphan"
    )
    validity_checks = relationship(
        "ValidityCheck", back_populates="project", cascade="all, delete-orphan"
    )
    codex_items = relationship(
        "CodexItem", back_populates="project", cascade="all, delete-orphan"
    )
    chat_histories = relationship(
        "ChatHistory", back_populates="project", cascade="all, delete-orphan"
    )
    presets = relationship(
        "Preset", back_populates="project", cascade="all, delete-orphan"
    )
    generation_history = relationship(
        "GenerationHistory", back_populates="project", cascade="all, delete-orphan"
    )
    events = relationship(
        "Event", back_populates="project", cascade="all, delete-orphan"
    )
    locations = relationship(
        "Location", back_populates="project", cascade="all, delete-orphan"
    )
    character_relationships = relationship(
        "CharacterRelationship", back_populates="project", cascade="all, delete-orphan"
    )
    character_relationship_analyses = relationship(
        "CharacterRelationshipAnalysis",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    event_connections = relationship(
        "EventConnection", back_populates="project", cascade="all, delete-orphan"
    )
    location_connections = relationship(
        "LocationConnection", back_populates="project", cascade="all, delete-orphan"
    )

    def to_dict(self):
        base_dict = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "universe_id": self.universe_id,
            "user_id": self.user_id,
            "target_word_count": self.target_word_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "architect_mode_enabled": self.architect_mode_enabled,
            "project_structure": self.project_structure,  # ADDED THIS LINE
        }
        return base_dict


class Chapter(Base):
    __tablename__ = "chapters"
    id = Column(String, primary_key=True)
    title = Column(String(500))  # Increase the length limit to 500
    content = Column(Text)  # Text type for long content
    chapter_number = Column(Integer, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    embedding_id = Column(String)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    last_processed_position = Column(Integer, default=0)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    project = relationship("Project", back_populates="chapters")
    processed_types = Column(
        JSON, default=list, nullable=False
    )  # Initialize as empty list
    structure_item_id = Column(
        String, nullable=True
    )  # New field for linking to project_structure
    validity_checks = relationship(
        "ValidityCheck", back_populates="chapter", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "chapter_number": self.chapter_number,
            "embedding_id": self.embedding_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ValidityCheck(Base):
    __tablename__ = "validity_checks"
    id = Column(String, primary_key=True)
    chapter_id = Column(String, ForeignKey("chapters.id"), nullable=False)
    chapter_title = Column(String)
    is_valid = Column(Boolean)
    overall_score = Column(Integer)
    general_feedback = Column(Text)
    style_guide_adherence_score = Column(Integer)
    style_guide_adherence_explanation = Column(Text)
    continuity_score = Column(Integer)
    continuity_explanation = Column(Text)
    areas_for_improvement = Column(JSON)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Add the relationship definition
    project = relationship("Project", back_populates="validity_checks")
    chapter = relationship("Chapter", back_populates="validity_checks")

    def to_dict(self):
        return {
            "id": self.id,
            "chapterId": self.chapter_id,
            "chapterTitle": self.chapter_title,
            "isValid": self.is_valid,
            "overallScore": self.overall_score,
            "generalFeedback": self.general_feedback,
            "styleGuideAdherenceScore": self.style_guide_adherence_score,
            "styleGuideAdherenceExplanation": self.style_guide_adherence_explanation,
            "continuityScore": self.continuity_score,
            "continuityExplanation": self.continuity_explanation,
            "areasForImprovement": self.areas_for_improvement,
        }


class CodexItem(Base):
    __tablename__ = "codex_items"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    type = Column(String, nullable=False)  # Will store the enum value as string
    subtype = Column(String)  # Will store the enum value as string
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    embedding_id = Column(String)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    # Add these fields for character-specific information
    backstory = Column(Text)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Add these relationships
    relationships = relationship(
        "CharacterRelationship",
        foreign_keys="CharacterRelationship.character_id",
        back_populates="character",
    )
    related_to = relationship(
        "CharacterRelationship",
        foreign_keys="CharacterRelationship.related_character_id",
        back_populates="related_character",
    )
    events = relationship("Event", back_populates="character")
    project = relationship("Project", back_populates="codex_items")
    voice_profile = relationship(
        "CharacterVoiceProfile",
        back_populates="codex_item",
        uselist=False,  # For a one-to-one relationship
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        base_data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.type,  # This will be the string value of the enum
            "subtype": self.subtype,
            "user_id": self.user_id,  # Added user_id
            "project_id": self.project_id,  # Added project_id
            "backstory": (
                self.backstory if self.type == CodexItemType.CHARACTER.value else None
            ),
            "embedding_id": self.embedding_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "voice_profile": (
                self.voice_profile.to_dict() if self.voice_profile else None
            ),
        }
        return base_data


class CharacterVoiceProfile(Base):
    __tablename__ = "character_voice_profiles"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    codex_item_id = Column(
        String,
        ForeignKey("codex_items.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)

    vocabulary = Column(Text, nullable=True)
    sentence_structure = Column(Text, nullable=True)
    speech_patterns_tics = Column(Text, nullable=True)
    tone = Column(Text, nullable=True)
    habits_mannerisms = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    codex_item = relationship("CodexItem", back_populates="voice_profile")

    def to_dict(self):
        return {
            "id": self.id,
            "codex_item_id": self.codex_item_id,
            "vocabulary": self.vocabulary,
            "sentence_structure": self.sentence_structure,
            "speech_patterns_tics": self.speech_patterns_tics,
            "tone": self.tone,
            "habits_mannerisms": self.habits_mannerisms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    project_id = Column(
        String, ForeignKey("projects.id"), nullable=False
    )  # Changed to String
    messages = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    agent_type = Column(
        String, default=AgentType.STANDARD.value, nullable=False, index=True
    )

    # Ensure indexes if needed
    __table_args__ = (
        Index(
            "ix_chat_history_user_project_agent", "user_id", "project_id", "agent_type"
        ),
    )

    project = relationship("Project", back_populates="chat_histories")


class Preset(Base):
    __tablename__ = "presets"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    data = Column(JSON, nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "name", name="_user_preset_uc"),)
    project = relationship("Project", back_populates="presets")


class GenerationHistory(Base):
    __tablename__ = "generation_history"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    num_chapters = Column(Integer, nullable=False)
    word_count = Column(Integer, nullable=True)
    plot = Column(Text, nullable=False)
    writing_style = Column(Text, nullable=False)
    instructions = Column(JSON, nullable=False)

    project = relationship("Project", back_populates="generation_history")

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "num_chapters": self.num_chapters,
            "word_count": self.word_count,
            "plot": self.plot,
            "writing_style": self.writing_style,
            "instructions": self.instructions,
        }


class Universe(Base):
    __tablename__ = "universes"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    # Add relationship to projects
    projects = relationship(
        "Project", back_populates="universe", cascade="all, delete-orphan"
    )


class ProcessedChapter(Base):
    __tablename__ = "processed_chapters"
    id = Column(String, primary_key=True)
    chapter_id = Column(String, ForeignKey("chapters.id"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    processed_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    function_name = Column(String, default="default_function_name", nullable=False)


class CharacterRelationship(Base):
    __tablename__ = "character_relationships"
    id = Column(String, primary_key=True)
    character_id = Column(String, ForeignKey("codex_items.id"), nullable=False)
    related_character_id = Column(String, ForeignKey("codex_items.id"), nullable=False)
    relationship_type = Column(String, nullable=False)
    description = Column(Text, nullable=True)  # Add this line
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)

    # Update these relationship definitions
    character = relationship(
        "CodexItem", foreign_keys=[character_id], back_populates="relationships"
    )
    related_character = relationship(
        "CodexItem", foreign_keys=[related_character_id], back_populates="related_to"
    )
    project = relationship("Project", back_populates="character_relationships")

    def to_dict(self):
        return {
            "id": self.id,
            "character_id": self.character_id,
            "related_character_id": self.related_character_id,
            "relationship_type": self.relationship_type,
            "description": self.description or "",  # Add this line
        }


class Event(Base):
    __tablename__ = "events"
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)  # Make timezone-aware
    character_id = Column(String, ForeignKey("codex_items.id"), nullable=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)  # Added this line
    location_id = Column(String, ForeignKey("locations.id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    character = relationship("CodexItem", back_populates="events")
    location = relationship("Location", back_populates="events")
    project = relationship("Project", back_populates="events")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "date": self.date.isoformat(),
            "character_id": self.character_id,
            "location_id": self.location_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Location(Base):
    __tablename__ = "locations"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    coordinates = Column(String, nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    events = relationship(
        "Event", back_populates="location", cascade="all, delete-orphan"
    )
    project = relationship("Project", back_populates="locations")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "coordinates": self.coordinates,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CharacterRelationshipAnalysis(Base):
    __tablename__ = "character_relationship_analyses"
    id = Column(String, primary_key=True)
    character1_id = Column(String, ForeignKey("codex_items.id"), nullable=False)
    character2_id = Column(String, ForeignKey("codex_items.id"), nullable=False)
    relationship_type = Column(String, nullable=False)
    description = Column(Text)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),  # Add default for updated_at
        onupdate=lambda: datetime.now(timezone.utc),
    )

    project = relationship("Project", back_populates="character_relationship_analyses")

    def to_dict(self):
        return {
            "id": self.id,
            "character1_id": self.character1_id,
            "character2_id": self.character2_id,
            "relationship_type": self.relationship_type,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class BaseConnection(Base):
    __abstract__ = True

    id = Column(String, primary_key=True)
    description = Column(Text, nullable=False)
    connection_type = Column(String, nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "connection_type": self.connection_type,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class EventConnection(BaseConnection):
    __tablename__ = "event_connections"

    event1_id = Column(String, ForeignKey("events.id"), nullable=False)
    event2_id = Column(String, ForeignKey("events.id"), nullable=False)
    impact = Column(Text)

    event1 = relationship("Event", foreign_keys=[event1_id])
    event2 = relationship("Event", foreign_keys=[event2_id])
    project = relationship("Project", back_populates="event_connections")

    def to_dict(self):
        result = super().to_dict()
        result.update(
            {
                "event1_id": self.event1_id,
                "event2_id": self.event2_id,
                "impact": self.impact,
            }
        )
        return result


class LocationConnection(BaseConnection):
    __tablename__ = "location_connections"

    location1_id = Column(String, ForeignKey("locations.id"), nullable=False)
    location2_id = Column(String, ForeignKey("locations.id"), nullable=False)
    travel_route = Column(Text)
    cultural_exchange = Column(Text)

    # Add these new columns
    location1_name = Column(String, nullable=False)
    location2_name = Column(String, nullable=False)

    location1 = relationship("Location", foreign_keys=[location1_id])
    location2 = relationship("Location", foreign_keys=[location2_id])
    project = relationship("Project", back_populates="location_connections")

    def to_dict(self):
        result = super().to_dict()
        result.update(
            {
                "location1_id": self.location1_id,
                "location2_id": self.location2_id,
                "location1_name": self.location1_name,
                "location2_name": self.location2_name,
                "travel_route": self.travel_route,
                "cultural_exchange": self.cultural_exchange,
            }
        )
        return result

    async def get_connections(
        self, model_class, project_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        try:
            query = (
                select(model_class)
                .filter_by(project_id=project_id, user_id=user_id)
                .options(
                    joinedload(
                        model_class.location1
                        if hasattr(model_class, "location1")
                        else model_class.event1
                    ),
                    joinedload(
                        model_class.location2
                        if hasattr(model_class, "location2")
                        else model_class.event2
                    ),
                )
            )

            # Fix: Store the query result in the connections variable
            async with db_instance.Session() as session:
                connections = await session.execute(query)
                connections = connections.unique().scalars().all()

            result = []
            for conn in connections:
                connection_dict = conn.to_dict()

                # Add related entity names based on connection type
                if isinstance(conn, EventConnection):
                    if conn.event1 and conn.event2:
                        connection_dict.update(
                            {
                                "event1_title": conn.event1.title,
                                "event2_title": conn.event2.title,
                            }
                        )
                elif isinstance(conn, LocationConnection):
                    if conn.location1 and conn.location2:
                        connection_dict.update(
                            {
                                "location1_name": conn.location1.name,
                                "location2_name": conn.location2.name,
                            }
                        )

                result.append(connection_dict)

            return result

        except Exception as e:
            logger.error(f"Error getting connections: {str(e)}")
            raise


class KnowledgeBaseItem(Base):
    __tablename__ = "knowledge_base_items"
    __table_args__ = (
        UniqueConstraint("embedding_id", "project_id", name="uq_embedding_project"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    project_id = Column(String, nullable=False)
    type = Column(
        String, nullable=False
    )  # e.g., 'manual_text', 'uploaded_file', 'chapter'
    content = Column(
        Text, nullable=True
    )  # Full content for 'manual_text', null otherwise
    item_metadata = Column(JSONB, nullable=True)  # Renamed from metadata
    source = Column(
        String, nullable=True
    )  # e.g., filename, 'manual_entry', chapter_title
    embedding_id = Column(
        String, nullable=True
    )  # ID from vector store, now often matches id
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Basic indexes
    Index("ix_kb_item_user_project", user_id, project_id)
    Index("ix_kb_item_type", type)


class Database:
    def __init__(self):
        try:
            self.logger = logging.getLogger(__name__)
            # SQLite connection for local use
            db_path = "./scrollwise.db"
            db_url = f"sqlite+aiosqlite:///{db_path}"

            self.engine = create_async_engine(
                db_url,
                echo=False,
                # SQLite doesn't support the same pool args as Postgres
            )

            # Create async session maker
            self.Session = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
        except Exception as e:
            logger.error("Error initializing Database", exc_info=True)
            raise

    async def __aenter__(self):
        """Support for async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensure proper cleanup when using as context manager."""
        await self.dispose()

    async def dispose(self):
        """Dispose of the engine and close all connections."""
        if hasattr(self, "engine"):
            await self.engine.dispose()
            logger.info("Database connections disposed")

    async def initialize(self):
        """Initialize the database connection and create all tables."""
        try:
            async with self.engine.begin() as conn:
                # Create all tables
                await conn.run_sync(Base.metadata.create_all)

            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error("Error initializing database", exc_info=True)
            raise

    async def get_projects(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Project).where(Project.user_id == user_id)
                result = await session.execute(query)
                projects = result.scalars().all()
                return [project.to_dict() for project in projects]
        except Exception as e:
            logger.error("Error getting projects", exc_info=True)
            raise

    async def get_universes(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Universe).where(Universe.user_id == user_id)
                result = await session.execute(query)
                universes = result.scalars().all()
                return [universe.to_dict() for universe in universes]
        except Exception as e:
            logger.error(f"Error getting universes: {str(e)}")
            raise

    # Removed sign_up, sign_in, sign_out methods (handled by Cognito)

    async def get_or_create_user(
        self, user_id: str, email: str
    ) -> Dict[str, Any]:
        """
        Local version: Retrieves a user by ID or creates one if not found.
        """
        try:
            async with self.Session() as session:
                get_user_query = select(User).where(User.id == user_id)
                result = await session.execute(get_user_query)
                user = result.scalars().first()

                if not user:
                    logger.info(f"Creating local user: {user_id}")
                    user = User(
                        id=user_id,
                        email=email,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                        subscription_plan="pro",
                        subscription_status="active",
                        has_completed_onboarding=True,
                    )
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)

                return user.to_dict()
        except Exception as e:
            logger.error(
                f"Error getting or creating user {user_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Gets a user by email from the local database."""
        try:
            async with self.Session() as session:
                query = select(User).where(User.email == email)
                result = await session.execute(query)
                user = result.scalars().first()
                if user:
                    return {
                        "id": user.id,
                        "email": user.email,
                        "api_key": user.api_key,
                        "openrouter_api_key": user.openrouter_api_key,
                        "model_settings": user.model_settings,
                        # Use the User model's to_dict method
                    }
                return user.to_dict()

        except Exception as e:
            logger.error(f"Error getting user by email: {str(e)}")
            return None  # Keep returning None on error for this specific getter

    async def get_all_chapters(self, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                query = (
                    select(Chapter)
                    .where(Chapter.user_id == user_id, Chapter.project_id == project_id)
                    .order_by(Chapter.chapter_number)
                )
                result = await session.execute(query)
                chapters = result.scalars().all()
                return [chapter.to_dict() for chapter in chapters]
        except Exception as e:
            logger.error(f"Error fetching all chapters: {str(e)}")
            raise

    async def create_chapter(
        self,
        title: str,
        content: str,
        project_id: str,
        user_id: str,
        structure_item_id: Optional[str] = None,  # Add new field
    ) -> Dict[str, Any]:  # Changed return type to Dict instead of str
        async with self.Session() as session:
            # Get the highest existing chapter number for this project
            max_chapter_number_result = await session.execute(
                select(func.max(Chapter.chapter_number))
                .where(Chapter.project_id == project_id)
                .where(Chapter.user_id == user_id)
            )
            max_chapter_number = max_chapter_number_result.scalar_one_or_none()
            new_chapter_number = (max_chapter_number or 0) + 1

            new_chapter = Chapter(
                id=str(uuid.uuid4()),
                title=title,
                content=content,
                chapter_number=new_chapter_number,
                user_id=user_id,
                project_id=project_id,
                structure_item_id=structure_item_id,  # Save new field
                created_at=datetime.now(timezone.utc),
            )
            session.add(new_chapter)
            await session.commit()
            await session.refresh(new_chapter)  # Refresh to get all attributes
            return new_chapter.to_dict()  # Return the dict representation

    async def update_chapter(
        self,
        chapter_id: str,
        user_id: str,  # Ensure user_id is passed
        project_id: str,  # Ensure project_id is passed
        title: Optional[str] = None,  # Make title optional
        content: Optional[str] = None,  # Make content optional
        structure_item_id: Optional[str] = None,  # Add new field
    ):
        async with self.Session() as session:
            stmt = (
                update(Chapter)
                .where(Chapter.id == chapter_id)
                .where(Chapter.user_id == user_id)
                .where(Chapter.project_id == project_id)
            )
            values_to_update = {}  # Initialize as an empty dictionary
            if title is not None:
                values_to_update["title"] = title
            if content is not None:
                values_to_update["content"] = content
                # If content is updated, reset processed types to allow re-analysis
                values_to_update["processed_types"] = []
            if (
                structure_item_id is not None
            ):  # Allow unsetting by passing null implicitly if not provided
                values_to_update["structure_item_id"] = structure_item_id

            if not values_to_update:
                self.logger.warning("Update chapter called with no values to update.")
                # Optionally, still fetch and return the chapter or handle as an error/no-op
                # For now, let's try to fetch and return the current state
                result = await session.execute(
                    select(Chapter).where(
                        Chapter.id == chapter_id,
                        Chapter.user_id == user_id,
                        Chapter.project_id == project_id,
                    )
                )
                chapter = result.scalar_one_or_none()
                if chapter:
                    return chapter.to_dict()
                return None  # Or raise error

            stmt = stmt.values(**values_to_update).returning(Chapter)
            result = await session.execute(stmt)
            updated_chapter = result.scalar_one_or_none()
            await session.commit()
            if updated_chapter:
                return updated_chapter.to_dict()
            return None

    async def delete_chapter(self, chapter_id, user_id, project_id):
        try:
            async with self.Session() as session:
                async with session.begin():
                    # 1. Fetch the project and its structure first
                    project_result = await session.execute(
                        select(Project).where(
                            Project.id == project_id, Project.user_id == user_id
                        )
                    )
                    project = project_result.scalar_one_or_none()

                    if not project:
                        logger.warning(
                            f"Project {project_id} not found for user {user_id} during chapter deletion."
                        )
                        return False

                    # 2. Delete dependent validity checks
                    delete_validity_stmt = delete(ValidityCheck).where(
                        ValidityCheck.chapter_id == chapter_id,
                        ValidityCheck.user_id == user_id,
                        ValidityCheck.project_id == project_id,
                    )
                    await session.execute(delete_validity_stmt)
                    logger.debug(
                        f"Deleted validity checks associated with chapter {chapter_id}"
                    )

                    # 3. Delete the chapter itself
                    delete_chapter_stmt = (
                        delete(Chapter)
                        .where(
                            Chapter.id == chapter_id,
                            Chapter.user_id == user_id,
                            Chapter.project_id == project_id,
                        )
                        .returning(Chapter.id)
                    )
                    result = await session.execute(delete_chapter_stmt)
                    deleted_id = result.scalar_one_or_none()
                    deleted_count = 1 if deleted_id else 0

                    # 4. If deletion was successful, update the project structure
                    if deleted_count > 0 and project.project_structure:
                        structure = project.project_structure.get(
                            "project_structure", []
                        )

                        def remove_chapter_from_structure(items):
                            found = False
                            new_items = []
                            for item in items:
                                if (
                                    item.get("id") == chapter_id
                                    and item.get("type") == "chapter"
                                ):
                                    found = True
                                    continue  # Skip this item
                                if "children" in item:
                                    item["children"], child_found = (
                                        remove_chapter_from_structure(item["children"])
                                    )
                                    if child_found:
                                        found = True
                                new_items.append(item)
                            return new_items, found

                        new_structure, found_in_structure = (
                            remove_chapter_from_structure(structure)
                        )

                        if found_in_structure:
                            # Only update if the chapter was actually found in the structure
                            project.project_structure = {
                                "project_structure": new_structure
                            }
                            session.add(project)  # Mark project as modified
                            logger.info(
                                f"Successfully updated project structure for project {project_id}"
                            )
                            logger.info(
                                f"Removed chapter {chapter_id} from project structure for project {project_id}"
                            )
                        else:
                            logger.warning(
                                f"Chapter {chapter_id} not found in project structure for project {project_id}"
                            )
                            # Still continue with deletion from chapters table

                # The transaction is committed automatically on exiting the 'async with session.begin()' block
                return deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting chapter: {str(e)}", exc_info=True)
            raise

    async def get_chapter(self, chapter_id: str, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                query = select(Chapter).where(
                    Chapter.id == chapter_id,
                    Chapter.user_id == user_id,
                    Chapter.project_id == project_id,
                )
                result = await session.execute(query)
                chapter = result.scalars().first()
                if chapter:
                    return chapter.to_dict()
                else:
                    raise Exception("Chapter not found")
        except Exception as e:
            logger.error(f"Error getting chapter: {str(e)}")
            raise

    async def get_chapter_by_number(
        self, project_id: str, user_id: str, chapter_number: int
    ) -> Optional[Dict[str, Any]]:
        """Gets a chapter by its number for a given project and user."""
        try:
            async with self.Session() as session:
                query = select(Chapter).where(
                    Chapter.project_id == project_id,
                    Chapter.user_id == user_id,
                    Chapter.chapter_number == chapter_number,
                )
                result = await session.execute(query)
                chapter = result.scalars().first()
                return chapter.to_dict() if chapter else None
        except Exception as e:
            logger.error(
                f"Error getting chapter by number (project: {project_id}, chapter: {chapter_number}): {str(e)}",
                exc_info=True,
            )
            # Do not raise here to allow tool to return a message
            return None

    async def get_all_validity_checks(self, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                query = select(ValidityCheck).where(
                    ValidityCheck.user_id == user_id,
                    ValidityCheck.project_id == project_id,
                )
                result = await session.execute(query)
                validity_checks = result.scalars().all()
                return [check.to_dict() for check in validity_checks]
        except Exception as e:
            logger.error(f"Error getting all validity checks: {str(e)}")
            raise

    async def delete_validity_check(self, check_id, user_id, project_id):
        try:
            async with self.Session() as session:
                query = delete(ValidityCheck).where(
                    ValidityCheck.id == check_id,
                    ValidityCheck.user_id == user_id,
                    ValidityCheck.project_id == project_id,
                )
                result = await session.execute(query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting validity check: {str(e)}")
            raise

    async def create_codex_item(
        self,
        name: str,
        description: str,
        type: str,
        subtype: Optional[str],
        user_id: str,
        project_id: str,
        backstory: Optional[str] = None,  # Add backstory parameter
    ) -> str:
        try:
            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
            async with self.Session() as session:
                codex_item = CodexItem(
                    id=str(uuid.uuid4()),
                    name=name,
                    description=description,
                    type=type,
                    subtype=subtype,
                    user_id=user_id,
                    project_id=project_id,
                    backstory=backstory,  # Pass backstory to constructor
                    created_at=datetime.now(timezone.utc),  # Use timezone aware now
                    updated_at=datetime.now(timezone.utc),  # Use timezone aware now
                )
                session.add(codex_item)
                await session.commit()
                return codex_item.id
        except Exception as e:
            logger.error(f"Error creating codex item: {str(e)}")
            raise

    async def get_all_codex_items(self, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                query = (
                    select(CodexItem)
                    .options(selectinload(CodexItem.voice_profile))
                    .where(CodexItem.user_id == user_id)
                    .where(CodexItem.project_id == project_id)
                    .order_by(CodexItem.name)
                )
                result = await session.execute(query)
                codex_items = result.scalars().all()
                return [item.to_dict() for item in codex_items]
        except Exception as e:
            logger.error(f"Error getting all codex items: {e}", exc_info=True)
            # Consider re-raising or returning an error indicator
            return []

    async def update_codex_item(
        self,
        item_id: str,
        user_id: str,  # Moved up
        project_id: str,  # Moved up
        name: Optional[str] = None,
        description: Optional[str] = None,
        type: Optional[str] = None,
        subtype: Optional[str] = None,
        backstory: Optional[str] = None,
    ):
        async with self.Session() as session:
            values_to_update = {"updated_at": func.now()}
            if name is not None:
                values_to_update["name"] = name
            if description is not None:
                values_to_update["description"] = description
            if type is not None:
                values_to_update["type"] = type
            if subtype is not None:
                values_to_update["subtype"] = subtype
            if backstory is not None:
                values_to_update["backstory"] = backstory

            if not values_to_update or len(values_to_update) == 1:  # Only updated_at
                # Fetch the item to return it even if no other fields were updated
                updated_item_stmt = (
                    select(CodexItem)
                    .where(
                        CodexItem.id == item_id,
                        CodexItem.user_id == user_id,
                        CodexItem.project_id == project_id,
                    )
                    .options(selectinload(CodexItem.voice_profile))
                )  # Eager load voice_profile
                updated_item_result = await session.execute(updated_item_stmt)
                updated_item = updated_item_result.scalars().first()
                return updated_item.to_dict() if updated_item else None

            stmt = (
                update(CodexItem)
                .where(
                    CodexItem.id == item_id,
                    CodexItem.user_id == user_id,
                    CodexItem.project_id == project_id,
                )
                .values(**values_to_update)
            )
            result = await session.execute(stmt)
            await session.commit()
            if result.rowcount > 0:
                # Fetch the updated item to return it
                updated_item_stmt = (
                    select(CodexItem)
                    .where(CodexItem.id == item_id)
                    .options(selectinload(CodexItem.voice_profile))
                )  # Eager load voice_profile
                updated_item_result = await session.execute(updated_item_stmt)
                updated_item = updated_item_result.scalars().first()
                return updated_item.to_dict() if updated_item else None
            return None

    async def delete_codex_item(self, item_id: str, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                query = delete(CodexItem).where(
                    CodexItem.id == item_id,
                    CodexItem.user_id == user_id,
                    CodexItem.project_id == project_id,
                )
                result = await session.execute(query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting codex item: {str(e)}")
            raise

    async def get_codex_item_by_id(self, item_id: str, user_id: str, project_id: str):
        """Retrieve a specific codex item by its ID, user ID, and project ID."""
        async with self.Session() as session:
            try:
                stmt = (
                    select(CodexItem)
                    .options(selectinload(CodexItem.voice_profile))
                    .where(
                        CodexItem.id == item_id,
                        CodexItem.user_id == user_id,
                        CodexItem.project_id == project_id,
                    )
                )
                result = await session.execute(stmt)
                codex_item = result.scalars().first()
                if codex_item:
                    return codex_item.to_dict()  # Convert to dict before returning
                return None
            except Exception as e:
                logger.error(f"Error getting codex item by ID: {e}")
                # Optionally re-raise or handle more gracefully
                raise  # Re-raise the exception to see it in the endpoint

    async def save_model_settings(
        self, user_id, settings: Dict[str, Any]
    ):  # Add type hint
        try:
            async with self.Session() as session:
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                user = result.scalars().first()

                if user:
                    # Assign the dictionary directly to the JSON field
                    # SQLAlchemy should handle serialization
                    if not isinstance(settings, dict):
                        logger.error(
                            f"Attempted to save non-dict settings for user {user_id}"
                        )
                        raise TypeError("Settings must be a dictionary.")
                    user.model_settings = settings
                    user.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    return True
                else:
                    # Raise specific error
                    raise ValueError(f"User not found with ID: {user_id}")
        except (TypeError, ValueError) as ve:
            logger.error(
                f"Validation error saving model settings for user {user_id}: {ve}"
            )
            raise  # Re-raise validation errors
        except Exception as e:
            # Log with traceback
            logger.error(
                f"Error saving model settings for user {user_id}: {str(e)}",
                exc_info=True,
            )
            raise  # Re-raise other exceptions

    async def get_model_settings(self, user_id):
        try:
            async with self.Session() as session:
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                user = result.scalars().first()
                if user and user.model_settings:
                    settings = user.model_settings
                    # --- Add check for string type and attempt JSON parsing ---
                    if isinstance(settings, str):
                        try:
                            settings = json.loads(settings)
                        except json.JSONDecodeError:
                            logger.warning(
                                f"Failed to parse model_settings JSON string for user {user_id}. Using defaults."
                            )
                            settings = None  # Treat as invalid if parsing fails
                    # --- End added check ---

                    # Ensure temperature is a float if it exists and is not None
                    # Check if settings is a dict *after* potential parsing
                    if (
                        isinstance(settings, dict)  # Check type again
                        and "temperature" in settings
                        and settings["temperature"] is not None
                    ):
                        try:
                            settings["temperature"] = float(settings["temperature"])
                        except (ValueError, TypeError):
                            # Handle case where temperature might be invalid format, default or log
                            logger.warning(
                                f"Invalid temperature format for user {user_id}, using default."
                            )
                            settings["temperature"] = 0.7  # Or fetch default
                    # Return the dictionary directly (or handle None case)
                    return settings if settings else self.get_default_model_settings()
                # Return default settings if user or settings not found
                return self.get_default_model_settings()
        except Exception as e:
            # Log with traceback
            logger.error(
                f"Error getting model settings for user {user_id}: {str(e)}",
                exc_info=True,
            )
            # Return default settings on error to prevent frontend issues
            return self.get_default_model_settings()

    def get_default_model_settings(self):
        """Returns the default model settings."""
        return {
            "mainLLM": "gemini-1.5-pro-002",  # Consider making defaults configurable
            "checkLLM": "gemini-1.5-pro-002",
            "embeddingsModel": "models/gemini-embedding-001",
            "titleGenerationLLM": "gemini-1.5-pro-002",
            "extractionLLM": "gemini-1.5-pro-002",
            "knowledgeBaseQueryLLM": "gemini-1.5-pro-002",
            "temperature": 0.7,
        }

    async def create_location(
        self,
        name: str,
        description: str,
        coordinates: Optional[str],
        user_id: str,
        project_id: str,
    ) -> str:
        try:
            async with self.Session() as session:
                location = Location(
                    id=str(uuid.uuid4()),
                    name=name,
                    description=description,
                    coordinates=coordinates,
                    user_id=user_id,
                    project_id=project_id,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(location)
                await session.commit()
                return location.id
        except Exception as e:
            logger.error(f"Error creating location: {str(e)}")
            raise

    async def delete_location(
        self, location_id: str, project_id: str, user_id: str
    ) -> bool:
        try:
            async with self.Session() as session:
                # First delete associated connections
                delete_connections_query = delete(LocationConnection).where(
                    or_(
                        LocationConnection.location1_id == location_id,
                        LocationConnection.location2_id == location_id,
                    )
                )
                await session.execute(delete_connections_query)

                # Then delete the location
                delete_location_query = delete(Location).where(
                    and_(
                        Location.id == location_id,
                        Location.project_id == project_id,
                        Location.user_id == user_id,
                    )
                )
                result = await session.execute(delete_location_query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting location: {str(e)}")
            raise

    async def mark_chapter_processed(
        self, chapter_id: str, user_id: str, process_type: str
    ):
        try:
            async with self.Session() as session:
                # Get the chapter with a SELECT FOR UPDATE to prevent race conditions
                query = (
                    select(Chapter)
                    .where(Chapter.id == chapter_id, Chapter.user_id == user_id)
                    .with_for_update()
                )

                result = await session.execute(query)
                chapter = result.scalars().first()

                if chapter:
                    # Initialize processed_types if it's None or empty list
                    if not chapter.processed_types:
                        chapter.processed_types = []

                    # Add the process_type if not already present
                    if process_type not in chapter.processed_types:
                        # Ensure processed_types is treated as a mutable list if needed
                        # SQLAlchemy's JSON type might handle this automatically with mutable=True
                        current_types = list(
                            chapter.processed_types
                        )  # Make a copy to modify
                        current_types.append(process_type)
                        chapter.processed_types = (
                            current_types  # Assign the new list back
                        )
                        # chapter.updated_at = datetime.now(timezone.utc) # Chapter doesn't have updated_at
                        await session.commit()
                        logger.debug(
                            f"Marked chapter {chapter_id} as processed for {process_type}"
                        )
                        return True

                return False

        except Exception as e:
            logger.error(f"Error marking chapter as processed: {str(e)}")
            raise

    async def is_chapter_processed_for_type(
        self, chapter_id: str, process_type: str
    ) -> bool:
        try:
            async with self.Session() as session:
                query = (
                    select(Chapter)
                    .where(Chapter.id == chapter_id)
                    .options(selectinload(Chapter.processed_types))
                )
                result = await session.execute(query)
                chapter = result.scalars().first()
                if chapter:
                    processed_types = chapter.processed_types
                    return process_type in processed_types
                return False
        except Exception as e:
            logger.error(f"Error checking chapter processed status: {str(e)}")
            raise

    async def get_event_by_id(
        self, event_id: str, user_id: str, project_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Event).where(
                    Event.id == event_id,
                    Event.user_id == user_id,
                    Event.project_id == project_id,
                )
                result = await session.execute(query)
                event = result.scalars().first()
                return event.to_dict() if event else None
        except Exception as e:
            logger.error(f"Error getting event by ID: {str(e)}")
            raise

    async def get_location_by_id(
        self, location_id: str, user_id: str, project_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Location).where(
                    Location.id == location_id,
                    Location.user_id == user_id,
                    Location.project_id == project_id,
                )
                result = await session.execute(query)
                location = result.scalars().first()
                return location.to_dict() if location else None
        except Exception as e:
            logger.error(f"Error getting location by ID: {str(e)}")
            raise

    async def update_codex_item_embedding_id(
        self, item_id: str, embedding_id: str
    ) -> bool:
        try:
            async with self.Session() as session:
                query = select(CodexItem).where(CodexItem.id == item_id)
                result = await session.execute(query)
                codex_item = result.scalars().first()
                if codex_item:
                    codex_item.embedding_id = embedding_id
                    codex_item.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    return True
                else:
                    raise Exception("Codex item not found")
        except Exception as e:
            logger.error(f"Error updating codex item embedding_id: {str(e)}")
            raise

    async def create_project(
        self,
        name: str,
        description: str,
        user_id: str,
        universe_id: Optional[str] = None,
    ) -> str:
        try:
            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
            async with self.Session() as session:
                project = Project(
                    id=str(uuid.uuid4()),
                    name=name,
                    description=description,
                    user_id=user_id,
                    universe_id=universe_id,
                    created_at=datetime.now(timezone.utc),  # Use timezone aware now
                    updated_at=datetime.now(timezone.utc),  # Use timezone aware now
                )
                session.add(project)
                await session.commit()
                return project.id
        except Exception as e:
            logger.error(f"Error creating project: {str(e)}")
            raise

    async def get_projects_by_universe(
        self, universe_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Project).where(
                    Project.universe_id == universe_id, Project.user_id == user_id
                )
                result = await session.execute(query)
                projects = result.scalars().all()
                return [project.to_dict() for project in projects]
        except Exception as e:
            logger.error(f"Error getting projects by universe: {str(e)}")
            raise

    async def get_project(
        self, project_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Project).where(
                    Project.id == project_id, Project.user_id == user_id
                )
                result = await session.execute(query)
                project = result.scalars().first()
                return project.to_dict() if project else None
        except Exception as e:
            logger.error(f"Error getting project: {str(e)}")
            raise

    async def update_project(
        self,
        project_id: str,
        name: Optional[str],
        description: Optional[str],
        user_id: str,
        universe_id: Optional[str] = None,
        target_word_count: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Project).where(
                    Project.id == project_id, Project.user_id == user_id
                )
                result = await session.execute(query)
                project = result.scalars().first()
                if project:
                    if name is not None:
                        project.name = name
                    if description is not None:
                        project.description = description
                    if universe_id is not None:
                        project.universe_id = universe_id
                    if target_word_count is not None:
                        project.target_word_count = target_word_count
                    project.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    await session.refresh(project)  # Refresh to get latest state
                    return project.to_dict()
                else:
                    raise Exception("Project not found")
        except Exception as e:
            logger.error(f"Error updating project: {str(e)}")
            raise

    async def update_project_universe(
        self, project_id: str, universe_id: Optional[str], user_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Project).where(
                    Project.id == project_id, Project.user_id == user_id
                )
                result = await session.execute(query)
                project = result.scalars().first()
                if project:
                    project.universe_id = universe_id
                    project.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    await session.refresh(project)  # Refresh to get latest state
                    return project.to_dict()
                else:
                    raise Exception("Project not found")
        except Exception as e:
            logger.error(f"Error updating project universe: {str(e)}")
            raise

    async def delete_project(self, project_id: str, user_id: str) -> bool:
        try:
            async with self.Session() as session:
                # Fetch the project object first
                query = select(Project).where(
                    Project.id == project_id, Project.user_id == user_id
                )
                result = await session.execute(query)
                project = result.scalars().first()

                if project:
                    # Delete the object using the session, allowing ORM cascades
                    await session.delete(project)
                    await session.commit()
                    return True
                else:
                    # Project not found or user doesn't own it
                    logger.warning(
                        f"Attempted to delete non-existent or unauthorized project: {project_id} for user {user_id}"
                    )
                    return False
        except Exception as e:
            logger.error(f"Error deleting project: {str(e)}")
            raise

    async def create_universe(
        self, name: str, user_id: str, description: Optional[str] = None
    ) -> str:
        try:
            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
            async with self.Session() as session:
                universe = Universe(
                    id=str(uuid.uuid4()),
                    name=name,
                    description=description,
                    user_id=user_id,
                    created_at=datetime.now(timezone.utc),  # Use timezone aware now
                    updated_at=datetime.now(timezone.utc),  # Use timezone aware now
                )
                session.add(universe)
                await session.commit()
                return universe.id
        except Exception as e:
            logger.error(f"Error creating universe: {str(e)}")
            raise ValueError(str(e))

    async def get_universe(
        self, universe_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Universe).where(
                    Universe.id == universe_id, Universe.user_id == user_id
                )
                result = await session.execute(query)
                universe = result.scalars().first()
                return universe.to_dict() if universe else None
        except Exception as e:
            logger.error(f"Error getting universe: {str(e)}")
            raise

    async def update_universe(
        self, universe_id: str, name: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Universe).where(
                    Universe.id == universe_id, Universe.user_id == user_id
                )
                result = await session.execute(query)
                universe = result.scalars().first()
                if universe:
                    universe.name = name
                    universe.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    await session.refresh(universe)  # Refresh to get latest state
                    return universe.to_dict()
                else:
                    raise Exception("Universe not found")
        except Exception as e:
            logger.error(f"Error updating universe: {str(e)}")
            raise

    async def delete_universe(self, universe_id: str, user_id: str) -> bool:
        try:
            async with self.Session() as session:
                # Fetch the universe object first
                query = select(Universe).where(
                    Universe.id == universe_id, Universe.user_id == user_id
                )
                result = await session.execute(query)
                universe = result.scalars().first()

                if universe:
                    # Delete the object using the session, allowing ORM cascades
                    await session.delete(universe)
                    await session.commit()
                    return True
                else:
                    # Universe not found or user doesn't own it
                    logger.warning(
                        f"Attempted to delete non-existent or unauthorized universe: {universe_id} for user {user_id}"
                    )
                    return False
        except Exception as e:
            logger.error(f"Error deleting universe: {str(e)}")
            raise

    async def get_universe_codex(
        self, universe_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = (
                    select(CodexItem)
                    .options(selectinload(CodexItem.voice_profile))
                    .join(Project, CodexItem.project_id == Project.id)
                    .where(
                        Project.universe_id == universe_id, CodexItem.user_id == user_id
                    )
                )
                result = await session.execute(query)
                codex_items = result.scalars().all()
                return [item.to_dict() for item in codex_items]
        except Exception as e:
            logger.error(f"Error getting universe codex: {str(e)}")
            raise

    async def get_universe_knowledge_base(
        self, universe_id: str, user_id: str, limit: int = 100, offset: int = 0
    ) -> Dict[str, List[Dict[str, Any]]]:
        try:
            # Fetch all projects for the given universe
            async with self.Session() as session:
                query = select(Project).where(
                    Project.universe_id == universe_id, Project.user_id == user_id
                )
                result = await session.execute(query)
                projects = result.scalars().all()
                project_ids = [project.id for project in projects]

            # Initialize the result dictionary
            knowledge_base = {project.id: [] for project in projects}

            # Fetch chapters and codex items with pagination
            for project_id in project_ids:
                async with self.Session() as session:
                    chapters_query = (
                        select(Chapter)
                        .where(Chapter.project_id == project_id)
                        .limit(limit)
                        .offset(offset)
                    )
                    codex_items_query = (
                        select(CodexItem)
                        .where(CodexItem.project_id == project_id)
                        .limit(limit)
                        .offset(offset)
                    )

                    chapters_result = await session.execute(chapters_query)
                    codex_items_result = await session.execute(codex_items_query)

                    chapters = chapters_result.scalars().all()
                    codex_items = codex_items_result.scalars().all()

                    for chapter in chapters:
                        knowledge_base[project_id].append(
                            {
                                "id": chapter.id,
                                "type": "chapter",
                                "title": chapter.title,
                                "content": chapter.content,
                                "embedding_id": chapter.embedding_id,
                            }
                        )

                    for item in codex_items:
                        knowledge_base[project_id].append(
                            {
                                "id": item.id,
                                "type": "codex_item",
                                "name": item.name,
                                "description": item.description,
                                "embedding_id": item.embedding_id,
                            }
                        )

            # Remove any empty projects
            knowledge_base = {k: v for k, v in knowledge_base.items() if v}

            return knowledge_base
        except Exception as e:
            logger.error(f"Error getting universe knowledge base: {str(e)}")
            raise

    async def get_characters(
        self,
        user_id: str,
        project_id: str,
        character_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            query = (
                select(CodexItem)
                .options(selectinload(CodexItem.voice_profile))
                .where(
                    CodexItem.user_id == user_id,
                    CodexItem.project_id == project_id,
                    CodexItem.type == CodexItemType.CHARACTER.value,
                )
            )

            if character_id:
                query = query.where(CodexItem.id == character_id)
            if name:
                query = query.where(CodexItem.name == name)

            async with self.Session() as session:
                result = await session.execute(query)
                characters = result.scalars().all()

                if character_id or name:
                    return characters[0].to_dict() if characters else None
                return [character.to_dict() for character in characters]
        except Exception as e:
            logger.error(f"Error getting characters: {str(e)}")
            raise

    async def get_events(
        self, project_id: str, user_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        try:
            query = select(Event).where(
                Event.user_id == user_id, Event.project_id == project_id
            )
            if limit is not None:
                query = query.limit(limit)
            async with self.Session() as session:
                result = await session.execute(query)
                events = result.scalars().all()
                return [event.to_dict() for event in events]
        except Exception as e:
            logger.error(f"Error getting events: {str(e)}")
            raise

    async def get_locations(
        self, user_id: str, project_id: str, k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        try:
            query = select(Location).where(
                Location.user_id == user_id, Location.project_id == project_id
            )
            if k is not None:
                query = query.limit(k)
            async with self.Session() as session:
                result = await session.execute(query)
                locations = result.scalars().all()
                return [location.to_dict() for location in locations]
        except Exception as e:
            logger.error(f"Error getting locations: {str(e)}")
            raise

    async def mark_latest_chapter_processed(self, project_id: str, process_type: str):
        try:
            async with self.Session() as session:
                # Fetch the latest chapter
                query = (
                    select(Chapter)
                    .where(Chapter.project_id == project_id)
                    .order_by(Chapter.chapter_number.desc())
                    .limit(1)
                )
                result = await session.execute(query)
                latest_chapter = result.scalars().first()
                if not latest_chapter:
                    raise Exception("Latest chapter not found")

                # Ensure processed_types is treated as mutable
                current_types = list(latest_chapter.processed_types)

                # Update processed_types if the process_type is not already present
                if process_type not in current_types:
                    current_types.append(process_type)
                    latest_chapter.processed_types = (
                        current_types  # Assign back the modified list
                    )
                    # latest_chapter.updated_at = datetime.now(timezone.utc) # Chapter doesn't have updated_at
                    await session.commit()
        except Exception as e:
            logger.error(f"Error marking latest chapter as processed: {str(e)}")
            raise

    async def is_chapter_processed(self, chapter_id: str, process_type: str) -> bool:
        try:
            async with self.Session() as session:
                query = (
                    select(Chapter)
                    .where(Chapter.id == chapter_id)
                    .options(selectinload(Chapter.processed_types))
                )
                result = await session.execute(query)
                chapter = result.scalars().first()
                if chapter:
                    processed_types = chapter.processed_types
                    return process_type in processed_types
                return False
        except Exception as e:
            logger.error(f"Error checking chapter processed status: {str(e)}")
            raise

    async def save_validity_check(
        self,
        chapter_id: str,
        chapter_title: str,
        is_valid: bool,
        overall_score: int,
        general_feedback: str,
        style_guide_adherence_score: int,
        style_guide_adherence_explanation: str,
        continuity_score: int,
        continuity_explanation: str,
        areas_for_improvement: List[str],
        user_id: str,
        project_id: str,
    ):
        try:
            async with self.Session() as session:
                validity_check = ValidityCheck(
                    id=str(uuid.uuid4()),
                    chapter_id=chapter_id,
                    chapter_title=chapter_title,
                    is_valid=is_valid,
                    overall_score=overall_score,
                    general_feedback=general_feedback,
                    style_guide_adherence_score=style_guide_adherence_score,
                    style_guide_adherence_explanation=style_guide_adherence_explanation,
                    continuity_score=continuity_score,
                    continuity_explanation=continuity_explanation,
                    areas_for_improvement=json.dumps(areas_for_improvement),
                    user_id=user_id,
                    project_id=project_id,
                    created_at=datetime.now(timezone.utc),  # Use timezone aware now
                )
                session.add(validity_check)
                await session.commit()
                return validity_check.id
        except Exception as e:
            logger.error(f"Error saving validity check: {str(e)}")
            raise

    async def get_validity_check(
        self, chapter_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(ValidityCheck).where(
                    ValidityCheck.chapter_id == chapter_id,
                    ValidityCheck.user_id == user_id,
                )
                result = await session.execute(query)
                validity_check = result.scalars().first()
                if validity_check:
                    return validity_check.to_dict()
                raise Exception("Validity check not found")
        except Exception as e:
            logger.error(f"Error getting validity check: {str(e)}")
            raise

    async def save_chat_history(
        self,
        user_id: str,
        project_id: str,
        history: List[Dict[str, Any]],
        agent_type: AgentType = AgentType.STANDARD,
    ):
        async with self.Session() as session:
            try:
                # Find existing history record for this user, project, and agent type
                stmt = select(ChatHistory).where(
                    ChatHistory.user_id == user_id,
                    ChatHistory.project_id == project_id,
                    ChatHistory.agent_type == agent_type.value,
                )
                result = await session.execute(stmt)
                existing_history_record = result.scalars().first()

                # Convert the input 'history' (which is the complete new history list)
                # from 'role' key (often from frontend/agent logic) to backend 'type' key.
                new_messages_backend_format = []
                for msg in history:
                    msg_copy = msg.copy()  # Work on a copy
                    if "content" not in msg_copy:  # Basic validation
                        logger.warning(
                            f"Skipping malformed message (no content): {msg}"
                        )
                        continue

                    if "role" in msg_copy:
                        msg_copy["type"] = msg_copy.pop("role")
                        new_messages_backend_format.append(msg_copy)
                    elif (
                        "type" in msg_copy
                    ):  # Already in backend format or only has 'type'
                        new_messages_backend_format.append(msg_copy)
                    else:
                        logger.warning(
                            f"Message has neither 'role' nor 'type', attempting to save as is but may cause issues: {msg}"
                        )
                        # Fallback: append as is if essential keys are missing, but this indicates an upstream issue.
                        # Or, decide to skip such messages:
                        # logger.warning(f"Skipping message due to missing 'role' or 'type': {msg}")
                        # continue
                        new_messages_backend_format.append(msg_copy)

                if existing_history_record:
                    # Update existing entry by replacing its messages field entirely
                    existing_history_record.messages = new_messages_backend_format
                    existing_history_record.updated_at = datetime.now(timezone.utc)
                    logger.debug(
                        f"Updating {agent_type.value} chat history for user {user_id}, project {project_id}, now with {len(new_messages_backend_format)} messages"
                    )
                else:
                    # Create new entry if no existing record was found
                    new_history_record = ChatHistory(
                        user_id=user_id,
                        project_id=project_id,
                        messages=new_messages_backend_format,
                        agent_type=agent_type.value,
                        # created_at and updated_at will use server_default
                    )
                    session.add(new_history_record)
                    logger.debug(
                        f"Creating new {agent_type.value} chat history for user {user_id}, project {project_id} with {len(new_messages_backend_format)} messages"
                    )

                await session.commit()
                logger.debug(
                    f"Successfully committed {agent_type.value} chat history for user {user_id}, project {project_id}"
                )
            except Exception as e:
                await session.rollback()
                logger.error(
                    f"Error saving chat history for {agent_type.value} (user: {user_id}, project: {project_id}): {e}",
                    exc_info=True,
                )
                raise

    async def get_chat_history(
        self,
        user_id: str,
        project_id: str,
        agent_type: AgentType = AgentType.STANDARD,
    ) -> List[Dict[str, Any]]:
        """Retrieves the chat history for a specific agent type."""
        logger.debug(
            f"Attempting to get {agent_type.value} chat history for user {user_id}, project {project_id}"
        )

        async with self.Session() as session:
            try:
                # Get the full ChatHistory object
                stmt = select(ChatHistory).where(
                    ChatHistory.user_id == user_id,
                    ChatHistory.project_id == project_id,
                    ChatHistory.agent_type == agent_type.value,
                )
                result = await session.execute(stmt)
                history_obj = result.scalars().first()

                # Extract messages from the object if it exists
                messages_json = history_obj.messages if history_obj else None

                # Ensure messages_json is a list
                if messages_json is None:
                    return []

                # If it's a string, try to parse it as JSON
                if isinstance(messages_json, str):
                    try:
                        messages_list = json.loads(messages_json)
                        if isinstance(messages_list, list):
                            # Convert from backend format (type) to frontend format (role)
                            return [
                                self._convert_message_format(msg)
                                for msg in messages_list
                            ]
                        logger.warning(
                            f"Chat history messages parsed from string, but result is not a list. Type: {type(messages_list)}"
                        )
                        return []
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Failed to parse chat history messages string as JSON. Using empty list."
                        )
                        return []

                # If it's already a list, convert format and return
                if isinstance(messages_json, list):
                    return [self._convert_message_format(msg) for msg in messages_json]

                # For any other type, return empty list
                logger.warning(
                    f"Unknown type for chat history messages: {type(messages_json)}. Using empty list."
                )
                return []
            except Exception as e:
                logger.error(f"Error retrieving chat history: {e}", exc_info=True)
                return []  # Return empty list on error

    def _convert_message_format(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to convert between backend and frontend message formats."""
        if not isinstance(message, dict):
            return message

        result = message.copy()

        # Bidirectional conversion for compatibility
        # If we have 'type' but not 'role', add 'role'
        if "type" in result and "role" not in result:
            result["role"] = result["type"]
        # If we have 'role' but not 'type', add 'type'
        elif "role" in result and "type" not in result:
            result["type"] = result["role"]

        return result

    async def delete_chat_history(
        self,
        user_id: str,
        project_id: str,
        agent_type: AgentType = AgentType.STANDARD,  # <-- Add agent_type parameter
    ) -> bool:
        """Deletes the chat history for a specific agent type."""
        # Removed string ID to UUID conversion

        async with self.Session() as session:
            try:
                stmt = delete(ChatHistory).where(
                    ChatHistory.user_id == user_id,  # Use String ID directly
                    ChatHistory.project_id == project_id,  # Use String ID directly
                    ChatHistory.agent_type
                    == agent_type.value,  # <-- Filter by agent_type
                )
                result = await session.execute(stmt)
                await session.commit()
                deleted_count = result.rowcount
                logger.info(
                    f"Deleted {deleted_count} {agent_type.value} chat history entries for user {user_id}, project {project_id}."
                )
                return deleted_count > 0
            except Exception as e:
                await session.rollback()
                logger.error(f"Error deleting chat history: {e}", exc_info=True)
                raise

    async def create_preset(
        self, user_id: str, project_id: str, name: str, data: Dict[str, Any]
    ) -> str:
        try:
            async with self.Session() as session:
                # Check if a preset with the same name exists
                query = select(Preset).where(
                    Preset.user_id == user_id,
                    Preset.project_id == project_id,
                    Preset.name == name,
                )
                result = await session.execute(query)
                preset = result.scalars().first()
                if preset:
                    raise ValueError(
                        f"A preset with name '{name}' already exists for this user and project."
                    )

                # Create new preset
                new_preset = Preset(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    project_id=project_id,
                    name=name,
                    data=data,
                )
                session.add(new_preset)
                await session.commit()
                return new_preset.id
        except ValueError as ve:
            logger.error(f"Error creating preset: {str(ve)}")
            raise
        except Exception as e:
            logger.error(f"Error creating preset: {str(e)}")
            raise

    async def get_presets(self, user_id: str, project_id: str) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Preset).where(
                    Preset.user_id == user_id, Preset.project_id == project_id
                )
                result = await session.execute(query)
                presets = result.scalars().all()
                return [
                    {"id": preset.id, "name": preset.name, "data": preset.data}
                    for preset in presets
                ]
        except Exception as e:
            logger.error(f"Error getting presets: {str(e)}")
            raise

    async def get_generation_history(
        self, project_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = (
                    select(GenerationHistory)
                    .where(
                        GenerationHistory.project_id == project_id,
                        GenerationHistory.user_id == user_id,
                    )
                    .order_by(GenerationHistory.timestamp.desc())
                )
                result = await session.execute(query)
                history = result.scalars().all()
                return [item.to_dict() for item in history]
        except Exception as e:
            logger.error(f"Error getting generation history: {str(e)}")
            raise

    async def get_generation_history(
        self, project_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = (
                    select(GenerationHistory)
                    .where(
                        GenerationHistory.project_id == project_id,
                        GenerationHistory.user_id == user_id,
                    )
                    .order_by(GenerationHistory.timestamp.desc())
                )
                result = await session.execute(query)
                history = result.scalars().all()
                return [item.to_dict() for item in history]
        except Exception as e:
            logger.error(f"Error getting generation history: {str(e)}")
            raise

    async def get_generation_history(
        self, project_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = (
                    select(GenerationHistory)
                    .where(
                        GenerationHistory.project_id == project_id,
                        GenerationHistory.user_id == user_id,
                    )
                    .order_by(GenerationHistory.timestamp.desc())
                )
                result = await session.execute(query)
                history = result.scalars().all()
                return [item.to_dict() for item in history]
        except Exception as e:
            logger.error(f"Error getting generation history: {str(e)}")
            raise

    async def get_generation_history(
        self, project_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = (
                    select(GenerationHistory)
                    .where(
                        GenerationHistory.project_id == project_id,
                        GenerationHistory.user_id == user_id,
                    )
                    .order_by(GenerationHistory.timestamp.desc())
                )
                result = await session.execute(query)
                history = result.scalars().all()
                return [item.to_dict() for item in history]
        except Exception as e:
            logger.error(f"Error getting generation history: {str(e)}")
            raise

    async def get_generation_history(
        self, project_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = (
                    select(GenerationHistory)
                    .where(
                        GenerationHistory.project_id == project_id,
                        GenerationHistory.user_id == user_id,
                    )
                    .order_by(GenerationHistory.timestamp.desc())
                )
                result = await session.execute(query)
                history = result.scalars().all()
                return [item.to_dict() for item in history]
        except Exception as e:
            logger.error(f"Error getting generation history: {str(e)}")
            raise

    async def delete_preset(
        self, preset_id: str, user_id: str, project_id: str
    ) -> bool:
        try:
            async with self.Session() as session:
                query = delete(Preset).where(
                    Preset.id == preset_id,
                    Preset.user_id == user_id,
                    Preset.project_id == project_id,
                )
                result = await session.execute(query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting preset: {str(e)}")
            raise

    async def get_preset_by_name(
        self, preset_name: str, user_id: str, project_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Preset).where(
                    Preset.name == preset_name,
                    Preset.user_id == user_id,
                    Preset.project_id == project_id,
                )
                result = await session.execute(query)
                preset = result.scalars().first()
                if preset:
                    return {"id": preset.id, "name": preset.name, "data": preset.data}
                return None
        except Exception as e:
            logger.error(f"Error getting preset by name: {str(e)}")
            return None

    async def update_preset(
        self,
        preset_id: str,
        user_id: str,
        project_id: str,
        updated_data: Dict[str, Any],
    ) -> bool:
        """Updates an existing preset with new data."""
        try:
            async with self.Session() as session:
                query = select(Preset).where(
                    Preset.id == preset_id,
                    Preset.user_id == user_id,
                    Preset.project_id == project_id,
                )
                result = await session.execute(query)
                preset = result.scalars().first()

                if preset:
                    preset.name = updated_data.get("name", preset.name)
                    if "data" in updated_data:
                        preset.data = updated_data["data"]
                    await session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error updating preset: {str(e)}")
            raise

    async def update_chapter_embedding_id(
        self, chapter_id: str, embedding_id: str
    ) -> bool:
        try:
            async with self.Session() as session:
                query = select(Chapter).where(Chapter.id == chapter_id)
                result = await session.execute(query)
                chapter = result.scalars().first()
                if chapter:
                    chapter.embedding_id = embedding_id
                    # chapter.updated_at = datetime.now(timezone.utc) # Chapter doesn't have updated_at
                    await session.commit()
                    return True
                else:
                    raise Exception("Chapter not found")
        except Exception as e:
            logger.error(f"Error updating chapter embedding_id: {str(e)}")
            raise

    async def delete_character_relationship(
        self, relationship_id: str, user_id: str, project_id: str
    ) -> bool:
        try:
            async with self.Session() as session:
                # Corrected query: Filter by relationship_id and project_id, and verify user_id via project
                query = (
                    delete(CharacterRelationship)
                    .where(CharacterRelationship.id == relationship_id)
                    .where(CharacterRelationship.project_id == project_id)
                    .where(
                        CharacterRelationship.project.has(user_id=user_id)
                    )  # Verify ownership via relationship
                )

                result = await session.execute(query)
                await session.commit()
                # Check if any row was actually deleted
                if result.rowcount == 0:
                    logger.warning(
                        f"Attempted to delete non-existent or unauthorized relationship: {relationship_id} for project {project_id}"
                    )
                    return False
                logger.info(
                    f"Deleted relationship {relationship_id} for project {project_id}"
                )
                return True
        except Exception as e:
            logger.error(f"Error deleting character relationship: {str(e)}")
            raise

    async def save_relationship_analysis(
        self,
        character1_id: str,
        character2_id: str,
        relationship_type: str,
        description: str,
        user_id: str,
        project_id: str,
    ) -> str:
        try:
            async with self.Session() as session:
                analysis = CharacterRelationshipAnalysis(
                    id=str(uuid.uuid4()),
                    character1_id=character1_id,
                    character2_id=character2_id,
                    relationship_type=relationship_type,
                    description=description,
                    user_id=user_id,
                    project_id=project_id,
                    created_at=datetime.now(timezone.utc),  # Use timezone aware now
                    updated_at=datetime.now(timezone.utc),  # Use timezone aware now
                )
                session.add(analysis)
                await session.commit()
                return analysis.id
        except Exception as e:
            logger.error(f"Error saving relationship analysis: {str(e)}")
            raise

    async def get_character_relationships(
        self, project_id: str, user_id: str  # user_id is not used but part of signature
    ) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                Character = aliased(CodexItem, name="character")
                RelatedCharacter = aliased(CodexItem, name="related_character")

                query = (
                    select(CharacterRelationship)
                    # Join 1: Ensure character_id links to a CODEX ITEM of TYPE CHARACTER
                    .join(
                        Character,
                        and_(
                            CharacterRelationship.character_id == Character.id,
                            Character.type == CodexItemType.CHARACTER.value,
                        ),
                    )
                    # Join 2: Ensure related_character_id links to a CODEX ITEM of TYPE CHARACTER
                    .join(
                        RelatedCharacter,
                        and_(
                            CharacterRelationship.related_character_id
                            == RelatedCharacter.id,
                            RelatedCharacter.type == CodexItemType.CHARACTER.value,
                        ),
                    ).where(CharacterRelationship.project_id == project_id)
                    # Eager load the related Character objects (using the standard relationship attributes)
                    .options(
                        joinedload(CharacterRelationship.character),
                        joinedload(CharacterRelationship.related_character),
                    )
                )
                result = await session.execute(query)
                # Use unique() to handle potential duplicates if relationship structure allows it
                relationships = result.unique().scalars().all()

                result_list = []
                for rel in relationships:
                    # Access related objects through the standard relationship attributes
                    char1_name = rel.character.name if rel.character else "Unknown"
                    char2_name = (
                        rel.related_character.name
                        if rel.related_character
                        else "Unknown"
                    )
                    result_list.append(
                        {
                            "id": rel.id,
                            "character_id": rel.character_id,
                            "related_character_id": rel.related_character_id,
                            "character1_name": char1_name,  # Send names from backend too
                            "character2_name": char2_name,
                            "relationship_type": rel.relationship_type,
                            "description": rel.description or "",
                        }
                    )
                return result_list
        except Exception as e:
            logger.error(f"Error getting character relationships: {str(e)}")
            raise

    async def update_character_backstory(
        self, character_id: str, backstory: str, user_id: str, project_id: str
    ):
        try:
            async with self.Session() as session:
                # Fetch the character
                query = select(CodexItem).where(
                    CodexItem.id == character_id,
                    CodexItem.user_id == user_id,
                    CodexItem.project_id == project_id,
                    CodexItem.type == CodexItemType.CHARACTER.value,
                )
                result = await session.execute(query)
                character = result.scalars().first()
                if not character:
                    raise ValueError(f"Character with ID {character_id} not found")

                # Update backstory and updated_at
                character.backstory = backstory
                character.updated_at = datetime.now(timezone.utc)
                await session.commit()
        except Exception as e:
            logger.error(f"Error updating character backstory: {str(e)}")
            raise

    async def delete_character_backstory(
        self, character_id: str, user_id: str, project_id: str
    ):
        try:
            async with self.Session() as session:
                # Fetch the character
                query = select(CodexItem).where(
                    CodexItem.id == character_id,
                    CodexItem.user_id == user_id,
                    CodexItem.project_id == project_id,
                    CodexItem.type == CodexItemType.CHARACTER.value,
                )
                result = await session.execute(query)
                character = result.scalars().first()
                if not character:
                    raise ValueError(f"Character with ID {character_id} not found")

                # Update backstory and updated_at
                character.backstory = None
                character.updated_at = datetime.now(timezone.utc)
                await session.commit()
        except Exception as e:
            logger.error(f"Error deleting character backstory: {str(e)}")
            raise

    async def get_chapter_count(self, project_id: str, user_id: str) -> int:
        try:
            async with self.Session() as session:
                query = select(func.count()).where(
                    Chapter.project_id == project_id, Chapter.user_id == user_id
                )
                result = await session.execute(query)
                return result.scalar_one()
        except Exception as e:
            logger.error(f"Error getting chapter count: {str(e)}")
            raise

    async def create_event(
        self,
        title: str,
        description: str,
        date: datetime,
        project_id: str,
        user_id: str,
        character_id: Optional[str] = None,
        location_id: Optional[str] = None,
    ) -> str:
        try:
            async with self.Session() as session:
                event = Event(
                    id=str(uuid.uuid4()),
                    title=title,
                    description=description,
                    date=date,
                    character_id=character_id,
                    project_id=project_id,
                    user_id=user_id,
                    location_id=location_id,
                    created_at=datetime.now(timezone.utc),  # Use timezone aware now
                    updated_at=datetime.now(timezone.utc),  # Use timezone aware now
                )
                session.add(event)
                await session.commit()
                return event.id
        except Exception as e:
            logger.error(f"Error creating event: {str(e)}")
            raise

    async def save_character_backstory(
        self, character_id: str, content: str, user_id: str, project_id: str
    ):
        try:
            async with self.Session() as session:
                # Fetch the character to verify it exists and check its current backstory
                query = select(CodexItem).where(
                    CodexItem.id == character_id,
                    CodexItem.user_id == user_id,
                    CodexItem.project_id == project_id,
                    CodexItem.type == CodexItemType.CHARACTER.value,
                )
                result = await session.execute(query)
                character = result.scalars().first()

                if not character:
                    raise ValueError("Character not found or not of type character")

                # Update backstory and updated_at
                new_backstory = (
                    f"{character.backstory}\n\n{content}"
                    if character.backstory
                    else content
                )
                character.backstory = new_backstory
                character.updated_at = datetime.now(timezone.utc)

                await session.commit()
                await session.refresh(character)  # Refresh to get latest state
                return character.to_dict()

        except Exception as e:
            logger.error(f"Error saving character backstory: {str(e)}")
            raise

    async def get_latest_unprocessed_chapter_content(
        self, project_id: str, user_id: str, process_type: str
    ):
        try:
            async with self.Session() as session:
                query = (
                    select(Chapter)
                    .where(Chapter.project_id == project_id, Chapter.user_id == user_id)
                    .order_by(Chapter.chapter_number)
                )
                result = await session.execute(query)
                chapters = result.scalars().all()

                unprocessed_chapters = [
                    {"id": chapter.id, "content": chapter.content}
                    for chapter in chapters
                    if process_type not in chapter.processed_types
                ]

                return unprocessed_chapters

        except Exception as e:
            logger.error(f"Error getting unprocessed chapter content: {str(e)}")
            raise

    async def create_character_relationship(
        self,
        character_id: str,
        related_character_id: str,
        relationship_type: str,
        project_id: str,
        description: Optional[str] = None,
    ) -> str:
        try:
            async with self.Session() as session:
                # First verify both characters exist and are of type character
                char1_query = select(CodexItem).where(
                    CodexItem.id == character_id,
                    CodexItem.project_id == project_id,
                    CodexItem.type == CodexItemType.CHARACTER.value,
                )
                char2_query = select(CodexItem).where(
                    CodexItem.id == related_character_id,
                    CodexItem.project_id == project_id,
                    CodexItem.type == CodexItemType.CHARACTER.value,
                )

                char1_result = await session.execute(char1_query)
                char2_result = await session.execute(char2_query)

                char1 = char1_result.scalars().first()
                char2 = char2_result.scalars().first()

                if not char1:
                    logger.error(
                        f"Character with ID {character_id} not found in the codex"
                    )
                    raise ValueError("Character not found")

                if not char2:
                    logger.error(
                        f"Character with ID {related_character_id} not found in the codex"
                    )
                    raise ValueError("Related character not found")

                relationship = CharacterRelationship(
                    id=str(uuid.uuid4()),
                    character_id=character_id,
                    related_character_id=related_character_id,
                    relationship_type=relationship_type,
                    description=description,
                    project_id=project_id,
                )

                session.add(relationship)
                await session.commit()
                return relationship.id

        except Exception as e:
            logger.error(f"Error creating character relationship: {str(e)}")
            raise

    async def update_event(
        self,
        event_id: str,
        title: str,
        description: str,
        date: datetime,
        character_id: Optional[str],
        location_id: Optional[str],
        project_id: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Event).where(
                    Event.id == event_id,
                    Event.user_id == user_id,
                    Event.project_id == project_id,
                )
                result = await session.execute(query)
                event = result.scalars().first()
                if event:
                    event.title = title
                    event.description = description
                    event.date = date
                    event.character_id = character_id
                    event.location_id = location_id
                    event.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    await session.refresh(event)  # Refresh to get latest state
                    return event.to_dict()
                else:
                    raise Exception("Event not found")
        except Exception as e:
            logger.error(f"Error updating event: {str(e)}")
            raise

    async def get_event_by_title(
        self, title: str, user_id: str, project_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Event).where(
                    Event.title == title,
                    Event.user_id == user_id,
                    Event.project_id == project_id,
                )
                result = await session.execute(query)
                event = result.scalars().first()
                return event.to_dict() if event else None
        except Exception as e:
            logger.error(f"Error getting event by title: {str(e)}")
            raise

    async def update_location(
        self, location_id: str, location_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Location).where(Location.id == location_id)
                result = await session.execute(query)
                location = result.scalars().first()
                if location:
                    # Only update allowed fields to prevent mass assignment issues
                    allowed_updates = [
                        "name",
                        "description",
                        "coordinates",
                    ]  # Add other updatable fields if needed
                    for key, value in location_data.items():
                        if key in allowed_updates:
                            setattr(location, key, value)
                    location.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    await session.refresh(location)  # Refresh to get latest state
                    return location.to_dict()
                else:
                    raise Exception("Location not found")
        except Exception as e:
            logger.error(f"Error updating location: {str(e)}")
            raise

    async def update_character_relationship(
        self,
        relationship_id: str,
        relationship_type: str,
        description: Optional[str],  # Added description back
        user_id: str,
        project_id: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                # Use update() for efficiency
                stmt = (
                    update(CharacterRelationship)
                    .where(
                        and_(
                            CharacterRelationship.id == relationship_id,
                            # CharacterRelationship.user_id == user_id, # Removed incorrect user_id filter
                            CharacterRelationship.project_id
                            == project_id,  # Rely on project_id for auth scope
                        )
                    )
                    .values(
                        relationship_type=relationship_type,
                        description=description,  # Set the description
                        # Note: CharacterRelationship doesn't have updated_at in the model shown
                    )
                    .returning(CharacterRelationship)  # Return the updated row
                )
                result = await session.execute(stmt)
                updated_relationship = result.scalars().first()
                await session.commit()

                if updated_relationship:
                    # Refresh might not be strictly necessary after returning()
                    # await session.refresh(updated_relationship)
                    return updated_relationship.to_dict()
                else:
                    logger.warning(
                        f"Update failed: Character relationship {relationship_id} not found for user {user_id}, project {project_id}"
                    )
                    return None  # Return None instead of raising Exception
        except Exception as e:
            # Log with exc_info=True for full traceback
            logger.error(
                f"Error updating character relationship {relationship_id}: {str(e)}",
                exc_info=True,
            )
            raise  # Re-raise the exception to be handled by the caller (FastAPI)

    async def get_location_by_name(
        self, name: str, user_id: str, project_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Location).where(
                    Location.name == name,
                    Location.user_id == user_id,
                    Location.project_id == project_id,
                )
                result = await session.execute(query)
                location = result.scalars().first()
                return location.to_dict() if location else None
        except Exception as e:
            logger.error(f"Error getting location by name: {str(e)}")
            raise

    async def dispose(self):
        """Dispose of the engine and close all connections."""
        if self.engine:
            await self.engine.dispose()

    async def create_location_connection(
        self,
        location1_id: str,
        location2_id: str,
        location1_name: str,
        location2_name: str,
        connection_type: str,
        description: str,
        travel_route: Optional[str],
        cultural_exchange: Optional[str],
        project_id: str,
        user_id: str,
    ) -> str:
        try:
            async with self.Session() as session:
                connection = LocationConnection(
                    id=str(uuid.uuid4()),
                    location1_id=location1_id,
                    location2_id=location2_id,
                    location1_name=location1_name,
                    location2_name=location2_name,
                    connection_type=connection_type,
                    description=description,
                    travel_route=travel_route,
                    cultural_exchange=cultural_exchange,
                    project_id=project_id,
                    user_id=user_id,
                    created_at=datetime.now(timezone.utc),  # Use timezone aware now
                    updated_at=datetime.now(timezone.utc),  # Use timezone aware now
                )
                session.add(connection)
                await session.commit()
                return connection.id

        except Exception as e:
            logger.error(f"Error creating location connection: {str(e)}")
            raise

    async def create_event_connection(
        self,
        event1_id: str,
        event2_id: str,
        connection_type: str,
        description: str,
        impact: str,
        project_id: str,
        user_id: str,
    ) -> str:
        try:
            async with self.Session() as session:
                connection = EventConnection(
                    id=str(uuid.uuid4()),
                    event1_id=event1_id,
                    event2_id=event2_id,
                    connection_type=connection_type,
                    description=description,
                    impact=impact,
                    project_id=project_id,
                    user_id=user_id,
                    created_at=datetime.now(timezone.utc),  # Use timezone aware now
                    updated_at=datetime.now(timezone.utc),  # Use timezone aware now
                )
                session.add(connection)
                await session.commit()
                return connection.id
        except Exception as e:
            logger.error(f"Error creating event connection: {str(e)}")
            raise

    async def get_location_connections(
        self, project_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(LocationConnection).where(
                    LocationConnection.project_id == project_id,
                    LocationConnection.user_id == user_id,
                )
                result = await session.execute(query)
                connections = result.scalars().all()
                return [conn.to_dict() for conn in connections]
        except Exception as e:
            logger.error(f"Error getting location connections: {str(e)}")
            raise

    async def get_event_connections(
        self, project_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(EventConnection).where(
                    EventConnection.project_id == project_id,
                    EventConnection.user_id == user_id,
                )
                result = await session.execute(query)
                connections = result.scalars().all()
                return [conn.to_dict() for conn in connections]
        except Exception as e:
            logger.error(f"Error getting event connections: {str(e)}")
            raise

    async def update_location_connection(
        self,
        connection_id: str,
        connection_type: str,
        description: str,
        travel_route: Optional[str],
        cultural_exchange: Optional[str],
        user_id: str,
        project_id: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(LocationConnection).where(
                    LocationConnection.id == connection_id,
                    LocationConnection.user_id == user_id,
                    LocationConnection.project_id == project_id,
                )
                result = await session.execute(query)
                connection = result.scalars().first()
                if connection:
                    connection.connection_type = connection_type
                    connection.description = description
                    connection.travel_route = travel_route
                    connection.cultural_exchange = cultural_exchange
                    connection.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    await session.refresh(connection)  # Refresh to get latest state
                    return connection.to_dict()
                else:
                    raise Exception("Location connection not found")
        except Exception as e:
            logger.error(f"Error updating location connection: {str(e)}")
            raise

    async def update_event_connection(
        self,
        connection_id: str,
        connection_type: str,
        description: str,
        impact: str,
        user_id: str,
        project_id: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(EventConnection).where(
                    EventConnection.id == connection_id,
                    EventConnection.user_id == user_id,
                    EventConnection.project_id == project_id,
                )
                result = await session.execute(query)
                connection = result.scalars().first()
                if connection:
                    connection.connection_type = connection_type
                    connection.description = description
                    connection.impact = impact
                    connection.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    await session.refresh(connection)  # Refresh to get latest state
                    return connection.to_dict()
                else:
                    raise Exception("Event connection not found")
        except Exception as e:
            logger.error(f"Error updating event connection: {str(e)}")
            raise

    async def delete_location_connection(
        self, connection_id: str, user_id: str, project_id: str
    ) -> bool:
        try:
            async with self.Session() as session:
                query = delete(LocationConnection).where(
                    LocationConnection.id == connection_id,
                    LocationConnection.user_id == user_id,
                    LocationConnection.project_id == project_id,
                )
                result = await session.execute(query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting location connection: {str(e)}")
            raise

    async def delete_event_connection(
        self, connection_id: str, user_id: str, project_id: str
    ) -> bool:
        try:
            async with self.Session() as session:
                query = delete(EventConnection).where(
                    EventConnection.id == connection_id,
                    EventConnection.user_id == user_id,
                    EventConnection.project_id == project_id,
                )
                result = await session.execute(query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting event connection: {str(e)}")
            raise

    async def delete_event(self, event_id: str, user_id: str, project_id: str) -> bool:
        try:
            async with self.Session() as session:
                # First delete associated connections
                delete_connections_query = delete(EventConnection).where(
                    or_(
                        EventConnection.event1_id == event_id,
                        EventConnection.event2_id == event_id,
                    )
                )
                await session.execute(delete_connections_query)

                # Then delete the event
                query = delete(Event).where(
                    Event.id == event_id,
                    Event.user_id == user_id,
                    Event.project_id == project_id,
                )
                result = await session.execute(query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting event: {str(e)}")
            raise

    async def get_project_knowledge_base(
        self, user_id: str, project_id: str
    ) -> List[Dict[str, Any]]:
        """Fetches all knowledge base related items for a specific project."""
        try:
            # Use self.Session() instead of self.async_session_factory()
            async with self.Session() as session:
                # Fetch Chapters
                chapter_query = select(Chapter).where(
                    Chapter.project_id == project_id, Chapter.user_id == user_id
                )
                chapters_result = await session.execute(chapter_query)
                chapters = chapters_result.scalars().all()

                # Fetch Codex Items
                codex_query = select(CodexItem).where(
                    CodexItem.project_id == project_id, CodexItem.user_id == user_id
                )
                codex_result = await session.execute(codex_query)
                codex_items = codex_result.scalars().all()

                # Fetch Manual/File Knowledge Base Items
                manual_kb_query = select(KnowledgeBaseItem).where(
                    KnowledgeBaseItem.project_id == project_id,
                    KnowledgeBaseItem.user_id == user_id,
                )
                manual_kb_result = await session.execute(manual_kb_query)
                manual_kb_items = manual_kb_result.scalars().all()

            # Combine and format results
            knowledge_base = []
            for chapter in chapters:
                knowledge_base.append(
                    {
                        "id": chapter.id,
                        "db_table": "chapters",  # Indicate source table
                        "type": "chapter",
                        "name": chapter.title,  # Use 'name' for consistency?
                        "content": chapter.content,
                        "metadata": {"chapter_number": chapter.chapter_number},
                        "embedding_id": chapter.embedding_id,
                        "created_at": (
                            chapter.created_at.isoformat()
                            if chapter.created_at
                            else None
                        ),
                        # Chapters don't have updated_at in the model
                        "updated_at": None,
                    }
                )

            for item in codex_items:
                knowledge_base.append(
                    {
                        "id": item.id,
                        "db_table": "codex_items",
                        "type": item.type,  # e.g., 'CHARACTER', 'LOCATION'
                        "name": item.name,
                        "content": item.description,  # Use description as main content
                        "metadata": {
                            "subtype": item.subtype,
                            "backstory": item.backstory,
                        },
                        "embedding_id": item.embedding_id,
                        "created_at": (
                            item.created_at.isoformat() if item.created_at else None
                        ),
                        "updated_at": (
                            item.updated_at.isoformat() if item.updated_at else None
                        ),
                    }
                )

            for item in manual_kb_items:
                knowledge_base.append(
                    {
                        "id": item.id,
                        "db_table": "knowledge_base_items",
                        "type": item.type,  # e.g., 'manual_text', 'uploaded_file'
                        "name": item.source
                        or f"Manual Entry ({item.id[:8]})",  # Generate a name if source is missing
                        "content": item.content,
                        "metadata": item.item_metadata,
                        "embedding_id": item.embedding_id,
                        "created_at": (
                            item.created_at.isoformat() if item.created_at else None
                        ),
                        "updated_at": (
                            item.updated_at.isoformat() if item.updated_at else None
                        ),
                    }
                )

            # Sort by creation date or type/name?
            knowledge_base.sort(key=lambda x: x.get("created_at") or "", reverse=True)

            return knowledge_base
        except Exception as e:
            logger.error(
                f"Error getting project knowledge base for {project_id}: {str(e)}"
            )
            raise

    async def create_knowledge_base_item(
        self,
        user_id: str,
        project_id: str,
        type: str,
        item_metadata: Dict[str, Any],  # Renamed parameter
        source: str,
        content: Optional[str] = None,
        embedding_id: Optional[str] = None,  # Optional, will often be None initially
    ) -> str:
        # Use self.Session() instead of self.async_session_factory()
        async with self.Session() as session:
            async with session.begin():
                item = KnowledgeBaseItem(
                    user_id=user_id,
                    project_id=project_id,
                    type=type,
                    content=content,
                    item_metadata=item_metadata,  # Use renamed field
                    source=source,
                    embedding_id=embedding_id,  # Store if provided
                )
                session.add(item)
                await session.flush()  # Flush to get the generated ID
                item_id = item.id
            logger.info(
                f"Created knowledge base item {item_id} for project {project_id}"
            )
            return item_id

    async def update_knowledge_base_item_embedding_id(
        self, item_id: str, embedding_id: str, user_id: str, project_id: str
    ) -> bool:
        """Updates the embedding_id for a specific knowledge base item."""
        # Use self.Session() instead of self.async_session_factory()
        async with self.Session() as session:
            async with session.begin():
                result = await session.execute(
                    update(KnowledgeBaseItem)
                    .where(
                        KnowledgeBaseItem.id == item_id,
                        KnowledgeBaseItem.user_id == user_id,  # Ensure ownership
                        KnowledgeBaseItem.project_id
                        == project_id,  # Ensure project match
                    )
                    .values(embedding_id=embedding_id, updated_at=func.now())
                )
                if result.rowcount == 1:
                    logger.info(
                        f"Updated embedding ID for knowledge base item {item_id}"
                    )
                    return True
                else:
                    logger.warning(
                        f"Failed to update embedding ID for item {item_id} (not found or unauthorized)."
                    )
                    return False

    async def delete_knowledge_base_item_by_id(
        self, item_id: str, user_id: str, project_id: str
    ) -> bool:
        """Deletes a knowledge base item by its primary ID."""
        # Use self.Session() instead of self.async_session_factory()
        async with self.Session() as session:
            async with session.begin():
                result = await session.execute(
                    delete(KnowledgeBaseItem).where(
                        KnowledgeBaseItem.id == item_id,
                        KnowledgeBaseItem.user_id == user_id,  # Ensure ownership
                        KnowledgeBaseItem.project_id
                        == project_id,  # Ensure project match
                    )
                )
                if result.rowcount == 1:
                    logger.info(f"Deleted knowledge base item {item_id}")
                    return True
                else:
                    logger.warning(
                        f"Failed to delete knowledge base item {item_id} (not found or unauthorized)."
                    )
                    return False

    async def get_knowledge_base_item_by_embedding_id(
        self, embedding_id: str, user_id: str, project_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a knowledge base item by its embedding ID."""
        try:
            async with self.Session() as session:
                # First try to find in knowledge_base_items
                query = select(KnowledgeBaseItem).where(
                    and_(
                        KnowledgeBaseItem.embedding_id == embedding_id,
                        KnowledgeBaseItem.user_id == user_id,
                        KnowledgeBaseItem.project_id == project_id,
                    )
                )
                result = await session.execute(query)
                item = result.scalar_one_or_none()

                if item:
                    return {
                        "id": item.id,
                        "type": item.type,
                        "content": item.content,
                        "metadata": item.item_metadata,
                        "embedding_id": item.embedding_id,
                        "source": item.source,
                    }

                # If not found, try chapters
                query = select(Chapter).where(
                    and_(
                        Chapter.embedding_id == embedding_id,
                        Chapter.user_id == user_id,
                        Chapter.project_id == project_id,
                    )
                )
                result = await session.execute(query)
                chapter = result.scalar_one_or_none()

                if chapter:
                    return {
                        "id": chapter.id,
                        "type": "chapter",
                        "content": chapter.content,
                        "metadata": {"title": chapter.title},
                        "embedding_id": chapter.embedding_id,
                        "source": f"Chapter {chapter.chapter_number}",
                    }

                # If not found, try codex items
                query = select(CodexItem).where(
                    and_(
                        CodexItem.embedding_id == embedding_id,
                        CodexItem.user_id == user_id,
                        CodexItem.project_id == project_id,
                    )
                )
                result = await session.execute(query)
                codex_item = result.scalar_one_or_none()

                if codex_item:
                    return {
                        "id": codex_item.id,
                        "type": codex_item.type,
                        "content": codex_item.description,
                        "metadata": {
                            "name": codex_item.name,
                            "subtype": codex_item.subtype,
                        },
                        "embedding_id": codex_item.embedding_id,
                        "source": codex_item.name,
                    }

                return None

        except Exception as e:
            logger.error(
                f"Error getting knowledge base item by embedding ID {embedding_id}: {str(e)}"
            )
            raise

    async def update_project_architect_mode(
        self, project_id: str, user_id: str, enabled: bool
    ) -> Optional[Dict[str, Any]]:
        """Updates the architect_mode_enabled flag for a specific project."""
        try:
            async with self.Session() as session:
                stmt = (
                    update(Project)
                    .where(Project.id == project_id, Project.user_id == user_id)
                    .values(
                        architect_mode_enabled=enabled,
                        updated_at=datetime.now(timezone.utc),  # Also update timestamp
                    )
                    .returning(Project)  # Return the updated row
                )
                result = await session.execute(stmt)
                await session.commit()
                updated_project = result.scalars().first()

                if updated_project:
                    return updated_project.to_dict()
                else:
                    logger.warning(
                        f"Project {project_id} not found or user {user_id} not authorized to update architect mode."
                    )
                    return None  # Indicate not found or not authorized
        except Exception as e:
            logger.error(
                f"Error updating project architect mode for {project_id}: {e}",
                exc_info=True,
            )
            raise  # Re-raise to be handled by endpoint

    async def save_architect_chat_history(
        self,
        user_id: str,
        project_id: str,
        history: List[Dict[str, Any]],
    ):
        await self.save_chat_history(user_id, project_id, history, AgentType.ARCHITECT)

    async def get_architect_chat_history(
        self,
        user_id: str,
        project_id: str,
    ) -> List[Dict[str, Any]]:
        return await self.get_chat_history(user_id, project_id, AgentType.ARCHITECT)

    async def delete_architect_chat_history(
        self,
        user_id: str,
        project_id: str,
    ) -> bool:
        return await self.delete_chat_history(user_id, project_id, AgentType.ARCHITECT)


    async def create_character_voice_profile(
        self,
        codex_item_id: str,
        user_id: str,  # Add user_id
        project_id: str,  # Add project_id
        voice_profile_data: Dict[str, Any],
    ) -> str:
        try:
            async with self.Session() as session:
                profile = CharacterVoiceProfile(
                    codex_item_id=codex_item_id,
                    user_id=user_id,  # Pass user_id
                    project_id=project_id,  # Pass project_id
                    vocabulary=voice_profile_data.get("vocabulary"),
                    sentence_structure=voice_profile_data.get("sentence_structure"),
                    speech_patterns_tics=voice_profile_data.get("speech_patterns_tics"),
                    tone=voice_profile_data.get("tone"),
                    habits_mannerisms=voice_profile_data.get("habits_mannerisms"),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(profile)
                await session.commit()
                return profile.id
        except Exception as e:
            logger.error(
                f"Error creating character voice profile: {str(e)}", exc_info=True
            )
            raise

    async def get_character_voice_profile_by_codex_id(
        self, codex_item_id: str, user_id: str, project_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(CharacterVoiceProfile).where(
                    CharacterVoiceProfile.codex_item_id == codex_item_id,
                    CharacterVoiceProfile.user_id == user_id,
                    CharacterVoiceProfile.project_id == project_id,
                )
                result = await session.execute(query)
                profile = result.scalars().first()
                return profile.to_dict() if profile else None
        except Exception as e:
            logger.error(
                f"Error getting character voice profile by codex_item_id: {str(e)}",
                exc_info=True,
            )
            raise

    async def update_character_voice_profile(
        self,
        codex_item_id: str,
        user_id: str,
        project_id: str,
        voice_profile_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(CharacterVoiceProfile).where(
                    CharacterVoiceProfile.codex_item_id == codex_item_id,
                    CharacterVoiceProfile.user_id == user_id,
                    CharacterVoiceProfile.project_id == project_id,
                )
                result = await session.execute(query)
                profile = result.scalars().first()

                if profile:
                    if "vocabulary" in voice_profile_data:
                        profile.vocabulary = voice_profile_data["vocabulary"]
                    if "sentence_structure" in voice_profile_data:
                        profile.sentence_structure = voice_profile_data[
                            "sentence_structure"
                        ]
                    if "speech_patterns_tics" in voice_profile_data:
                        profile.speech_patterns_tics = voice_profile_data[
                            "speech_patterns_tics"
                        ]
                    if "tone" in voice_profile_data:
                        profile.tone = voice_profile_data["tone"]
                    if "habits_mannerisms" in voice_profile_data:
                        profile.habits_mannerisms = voice_profile_data[
                            "habits_mannerisms"
                        ]
                    profile.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    await session.refresh(profile)
                    return profile.to_dict()
                else:
                    # Optionally, create if not found, or raise an error
                    # For now, let's return None if not found to update
                    logger.warning(
                        f"CharacterVoiceProfile not found for codex_item_id {codex_item_id} to update."
                    )
                    return None
        except Exception as e:
            logger.error(
                f"Error updating character voice profile: {str(e)}", exc_info=True
            )
            raise

    async def get_or_create_character_voice_profile(
        self,
        codex_item_id: str,
        user_id: str,
        project_id: str,
        voice_profile_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Try to get existing profile
        existing_profile = await self.get_character_voice_profile_by_codex_id(
            codex_item_id, user_id, project_id
        )
        if existing_profile:
            if voice_profile_data:  # If data provided, update it
                updated_profile = await self.update_character_voice_profile(
                    codex_item_id, user_id, project_id, voice_profile_data
                )
                if updated_profile:
                    return updated_profile
                # Handle update failure, though unlikely if get succeeded
                logger.error(
                    f"Failed to update existing voice profile for {codex_item_id}"
                )
                return existing_profile  # return stale existing one on error?
            return existing_profile

        # If not found, create a new one
        if voice_profile_data is None:
            voice_profile_data = {}  # Create with empty data if none provided

        profile_id = await self.create_character_voice_profile(
            codex_item_id, user_id, project_id, voice_profile_data
        )
        # Fetch the newly created profile to return its dict representation
        new_profile = await self.get_character_voice_profile_by_codex_id(
            codex_item_id, user_id, project_id
        )
        if not new_profile:
            raise Exception(
                f"Failed to create or retrieve character voice profile for {codex_item_id}"
            )
        return new_profile

    async def delete_character_voice_profile(
        self, codex_item_id: str, user_id: str, project_id: str
    ) -> bool:
        try:
            async with self.Session() as session:
                stmt = delete(CharacterVoiceProfile).where(
                    CharacterVoiceProfile.codex_item_id == codex_item_id,
                    CharacterVoiceProfile.user_id == user_id,
                    CharacterVoiceProfile.project_id == project_id,
                )
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(
                f"Error deleting character voice profile: {str(e)}", exc_info=True
            )
            raise

    async def get_user_subscription_info(
        self, user_id: str
    ) -> Optional[Dict[str, str]]:
        """Retrieves a user's subscription plan and status."""
        try:
            async with self.Session() as session:
                query = select(User.subscription_plan, User.subscription_status).where(
                    User.id == user_id
                )
                result = await session.execute(query)
                user_info = result.one_or_none()
                if user_info:
                    return {
                        "plan": user_info.subscription_plan,
                        "status": user_info.subscription_status,
                    }
                else:
                    logger.warning(
                        f"User {user_id} not found for subscription info retrieval."
                    )
                    return None
        except Exception as e:
            logger.error(
                f"Error getting user subscription info for {user_id}: {str(e)}",
                exc_info=True,
            )
            return None

    async def get_project_structure(
        self, project_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        async with self.Session() as session:
            project = await session.get(Project, project_id)
            if project and project.user_id == user_id:
                structure = project.project_structure

                # Ensure field consistency in the structure (name/title fields)
                if (
                    structure
                    and isinstance(structure, dict)
                    and "project_structure" in structure
                ):

                    def normalize_fields(items):
                        for item in items:
                            # Ensure consistency between 'name' and 'title' fields
                            if "name" in item and "title" not in item:
                                item["title"] = item["name"]
                            elif "title" in item and "name" not in item:
                                item["name"] = item["title"]

                            # Process children recursively
                            if "children" in item and isinstance(
                                item["children"], list
                            ):
                                normalize_fields(item["children"])

                    if "project_structure" in structure and isinstance(
                        structure["project_structure"], list
                    ):
                        normalize_fields(structure["project_structure"])

                return structure
            return None

    async def update_project_structure(
        self,
        project_id: str,
        structure: List[Dict[str, Any]],
        user_id: str,
    ) -> Optional[List[Dict[str, Any]]]:
        async with self.Session() as session:
            try:
                project = await session.get(Project, project_id)
                if not project or project.user_id != user_id:
                    self.logger.warning(
                        f"Project not found or access denied for user {user_id} on project {project_id}"
                    )
                    return None

                chapters_to_update = {}  # {chapter_id: parent_id}
                folders_only_structure = []

                def process_items_recursive(
                    items, parent_id=None, parent_folder_list=None
                ):
                    """
                    Recursively traverses the structure to:
                    1. Populate `chapters_to_update` with {chapter_id: parent_id}.
                    2. Build the `folders_only_structure` by appending folders to their parent's list.
                    """
                    # Use a direct reference to the root list if no parent list is provided
                    current_folder_list = (
                        parent_folder_list
                        if parent_folder_list is not None
                        else folders_only_structure
                    )

                    for item in items:
                        item_id = item.get("id")
                        item_type = item.get("type")

                        if item_type == "chapter":
                            chapters_to_update[item_id] = parent_id
                        elif item_type in ["folder", "act", "stage", "substage"]:
                            folder_item = {
                                "id": item_id,
                                "type": "folder",  # Standardize to 'folder'
                                "title": item.get(
                                    "title", item.get("name", "Untitled")
                                ),
                                "description": item.get("description", ""),
                                "children": [],
                            }
                            current_folder_list.append(folder_item)

                            if "children" in item and item["children"]:
                                # Recurse, passing the new folder's children list to be populated
                                process_items_recursive(
                                    item["children"], item_id, folder_item["children"]
                                )

                # Start the traversal to collect chapter-to-folder mappings
                process_items_recursive(structure)

                # Persist the full structure (including chapters) to the database
                project.project_structure = {"project_structure": structure}
                session.add(project)

                # Now, update the structure_item_id for all chapters
                all_project_chapters = (
                    (
                        await session.execute(
                            select(Chapter).where(
                                Chapter.project_id == project_id,
                                Chapter.user_id == user_id,
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

                for chapter in all_project_chapters:
                    # Only update chapters that were explicitly part of the submitted structure.
                    if chapter.id in chapters_to_update:
                        parent_id = chapters_to_update.get(chapter.id)
                        if chapter.structure_item_id != parent_id:
                            chapter.structure_item_id = parent_id

                await session.commit()
                self.logger.info(
                    f"Successfully updated project structure for project {project_id}"
                )

                # We can return the original structure as confirmation,
                # as the GET endpoint is responsible for the final assembly.
                return structure

            except Exception as e:
                await session.rollback()
                self.logger.error(
                    f"Failed to update project structure for project {project_id}: {e}",
                    exc_info=True,
                )
                return None

    async def get_openrouter_api_key(self, user_id: str) -> Optional[str]:
        """Retrieves the OpenRouter API key for a user."""
        async with self.Session() as session:
            user = await session.get(User, user_id)
            if user:
                return user.openrouter_api_key
            return None

    async def save_anthropic_api_key(
        self, user_id: str, anthropic_api_key: Optional[str]
    ) -> None:
        """Saves or clears the Anthropic API key for a user."""
        async with self.Session() as session:
            user = await session.get(User, user_id)
            if user:
                user.anthropic_api_key = anthropic_api_key
                user.updated_at = datetime.now(timezone.utc)
                await session.commit()
                logger.info(
                    f"Anthropic API key {'saved' if anthropic_api_key else 'cleared'} for user {user_id}"
                )
            else:
                logger.warning(
                    f"User {user_id} not found for saving Anthropic API key."
                )

    async def get_anthropic_api_key(self, user_id: str) -> Optional[str]:
        """Retrieves the Anthropic API key for a user."""
        async with self.Session() as session:
            user = await session.get(User, user_id)
            if user:
                return user.anthropic_api_key
            return None

    async def save_openai_api_key(
        self, user_id: str, openai_api_key: Optional[str]
    ) -> None:
        """Saves or clears the OpenAI API key for a user."""
        async with self.Session() as session:
            user = await session.get(User, user_id)
            if user:
                user.openai_api_key = openai_api_key
                user.updated_at = datetime.now(timezone.utc)
                await session.commit()
                logger.info(
                    f"OpenAI API key {'saved' if openai_api_key else 'cleared'} for user {user_id}"
                )
            else:
                logger.warning(f"User {user_id} not found for saving OpenAI API key.")

    async def get_openai_api_key(self, user_id: str) -> Optional[str]:
        """Retrieves the OpenAI API key for a user."""
        async with self.Session() as session:
            user = await session.get(User, user_id)
            if user:
                return user.openai_api_key
            return None


db_instance = Database()

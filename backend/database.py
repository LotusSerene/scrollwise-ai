import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, joinedload
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, String, Integer, Boolean, Text, ForeignKey, JSON, UniqueConstraint, DateTime, and_, func, QueuePool, select, delete, or_
from sqlalchemy.dialects.postgresql import TEXT, JSONB
import json
import os
from dotenv import load_dotenv
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import selectinload
from cryptography.fernet import Fernet
from contextlib import asynccontextmanager
from base64 import b64encode, b64decode
from models import CodexItemType, WorldbuildingSubtype
from supabase import create_client, Client

load_dotenv()

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    api_key = Column(String)
    model_settings = Column(Text)
    
    # Add the projects relationship
    projects = relationship("Project", back_populates="user")

class Project(Base):
    __tablename__ = 'projects'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    universe_id = Column(String, ForeignKey('universes.id'), nullable=True)
    target_word_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Add the user relationship
    user = relationship("User", back_populates="projects")

    # Update relationships to include cascade deletes
    chapters = relationship("Chapter", back_populates="project", cascade="all, delete-orphan")
    validity_checks = relationship("ValidityCheck", back_populates="project", cascade="all, delete-orphan")
    codex_items = relationship("CodexItem", back_populates="project", cascade="all, delete-orphan")
    chat_histories = relationship("ChatHistory", back_populates="project", cascade="all, delete-orphan")
    presets = relationship("Preset", back_populates="project", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="project", cascade="all, delete-orphan")
    locations = relationship("Location", back_populates="project", cascade="all, delete-orphan")
    character_relationships = relationship("CharacterRelationship", back_populates="project", cascade="all, delete-orphan")
    character_relationship_analyses = relationship("CharacterRelationshipAnalysis", back_populates="project", cascade="all, delete-orphan")
    event_connections = relationship("EventConnection", back_populates="project", cascade="all, delete-orphan")
    location_connections = relationship("LocationConnection", back_populates="project", cascade="all, delete-orphan")

    def to_dict(self):
        base_dict = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'universe_id': self.universe_id,
            'user_id': self.user_id,
            'targetWordCount': self.target_word_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        return base_dict



class Chapter(Base):
    __tablename__ = 'chapters'
    id = Column(String, primary_key=True)
    title = Column(String(500))  # Increase the length limit to 500
    content = Column(Text)  # Text type for long content
    chapter_number = Column(Integer, nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    embedding_id = Column(String)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    last_processed_position = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    project = relationship("Project", back_populates="chapters")
    processed_types = Column(JSON, default=list, nullable=False)  # Changed from lambda to list
    validity_checks = relationship("ValidityCheck", back_populates="chapter", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'chapter_number': self.chapter_number,
            'embedding_id': self.embedding_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ValidityCheck(Base):
    __tablename__ = 'validity_checks'
    id = Column(String, primary_key=True)
    chapter_id = Column(String, ForeignKey('chapters.id'), nullable=False)
    chapter_title = Column(String)
    is_valid = Column(Boolean)
    overall_score = Column(Integer)
    general_feedback = Column(Text)
    style_guide_adherence_score = Column(Integer)
    style_guide_adherence_explanation = Column(Text)
    continuity_score = Column(Integer)
    continuity_explanation = Column(Text)
    areas_for_improvement = Column(JSON)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Add the relationship definition
    project = relationship("Project", back_populates="validity_checks")
    chapter = relationship("Chapter", back_populates="validity_checks")

    def to_dict(self):
        return {
            'id': self.id,
            'chapterId': self.chapter_id,
            'chapterTitle': self.chapter_title,
            'isValid': self.is_valid,
            'overallScore': self.overall_score,
            'generalFeedback': self.general_feedback,
            'styleGuideAdherenceScore': self.style_guide_adherence_score,
            'styleGuideAdherenceExplanation': self.style_guide_adherence_explanation,
            'continuityScore': self.continuity_score,
            'continuityExplanation': self.continuity_explanation,
            'areasForImprovement': self.areas_for_improvement
        }

class CodexItem(Base):
    __tablename__ = 'codex_items'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    type = Column(String, nullable=False)  # Will store the enum value as string
    subtype = Column(String)  # Will store the enum value as string
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    embedding_id = Column(String)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    # Add these fields for character-specific information
    backstory = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    # Add these relationships
    relationships = relationship("CharacterRelationship", 
                                 foreign_keys="CharacterRelationship.character_id",
                                 back_populates="character")
    related_to = relationship("CharacterRelationship",
                              foreign_keys="CharacterRelationship.related_character_id",
                              back_populates="related_character")
    events = relationship("Event", back_populates="character")
    project = relationship("Project", back_populates="codex_items")

    def to_dict(self):
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'type': self.type,  # This will be the string value of the enum
            'subtype': self.subtype,
            'backstory': self.backstory if self.type == CodexItemType.CHARACTER.value else None,
            'embedding_id': self.embedding_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        return data

class ChatHistory(Base):
    __tablename__ = 'chat_history'
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    messages = Column(Text, nullable=False)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    project = relationship("Project", back_populates="chat_histories")

class Preset(Base):
    __tablename__ = 'presets'
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    name = Column(String, nullable=False)
    data = Column(JSON, nullable=False)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'name', name='_user_preset_uc'),)
    project = relationship("Project", back_populates="presets")

class Universe(Base):
    __tablename__ = 'universes'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
class ProcessedChapter(Base):
    __tablename__ = 'processed_chapters'
    id = Column(String, primary_key=True)
    chapter_id = Column(String, ForeignKey('chapters.id'), nullable=False)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    processed_at = Column(DateTime, default=datetime.now(timezone.utc))
    function_name = Column(String, default='default_function_name', nullable=False)

class CharacterRelationship(Base):
    __tablename__ = 'character_relationships'
    id = Column(String, primary_key=True)
    character_id = Column(String, ForeignKey('codex_items.id'), nullable=False)
    related_character_id = Column(String, ForeignKey('codex_items.id'), nullable=False)
    relationship_type = Column(String, nullable=False)
    description = Column(Text, nullable=True)  # Add this line
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)

    # Update these relationship definitions
    character = relationship("CodexItem", 
                             foreign_keys=[character_id], 
                             back_populates="relationships")
    related_character = relationship("CodexItem", 
                                     foreign_keys=[related_character_id],
                                     back_populates="related_to")
    project = relationship("Project", back_populates="character_relationships")

    def to_dict(self):
        return {
            'id': self.id,
            'character_id': self.character_id,
            'related_character_id': self.related_character_id,
            'relationship_type': self.relationship_type,
            'description': self.description or ''  # Add this line
        }

class Event(Base):
    __tablename__ = 'events'
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    date = Column(DateTime, nullable=False)
    character_id = Column(String, ForeignKey('codex_items.id'), nullable=True)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)  # Added this line
    location_id = Column(String, ForeignKey('locations.id'), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    character = relationship("CodexItem", back_populates="events")
    location = relationship("Location", back_populates="events")
    project = relationship("Project", back_populates="events")

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'date': self.date.isoformat(),
            'character_id': self.character_id,
            'location_id': self.location_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Location(Base):
    __tablename__ = 'locations'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    coordinates = Column(String, nullable=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    events = relationship("Event", back_populates="location")
    project = relationship("Project", back_populates="locations")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'coordinates': self.coordinates,
            'project_id': self.project_id,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class CharacterBackstory(Base):
    __tablename__ = 'character_backstories'
    id = Column(String, primary_key=True)
    character_id = Column(String, ForeignKey('codex_items.id'), nullable=False)
    content = Column(Text, nullable=False)
    chapter_id = Column(String, ForeignKey('chapters.id'), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'character_id': self.character_id,
            'content': self.content,
            'chapter_id': self.chapter_id,
            'created_at': self.created_at.isoformat()
        }


class CharacterRelationshipAnalysis(Base):
    __tablename__ = 'character_relationship_analyses'
    id = Column(String, primary_key=True)
    character1_id = Column(String, ForeignKey('codex_items.id'), nullable=False)
    character2_id = Column(String, ForeignKey('codex_items.id'), nullable=False)
    relationship_type = Column(String, nullable=False)
    description = Column(Text)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="character_relationship_analyses")

    def to_dict(self):
        return {
            'id': self.id,
            'character1_id': self.character1_id,
            'character2_id': self.character2_id,
            'relationship_type': self.relationship_type,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class BaseConnection(Base):
    __abstract__ = True
    
    id = Column(String, primary_key=True)
    description = Column(Text, nullable=False)
    connection_type = Column(String, nullable=False)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
                       onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'connection_type': self.connection_type,
            'project_id': self.project_id,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class EventConnection(BaseConnection):
    __tablename__ = 'event_connections'
    
    event1_id = Column(String, ForeignKey('events.id'), nullable=False)
    event2_id = Column(String, ForeignKey('events.id'), nullable=False)
    impact = Column(Text)
    
    event1 = relationship("Event", foreign_keys=[event1_id])
    event2 = relationship("Event", foreign_keys=[event2_id])
    project = relationship("Project", back_populates="event_connections")
    
    def to_dict(self):
        result = super().to_dict()
        result.update({
            'event1_id': self.event1_id,
            'event2_id': self.event2_id,
            'impact': self.impact
        })
        return result

class LocationConnection(BaseConnection):
    __tablename__ = 'location_connections'
    
    location1_id = Column(String, ForeignKey('locations.id'), nullable=False)
    location2_id = Column(String, ForeignKey('locations.id'), nullable=False)
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
        result.update({
            'location1_id': self.location1_id,
            'location2_id': self.location2_id,
            'location1_name': self.location1_name,
            'location2_name': self.location2_name,
            'travel_route': self.travel_route,
            'cultural_exchange': self.cultural_exchange
        })
        return result

class ConnectionService:
    def __init__(self, logger):
        self.logger = logger

    async def get_connections(self, model_class, project_id: str, user_id: str) -> List[Dict[str, Any]]:
        try:
            query = (
                select(model_class)
                .filter_by(project_id=project_id, user_id=user_id)
                .options(
                    joinedload(model_class.location1 if hasattr(model_class, 'location1') else model_class.event1),
                    joinedload(model_class.location2 if hasattr(model_class, 'location2') else model_class.event2)
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
                        connection_dict.update({
                            'event1_title': conn.event1.title,
                            'event2_title': conn.event2.title
                        })
                elif isinstance(conn, LocationConnection):
                    if conn.location1 and conn.location2:
                        connection_dict.update({
                            'location1_name': conn.location1.name,
                            'location2_name': conn.location2.name
                        })
                        
                result.append(connection_dict)
                
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting connections: {str(e)}")
            raise



class KnowledgeBaseItem(Base):
    __tablename__ = 'knowledge_base_items'
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)

class Database:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        
        # Initialize Supabase client
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set")
            
        self.supabase: Client = create_client(supabase_url, supabase_key)

    async def get_projects(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            response = self.supabase.table('projects').select('*').eq('user_id', user_id).execute()
            return response.data
        except Exception as e:
            self.logger.error(f"Error getting projects: {str(e)}")
            raise

    async def get_universes(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            response = self.supabase.table('universes').select('*').eq('user_id', user_id).execute()
            return response.data
        except Exception as e:
            self.logger.error(f"Error getting universes: {str(e)}")
            raise

    async def check_user_approval(self, user_id: str) -> bool:
        try:
            response = self.supabase.table('user_approvals').select('is_approved').eq('id', user_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0].get('is_approved', False)
            return False
        except Exception as e:
            self.logger.error(f"Error checking user approval: {str(e)}")
            return False

    async def initialize(self):
        """Initialize the database connection."""
        # No need for explicit initialization with Supabase
        pass

    async def create_user(self, email: str, password: str):
        try:
            # Use Supabase auth to create user
            response = await self.supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            return response.user.id
        except Exception as e:
            self.logger.error(f"Error creating user: {str(e)}")
            raise

    async def get_user_by_email(self, email: str):
        try:
            # Query Supabase for user
            response = await self.supabase.from_('users').select('*').eq('email', email).single()
            return response.data
        except Exception as e:
            self.logger.error(f"Error getting user: {str(e)}")
            return None

    async def get_all_chapters(self, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                chapters = await session.execute(select(Chapter).filter_by(user_id=user_id, project_id=project_id).order_by(Chapter.chapter_number))
                chapters = chapters.scalars().all()
                return [chapter.to_dict() for chapter in chapters]
            except Exception as e:
                self.logger.error(f"Error fetching all chapters: {str(e)}")
                raise

    async def create_chapter(self, title: str, content: str, user_id: str, project_id: str, chapter_number: Optional[int] = None, embedding_id: Optional[str] = None) -> str:
        async with await self.get_session() as session:
            try:
                # Log initial chapter creation attempt
               # self.logger.info(f"Creating new chapter - Title: {title}, User: {user_id}, Project: {project_id}")
                
                # Get the highest chapter number for this project if not provided
                if chapter_number is None:
                    latest_chapter = await session.execute(select(Chapter).filter_by(project_id=project_id).order_by(Chapter.chapter_number.desc()))
                    latest_chapter = latest_chapter.scalars().first()
                    chapter_number = (latest_chapter.chapter_number + 1) if latest_chapter else 1
                    #self.logger.debug(f"Assigned chapter number: {chapter_number}")

                chapter = Chapter(
                    id=str(uuid.uuid4()),
                    title=title,
                    content=content,
                    chapter_number=chapter_number,
                    user_id=user_id,
                    project_id=project_id,
                    embedding_id=embedding_id,
                    processed_types=[]
                )
                session.add(chapter)
                await session.commit()
                
                #self.logger.info(f"Successfully created chapter - ID: {chapter.id}, Number: {chapter_number}")
                return chapter.id
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error creating chapter: {str(e)}", exc_info=True)
                raise

    async def update_chapter(self, chapter_id, title, content, user_id, project_id):
        async with await self.get_session() as session:
            try:
                chapter = await session.get(Chapter, chapter_id)
                if chapter and chapter.user_id == user_id and chapter.project_id == project_id:
                    chapter.title = title
                    chapter.content = content
                    await session.commit()
                    return chapter.to_dict()
                raise
            except Exception as e:
                self.logger.error(f"Error getting chapter: {str(e)}")
                raise

    async def delete_chapter(self, chapter_id, user_id, project_id):
        async with await self.get_session() as session:
            try:
                # First, delete related validity checks
                await session.execute(delete(ValidityCheck).where(ValidityCheck.chapter_id == chapter_id, ValidityCheck.user_id == user_id, ValidityCheck.project_id == project_id))

                # Then, delete the chapter
                chapter = await session.get(Chapter, chapter_id)
                if chapter and chapter.user_id == user_id and chapter.project_id == project_id:
                    await session.delete(chapter)
                    await session.commit()
                    return True
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting chapter: {str(e)}")
                raise

    async def get_chapter(self, chapter_id: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                chapter = await session.get(Chapter, chapter_id)
                if chapter and chapter.user_id == user_id and chapter.project_id == project_id:
                    return chapter.to_dict()
                raise Exception("Chapter not found")  # Add a specific exception message
            except Exception as e:
                self.logger.error(f"Error getting chapter: {str(e)}")
                raise

    async def get_all_validity_checks(self, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                checks = await session.execute(select(ValidityCheck).filter_by(user_id=user_id, project_id=project_id))
                checks = checks.scalars().all()
                return [check.to_dict() for check in checks]
            except Exception as e:
                self.logger.error(f"Error getting all validity checks: {str(e)}")
                raise

    async def delete_validity_check(self, check_id, user_id, project_id):
        async with await self.get_session() as session:
            try:
                validity_check = await session.get(ValidityCheck, check_id)
                if validity_check and validity_check.user_id == user_id and validity_check.project_id == project_id:
                    await session.delete(validity_check)
                    await session.commit()
                    return True
                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting validity check: {str(e)}")
                raise


    async def create_codex_item(self, name: str, description: str, type: str, subtype: Optional[str], user_id: str, project_id: str) -> str:
        async with await self.get_session() as session:
            try:
                current_time = datetime.now(timezone.utc).replace(tzinfo=None)
                item = CodexItem(
                    id=str(uuid.uuid4()),
                    name=name,
                    description=description,
                    type=type,
                    subtype=subtype,
                    user_id=user_id,
                    project_id=project_id,
                    created_at=current_time,
                    updated_at=current_time,
                )
                session.add(item)
                await session.commit()
                return item.id
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error creating codex item: {str(e)}")
                raise

    async def get_all_codex_items(self, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                codex_items = await session.execute(select(CodexItem).filter_by(user_id=user_id, project_id=project_id))
                codex_items = codex_items.scalars().all()
                return [item.to_dict() for item in codex_items]
            except Exception as e:
                self.logger.error(f"Error getting all codex items: {str(e)}")
                raise

    async def update_codex_item(self, item_id: str, name: str, description: str, type: str, subtype: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                codex_item = await session.get(CodexItem, item_id)
                if codex_item and codex_item.user_id == user_id and codex_item.project_id == project_id:
                    codex_item.name = name
                    codex_item.description = description
                    codex_item.type = type
                    codex_item.subtype = subtype
                    codex_item.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return codex_item.to_dict()
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating codex item: {str(e)}")
                raise

    async def delete_codex_item(self, item_id: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                # First, delete related character relationship analyses
                await session.execute(delete(CharacterRelationshipAnalysis).where(
                    (CharacterRelationshipAnalysis.character1_id == item_id) |
                    (CharacterRelationshipAnalysis.character2_id == item_id)
                ))

                codex_item = await session.get(CodexItem, item_id)
                if codex_item and codex_item.user_id == user_id and codex_item.project_id == project_id:
                    events = await session.execute(select(Event).filter_by(character_id=item_id))
                    events = events.scalars().all()
                    for event in events:
                        event.character_id = None
                        event.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

                    await session.delete(codex_item)
                    await session.commit()
                    return True
                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting codex item: {str(e)}")
                raise

    async def get_codex_item_by_id(self, item_id: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                codex_item = await session.get(CodexItem, item_id)
                if codex_item and codex_item.user_id == user_id and codex_item.project_id == project_id:
                    return codex_item.to_dict()
                raise Exception("Codex item not found")  # Add a specific exception message
            except Exception as e:
                self.logger.error(f"Error getting API key: {str(e)}")
                raise

    async def save_api_key(self, user_id, api_key):
        async with await self.get_session() as session:
            try:
                user = await session.get(User, user_id)
                if user:
                    # Encrypt the API key before saving
                    encrypted_key = self.fernet.encrypt(api_key.encode())
                    user.api_key = b64encode(encrypted_key).decode()
                    await session.commit()
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error saving API key: {str(e)}")
                raise

    async def get_api_key(self, user_id):
        async with await self.get_session() as session:
            try:
                user = await session.get(User, user_id)
                if user and user.api_key:
                    # Decrypt the API key before returning
                    encrypted_key = b64decode(user.api_key)
                    decrypted_key = self.fernet.decrypt(encrypted_key)
                    return decrypted_key.decode()
                return None
            except Exception as e:
                self.logger.error(f"Error getting API key: {str(e)}")
                raise

    async def remove_api_key(self, user_id):
        async with await self.get_session() as session:
            try:
                user = await session.get(User, user_id)
                if user:
                    user.api_key = None
                    await session.commit()
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error removing API key: {str(e)}")
                raise

    async def save_model_settings(self, user_id, settings):
        async with await self.get_session() as session:
            try:
                user = await session.get(User, user_id)
                if user:
                    user.model_settings = json.dumps(settings)
                    await session.commit()
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error saving model settings: {str(e)}")
                raise

    async def create_location(self, name: str, description: str, coordinates: Optional[str], user_id: str, project_id: str) -> str:
        async with await self.get_session() as session:
            try:
                location = Location(
                    id=str(uuid.uuid4()),
                    name=name,
                    description=description,
                    coordinates=coordinates,
                    user_id=user_id,
                    project_id=project_id,
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )
                session.add(location)
                await session.commit()
                return location.id
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error creating location: {str(e)}")
                raise

    async def delete_location(self, location_id: str, project_id: str, user_id: str) -> bool:
        async with await self.get_session() as session:
            try:
                # First verify the location exists and belongs to the user/project
                location = await session.get(Location, location_id)
                if location and location.user_id == user_id and location.project_id == project_id:
                    # Delete associated connections first
                    await session.execute(
                        delete(LocationConnection).where(
                            or_(
                                LocationConnection.location1_id == location_id,
                                LocationConnection.location2_id == location_id
                            )
                        )
                    )
                    # Then delete the location
                    await session.delete(location)
                    await session.commit()
                    return True
                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting location: {str(e)}")
                raise

    async def delete_event(self, event_id: str, project_id: str, user_id: str) -> bool:
        async with await self.get_session() as session:
            try:
                # First delete any event connections that reference this event
                await session.execute(
                    delete(EventConnection).where(
                        or_(
                            EventConnection.event1_id == event_id,
                            EventConnection.event2_id == event_id
                        )
                    )
                )
                
                # Then delete the event itself
                event = await session.get(Event, event_id)
                if event and event.user_id == user_id and event.project_id == project_id:
                    await session.delete(event)
                    await session.commit()
                    return True
                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting event: {str(e)}")
                raise

    async def mark_chapter_processed(self, chapter_id: str, user_id: str, process_type: str) -> None:
        async with await self.get_session() as session:
            try:
                chapter = await session.get(Chapter, chapter_id)
                if chapter and chapter.user_id == user_id:
                    if not chapter.processed_types:
                        chapter.processed_types = []
                    if process_type not in chapter.processed_types:
                        chapter.processed_types.append(process_type)
                    await session.commit()
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error marking chapter as processed: {str(e)}")
                raise

    async def is_chapter_processed_for_type(self, chapter_id: str, process_type: str) -> bool:
        async with await self.get_session() as session:
            try:
                chapter = await session.get(Chapter, chapter_id)
                if chapter and isinstance(chapter.processed_types, list):
                    return process_type in chapter.processed_types
                return False
            except Exception as e:
                self.logger.error(f"Error marking chapter as processed: {str(e)}")
                raise


    async def get_event_by_id(self, event_id: str, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                event = await session.get(Event, event_id)
                if event and event.user_id == user_id and event.project_id == project_id:
                    return event.to_dict()
                raise
            except Exception as e:
                self.logger.error(f"Error checking chapter processed status: {str(e)}")
                raise

    async def get_location_by_id(self, location_id: str, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                location = await session.get(Location, location_id)
                if location and location.user_id == user_id and location.project_id == project_id:
                    return location.to_dict()
                return None
            except Exception as e:
                self.logger.error(f"Error getting location by ID: {str(e)}")
                raise

    async def update_codex_item_embedding_id(self, item_id, embedding_id):
        async with await self.get_session() as session:
            try:
                codex_item = await session.get(CodexItem, item_id)
                if codex_item:
                    codex_item.embedding_id = embedding_id
                    await session.commit()
                    return True
                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating codex item embedding_id: {str(e)}")
                raise


    async def create_project(self, name: str, description: str, user_id: str, universe_id: Optional[str] = None) -> str:
        try:
            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
            
            # Create project data
            project_data = {
                "name": name,
                "description": description,
                "user_id": user_id,
                "universe_id": universe_id,
                "created_at": current_time.isoformat(),
                "updated_at": current_time.isoformat()
            }
            
            # Insert into Supabase
            response = self.supabase.table('projects').insert(project_data).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]['id']
            else:
                raise Exception("Failed to create project")
                
        except Exception as e:
            self.logger.error(f"Error creating project: {str(e)}")
            raise


    async def get_projects_by_universe(self, universe_id: str, user_id: str) -> List[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                projects = await session.execute(select(Project).filter_by(universe_id=universe_id, user_id=user_id))
                projects = projects.scalars().all()
                return [project.to_dict() for project in projects]
            except Exception as e:
                self.logger.error(f"Error getting universe: {str(e)}")
                raise

    async def get_project(self, project_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                project = await session.get(Project, project_id)
                if project and project.user_id == user_id:
                    return project.to_dict()
                raise Exception("Project not found")  # Add a specific exception message
            except Exception as e:
                self.logger.error(f"Error getting project: {str(e)}")
                raise

    async def update_project(self, project_id: str, name: Optional[str], description: Optional[str], user_id: str, universe_id: Optional[str] = None, target_word_count: Optional[int] = None) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                project = await session.get(Project, project_id)
                if project and project.user_id == user_id:
                    if name is not None:
                        project.name = name
                    if description is not None:
                        project.description = description
                    if universe_id is not None:
                        project.universe_id = universe_id
                    if target_word_count is not None:
                        project.target_word_count = target_word_count
                    project.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return project.to_dict()
                raise
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating project: {str(e)}")
                raise

    async def update_project_universe(self, project_id: str, universe_id: Optional[str], user_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                project = await session.get(Project, project_id)
                if project and project.user_id == user_id:
                    project.universe_id = universe_id
                    project.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return project.to_dict()
                raise
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating project universe: {str(e)}")
                raise

    async def delete_project(self, project_id: str, user_id: str) -> bool:
        async with await self.get_session() as session:
            try:
                project = await session.get(Project, project_id)
                if project and project.user_id == user_id:
                    await session.delete(project)
                    await session.commit()
                    return True
                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting project: {str(e)}")
                raise


    async def create_universe(self, name: str, user_id: str, description: Optional[str] = None) -> str:
        async with await self.get_session() as session:
            try:
                current_time = datetime.now(timezone.utc).replace(tzinfo=None)
                universe = Universe(
                    id=str(uuid.uuid4()),
                    name=name,
                    description=description,
                    user_id=user_id,
                    created_at=current_time,
                    updated_at=current_time
                )
                session.add(universe)
                await session.commit()
                return universe.id
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error creating universe: {str(e)}")
                raise ValueError(str(e))

    async def get_universe(self, universe_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                universe = await session.get(Universe, universe_id)
                if universe and universe.user_id == user_id:
                    return universe.to_dict()
                raise
            except Exception as e:
                self.logger.error(f"Error updating universe: {str(e)}")
                raise


    async def update_universe(self, universe_id: str, name: str, user_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                universe = await session.get(Universe, universe_id)
                if universe and universe.user_id == user_id:
                    universe.name = name
                    await session.commit()
                    return universe.to_dict()
                raise
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating universe: {str(e)}")
                raise


    async def delete_universe(self, universe_id: str, user_id: str) -> bool:
        async with await self.get_session() as session:
            try:
                universe = await session.get(Universe, universe_id)
                if universe and universe.user_id == user_id:
                    await session.delete(universe)
                    await session.commit()
                    return True
                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting universe: {str(e)}")
                raise

    async def get_universe_codex(self, universe_id: str, user_id: str) -> List[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                codex_items = await session.execute(select(CodexItem).join(Project).filter(
                    and_(Project.universe_id == universe_id, CodexItem.user_id == user_id)
                ))
                codex_items = codex_items.scalars().all()
                return [item.to_dict() for item in codex_items]
            except Exception as e:
                self.logger.error(f"Error getting events: {str(e)}")
                raise

    async def get_universe_knowledge_base(self, universe_id: str, user_id: str, limit: int = 100, offset: int = 0) -> Dict[str, List[Dict[str, Any]]]:
        async with await self.get_session() as session:
            try:
                # Fetch all projects for the given universe
                projects = await session.execute(select(Project).filter_by(universe_id=universe_id, user_id=user_id))
                projects = projects.scalars().all()
                project_ids = [project.id for project in projects]

                # Initialize the result dictionary
                knowledge_base = {project.id: [] for project in projects}

                # Fetch chapters and codex items with pagination
                for project_id in project_ids:
                    chapters = await session.execute(select(Chapter).filter_by(project_id=project_id).limit(limit).offset(offset))
                    codex_items = await session.execute(select(CodexItem).filter_by(project_id=project_id).limit(limit).offset(offset))

                    chapters = chapters.scalars().all()
                    codex_items = codex_items.scalars().all()

                    for chapter in chapters:
                        knowledge_base[project_id].append({
                            'id': chapter.id,
                            'type': 'chapter',
                            'title': chapter.title,
                            'content': chapter.content,
                            'embedding_id': chapter.embedding_id
                        })

                    for item in codex_items:
                        knowledge_base[project_id].append({
                            'id': item.id,
                            'type': 'codex_item',
                            'name': item.name,
                            'description': item.description,
                            'embedding_id': item.embedding_id
                        })

                # Remove any empty projects
                knowledge_base = {k: v for k, v in knowledge_base.items() if v}

                return knowledge_base
            except Exception as e:
                self.logger.error(f"Error getting locations: {str(e)}")
                raise

    async def get_characters(self, user_id: str, project_id: str, character_id: Optional[str] = None, name: Optional[str] = None):
        async with await self.get_session() as session:
            try:
                query = select(CodexItem).where(
                    and_(
                        CodexItem.user_id == user_id,
                        CodexItem.project_id == project_id,
                        CodexItem.type == CodexItemType.CHARACTER.value
                    )
                )
                
                if character_id:
                    query = query.filter_by(id=character_id)
                if name:
                    query = query.filter_by(name=name)
                
                characters = await session.execute(query)
                characters = characters.scalars().all()
                
                if character_id or name:
                    return characters[0].to_dict() if characters else None
                return [character.to_dict() for character in characters]
            except Exception as e:
                self.logger.error(f"Error getting characters: {str(e)}")
                raise


    async def get_events(self, project_id: str, user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                query = select(Event).filter_by(
                    user_id=user_id,
                    project_id=project_id
                )
                if limit is not None:
                    query = query.limit(limit)
                events = await session.execute(query)
                return [event.to_dict() for event in events.scalars().all()]
            except Exception as e:
                self.logger.error(f"Error getting events: {str(e)}")
                raise

    async def get_locations(self, user_id: str, project_id: str, k: Optional[int] = None) -> List[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                query = select(Location).filter_by(
                    user_id=user_id,
                    project_id=project_id
                )
                if k is not None:
                    query = query.limit(k)
                locations = await session.execute(query)
                return [location.to_dict() for location in locations.scalars().all()]
            except Exception as e:
                self.logger.error(f"Error getting locations: {str(e)}")
                raise

    async def mark_latest_chapter_processed(self, project_id: str, process_type: str):
        async with await self.get_session() as session:
            try:
                latest_chapter = await session.execute(select(Chapter).filter(
                    Chapter.project_id == project_id
                ).order_by(Chapter.chapter_number.desc()))
                latest_chapter = latest_chapter.scalars().first()

                if latest_chapter:
                    if not latest_chapter.processed_types:
                        latest_chapter.processed_types = []
                    if process_type not in latest_chapter.processed_types:
                        latest_chapter.processed_types.append(process_type)
                    await session.commit()
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error marking latest chapter as processed: {str(e)}")
                raise

    async def is_chapter_processed(self, chapter_id: str, process_type: str) -> bool:
        async with await self.get_session() as session:
            try:
                chapter = await session.get(Chapter, chapter_id)
                if chapter and isinstance(chapter.processed_types, list):
                    return process_type in chapter.processed_types
                return False
            except Exception as e:
                self.logger.error(f"Error checking chapter processed status: {str(e)}")
                raise

    async def get_model_settings(self, user_id):
        async with await self.get_session() as session:
            try:
                user = await session.get(User, user_id)
                if user and user.model_settings:
                    return json.loads(user.model_settings)
                return {
                    'mainLLM': 'gemini-1.5-pro-002',
                    'checkLLM': 'gemini-1.5-pro-002',
                    'embeddingsModel': 'models/text-embedding-004',
                    'titleGenerationLLM': 'gemini-1.5-pro-002',
                    'extractionLLM': 'gemini-1.5-pro-002',
                    'knowledgeBaseQueryLLM': 'gemini-1.5-pro-002'
                }
            except Exception as e:
                self.logger.error(f"Error getting validity check: {str(e)}")
                raise

    async def save_validity_check(self, chapter_id: str, chapter_title: str, is_valid: bool, overall_score: int, general_feedback: str, style_guide_adherence_score: int, style_guide_adherence_explanation: str, continuity_score: int, continuity_explanation: str, areas_for_improvement: List[str], user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                check = ValidityCheck(
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
                    areas_for_improvement=areas_for_improvement,
                    user_id=user_id,
                    project_id=project_id
                )
                session.add(check)
                await session.commit()
                return check.id
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error saving validity check: {str(e)}")
                raise

    async def get_validity_check(self, chapter_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                validity_check = await session.get(ValidityCheck, chapter_id)
                if validity_check and validity_check.user_id == user_id:
                    return {
                        'id': validity_check.id,
                        'chapter_title': validity_check.chapter_title,
                        'is_valid': validity_check.is_valid,
                        'overall_score': validity_check.overall_score,
                        'general_feedback': validity_check.general_feedback,
                        'style_guide_adherence_score': validity_check.style_guide_adherence_score,
                        'style_guide_adherence_explanation': validity_check.style_guide_adherence_explanation,
                        'continuity_score': validity_check.continuity_score,
                        'continuity_explanation': validity_check.continuity_explanation,
                        'areas_for_improvement': validity_check.areas_for_improvement,
                        'created_at': validity_check.created_at
                    }
                raise Exception("Validity check not found")  # Add a specific exception message
            except Exception as e:
                self.logger.error(f"Error getting validity check: {str(e)}")
                raise

    async def save_chat_history(self, user_id: str, project_id: str, messages: List[Dict[str, Any]]):
        async with await self.get_session() as session:
            try:
                chat_history = await session.execute(select(ChatHistory).filter_by(user_id=user_id, project_id=project_id))
                chat_history = chat_history.scalars().first()
                
                if chat_history:
                    chat_history.messages = json.dumps(messages)
                else:
                    chat_history = ChatHistory(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        project_id=project_id,
                        messages=json.dumps(messages)
                    )
                    session.add(chat_history)
                await session.commit()
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error saving chat history: {str(e)}")
                raise

    async def get_chat_history(self, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                chat_history = await session.execute(select(ChatHistory).filter_by(user_id=user_id, project_id=project_id))
                chat_history = chat_history.scalars().first()
                return json.loads(chat_history.messages) if chat_history else []
            except Exception as e:
                self.logger.error(f"Error getting chat history: {str(e)}")
                raise


    async def delete_chat_history(self, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                # Use select() to find the chat history by user_id and project_id
                chat_history = await session.execute(
                    select(ChatHistory)
                    .filter_by(user_id=user_id, project_id=project_id)
                )
                chat_history = chat_history.scalars().first()
                
                if chat_history:
                    await session.delete(chat_history)
                    await session.commit()
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting chat history: {str(e)}")
                raise


    async def create_preset(self, user_id: str, project_id: str, name: str, data: Dict[str, Any]):
        async with await self.get_session() as session:
            try:
                # Check if a preset with the same name, user_id, and project_id already exists
                existing_preset = await session.execute(select(Preset).filter_by(user_id=user_id, project_id=project_id, name=name))
                existing_preset = existing_preset.scalars().first()
                if existing_preset:
                    raise ValueError(f"A preset with name '{name}' already exists for this user and project.")
                
                preset = Preset(id=str(uuid.uuid4()), user_id=user_id, project_id=project_id, name=name, data=data)
                session.add(preset)
                await session.commit()
                return preset.id
            except ValueError as ve:
                await session.rollback()
                self.logger.error(f"Error creating preset: {str(ve)}")
                raise
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error creating preset: {str(e)}")
                raise

    async def get_presets(self, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                presets = await session.execute(select(Preset).filter_by(user_id=user_id, project_id=project_id))
                presets = presets.scalars().all()
                return [{"id": preset.id, "name": preset.name, "data": preset.data} for preset in presets]
            except Exception as e:
                self.logger.error(f"Error getting presets: {str(e)}")
                raise

    async def delete_preset(self, preset_name: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                preset = await session.execute(select(Preset).filter_by(name=preset_name, user_id=user_id, project_id=project_id))
                preset = preset.scalars().first()
                if preset:
                    await session.delete(preset)
                    await session.commit()
                    return True
                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting preset: {str(e)}")
                raise

    async def get_preset_by_name(self, preset_name: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                preset = await session.execute(select(Preset).filter_by(name=preset_name, user_id=user_id, project_id=project_id))
                preset = preset.scalars().first()
                if preset:
                    return {"id": preset.id, "name": preset.name, "data": preset.data}
                raise
            except Exception as e:
                self.logger.error(f"Error getting preset by name: {str(e)}")
                raise

    async def update_chapter_embedding_id(self, chapter_id, embedding_id):
        async with await self.get_session() as session:
            try:
                chapter = await session.get(Chapter, chapter_id)
                if chapter:
                    chapter.embedding_id = embedding_id
                    await session.commit()
                    return True
                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating chapter embedding_id: {str(e)}")
                raise

    async def delete_character_relationship(self, relationship_id: str, user_id: str, project_id: str) -> bool:
        async with await self.get_session() as session:
            try:
                relationship = await session.execute(select(CharacterRelationship).join(
                    CodexItem, CharacterRelationship.character_id == CodexItem.id
                ).filter(
                    CharacterRelationship.id == relationship_id,
                    CodexItem.project_id == project_id,
                    CodexItem.user_id == user_id
                ))
                relationship = relationship.scalars().first()
                if relationship:
                    await session.delete(relationship)
                    await session.commit()
                    return True
                else:
                    raise Exception("Relationship not found")
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting character relationship: {str(e)}")
                raise

    async def save_relationship_analysis(self, character1_id: str, character2_id: str, relationship_type: str, 
                                 description: str, user_id: str, project_id: str) -> str:
        async with await self.get_session() as session:
            try:
                analysis = CharacterRelationshipAnalysis(
                    id=str(uuid.uuid4()),
                    character1_id=character1_id,
                    character2_id=character2_id,
                    relationship_type=relationship_type,
                    description=description,
                    user_id=user_id,
                    project_id=project_id
                )
                session.add(analysis)
                await session.commit()
                return analysis.id
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error saving relationship analysis: {str(e)}")
                raise

    async def get_character_relationships(self, project_id: str, user_id: str) -> List[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                relationships = (
                    await session.execute(select(CharacterRelationship)
                    .join(
                        CodexItem,
                        CharacterRelationship.character_id == CodexItem.id
                    )
                    .filter(
                        CodexItem.project_id == project_id,
                        CodexItem.user_id == user_id
                    ))
                ).scalars().all()

                result = []
                for rel in relationships:
                    character1 = await session.get(CodexItem, rel.character_id)
                    character2 = await session.get(CodexItem, rel.related_character_id)
                    
                    if character1 and character2:
                        result.append({
                            'id': rel.id,
                            'character1_id': rel.character_id,
                            'character2_id': rel.related_character_id,
                            'character1_name': character1.name,
                            'character2_name': character2.name,
                            'relationship_type': rel.relationship_type,
                            'description': rel.description or ''  # Add this line
                        })

                return result
            except Exception as e:
                self.logger.error(f"Error getting character relationships: {str(e)}")
                raise

    async def update_character_backstory(self, character_id: str, backstory: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                character = await session.get(CodexItem, character_id)
                if character:
                    if character.user_id != user_id:
                        raise ValueError(f"User {user_id} is not authorized to update character {character_id}")
                    if character.project_id != project_id:
                        raise ValueError(f"Character {character_id} does not belong to project {project_id}")
                    character.backstory = backstory
                    character.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                else:
                    raise ValueError(f"Character with ID {character_id} not found")
            except Exception as e:
                self.logger.error(f"Error updating character backstory: {str(e)}")
                raise

    async def delete_character_backstory(self, character_id: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                character = await session.get(CodexItem, character_id)
                if character and character.user_id == user_id and character.project_id == project_id:
                    character.backstory = None
                    # Use a timezone-naive datetime
                    character.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                else:
                    raise ValueError("Character not found")
            except Exception as e:
                self.logger.error(f"Error deleting character backstory: {str(e)}")
                raise

    async def get_chapter_count(self, project_id: str, user_id: str) -> int:
        async with await self.get_session() as session:
            chapters = await session.execute(select(Chapter).filter_by(project_id=project_id, user_id=user_id))
            chapters = chapters.scalars().all()
            return len(chapters)

    async def create_event(self, title: str, description: str, date: datetime, project_id: str, user_id: str, character_id: Optional[str] = None, location_id: Optional[str] = None) -> str:
        async with await self.get_session() as session:
            try:
                event = Event(
                    id=str(uuid.uuid4()),
                    title=title,
                    description=description,
                    date=date,
                    character_id=character_id,
                    project_id=project_id,
                    user_id=user_id,
                    location_id=location_id,
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )
                session.add(event)
                await session.commit()
                return event.id
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error creating event: {str(e)}")
                raise

    async def save_character_backstory(self, character_id: str, content: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                character = await session.get(CodexItem, character_id)
                if character and character.user_id == user_id and character.project_id == project_id and character.type == 'character':
                    if character.backstory:
                        character.backstory += f"\n\n{content}"
                    else:
                        character.backstory = content
                    # Convert to timezone-naive datetime before saving
                    character.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return character.to_dict()
                raise
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error saving character backstory: {str(e)}")
                raise

    async def get_character_backstories(self, character_id: str) -> List[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                backstories = await session.execute(select(CharacterBackstory).filter_by(character_id=character_id).order_by(CharacterBackstory.created_at))
                backstories = backstories.scalars().all()
                return [backstory.to_dict() for backstory in backstories]
            except Exception as e:
                self.logger.error(f"Error updating event: {str(e)}")
                raise

    async def get_latest_unprocessed_chapter_content(self, project_id: str, user_id: str, process_type: str):
        async with await self.get_session() as session:
            try:
                # Get all unprocessed chapters instead of just the first one
                chapters = await session.execute(
                    select(Chapter).filter(
                        Chapter.project_id == project_id,
                        Chapter.user_id == user_id,
                        ~Chapter.processed_types.cast(JSONB).contains([process_type])
                    ).order_by(Chapter.chapter_number)  # Order by chapter number ascending
                )
                chapters = chapters.scalars().all()  # Get all results instead of .first()
                
                if chapters:
                    return [{
                        'id': chapter.id,
                        'content': chapter.content
                    } for chapter in chapters]
                raise
            except Exception as e:
                self.logger.error(f"Error getting unprocessed chapter content: {str(e)}")
                raise

    async def create_character_relationship(self, character_id: str, related_character_id: str, 
                                            relationship_type: str, project_id: str, 
                                            description: Optional[str] = None) -> str:
        async with await self.get_session() as session:
            try:
                # Ensure character IDs are not None before querying
                if character_id is None or related_character_id is None:
                    raise ValueError("Character IDs cannot be None")
                
                # Check if both characters exist in the codex_items table
                character = await session.execute(
                    select(CodexItem).filter_by(id=character_id, project_id=project_id, type='character')
                )
                character = character.scalars().first()
                related_character = await session.execute(
                    select(CodexItem).filter_by(id=related_character_id, project_id=project_id, type='character')
                )
                related_character = related_character.scalars().first()
                
                if not character:
                    self.logger.error(f"Character with ID {character_id} not found in the codex")
                if not related_character:
                    self.logger.error(f"Character with ID {related_character_id} not found in the codex")
                
                if not character or not related_character:
                    raise ValueError("One or both characters do not exist in the codex")
                
                relationship = CharacterRelationship(
                    id=str(uuid.uuid4()),
                    character_id=character.id,
                    related_character_id=related_character.id,
                    relationship_type=relationship_type,
                    description=description,  # Add this line
                    project_id=project_id
                )
                session.add(relationship)
                await session.commit()
                return relationship.id
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error creating character relationship: {str(e)}")
                raise

    async def update_event(self, event_id: str, title: str, description: str, date: datetime, character_id: Optional[str], location_id: Optional[str], project_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                event = await session.get(Event, event_id)
                if event and event.user_id == user_id and event.project_id == project_id:
                    event.title = title
                    event.description = description
                    event.date = date
                    event.character_id = character_id
                    event.location_id = location_id
                    event.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return event.to_dict()
                raise Exception("Event not found")  # Add a specific exception message
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating event: {str(e)}")
                raise

    async def get_event_by_title(self, title: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                event = await session.execute(select(Event).filter_by(title=title, user_id=user_id, project_id=project_id))
                event = event.scalars().first()
                return event.to_dict() if event else None
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error getting event by title: {str(e)}")
                raise

    async def update_location(self, location_id: str, location_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                location = await session.get(Location, location_id)
                if location:
                    for key, value in location_data.items():
                        setattr(location, key, value)
                    await session.commit()
                    return location.to_dict()
                raise Exception("Location not found")  # Add a specific exception message
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating location: {str(e)}")
                raise
    
    async def update_character_relationship(self, relationship_id: str, relationship_type: str, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                relationship = await session.execute(
                    select(CharacterRelationship).join(
                        CodexItem, CharacterRelationship.character_id == CodexItem.id
                    ).filter(
                        CharacterRelationship.id == relationship_id,
                        CodexItem.project_id == project_id,
                        CodexItem.user_id == user_id
                    )
                )
                relationship = relationship.scalars().first()
                if relationship:
                    relationship.relationship_type = relationship_type
                    await session.commit()
                    return relationship.to_dict()
                raise
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating character relationship: {str(e)}")
                raise

    async def get_location_by_name(self, name: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                location = await session.execute(
                    select(Location).filter_by(
                        name=name, 
                        user_id=user_id, 
                        project_id=project_id
                    )
                )
                location = location.scalars().first()
                if location:
                    return location.to_dict()
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error getting location by ID: {str(e)}")
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
        user_id: str
    ) -> str:
        async with await self.get_session() as session:
            try:
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
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )
                session.add(connection)
                await session.commit()
                return connection.id
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error creating location connection: {str(e)}")
                raise

    async def create_event_connection(
        self,
        event1_id: str,
        event2_id: str,
        connection_type: str,
        description: str,
        impact: str,
        project_id: str,
        user_id: str
    ) -> str:
        async with await self.get_session() as session:
            try:
                connection = EventConnection(
                    id=str(uuid.uuid4()),
                    event1_id=event1_id,
                    event2_id=event2_id,
                    connection_type=connection_type,
                    description=description,
                    impact=impact,
                    project_id=project_id,
                    user_id=user_id,
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )
                session.add(connection)
                await session.commit()
                return connection.id
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error creating event connection: {str(e)}")
                raise

    async def get_location_connections(self, project_id: str, user_id: str) -> List[Dict[str, Any]]:
        return await self.connection_service.get_connections(LocationConnection, project_id, user_id)

    async def get_event_connections(self, project_id: str, user_id: str) -> List[Dict[str, Any]]:
        return await self.connection_service.get_connections(EventConnection, project_id, user_id)
    
    async def update_location_connection(
        self,
        connection_id: str,
        connection_type: str,
        description: str,
        travel_route: Optional[str],
        cultural_exchange: Optional[str],
        user_id: str,
        project_id: str
    ) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                connection = await session.get(LocationConnection, connection_id)
                if connection and connection.user_id == user_id and connection.project_id == project_id:
                    connection.connection_type = connection_type
                    connection.description = description
                    connection.travel_route = travel_route
                    connection.cultural_exchange = cultural_exchange
                    connection.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return connection.to_dict()
                return None
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating location connection: {str(e)}")
                raise

    async def update_event_connection(
        self,
        connection_id: str,
        connection_type: str,
        description: str,
        impact: str,
        user_id: str,
        project_id: str
    ) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                connection = await session.get(EventConnection, connection_id)
                if connection and connection.user_id == user_id and connection.project_id == project_id:
                    connection.connection_type = connection_type
                    connection.description = description
                    connection.impact = impact
                    connection.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return connection.to_dict()
                return None
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating event connection: {str(e)}")
                raise

    async def delete_location_connection(self, connection_id: str, user_id: str, project_id: str) -> bool:
        async with await self.get_session() as session:
            try:
                # First verify the connection exists and belongs to the user/project
                connection = await session.get(LocationConnection, connection_id)
                if connection and connection.user_id == user_id and connection.project_id == project_id:
                    await session.delete(connection)
                    await session.commit()
                    return True
                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting location connection: {str(e)}")
                raise

    async def delete_event_connection(self, connection_id: str, user_id: str, project_id: str) -> bool:
        async with await self.get_session() as session:
            try:
                connection = await session.get(EventConnection, connection_id)
                if connection and connection.user_id == user_id and connection.project_id == project_id:
                    await session.delete(connection)
                    await session.commit()
                    return True
                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting event connection: {str(e)}")
                raise

    async def approve_user(self, user_id: str) -> bool:
        try:
            await self.supabase.table('user_approvals').update({'is_approved': True}).eq('id', user_id)
            return True
        except Exception as e:
            self.logger.error(f"Error approving user: {str(e)}")
            return False


db_instance = Database()



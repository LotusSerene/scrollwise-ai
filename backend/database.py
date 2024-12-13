import logging
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime, Text, JSON, UniqueConstraint, and_, func, QueuePool, select, delete, or_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, joinedload, sessionmaker, Session, selectinload
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import TEXT, JSONB
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone, timedelta
import json
import os
from dotenv import load_dotenv
import uuid
from typing import Optional, List, Dict, Any
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
    api_key = Column(String)
    model_settings = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
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
        
        # Initialize Fernet encryption
        encryption_key = os.getenv('ENCRYPTION_KEY')
        if not encryption_key:
            encryption_key = Fernet.generate_key()
            self.logger.warning("No ENCRYPTION_KEY found in environment, generated new key")
        self.fernet = Fernet(encryption_key)
        
        # Initialize SQLAlchemy engine
        self.engine = create_engine("sqlite:///local.db", poolclass=StaticPool)
        
        # Create a session factory
        self.Session = sessionmaker(bind=self.engine)
        
        # Create all tables
        Base.metadata.create_all(self.engine)

    async def get_projects(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Project).where(Project.user_id == user_id)
                result = await session.execute(query)
                projects = result.scalars().all()
                return [project.to_dict() for project in projects]
        except Exception as e:
            self.logger.error(f"Error getting projects: {str(e)}")
            raise

    async def get_universes(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Universe).where(Universe.user_id == user_id)
                result = await session.execute(query)
                universes = result.scalars().all()
                return [universe.to_dict() for universe in universes]
        except Exception as e:
            self.logger.error(f"Error getting universes: {str(e)}")
            raise

    async def check_user_approval(self, user_id: str) -> bool:
        try:
            async with self.Session() as session:
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                user = result.scalars().first()
                if user:
                    # Assuming you have an 'is_approved' column in your User model
                    # For now, we'll return True if the user exists, as we're not storing approval in the local DB
                    return True
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
            auth_response = await self.supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            
            # Create a corresponding record in the users table using SQLAlchemy
            session = self.Session()
            try:
                new_user = User(
                    id=auth_response.user.id,
                    email=email,
                )
                session.add(new_user)
                session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(f"Error inserting user into local database: {str(e)}")
                raise Exception("Failed to create user record locally")
            finally:
                session.close()
                
            return auth_response.user.id
            
        except Exception as e:
            self.logger.error(f"Error creating user (Supabase auth): {str(e)}")
            raise

    async def get_user_by_email(self, email: str):
        try:
            async with self.Session() as session:
                query = select(User).where(User.email == email)
                result = await session.execute(query)
                user = result.scalars().first()
                return user.to_dict() if user else None
        except Exception as e:
            self.logger.error(f"Error getting user: {str(e)}")
            return None

    async def get_all_chapters(self, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                query = select(Chapter).where(Chapter.user_id == user_id, Chapter.project_id == project_id).order_by(Chapter.chapter_number)
                result = await session.execute(query)
                chapters = result.scalars().all()
                return [chapter.to_dict() for chapter in chapters]
        except Exception as e:
            self.logger.error(f"Error fetching all chapters: {str(e)}")
            raise

    async def create_chapter(self, title: str, content: str, user_id: str, project_id: str, chapter_number: Optional[int] = None, embedding_id: Optional[str] = None) -> str:
        try:
            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
            async with self.Session() as session:
                chapter = Chapter(
                    id=str(uuid.uuid4()),
                    title=title,
                    content=content,
                    user_id=user_id,
                    project_id=project_id,
                    chapter_number=chapter_number,
                    embedding_id=embedding_id,
                    created_at=current_time
                )
                session.add(chapter)
                await session.commit()
                return chapter.id
        except Exception as e:
            self.logger.error(f"Error creating chapter: {str(e)}")
            raise

    async def update_chapter(self, chapter_id, title, content, user_id, project_id):
        try:
            async with self.Session() as session:
                query = select(Chapter).where(Chapter.id == chapter_id, Chapter.user_id == user_id, Chapter.project_id == project_id)
                result = await session.execute(query)
                chapter = result.scalars().first()
                if chapter:
                    chapter.title = title
                    chapter.content = content
                    await session.commit()
                    return chapter.to_dict()
                else:
                    raise Exception("Chapter not found")
        except Exception as e:
            self.logger.error(f"Error updating chapter: {str(e)}")
            raise

    async def delete_chapter(self, chapter_id, user_id, project_id):
        try:
            async with self.Session() as session:
                query = delete(Chapter).where(Chapter.id == chapter_id, Chapter.user_id == user_id, Chapter.project_id == project_id)
                result = await session.execute(query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error deleting chapter: {str(e)}")
            raise

    async def get_chapter(self, chapter_id: str, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                query = select(Chapter).where(Chapter.id == chapter_id, Chapter.user_id == user_id, Chapter.project_id == project_id)
                result = await session.execute(query)
                chapter = result.scalars().first()
                if chapter:
                    return chapter.to_dict()
                else:
                    raise Exception("Chapter not found")
        except Exception as e:
            self.logger.error(f"Error getting chapter: {str(e)}")
            raise

    async def get_all_validity_checks(self, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                query = select(ValidityCheck).where(ValidityCheck.user_id == user_id, ValidityCheck.project_id == project_id)
                result = await session.execute(query)
                validity_checks = result.scalars().all()
                return [check.to_dict() for check in validity_checks]
        except Exception as e:
            self.logger.error(f"Error getting all validity checks: {str(e)}")
            raise

    async def delete_validity_check(self, check_id, user_id, project_id):
        try:
            async with self.Session() as session:
                query = delete(ValidityCheck).where(ValidityCheck.id == check_id, ValidityCheck.user_id == user_id, ValidityCheck.project_id == project_id)
                result = await session.execute(query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error deleting validity check: {str(e)}")
            raise

    async def create_codex_item(self, name: str, description: str, type: str, subtype: Optional[str], user_id: str, project_id: str) -> str:
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
                    created_at=current_time,
                    updated_at=current_time
                )
                session.add(codex_item)
                await session.commit()
                return codex_item.id
        except Exception as e:
            self.logger.error(f"Error creating codex item: {str(e)}")
            raise

    async def get_all_codex_items(self, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                query = select(CodexItem).where(CodexItem.user_id == user_id, CodexItem.project_id == project_id)
                result = await session.execute(query)
                codex_items = result.scalars().all()
                return [item.to_dict() for item in codex_items]
        except Exception as e:
            self.logger.error(f"Error getting all codex items: {str(e)}")
            raise

    async def update_codex_item(self, item_id: str, name: str, description: str, type: str, subtype: str, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                query = select(CodexItem).where(CodexItem.id == item_id, CodexItem.user_id == user_id, CodexItem.project_id == project_id)
                result = await session.execute(query)
                codex_item = result.scalars().first()
                if codex_item:
                    codex_item.name = name
                    codex_item.description = description
                    codex_item.type = type
                    codex_item.subtype = subtype
                    codex_item.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return codex_item.to_dict()
                else:
                    raise Exception("Codex item not found")
        except Exception as e:
            self.logger.error(f"Error updating codex item: {str(e)}")
            raise

    async def delete_codex_item(self, item_id: str, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                query = delete(CodexItem).where(CodexItem.id == item_id, CodexItem.user_id == user_id, CodexItem.project_id == project_id)
                result = await session.execute(query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error deleting codex item: {str(e)}")
            raise

    async def get_codex_item_by_id(self, item_id: str, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                query = select(CodexItem).where(CodexItem.id == item_id, CodexItem.user_id == user_id, CodexItem.project_id == project_id)
                result = await session.execute(query)
                codex_item = result.scalars().first()
                if codex_item:
                    return codex_item.to_dict()
                else:
                    raise Exception("Codex item not found")
        except Exception as e:
            self.logger.error(f"Error getting codex item by ID: {str(e)}")
            raise

        
    async def save_api_key(self, user_id: str, api_key: str):
        try:
            # Get the user's email from the Supabase auth user (this part remains)
            user_response = await self.supabase.auth.admin.get_user_by_id(user_id)
            if not user_response or not user_response.user:
                raise Exception("User not found in auth system")
            user_email = user_response.user.email
            # Encrypt the API key before saving
            encrypted_key = self.fernet.encrypt(api_key.encode())
            encoded_key = b64encode(encrypted_key).decode()
            # Update or insert the API key using SQLAlchemy
            session = self.Session()
            try:
                user = session.query(User).filter_by(id=user_id).first()
                if user:
                    # User exists, update the API key and updated_at
                    user.api_key = encoded_key
                    user.updated_at = datetime.now(timezone.utc)
                else:
                    # User does not exist, create a new record
                    new_user = User(
                        id=user_id,
                        email=user_email,
                        api_key=encoded_key,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                    session.add(new_user)
                session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(f"Error saving API key to local database: {str(e)}")
                raise
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Error saving API key (Supabase auth or general): {str(e)}")
            raise

    async def get_api_key(self, user_id):
        try:
            async with self.Session() as session:
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                user = result.scalars().first()
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
        try:
            async with self.Session() as session:
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                user = result.scalars().first()
                if user:
                    user.api_key = None
                    user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                else:
                    raise Exception("User not found")
        except Exception as e:
            self.logger.error(f"Error removing API key: {str(e)}")
            raise

    async def save_model_settings(self, user_id, settings):
        try:
            async with self.Session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                if user:
                    user.model_settings = json.dumps(settings)
                    user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                else:
                    raise Exception("User not found")
        except Exception as e:
            self.logger.error(f"Error saving model settings: {str(e)}")
            raise

    async def create_location(self, name: str, description: str, coordinates: Optional[str], user_id: str, project_id: str) -> str:
        try:
            async with self.Session() as session:
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
            self.logger.error(f"Error creating location: {str(e)}")
            raise

    async def delete_location(self, location_id: str, project_id: str, user_id: str) -> bool:
        try:
            async with self.Session() as session:
                # First delete associated connections
                delete_connections_query = delete(LocationConnection).where(
                    or_(
                        LocationConnection.location1_id == location_id,
                        LocationConnection.location2_id == location_id
                    )
                )
                await session.execute(delete_connections_query)
                
                # Then delete the location
                delete_location_query = delete(Location).where(
                    and_(
                        Location.id == location_id,
                        Location.project_id == project_id,
                        Location.user_id == user_id
                    )
                )
                result = await session.execute(delete_location_query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error deleting location: {str(e)}")
            raise

    async def mark_chapter_processed(self, chapter_id: str, user_id: str, process_type: str) -> None:
        try:
            async with self.Session() as session:
                # Fetch the chapter
                query = select(Chapter).where(Chapter.id == chapter_id, Chapter.user_id == user_id)
                result = await session.execute(query)
                chapter = result.scalars().first()
                if not chapter:
                    raise Exception("Chapter not found")

                processed_types = chapter.processed_types

                # Update processed_types if the process_type is not already present
                if process_type not in processed_types:
                    processed_types.append(process_type)
                    chapter.processed_types = processed_types
                    chapter.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
        except Exception as e:
            self.logger.error(f"Error marking chapter as processed: {str(e)}")
            raise


    async def is_chapter_processed_for_type(self, chapter_id: str, process_type: str) -> bool:
        try:
            async with self.Session() as session:
                query = select(Chapter).where(Chapter.id == chapter_id).options(selectinload(Chapter.processed_types))
                result = await session.execute(query)
                chapter = result.scalars().first()
                if chapter:
                    processed_types = chapter.processed_types
                    return process_type in processed_types
                return False
        except Exception as e:
            self.logger.error(f"Error checking chapter processed status: {str(e)}")
            raise


    async def get_event_by_id(self, event_id: str, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Event).where(Event.id == event_id, Event.user_id == user_id, Event.project_id == project_id)
                result = await session.execute(query)
                event = result.scalars().first()
                return event.to_dict() if event else None
        except Exception as e:
            self.logger.error(f"Error getting event by ID: {str(e)}")
            raise

    async def get_location_by_id(self, location_id: str, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Location).where(Location.id == location_id, Location.user_id == user_id, Location.project_id == project_id)
                result = await session.execute(query)
                location = result.scalars().first()
                return location.to_dict() if location else None
        except Exception as e:
            self.logger.error(f"Error getting location by ID: {str(e)}")
            raise

    async def update_codex_item_embedding_id(self, item_id: str, embedding_id: str) -> bool:
        try:
            async with self.Session() as session:
                query = select(CodexItem).where(CodexItem.id == item_id)
                result = await session.execute(query)
                codex_item = result.scalars().first()
                if codex_item:
                    codex_item.embedding_id = embedding_id
                    codex_item.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return True
                else:
                    raise Exception("Codex item not found")
        except Exception as e:
            self.logger.error(f"Error updating codex item embedding_id: {str(e)}")
            raise


    async def create_project(self, name: str, description: str, user_id: str, universe_id: Optional[str] = None) -> str:
        try:
            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
            async with self.Session() as session:
                project = Project(
                    id=str(uuid.uuid4()),
                    name=name,
                    description=description,
                    user_id=user_id,
                    universe_id=universe_id,
                    created_at=current_time,
                    updated_at=current_time
                )
                session.add(project)
                await session.commit()
                return project.id
        except Exception as e:
            self.logger.error(f"Error creating project: {str(e)}")
            raise


    async def get_projects_by_universe(self, universe_id: str, user_id: str) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Project).where(Project.universe_id == universe_id, Project.user_id == user_id)
                result = await session.execute(query)
                projects = result.scalars().all()
                return [project.to_dict() for project in projects]
        except Exception as e:
            self.logger.error(f"Error getting projects by universe: {str(e)}")
            raise

    async def get_project(self, project_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Project).where(Project.id == project_id, Project.user_id == user_id)
                result = await session.execute(query)
                project = result.scalars().first()
                return project.to_dict() if project else None
        except Exception as e:
            self.logger.error(f"Error getting project: {str(e)}")
            raise

    async def update_project(self, project_id: str, name: Optional[str], description: Optional[str], user_id: str, universe_id: Optional[str] = None, target_word_count: Optional[int] = None) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Project).where(Project.id == project_id, Project.user_id == user_id)
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
                    project.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return project.to_dict()
                else:
                    raise Exception("Project not found")
        except Exception as e:
            self.logger.error(f"Error updating project: {str(e)}")
            raise

    async def update_project_universe(self, project_id: str, universe_id: Optional[str], user_id: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Project).where(Project.id == project_id, Project.user_id == user_id)
                result = await session.execute(query)
                project = result.scalars().first()
                if project:
                    project.universe_id = universe_id
                    project.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return project.to_dict()
                else:
                    raise Exception("Project not found")
        except Exception as e:
            self.logger.error(f"Error updating project universe: {str(e)}")
            raise

    async def delete_project(self, project_id: str, user_id: str) -> bool:
        try:
            async with self.Session() as session:
                query = delete(Project).where(Project.id == project_id, Project.user_id == user_id)
                result = await session.execute(query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error deleting project: {str(e)}")
            raise


    async def create_universe(self, name: str, user_id: str, description: Optional[str] = None) -> str:
        try:
            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
            async with self.Session() as session:
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
            self.logger.error(f"Error creating universe: {str(e)}")
            raise ValueError(str(e))

    async def get_universe(self, universe_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Universe).where(Universe.id == universe_id, Universe.user_id == user_id)
                result = await session.execute(query)
                universe = result.scalars().first()
                return universe.to_dict() if universe else None
        except Exception as e:
            self.logger.error(f"Error getting universe: {str(e)}")
            raise


    async def update_universe(self, universe_id: str, name: str, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Universe).where(Universe.id == universe_id, Universe.user_id == user_id)
                result = await session.execute(query)
                universe = result.scalars().first()
                if universe:
                    universe.name = name
                    universe.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return universe.to_dict()
                else:
                    raise Exception("Universe not found")
        except Exception as e:
            self.logger.error(f"Error updating universe: {str(e)}")
            raise


    async def delete_universe(self, universe_id: str, user_id: str) -> bool:
        try:
            async with self.Session() as session:
                query = delete(Universe).where(Universe.id == universe_id, Universe.user_id == user_id)
                result = await session.execute(query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error deleting universe: {str(e)}")
            raise

    async def get_universe_codex(self, universe_id: str, user_id: str) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = (
                    select(CodexItem)
                    .join(Project, CodexItem.project_id == Project.id)
                    .where(Project.universe_id == universe_id, CodexItem.user_id == user_id)
                )
                result = await session.execute(query)
                codex_items = result.scalars().all()
                return [item.to_dict() for item in codex_items]
        except Exception as e:
            self.logger.error(f"Error getting universe codex: {str(e)}")
            raise

    async def get_universe_knowledge_base(self, universe_id: str, user_id: str, limit: int = 100, offset: int = 0) -> Dict[str, List[Dict[str, Any]]]:
        try:
            # Fetch all projects for the given universe
            async with self.Session() as session:
                query = select(Project).where(Project.universe_id == universe_id, Project.user_id == user_id)
                result = await session.execute(query)
                projects = result.scalars().all()
                project_ids = [project.id for project in projects]

            # Initialize the result dictionary
            knowledge_base = {project.id: [] for project in projects}

            # Fetch chapters and codex items with pagination
            for project_id in project_ids:
                async with self.Session() as session:
                    chapters_query = select(Chapter).where(Chapter.project_id == project_id).limit(limit).offset(offset)
                    codex_items_query = select(CodexItem).where(CodexItem.project_id == project_id).limit(limit).offset(offset)

                    chapters_result = await session.execute(chapters_query)
                    codex_items_result = await session.execute(codex_items_query)

                    chapters = chapters_result.scalars().all()
                    codex_items = codex_items_result.scalars().all()

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
            self.logger.error(f"Error getting universe knowledge base: {str(e)}")
            raise



    async def get_characters(self, user_id: str, project_id: str, character_id: Optional[str] = None, name: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            query = select(CodexItem).where(
                CodexItem.user_id == user_id,
                CodexItem.project_id == project_id,
                CodexItem.type == CodexItemType.CHARACTER.value
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
            self.logger.error(f"Error getting characters: {str(e)}")
            raise

    async def get_events(self, project_id: str, user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        try:
            query = select(Event).where(Event.user_id == user_id, Event.project_id == project_id)
            if limit is not None:
                query = query.limit(limit)
            async with self.Session() as session:
                result = await session.execute(query)
                events = result.scalars().all()
                return [event.to_dict() for event in events]
        except Exception as e:
            self.logger.error(f"Error getting events: {str(e)}")
            raise

    async def get_locations(self, user_id: str, project_id: str, k: Optional[int] = None) -> List[Dict[str, Any]]:
        try:
            query = select(Location).where(Location.user_id == user_id, Location.project_id == project_id)
            if k is not None:
                query = query.limit(k)
            async with self.Session() as session:
                result = await session.execute(query)
                locations = result.scalars().all()
                return [location.to_dict() for location in locations]
        except Exception as e:
            self.logger.error(f"Error getting locations: {str(e)}")
            raise


    async def mark_latest_chapter_processed(self, project_id: str, process_type: str):
        try:
            async with self.Session() as session:
                # Fetch the latest chapter
                query = select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_number.desc()).limit(1)
                result = await session.execute(query)
                latest_chapter = result.scalars().first()
                if not latest_chapter:
                    raise Exception("Latest chapter not found")

                processed_types = latest_chapter.processed_types

                # Update processed_types if the process_type is not already present
                if process_type not in processed_types:
                    processed_types.append(process_type)
                    latest_chapter.processed_types = processed_types
                    latest_chapter.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
        except Exception as e:
            self.logger.error(f"Error marking latest chapter as processed: {str(e)}")
            raise

    async def is_chapter_processed(self, chapter_id: str, process_type: str) -> bool:
        try:
            async with self.Session() as session:
                query = select(Chapter).where(Chapter.id == chapter_id).options(selectinload(Chapter.processed_types))
                result = await session.execute(query)
                chapter = result.scalars().first()
                if chapter:
                    processed_types = chapter.processed_types
                    return process_type in processed_types
                return False
        except Exception as e:
            self.logger.error(f"Error checking chapter processed status: {str(e)}")
            raise

    async def get_model_settings(self, user_id):
        try:
            async with self.Session() as session:
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                user = result.scalars().first()
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
            self.logger.error(f"Error getting model settings: {str(e)}")
            raise

    async def save_validity_check(self, chapter_id: str, chapter_title: str, is_valid: bool, overall_score: int, general_feedback: str, style_guide_adherence_score: int, style_guide_adherence_explanation: str, continuity_score: int, continuity_explanation: str, areas_for_improvement: List[str], user_id: str, project_id: str):
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
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )
                session.add(validity_check)
                await session.commit()
                return validity_check.id
        except Exception as e:
            self.logger.error(f"Error saving validity check: {str(e)}")
            raise

    async def get_validity_check(self, chapter_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(ValidityCheck).where(ValidityCheck.chapter_id == chapter_id, ValidityCheck.user_id == user_id)
                result = await session.execute(query)
                validity_check = result.scalars().first()
                if validity_check:
                    return validity_check.to_dict()
                raise Exception("Validity check not found")
        except Exception as e:
            self.logger.error(f"Error getting validity check: {str(e)}")
            raise

    async def save_chat_history(self, user_id: str, project_id: str, messages: List[Dict[str, Any]]):
        try:
            async with self.Session() as session:
                # First check if a chat history exists for this user and project
                query = select(ChatHistory).where(ChatHistory.user_id == user_id, ChatHistory.project_id == project_id)
                result = await session.execute(query)
                chat_history = result.scalars().first()
                
                chat_data = {
                    "messages": json.dumps(messages),
                    "user_id": user_id,
                    "project_id": project_id
                }
                
                if chat_history:
                    # Update existing chat history
                    chat_history.messages = chat_data["messages"]
                    chat_history.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                else:
                    # Create new chat history
                    new_chat_history = ChatHistory(
                        id=str(uuid.uuid4()),
                        **chat_data,
                        created_at=datetime.now(timezone.utc).replace(tzinfo=None)
                    )
                    session.add(new_chat_history)
                
                await session.commit()
        except Exception as e:
            self.logger.error(f"Error saving chat history: {str(e)}")
            raise

    async def get_chat_history(self, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                query = select(ChatHistory.messages).where(ChatHistory.user_id == user_id, ChatHistory.project_id == project_id)
                result = await session.execute(query)
                chat_history = result.scalars().first()
                if chat_history:
                    return json.loads(chat_history)
                return []
        except Exception as e:
            self.logger.error(f"Error getting chat history: {str(e)}")
            raise


    async def delete_chat_history(self, user_id: str, project_id: str) -> bool:
        try:
            async with self.Session() as session:
                query = delete(ChatHistory).where(ChatHistory.user_id == user_id, ChatHistory.project_id == project_id)
                result = await session.execute(query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error deleting chat history: {str(e)}")
            raise



    async def create_preset(self, user_id: str, project_id: str, name: str, data: Dict[str, Any]) -> str:
        try:
            async with self.Session() as session:
                # Check if a preset with the same name exists
                query = select(Preset).where(Preset.user_id == user_id, Preset.project_id == project_id, Preset.name == name)
                result = await session.execute(query)
                preset = result.scalars().first()
                if preset:
                    raise ValueError(f"A preset with name '{name}' already exists for this user and project.")
                
                # Create new preset
                new_preset = Preset(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    project_id=project_id,
                    name=name,
                    data=data
                )
                session.add(new_preset)
                await session.commit()
                return new_preset.id
        except ValueError as ve:
            self.logger.error(f"Error creating preset: {str(ve)}")
            raise
        except Exception as e:
            self.logger.error(f"Error creating preset: {str(e)}")
            raise

    async def get_presets(self, user_id: str, project_id: str) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Preset).where(Preset.user_id == user_id, Preset.project_id == project_id)
                result = await session.execute(query)
                presets = result.scalars().all()
                return [{"id": preset.id, "name": preset.name, "data": preset.data} for preset in presets]
        except Exception as e:
            self.logger.error(f"Error getting presets: {str(e)}")
            raise


    async def delete_preset(self, preset_id: str, user_id: str, project_id: str) -> bool:
        try:
            async with self.Session() as session:
                query = delete(Preset).where(Preset.id == preset_id, Preset.user_id == user_id, Preset.project_id == project_id)
                result = await session.execute(query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error deleting preset: {str(e)}")
            raise


    async def get_preset_by_name(self, preset_name: str, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Preset).where(Preset.name == preset_name, Preset.user_id == user_id, Preset.project_id == project_id)
                result = await session.execute(query)
                preset = result.scalars().first()
                if preset:
                    return {"id": preset.id, "name": preset.name, "data": preset.data}
                return None
        except Exception as e:
            self.logger.error(f"Error getting preset by name: {str(e)}")
            return None


    async def update_chapter_embedding_id(self, chapter_id: str, embedding_id: str) -> bool:
        try:
            async with self.Session() as session:
                query = select(Chapter).where(Chapter.id == chapter_id)
                result = await session.execute(query)
                chapter = result.scalars().first()
                if chapter:
                    chapter.embedding_id = embedding_id
                    chapter.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return True
                else:
                    raise Exception("Chapter not found")
        except Exception as e:
            self.logger.error(f"Error updating chapter embedding_id: {str(e)}")
            raise

    async def delete_character_relationship(self, relationship_id: str, user_id: str, project_id: str) -> bool:
        try:
            async with self.Session() as session:
                query = delete(CharacterRelationship).where(
                    CharacterRelationship.id == relationship_id,
                    CharacterRelationship.user_id == user_id,
                    CharacterRelationship.project_id == project_id
                )
                result = await session.execute(query)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error deleting character relationship: {str(e)}")
            raise


    async def save_relationship_analysis(self, character1_id: str, character2_id: str, relationship_type: str, 
                             description: str, user_id: str, project_id: str) -> str:
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
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )
                session.add(analysis)
                await session.commit()
                return analysis.id
        except Exception as e:
            self.logger.error(f"Error saving relationship analysis: {str(e)}")
            raise

    async def get_character_relationships(self, project_id: str, user_id: str) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = (
                    select(CharacterRelationship)
                    .join(CodexItem, CharacterRelationship.character_id == CodexItem.id, isouter=True)
                    .join(CodexItem, CharacterRelationship.related_character_id == CodexItem.id, isouter=True, aliased=True)
                    .where(CharacterRelationship.project_id == project_id)
                    .options(
                        joinedload(CharacterRelationship.character),
                        joinedload(CharacterRelationship.related_character)
                    )
                )
                result = await session.execute(query)
                relationships = result.scalars().all()
                
                result = []
                for rel in relationships:
                    result.append({
                        'id': rel.id,
                        'character1_id': rel.character_id,
                        'character2_id': rel.related_character_id,
                        'character1_name': rel.character.name if rel.character else None,
                        'character2_name': rel.related_character.name if rel.related_character else None,
                        'relationship_type': rel.relationship_type,
                        'description': rel.description or ''
                    })
                return result
        except Exception as e:
            self.logger.error(f"Error getting character relationships: {str(e)}")
            raise


    async def update_character_backstory(self, character_id: str, backstory: str, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                # Fetch the character
                query = select(CodexItem).where(CodexItem.id == character_id, CodexItem.user_id == user_id, CodexItem.project_id == project_id, CodexItem.type == CodexItemType.CHARACTER.value)
                result = await session.execute(query)
                character = result.scalars().first()
                if not character:
                    raise ValueError(f"Character with ID {character_id} not found")

                # Update backstory and updated_at
                character.backstory = backstory
                character.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await session.commit()
        except Exception as e:
            self.logger.error(f"Error updating character backstory: {str(e)}")
            raise

    async def delete_character_backstory(self, character_id: str, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                # Fetch the character
                query = select(CodexItem).where(CodexItem.id == character_id, CodexItem.user_id == user_id, CodexItem.project_id == project_id, CodexItem.type == CodexItemType.CHARACTER.value)
                result = await session.execute(query)
                character = result.scalars().first()
                if not character:
                    raise ValueError(f"Character with ID {character_id} not found")

                # Update backstory and updated_at
                character.backstory = None
                character.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await session.commit()
        except Exception as e:
            self.logger.error(f"Error deleting character backstory: {str(e)}")
            raise

    async def get_chapter_count(self, project_id: str, user_id: str) -> int:
        try:
            async with self.Session() as session:
                query = select(func.count()).where(Chapter.project_id == project_id, Chapter.user_id == user_id)
                result = await session.execute(query)
                return result.scalar_one()
        except Exception as e:
            self.logger.error(f"Error getting chapter count: {str(e)}")
            raise

    async def create_event(self, title: str, description: str, date: datetime, project_id: str, user_id: str, character_id: Optional[str] = None, location_id: Optional[str] = None) -> str:
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
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )
                session.add(event)
                await session.commit()
                return event.id
        except Exception as e:
            self.logger.error(f"Error creating event: {str(e)}")
            raise

    async def save_character_backstory(self, character_id: str, content: str, user_id: str, project_id: str):
        try:
            async with self.Session() as session:
                # Fetch the character to verify it exists and check its current backstory
                query = select(CodexItem).where(CodexItem.id == character_id, CodexItem.user_id == user_id, CodexItem.project_id == project_id, CodexItem.type == CodexItemType.CHARACTER.value)
                result = await session.execute(query)
                character = result.scalars().first()
                
                if not character:
                    raise ValueError("Character not found or not of type character")
                
                # Update backstory and updated_at
                new_backstory = f"{character.backstory}\n\n{content}" if character.backstory else content
                character.backstory = new_backstory
                character.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                
                await session.commit()
                return character.to_dict()
                
        except Exception as e:
            self.logger.error(f"Error saving character backstory: {str(e)}")
            raise

    async def get_character_backstories(self, character_id: str) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(CharacterBackstory).where(CharacterBackstory.character_id == character_id).order_by(CharacterBackstory.created_at)
                result = await session.execute(query)
                backstories = result.scalars().all()
                return [backstory.to_dict() for backstory in backstories]
        except Exception as e:
            self.logger.error(f"Error getting character backstories: {str(e)}")
            raise

    async def get_latest_unprocessed_chapter_content(self, project_id: str, user_id: str, process_type: str):
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
                    {
                        'id': chapter.id,
                        'content': chapter.content
                    }
                    for chapter in chapters
                    if process_type not in chapter.processed_types
                ]
                
                return unprocessed_chapters
                
        except Exception as e:
            self.logger.error(f"Error getting unprocessed chapter content: {str(e)}")
            raise

    async def create_character_relationship(self, character_id: str, related_character_id: str, relationship_type: str, project_id: str, 
description: Optional[str] = None) -> str:
        try:
            async with self.Session() as session:
                # First verify both characters exist and are of type character
                char1_query = select(CodexItem).where(CodexItem.id == character_id, CodexItem.project_id == project_id, CodexItem.type == CodexItemType.CHARACTER.value)
                char2_query = select(CodexItem).where(CodexItem.id == related_character_id, CodexItem.project_id == project_id, CodexItem.type == CodexItemType.CHARACTER.value)
                
                char1_result = await session.execute(char1_query)
                char2_result = await session.execute(char2_query)
                
                char1 = char1_result.scalars().first()
                char2 = char2_result.scalars().first()
                
                if not char1:
                    self.logger.error(f"Character with ID {character_id} not found in the codex")
                    raise ValueError("Character not found")
                    
                if not char2:
                    self.logger.error(f"Character with ID {related_character_id} not found in the codex")
                    raise ValueError("Related character not found")
                
                relationship = CharacterRelationship(
                    id=str(uuid.uuid4()),
                    character_id=character_id,
                    related_character_id=related_character_id,
                    relationship_type=relationship_type,
                    description=description,
                    project_id=project_id
                )
                
                session.add(relationship)
                await session.commit()
                return relationship.id
                
        except Exception as e:
            self.logger.error(f"Error creating character relationship: {str(e)}")
            raise


    async def update_event(self, event_id: str, title: str, description: str, date: datetime, 
                      character_id: Optional[str], location_id: Optional[str], 
                      project_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Event).where(Event.id == event_id, Event.user_id == user_id, Event.project_id == project_id)
                result = await session.execute(query)
                event = result.scalars().first()
                if event:
                    event.title = title
                    event.description = description
                    event.date = date
                    event.character_id = character_id
                    event.location_id = location_id
                    event.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return event.to_dict()
                else:
                    raise Exception("Event not found")
        except Exception as e:
            self.logger.error(f"Error updating event: {str(e)}")
            raise

    async def get_event_by_title(self, title: str, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Event).where(Event.title == title, Event.user_id == user_id, Event.project_id == project_id)
                result = await session.execute(query)
                event = result.scalars().first()
                return event.to_dict() if event else None
        except Exception as e:
            self.logger.error(f"Error getting event by title: {str(e)}")
            raise

    async def update_location(self, location_id: str, location_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Location).where(Location.id == location_id)
                result = await session.execute(query)
                location = result.scalars().first()
                if location:
                    for key, value in location_data.items():
                        setattr(location, key, value)
                    location.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return location.to_dict()
                else:
                    raise Exception("Location not found")
        except Exception as e:
            self.logger.error(f"Error updating location: {str(e)}")
            raise

    
    async def update_character_relationship(self, relationship_id: str, relationship_type: str, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(CharacterRelationship).where(
                    CharacterRelationship.id == relationship_id,
                    CharacterRelationship.user_id == user_id,
                    CharacterRelationship.project_id == project_id
                )
                result = await session.execute(query)
                relationship = result.scalars().first()
                if relationship:
                    relationship.relationship_type = relationship_type
                    relationship.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return relationship.to_dict()
                else:
                    raise Exception("Character relationship not found")
        except Exception as e:
            self.logger.error(f"Error updating character relationship: {str(e)}")
            raise



    async def get_location_by_name(self, name: str, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = select(Location).where(Location.name == name, Location.user_id == user_id, Location.project_id == project_id)
                result = await session.execute(query)
                location = result.scalars().first()
                return location.to_dict() if location else None
        except Exception as e:
            self.logger.error(f"Error getting location by name: {str(e)}")
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
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )
                session.add(connection)
                await session.commit()
                return connection.id
                
        except Exception as e:
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
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )
                session.add(connection)
                await session.commit()
                return connection.id
        except Exception as e:
            self.logger.error(f"Error creating event connection: {str(e)}")
            raise

    async def get_location_connections(self, project_id: str, user_id: str) -> List[Dict[str, Any]]:
        try:
            async with self.Session() as session:
                query = (
                    select(LocationConnection)
                    .where(LocationConnection.project_id == project_id, LocationConnection.user_id == user_id)
                )
                result = await session.execute(query)
                connections = result.scalars().all()
                return [conn.to_dict() for conn in connections]
        except Exception as e:
            self.logger.error(f"Error getting location connections: {str(e)}")
            raise

    async def get_event_connections(self, project_id: str, user_id: str) -> List[Dict[str, Any]]:
        try:
            response = self.supabase.table('event_connections').select('*').eq('project_id', project_id).eq('user_id', user_id).execute()
            connections = response.data
            result = []
            for conn in connections:
                connection_dict = conn.to_dict()
                result.append(connection_dict)
            return result
        except Exception as e:
            self.logger.error(f"Error getting event connections: {str(e)}")
            raise
    
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
        try:
            update_data = {
                "connection_type": connection_type,
                "description": description,
                "travel_route": travel_route,
                "cultural_exchange": cultural_exchange,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            response = self.supabase.table('location_connections').update(update_data).eq('id', connection_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
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
        try:
            update_data = {
                "connection_type": connection_type,
                "description": description,
                "impact": impact,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            response = self.supabase.table('event_connections').update(update_data).eq('id', connection_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            self.logger.error(f"Error updating event connection: {str(e)}")
            raise

    async def delete_location_connection(self, connection_id: str, user_id: str, project_id: str) -> bool:
        try:
            response = self.supabase.table('location_connections').delete().eq('id', connection_id).eq('user_id', user_id).eq('project_id', project_id).execute()
            return bool(response.data)
        except Exception as e:
            self.logger.error(f"Error deleting location connection: {str(e)}")
            raise

    async def delete_event_connection(self, connection_id: str, user_id: str, project_id: str) -> bool:
        try:
            response = self.supabase.table('event_connections').delete().eq('id', connection_id).eq('user_id', user_id).eq('project_id', project_id).execute()
            return bool(response.data)
        except Exception as e:
            self.logger.error(f"Error deleting event connection: {str(e)}")
            raise

    async def approve_user(self, user_id: str) -> bool:
        try:
            response = self.supabase.table('user_approvals').update({'is_approved': True}).eq('id', user_id).execute()
            return bool(response.data)
        except Exception as e:
            self.logger.error(f"Error approving user: {str(e)}")
            return False

    async def delete_event(self, event_id: str, user_id: str, project_id: str) -> bool:
        try:
            # Delete event where id, user_id, and project_id match
            response = self.supabase.table('events').delete().eq('id', event_id).eq('user_id', user_id).eq('project_id', project_id).execute()
            
            # Return True if something was deleted, False otherwise
            return bool(response.data)
        except Exception as e:
            self.logger.error(f"Error deleting event: {str(e)}")
            raise


db_instance = Database()



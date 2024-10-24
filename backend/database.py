import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from sqlalchemy import delete  # Changed this line
from sqlalchemy import Column, String, Integer, Boolean, Text, ForeignKey, JSON, UniqueConstraint, DateTime, and_, func, QueuePool, select
from sqlalchemy.dialects.postgresql import TEXT, JSONB
import json
import os
from dotenv import load_dotenv
import uuid
import asyncio
from typing import Optional, List, Dict, Any
import datetime as dt  # Add this line if you need the module itself
from sqlalchemy import exists, alias
from models import ChapterValidation


load_dotenv()

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    api_key = Column(String)
    model_settings = Column(Text)

class Project(Base):
    __tablename__ = 'projects'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    universe_id = Column(String, ForeignKey('universes.id'), nullable=True)
    target_word_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Update the relationships with proper back_populates
    chapters = relationship("Chapter", back_populates="project", cascade="all, delete-orphan")
    validity_checks = relationship("ValidityCheck", back_populates="project", cascade="all, delete-orphan")
    codex_items = relationship("CodexItem", back_populates="project", cascade="all, delete-orphan")
    chat_histories = relationship("ChatHistory", back_populates="project", cascade="all, delete-orphan")
    presets = relationship("Preset", back_populates="project", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'universe_id': self.universe_id,
            'targetWordCount': self.target_word_count,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    project = relationship("Project", back_populates="chapters")
    processed_types = Column(JSON, default=list, nullable=False)  # Changed from lambda to list

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
    type = Column(String, nullable=False)
    subtype = Column(String)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    embedding_id = Column(String)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    # Add these fields for character-specific information
    backstory = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
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
            'type': self.type,
            'subtype': self.subtype,
            'backstory': self.backstory if self.type == 'character' else None,
            'embedding_id': self.embedding_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        if self.type == 'character':
            data['backstory'] = self.backstory
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
    user_id = Column(String, ForeignKey('users.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name
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

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'date': self.date.isoformat(),
            'character_id': self.character_id,
            'location_id': self.location_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Location(Base):
    __tablename__ = 'locations'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    coordinates = Column(String, nullable=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    events = relationship("Event", back_populates="location")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'coordinates': self.coordinates,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
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

# Add this with the other model definitions (around line 31)
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

class Database:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is not set")
        
        # Convert the database URL to use the async driver
        if db_url.startswith('postgresql://'):
            db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
        
        # Remove QueuePool and use default async pool settings
        self.engine = create_async_engine(
            db_url,
            echo=True,  # Set to False in production
            pool_pre_ping=True,
            pool_size=20,  # Adjust based on your needs
            max_overflow=10,
            pool_recycle=3600
        )
        self.Session = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def initialize(self):
        """Initialize the database by creating all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self):
        return self.Session()

    async def create_user(self, email, password):
        async with await self.get_session() as session:
            try:
                user = User(id=str(uuid.uuid4()), email=email, password=password)
                session.add(user)
                await session.commit()
                return user.id
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error creating user: {str(e)}")
                raise
            finally:
                await session.close()

    async def get_user_by_email(self, email):
        async with await self.get_session() as session:
            try:
                user = await session.execute(select(User).filter_by(email=email))
                user = user.scalars().first()
                if user:
                    return {
                        'id': user.id,
                        'username': user.email,
                        'hashed_password': user.password,
                        'email': user.email,
                        'api_key': user.api_key,
                        'model_settings': json.loads(user.model_settings) if user.model_settings else None
                    }
                return None
            finally:
                await session.close()

    async def get_all_chapters(self, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                chapters = await session.execute(select(Chapter).filter_by(user_id=user_id, project_id=project_id).order_by(Chapter.chapter_number))
                chapters = chapters.scalars().all()
                return [chapter.to_dict() for chapter in chapters]
            except Exception as e:
                self.logger.error(f"Error fetching all chapters: {str(e)}")
                raise
            finally:
                await session.close()

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
            finally:
                await session.close()

    async def update_chapter(self, chapter_id, title, content, user_id, project_id):
        async with await self.get_session() as session:
            try:
                chapter = await session.get(Chapter, chapter_id)
                if chapter and chapter.user_id == user_id and chapter.project_id == project_id:
                    chapter.title = title
                    chapter.content = content
                    await session.commit()
                    return chapter.to_dict()
                return None
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating chapter: {str(e)}")
                raise
            finally:
                await session.close()

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
                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting chapter: {str(e)}")
                raise
            finally:
                await session.close()

    async def get_chapter(self, chapter_id: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                chapter = await session.get(Chapter, chapter_id)
                if chapter and chapter.user_id == user_id and chapter.project_id == project_id:
                    return chapter.to_dict()
                return None
            finally:
                await session.close()

    async def get_all_validity_checks(self, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                checks = await session.execute(select(ValidityCheck).filter_by(user_id=user_id, project_id=project_id))
                checks = checks.scalars().all()
                return [check.to_dict() for check in checks]
            finally:
                await session.close()

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
            finally:
                await session.close()

    async def create_codex_item(self, name: str, description: str, type: str, subtype: Optional[str], user_id: str, project_id: str) -> str:
        async with await self.get_session() as session:
            try:
                # Create timezone-naive datetime objects
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
            finally:
                await session.close()

    async def get_all_codex_items(self, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                codex_items = await session.execute(select(CodexItem).filter_by(user_id=user_id, project_id=project_id))
                codex_items = codex_items.scalars().all()
                return [item.to_dict() for item in codex_items]
            finally:
                await session.close()

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
                return None
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating codex item: {str(e)}")
                raise
            finally:
                await session.close()

    async def delete_codex_item(self, item_id: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                codex_item = await session.get(CodexItem, item_id)
                if codex_item and codex_item.user_id == user_id and codex_item.project_id == project_id:
                    events = await session.execute(select(Event).filter_by(character_id=item_id))
                    events = events.scalars().all()
                    for event in events:
                        event.character_id = None
                        # Ensure the updated_at is timezone-naive
                        event.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

                    await session.delete(codex_item)
                    await session.commit()
                    return True
                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting codex item: {str(e)}")
                raise
            finally:
                await session.close()

    async def get_codex_item_by_id(self, item_id: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                codex_item = await session.get(CodexItem, item_id)
                if codex_item and codex_item.user_id == user_id and codex_item.project_id == project_id:
                    return codex_item.to_dict()
                return None
            finally:
                await session.close()

    async def save_api_key(self, user_id, api_key):
        async with await self.get_session() as session:
            try:
                user = await session.get(User, user_id)
                if user:
                    user.api_key = api_key
                    await session.commit()
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error saving API key: {str(e)}")
                raise
            finally:
                await session.close()

    async def get_api_key(self, user_id):
        async with await self.get_session() as session:
            try:
                user = await session.get(User, user_id)
                return user.api_key if user else None
            finally:
                await session.close()

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
            finally:
                await session.close()

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
            finally:
                await session.close()

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
            finally:
                await session.close()

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
            finally:
                await session.close()

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
                return None
            finally:
                await session.close()

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
            finally:
                await session.close()

    async def get_chat_history(self, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                chat_history = await session.execute(select(ChatHistory).filter_by(user_id=user_id, project_id=project_id))
                chat_history = chat_history.scalars().first()
                return json.loads(chat_history.messages) if chat_history else []
            finally:
                await session.close()

    async def delete_chat_history(self, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                chat_history = await session.get(ChatHistory, (user_id, project_id))
                if chat_history:
                    await session.delete(chat_history)
                    await session.commit()
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting chat history: {str(e)}")
                raise
            finally:
                await session.close()

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
            finally:
                await session.close()

    async def get_presets(self, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                presets = await session.execute(select(Preset).filter_by(user_id=user_id, project_id=project_id))
                presets = presets.scalars().all()
                return [{"id": preset.id, "name": preset.name, "data": preset.data} for preset in presets]
            finally:
                await session.close()

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
            finally:
                await session.close()

    async def get_preset_by_name(self, preset_name: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                preset = await session.execute(select(Preset).filter_by(name=preset_name, user_id=user_id, project_id=project_id))
                preset = preset.scalars().first()
                if preset:
                    return {"id": preset.id, "name": preset.name, "data": preset.data}
                return None
            finally:
                await session.close()

    # Add methods to update embedding_id for existing chapters and codex_items 

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
            finally:
                await session.close()

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
                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting character relationship: {str(e)}")
                raise
            finally:
                await session.close()

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
            finally:
                await session.close()

    async def get_character_by_id(self, character_id: str, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                character = await session.execute(select(CodexItem).filter(
                    CodexItem.id == character_id,
                    CodexItem.project_id == project_id,
                    CodexItem.user_id == user_id,  # Add user_id filter
                    CodexItem.type == 'character'
                ))
                character = character.scalars().first()
                
                if character:
                    return character.to_dict()
                return None
            finally:
                await session.close()

    async def get_latest_chapter_content(self, project_id: str) -> Optional[str]:
        async with await self.get_session() as session:
            try:
                latest_chapter = await session.execute(select(Chapter).filter(
                    Chapter.project_id == project_id
                ).order_by(Chapter.chapter_number.desc()))
                latest_chapter = latest_chapter.scalars().first()
                
                if latest_chapter:
                    return latest_chapter.content
                return None
            finally:
                await session.close()

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
            finally:
                await session.close()


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
            finally:
                await session.close()

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
            finally:
                await session.close()


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
            finally:
                await session.close()

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
            finally:
                await session.close()

    async def delete_location(self, location_id: str, user_id: str, project_id: str) -> bool:
        async with await self.get_session() as session:
            try:
                location = await session.get(Location, location_id)
                if location and location.user_id == user_id and location.project_id == project_id:
                    await session.delete(location)
                    await session.commit()
                    return True
                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error deleting location: {str(e)}")
                raise
            finally:
                await session.close()

    async def delete_event(self, event_id: str, user_id: str, project_id: str) -> bool:
        async with await self.get_session() as session:
            try:
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
            finally:
                await session.close()

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
            finally:
                await session.close()

    async def is_chapter_processed_for_type(self, chapter_id: str, process_type: str) -> bool:
        async with await self.get_session() as session:
            try:
                chapter = await session.get(Chapter, chapter_id)
                if chapter and isinstance(chapter.processed_types, list):
                    return process_type in chapter.processed_types
                return False
            finally:
                await session.close()

    async def get_latest_chapter(self, project_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                chapter = await session.execute(select(Chapter).filter_by(
                    project_id=project_id,
                    user_id=user_id
                ).order_by(Chapter.chapter_number.desc()))
                chapter = chapter.scalars().first()
                
                if chapter:
                    return chapter.to_dict()
                return None
            finally:
                await session.close()

    async def get_event_by_id(self, event_id: str, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                event = await session.get(Event, event_id)
                if event and event.user_id == user_id and event.project_id == project_id:
                    return event.to_dict()
                return None
            finally:
                await session.close()

    async def get_location_by_id(self, location_id: str, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                location = await session.get(Location, location_id)
                if location and location.user_id == user_id and location.project_id == project_id:
                    return location.to_dict()
                return None
            finally:
                await session.close()

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
            finally:
                await session.close()

    async def create_project(self, name: str, description: str, user_id: str, universe_id: Optional[str] = None) -> str:
        async with await self.get_session() as session:
            try:
                # Create timezone-naive datetime objects
                current_time = datetime.now(timezone.utc).replace(tzinfo=None)
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
                await session.rollback()
                self.logger.error(f"Error creating project: {str(e)}")
                raise
            finally:
                await session.close()

    async def get_projects(self, user_id: str) -> List[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                projects = await session.execute(select(Project).filter_by(user_id=user_id))
                projects = projects.scalars().all()
                return [project.to_dict() for project in projects]
            finally:
                await session.close()

    async def get_projects_by_universe(self, universe_id: str, user_id: str) -> List[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                projects = await session.execute(select(Project).filter_by(universe_id=universe_id, user_id=user_id))
                projects = projects.scalars().all()
                return [project.to_dict() for project in projects]
            finally:
                await session.close()

    async def get_project(self, project_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                project = await session.get(Project, project_id)
                if project and project.user_id == user_id:
                    return project.to_dict()
                return None
            finally:
                await session.close()

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
                return None
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating project: {str(e)}")
                raise
            finally:
                await session.close()

    async def update_project_universe(self, project_id: str, universe_id: Optional[str], user_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                project = await session.get(Project, project_id)
                if project and project.user_id == user_id:
                    project.universe_id = universe_id
                    # Use a timezone-naive datetime
                    project.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return project.to_dict()
                return None
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating project universe: {str(e)}")
                raise
            finally:
                await session.close()

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
            finally:
                await session.close()

    async def get_universes(self, user_id: str) -> List[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                universes = await session.execute(select(Universe).filter_by(user_id=user_id))
                universes = universes.scalars().all()
                return [universe.to_dict() for universe in universes]
            except Exception as e:
                self.logger.error(f"Error fetching universes: {str(e)}")
                raise
            finally:
                await session.close()

    async def create_universe(self, name: str, user_id: str) -> str:
        async with await self.get_session() as session:
            try:
                universe = Universe(id=str(uuid.uuid4()), name=name, user_id=user_id)
                session.add(universe)
                await session.commit()
                return universe.id
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error creating universe: {str(e)}")
                raise ValueError(str(e))  # Ensure the error is a string
            finally:
                await session.close()

    async def get_universe(self, universe_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                universe = await session.get(Universe, universe_id)
                if universe and universe.user_id == user_id:
                    return universe.to_dict()
                return None
            finally:
                await session.close()

    async def update_universe(self, universe_id: str, name: str, user_id: str) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                universe = await session.get(Universe, universe_id)
                if universe and universe.user_id == user_id:
                    universe.name = name
                    await session.commit()
                    return universe.to_dict()
                return None
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating universe: {str(e)}")
                raise
            finally:
                await session.close()

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
            finally:
                await session.close()

    async def get_universe_codex(self, universe_id: str, user_id: str) -> List[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                codex_items = await session.execute(select(CodexItem).join(Project).filter(
                    and_(Project.universe_id == universe_id, CodexItem.user_id == user_id)
                ))
                codex_items = codex_items.scalars().all()
                return [item.to_dict() for item in codex_items]
            finally:
                await session.close()

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
            finally:
                await session.close()

    async def get_character_by_name(self, name: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                character = await session.execute(select(CodexItem).filter_by(name=name, user_id=user_id, project_id=project_id, type='character'))
                character = character.scalars().first()
                if character:
                    return character.to_dict()
                return None
            finally:
                await session.close()

    async def get_events(self, project_id: str, user_id: str) -> List[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                events = await session.execute(select(Event).filter_by(project_id=project_id))
                events = events.scalars().all()
                return [event.to_dict() for event in events]
            finally:
                await session.close()

    async def get_locations(self, user_id: str, project_id: str) -> List[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                locations = await session.execute(select(Location).filter_by(user_id=user_id, project_id=project_id))
                locations = locations.scalars().all()
                return [location.to_dict() for location in locations]
            finally:
                await session.close()

    async def is_chapter_processed(self, chapter_id: str, project_id: str) -> bool:
        async with await self.get_session() as session:
            try:
                processed_chapter = await session.execute(select(ProcessedChapter).filter_by(
                    chapter_id=chapter_id, 
                    project_id=project_id
                ))
                processed_chapter = processed_chapter.scalars().first()
                return processed_chapter is not None
            finally:
                await session.close()

    async def mark_latest_chapter_processed(self, project_id: str, function_name: str):
        async with await self.get_session() as session:
            try:
                latest_chapter = await session.execute(select(Chapter).filter(
                    Chapter.project_id == project_id
                ).order_by(Chapter.chapter_number.desc()))
                latest_chapter = latest_chapter.scalars().first()

                if latest_chapter:
                    processed_chapter = ProcessedChapter(
                        id=str(uuid.uuid4()),
                        chapter_id=latest_chapter.id,
                        project_id=project_id,
                        processed_at=lambda: datetime.now(timezone.utc)
                    )
                    session.add(processed_chapter)
                    await session.commit()
            finally:
                await session.close()

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
                return None
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error saving character backstory: {str(e)}")
                raise
            finally:
                await session.close()

    async def get_character_backstories(self, character_id: str) -> List[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                backstories = await session.execute(select(CharacterBackstory).filter_by(character_id=character_id).order_by(CharacterBackstory.created_at))
                backstories = backstories.scalars().all()
                return [backstory.to_dict() for backstory in backstories]
            finally:
                await session.close()

    async def get_characters_from_codex(self, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                characters = await session.execute(select(CodexItem).filter_by(
                    user_id=user_id, 
                    project_id=project_id, 
                    type='character'
                ))
                characters = characters.scalars().all()
                return [character.to_dict() for character in characters]
            finally:
                await session.close()

    async def get_latest_unprocessed_chapter_content(self, project_id: str, user_id: str, process_type: str):
        async with await self.get_session() as session:
            try:
                # Use JSON containment operator @> instead of LIKE
                chapter = await session.execute(
                    select(Chapter).filter(
                        Chapter.project_id == project_id,
                        Chapter.user_id == user_id,
                        ~Chapter.processed_types.cast(JSONB).contains([process_type])
                    ).order_by(Chapter.chapter_number.desc())
                )
                chapter = chapter.scalars().first()
                
                if chapter:
                    return {
                        'id': chapter.id,
                        'content': chapter.content
                    }
                return None
            finally:
                await session.close()

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
            finally:
                await session.close()

    async def update_event(self, event_id: str, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                event = await session.get(Event, event_id)
                if event:
                    for key, value in event_data.items():
                        setattr(event, key, value)
                    await session.commit()
                    return event.to_dict()
                return None
            finally:
                await session.close()

    async def get_event_by_title(self, title: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                event = await session.execute(select(Event).filter_by(title=title, user_id=user_id, project_id=project_id))
                event = event.scalars().first()
                return event.to_dict() if event else None
            finally:
                await session.close()


    async def get_location_by_title(self, title: str, user_id: str, project_id: str):
        async with await self.get_session() as session:
            try:
                location = await session.execute(select(Location).filter_by(title=title, user_id=user_id, project_id=project_id))
                location = location.scalars().first()
                return location.to_dict() if location else None
            finally:
                await session.close()

    async def update_location(self, location_id: str, location_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with await self.get_session() as session:
            try:
                location = await session.get(Location, location_id)
                if location:
                    for key, value in location_data.items():
                        setattr(location, key, value)
                    await session.commit()
                    return location.to_dict()
                return None
            finally:
                await session.close()
                

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
                return None
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Error updating character relationship: {str(e)}")
                raise
            finally:
                await session.close()
    
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
                return None
            finally:
                await session.close()

    async def dispose(self):
        """Dispose of the engine and close all connections."""
        if self.engine:
            await self.engine.dispose()

db_instance = Database()



# backend/database.py
import logging
from sqlalchemy import create_engine, Column, String, Integer, Boolean, Text, ForeignKey, JSON, UniqueConstraint, DateTime, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, joinedload, relationship
from sqlalchemy.pool import QueuePool
from sqlalchemy.dialects.postgresql import TEXT
import json
import os
from dotenv import load_dotenv
import uuid
import asyncio
from typing import Optional, List, Dict, Any
import datetime
from datetime import timezone
from sqlalchemy import exists
from sqlalchemy import alias


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
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc), onupdate=lambda: datetime.datetime.now(timezone.utc))

    # Add these relationships with cascade delete
    chapters = relationship("Chapter", cascade="all, delete-orphan", back_populates="project")
    validity_checks = relationship("ValidityCheck", cascade="all, delete-orphan", back_populates="project")
    codex_items = relationship("CodexItem", cascade="all, delete-orphan", back_populates="project")
    chat_histories = relationship("ChatHistory", cascade="all, delete-orphan", back_populates="project")
    presets = relationship("Preset", cascade="all, delete-orphan", back_populates="project")

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
    title = Column(String(255), nullable=False)
    content = Column(TEXT, nullable=False)
    chapter_number = Column(Integer, nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    embedding_id = Column(String)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    last_processed_position = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    project = relationship("Project", back_populates="chapters")

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
    overall_score = Column(Integer) # Added overall_score
    general_feedback = Column(Text) # Changed feedback to general_feedback
    style_guide_adherence_score = Column(Integer) # Added style_guide_adherence_score
    style_guide_adherence_explanation = Column(Text) # Added style_guide_adherence_explanation
    continuity_score = Column(Integer) # Added continuity_score
    continuity_explanation = Column(Text) # Added continuity_explanation
    areas_for_improvement = Column(JSON) # Changed test_results to areas_for_improvement
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    project = relationship("Project", back_populates="validity_checks")

    def to_dict(self):
        return {
            'id': self.id,
            'chapterId': self.chapter_id,
            'chapterTitle': self.chapter_title,
            'isValid': self.is_valid,
            'overallScore': self.overall_score, # Added overallScore
            'generalFeedback': self.general_feedback, # Changed feedback to generalFeedback
            'styleGuideAdherenceScore': self.style_guide_adherence_score, # Added styleGuideAdherenceScore
            'styleGuideAdherenceExplanation': self.style_guide_adherence_explanation, # Added styleGuideAdherenceExplanation
            'continuityScore': self.continuity_score, # Added continuityScore
            'continuityExplanation': self.continuity_explanation, # Added continuityExplanation
            'areasForImprovement': self.areas_for_improvement # Changed test_results to areasForImprovement
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
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc), onupdate=lambda: datetime.datetime.now(timezone.utc))
    
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
    processed_at = Column(DateTime, default=datetime.datetime.utcnow)
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
    character_id = Column(String, ForeignKey('codex_items.id'), nullable=True)  # Change this
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    location_id = Column(String, ForeignKey('locations.id'), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc), onupdate=lambda: datetime.datetime.now(timezone.utc))

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
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc), onupdate=lambda: datetime.datetime.now(timezone.utc))

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
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))

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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.datetime.now(timezone.utc))

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
        
        self.engine = create_engine(db_url, poolclass=QueuePool, pool_size=20, max_overflow=0, 
                                    client_encoding='utf8')
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        
        Base.metadata.create_all(self.engine)

    def get_session(self):
        return self.Session()

    def create_user(self, email, password):
        session = self.get_session()
        try:
            user = User(id=str(uuid.uuid4()), email=email, password=password)
            session.add(user)
            session.commit()
            return user.id
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error creating user: {str(e)}")
            raise
        finally:
            session.close()

    def get_user_by_email(self, email):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(email=email).first()
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
            session.close()

    def get_all_chapters(self, user_id: str, project_id: str):
        session = self.get_session()
        try:
            chapters = session.query(Chapter).filter_by(user_id=user_id, project_id=project_id).order_by(Chapter.chapter_number).all()
            return [chapter.to_dict() for chapter in chapters]
        except Exception as e:
            self.logger.error(f"Error fetching all chapters: {str(e)}")
            raise
        finally:
            session.close()

    async def create_chapter(self, title, content, user_id, project_id):
        return await asyncio.to_thread(self._create_chapter, title, content, user_id, project_id)

    def _create_chapter(self, title, content, user_id, project_id, embedding_id=None):
        session = self.get_session()
        try:
            chapter_number = session.query(Chapter).filter_by(user_id=user_id, project_id=project_id).count() + 1
            chapter = Chapter(
                id=str(uuid.uuid4()),
                title=title,
                content=content,
                chapter_number=chapter_number,
                user_id=user_id,
                project_id=project_id,
                embedding_id=embedding_id
            )
            session.add(chapter)
            session.commit()
            return chapter.to_dict()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error creating chapter: {str(e)}")
            raise
        finally:
            session.close()

    def update_chapter(self, chapter_id, title, content, user_id, project_id):
        session = self.get_session()
        try:
            chapter = session.query(Chapter).filter_by(id=chapter_id, user_id=user_id, project_id=project_id).first()
            if chapter:
                chapter.title = title
                chapter.content = content
                session.commit()
                return chapter.to_dict()
            return None
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error updating chapter: {str(e)}")
            raise
        finally:
            session.close()

    def delete_chapter(self, chapter_id, user_id, project_id):
        session = self.get_session()
        try:
            # First, delete related validity checks
            session.query(ValidityCheck).filter_by(chapter_id=chapter_id, user_id=user_id, project_id=project_id).delete()

            # Then, delete the chapter
            chapter = session.query(Chapter).filter_by(id=chapter_id, user_id=user_id, project_id=project_id).first()
            if chapter:
                session.delete(chapter)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error deleting chapter: {str(e)}")
            raise
        finally:
            session.close()

    def get_chapter(self, chapter_id, user_id, project_id):
        session = self.get_session()
        try:
            chapter = session.query(Chapter).filter_by(id=chapter_id, user_id=user_id, project_id=project_id).first()
            if chapter:
                return chapter.to_dict()
            return None
        finally:
            session.close()

    def get_all_validity_checks(self, user_id: str, project_id: str):
        session = self.get_session()
        try:
            checks = session.query(ValidityCheck).filter_by(user_id=user_id, project_id=project_id).all()
            return [check.to_dict() for check in checks]
        finally:
            session.close()

    def delete_validity_check(self, check_id, user_id, project_id):
        session = self.get_session()
        try:
            validity_check = session.query(ValidityCheck).filter_by(id=check_id, user_id=user_id, project_id=project_id).first()
            if validity_check:
                session.delete(validity_check)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error deleting validity check: {str(e)}")
            raise
        finally:
            session.close()

    async def create_codex_item(self, name: str, description: str, item_type: str, subtype: Optional[str], user_id: str, project_id: str) -> str:
        session = self.get_session()
        try:
            item_id = str(uuid.uuid4())
            new_item = CodexItem(
                id=item_id,
                name=name,
                description=description,
                type=item_type,
                subtype=subtype,
                user_id=user_id,
                project_id=project_id
            )
            session.add(new_item)
            session.commit()
            return item_id
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error creating codex item: {str(e)}")
            raise
        finally:
            session.close()

    def get_all_codex_items(self, user_id: str, project_id: str):
        session = self.get_session()
        try:
            codex_items = session.query(CodexItem).filter_by(user_id=user_id, project_id=project_id).all()
            return [item.to_dict() for item in codex_items]
        finally:
            session.close()

    def update_codex_item(self, item_id: str, name: str, description: str, type: str, subtype: str, user_id: str, project_id: str):
        session = self.get_session()
        try:
            codex_item = session.query(CodexItem).filter_by(id=item_id, user_id=user_id, project_id=project_id).first()
            if codex_item:
                codex_item.name = name
                codex_item.description = description
                codex_item.type = type
                codex_item.subtype = subtype
                session.commit()
                return codex_item.to_dict()
            return None
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error updating codex item: {str(e)}")
            raise
        finally:
            session.close()

    def delete_codex_item(self, item_id: str, user_id: str, project_id: str):
        session = self.get_session()
        try:
            codex_item = session.query(CodexItem).filter_by(id=item_id, user_id=user_id, project_id=project_id).first()
            if codex_item:
                session.delete(codex_item)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error deleting codex item: {str(e)}")
            raise
        finally:
            session.close()

    def get_codex_item_by_id(self, item_id: str, user_id: str, project_id: str):
        session = self.get_session()
        try:
            codex_item = session.query(CodexItem).filter_by(id=item_id, user_id=user_id, project_id=project_id).first()
            if codex_item:
                return codex_item.to_dict()
            return None
        finally:
            session.close()

    def save_api_key(self, user_id, api_key):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                user.api_key = api_key
                session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error saving API key: {str(e)}")
            raise
        finally:
            session.close()

    def get_api_key(self, user_id):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            return user.api_key if user else None
        finally:
            session.close()

    def remove_api_key(self, user_id):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                user.api_key = None
                session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error removing API key: {str(e)}")
            raise
        finally:
            session.close()

    def save_model_settings(self, user_id, settings):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                user.model_settings = json.dumps(settings)
                session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error saving model settings: {str(e)}")
            raise
        finally:
            session.close()

    def get_model_settings(self, user_id):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if user and user.model_settings:
                return json.loads(user.model_settings)
            return {
                'mainLLM': 'gemini-1.5-pro-002',
                'checkLLM': 'gemini-1.5-pro-002',
                'embeddingsModel': 'models/text-embedding-004',
                'titleGenerationLLM': 'gemini-1.5-pro-002',
                'CodexExtractionLLM': 'gemini-1.5-pro-002',
                'knowledgeBaseQueryLLM': 'gemini-1.5-pro-002'
            }
        finally:
            session.close()

    async def save_validity_check(self, chapter_id: str, chapter_title: str, is_valid: bool, overall_score: int, general_feedback: str, style_guide_adherence_score: int, style_guide_adherence_explanation: str, continuity_score: int, continuity_explanation: str, areas_for_improvement: List[str], user_id: str, project_id: str):
        return await asyncio.to_thread(self._save_validity_check, chapter_id, chapter_title, is_valid, overall_score, general_feedback, style_guide_adherence_score, style_guide_adherence_explanation, continuity_score, continuity_explanation, areas_for_improvement, user_id, project_id)

    def _save_validity_check(self, chapter_id: str, chapter_title: str, is_valid: bool, overall_score: int, general_feedback: str, style_guide_adherence_score: int, style_guide_adherence_explanation: str, continuity_score: int, continuity_explanation: str, areas_for_improvement: List[str], user_id: str, project_id: str):
        session = self.get_session()
        try:
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
                areas_for_improvement=areas_for_improvement,
                user_id=user_id,
                project_id=project_id
            )
            session.add(validity_check)
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error saving validity check: {str(e)}")
            raise
        finally:
            session.close()

    def save_chat_history(self, user_id: str, project_id: str, messages: List[Dict[str, Any]]):
        session = self.get_session()
        try:
            chat_history = session.query(ChatHistory).filter_by(user_id=user_id, project_id=project_id).first()
            
            # Convert ChatHistoryItem objects to dictionaries
            serializable_messages = [
                {"type": msg["type"], "content": msg["content"]}
                for msg in messages
            ]
            
            if chat_history:
                chat_history.messages = json.dumps(serializable_messages)
            else:
                chat_history = ChatHistory(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    project_id=project_id,
                    messages=json.dumps(serializable_messages)
                )
                session.add(chat_history)
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error saving chat history: {str(e)}")
            raise
        finally:
            session.close()

    def get_chat_history(self, user_id: str, project_id: str):
        session = self.get_session()
        try:
            chat_history = session.query(ChatHistory).filter_by(user_id=user_id, project_id=project_id).first()
            return json.loads(chat_history.messages) if chat_history else []
        finally:
            session.close()

    def delete_chat_history(self, user_id: str, project_id: str):
        session = self.get_session()
        try:
            chat_history = session.query(ChatHistory).filter_by(user_id=user_id, project_id=project_id).first()
            if chat_history:
                session.delete(chat_history)
                session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error deleting chat history: {str(e)}")
            raise
        finally:
            session.close()
    def create_preset(self, user_id: str, project_id: str, name: str, data: Dict[str, Any]):
        session = self.get_session()
        try:
            # Check if a preset with the same name, user_id, and project_id already exists
            existing_preset = session.query(Preset).filter_by(user_id=user_id, project_id=project_id, name=name).first()
            if existing_preset:
                raise ValueError(f"A preset with name '{name}' already exists for this user and project.")
            
            preset = Preset(id=str(uuid.uuid4()), user_id=user_id, project_id=project_id, name=name, data=data)
            session.add(preset)
            session.commit()
            return preset.id
        except ValueError as ve:
            session.rollback()
            self.logger.error(f"Error creating preset: {str(ve)}")
            raise
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error creating preset: {str(e)}")
            raise
        finally:
            session.close()

    def get_presets(self, user_id: str, project_id: str):
        session = self.get_session()
        try:
            presets = session.query(Preset).filter_by(user_id=user_id, project_id=project_id).all()
            return [{"id": preset.id, "name": preset.name, "data": preset.data} for preset in presets]
        finally:
            session.close()

    def delete_preset(self, preset_name: str, user_id: str, project_id: str):
        session = self.get_session()
        try:
            preset = session.query(Preset).filter_by(name=preset_name, user_id=user_id, project_id=project_id).first()
            if preset:
                session.delete(preset)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error deleting preset: {str(e)}")
            raise
        finally:
            session.close()

    def get_preset_by_name(self, preset_name: str, user_id: str, project_id: str):
        session = self.get_session()
        try:
            preset = session.query(Preset).filter_by(name=preset_name, user_id=user_id, project_id=project_id).first()
            if preset:
                return {"id": preset.id, "name": preset.name, "data": preset.data}
            return None
        finally:
            session.close()

    # Add methods to update embedding_id for existing chapters and codex_items 

    def update_chapter_embedding_id(self, chapter_id, embedding_id):
        session = self.get_session()
        try:
            chapter = session.query(Chapter).filter_by(id=chapter_id).first()
            if chapter:
                chapter.embedding_id = embedding_id
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error updating chapter embedding_id: {str(e)}")
            raise
        finally:
            session.close()

    def update_codex_item_embedding_id(self, item_id, embedding_id):
        session = self.get_session()
        try:
            codex_item = session.query(CodexItem).filter_by(id=item_id).first()
            if codex_item:
                codex_item.embedding_id = embedding_id
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error updating codex item embedding_id: {str(e)}")
            raise
        finally:
            session.close()

    def create_project(self, name: str, description: str, user_id: str, universe_id: Optional[str] = None) -> str:
        session = self.get_session()
        try:
            project = Project(id=str(uuid.uuid4()), name=name, description=description, user_id=user_id, universe_id=universe_id)
            session.add(project)
            session.commit()
            return project.id
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error creating project: {str(e)}")
            raise
        finally:
            session.close()

    def get_projects(self, user_id: str) -> List[Dict[str, Any]]:
        session = self.get_session()
        try:
            projects = session.query(Project).filter_by(user_id=user_id).all()
            return [project.to_dict() for project in projects]
        finally:
            session.close()

    def get_projects_by_universe(self, universe_id: str, user_id: str) -> List[Dict[str, Any]]:
        session = self.get_session()
        try:
            projects = session.query(Project).filter_by(universe_id=universe_id, user_id=user_id).all()
            return [project.to_dict() for project in projects]
        finally:
            session.close()

    def get_project(self, project_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session()
        try:
            project = session.query(Project).filter_by(id=project_id, user_id=user_id).first()
            return project.to_dict() if project else None
        finally:
            session.close()

    def update_project(self, project_id: str, name: Optional[str], description: Optional[str], user_id: str, universe_id: Optional[str] = None, target_word_count: Optional[int] = None) -> Optional[Dict[str, Any]]:
        session = self.get_session()
        try:
            project = session.query(Project).filter_by(id=project_id, user_id=user_id).first()
            if project:
                if name is not None:
                    project.name = name
                if description is not None:
                    project.description = description
                if universe_id is not None:
                    project.universe_id = universe_id
                if target_word_count is not None:
                    project.target_word_count = target_word_count
                project.updated_at = datetime.datetime.now(timezone.utc)
                session.commit()
                return project.to_dict()
            return None
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error updating project: {str(e)}")
            raise
        finally:
            session.close()

    def update_project_universe(self, project_id: str, universe_id: Optional[str], user_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session()
        try:
            project = session.query(Project).filter_by(id=project_id, user_id=user_id).first()
            if project:
                project.universe_id = universe_id  # This can now be None
                project.updated_at = datetime.datetime.now(timezone.utc)
                session.commit()
                return project.to_dict()
            return None
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error updating project universe: {str(e)}")
            raise
        finally:
            session.close()

    def delete_project(self, project_id: str, user_id: str) -> bool:
        session = self.get_session()
        try:
            project = session.query(Project).filter_by(id=project_id, user_id=user_id).first()
            if project:
                session.delete(project)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error deleting project: {str(e)}")
            raise
        finally:
            session.close()

    def get_universes(self, user_id: str) -> List[Dict[str, Any]]:
        session = self.get_session()
        try:
            universes = session.query(Universe).filter_by(user_id=user_id).all()
            return [universe.to_dict() for universe in universes]
        except Exception as e:
            self.logger.error(f"Error fetching universes: {str(e)}")
            raise
        finally:
            session.close()

    def create_universe(self, name: str, user_id: str) -> str:
        session = self.get_session()
        try:
            universe = Universe(id=str(uuid.uuid4()), name=name, user_id=user_id)
            session.add(universe)
            session.commit()
            return universe.id
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error creating universe: {str(e)}")
            raise ValueError(str(e))  # Ensure the error is a string
        finally:
            session.close()

    def get_universe(self, universe_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session()
        try:
            universe = session.query(Universe).filter(and_(Universe.id == universe_id, Universe.user_id == user_id)).first()
            if universe:
                return universe.to_dict()
            return None
        finally:
            session.close()

    def update_universe(self, universe_id: str, name: str, user_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session()
        try:
            universe = session.query(Universe).filter(and_(Universe.id == universe_id, Universe.user_id == user_id)).first()
            if universe:
                universe.name = name
                session.commit()
                return universe.to_dict()
            return None
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error updating universe: {str(e)}")
            raise
        finally:
            session.close()

    def delete_universe(self, universe_id: str, user_id: str) -> bool:
        session = self.get_session()
        try:
            universe = session.query(Universe).filter(and_(Universe.id == universe_id, Universe.user_id == user_id)).first()
            if universe:
                session.delete(universe)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error deleting universe: {str(e)}")
            raise
        finally:
            session.close()

    def get_universe_codex(self, universe_id: str, user_id: str) -> List[Dict[str, Any]]:
        session = self.get_session()
        try:
            codex_items = session.query(CodexItem).join(Project).filter(
                and_(Project.universe_id == universe_id, CodexItem.user_id == user_id)
            ).all()
            return [item.to_dict() for item in codex_items]
        finally:
            session.close()

    def get_universe_knowledge_base(self, universe_id: str, user_id: str, limit: int = 100, offset: int = 0) -> Dict[str, List[Dict[str, Any]]]:
        session = self.get_session()
        try:
            # Fetch all projects for the given universe
            projects = session.query(Project).filter_by(universe_id=universe_id, user_id=user_id).all()
            project_ids = [project.id for project in projects]

            # Initialize the result dictionary
            knowledge_base = {project.id: [] for project in projects}

            # Fetch chapters and codex items with pagination
            for project_id in project_ids:
                chapters = session.query(Chapter).filter_by(project_id=project_id).limit(limit).offset(offset).all()
                codex_items = session.query(CodexItem).filter_by(project_id=project_id).limit(limit).offset(offset).all()

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
            session.close()

    def get_projects_by_universe(self, universe_id: str, user_id: str) -> List[Dict[str, Any]]:
        session = self.get_session()
        try:
            projects = session.query(Project).filter_by(universe_id=universe_id, user_id=user_id).all()
            return [project.to_dict() for project in projects]
        finally:
            session.close()

    def get_character(self, character_id: str, user_id: str, project_id: str):
        return self.get_codex_item_by_id(character_id, user_id, project_id)

    def get_character_by_name(self, name: str, user_id: str, project_id: str):
        session = self.get_session()
        try:
            character = session.query(CodexItem).filter_by(name=name, user_id=user_id, project_id=project_id, type='character').first()
            if character:
                return character.to_dict()
            return None
        finally:
            session.close()


    def create_event(self, title: str, description: str, date: datetime, character_id: Optional[str], location_id: Optional[str], project_id: str, user_id: str) -> str:
        session = self.get_session()
        try:
            # Check if the project exists and belongs to the user
            project_exists = session.query(exists().where(and_(Project.id == project_id, Project.user_id == user_id))).scalar()
            if not project_exists:
                raise ValueError("Project not found or doesn't belong to the user")

            event = Event(id=str(uuid.uuid4()), title=title, description=description, date=date, character_id=character_id, location_id=location_id, project_id=project_id)
            session.add(event)
            session.commit()
            return event.id
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error creating event: {str(e)}")
            raise
        finally:
            session.close()

    def get_events(self, project_id: str, user_id: str) -> List[Dict[str, Any]]:
        session = self.get_session()
        try:
            # Check if the project belongs to the user
            project_exists = session.query(exists().where(and_(Project.id == project_id, Project.user_id == user_id))).scalar()
            if not project_exists:
                raise ValueError("Project not found or doesn't belong to the user")

            events = session.query(Event).filter_by(project_id=project_id).all()
            return [event.to_dict() for event in events]
        finally:
            session.close()

    def create_location(self, name: str, description: str, coordinates: Optional[str], user_id: str, project_id: str) -> str:
        session = self.get_session()
        try:
            # Check if the project exists and belongs to the user
            project_exists = session.query(exists().where(and_(Project.id == project_id, Project.user_id == user_id))).scalar()
            if not project_exists:
                raise ValueError("Project not found or doesn't belong to the user")

            location = Location(id=str(uuid.uuid4()), name=name, description=description, coordinates=coordinates, user_id=user_id, project_id=project_id)
            session.add(location)
            session.commit()
            return location.id
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error creating location: {str(e)}")
            raise
        finally:
            session.close()

    def get_locations(self, user_id: str, project_id: str) -> List[Dict[str, Any]]:
        session = self.get_session()
        try:
            locations = session.query(Location).filter_by(user_id=user_id, project_id=project_id).all()
            return [location.to_dict() for location in locations]
        finally:
            session.close()


    def is_chapter_processed(self, chapter_id: str, project_id: str) -> bool:
        session = self.get_session()
        try:
            processed_chapter = session.query(ProcessedChapter).filter_by(
                chapter_id=chapter_id, 
                project_id=project_id
            ).first()
            return processed_chapter is not None
        finally:
            session.close()

    def mark_latest_chapter_processed(self, project_id: str, function_name: str):
        session = self.get_session()
        try:
            latest_chapter = session.query(Chapter).filter(
                Chapter.project_id == project_id
            ).order_by(Chapter.created_at.desc()).first()

            if latest_chapter:
                processed_chapter = ProcessedChapter(
                    id=str(uuid.uuid4()),
                    chapter_id=latest_chapter.id,
                    project_id=project_id,
                    processed_at=datetime.datetime.utcnow(),
                    function_name=function_name
                )
                session.add(processed_chapter)
                session.commit()
        finally:
            session.close()

    def get_remaining_chapter_content(self, chapter_id: str, project_id: str) -> Optional[str]:
        session = self.get_session()
        try:
            chapter = session.query(Chapter).filter_by(
                id=chapter_id, 
                project_id=project_id
            ).first()
            if chapter:
                return chapter.content[chapter.last_processed_position:]
            return None
        finally:
            session.close()

    def save_character_backstory(self, character_id: str, content: str, user_id: str, project_id: str):
        session = self.get_session()
        try:
            character = session.query(CodexItem).filter_by(
                id=character_id, 
                user_id=user_id, 
                project_id=project_id, 
                type='character'
            ).first()
            if character:
                if character.backstory:
                    character.backstory += f"\n\n{content}"
                else:
                    character.backstory = content
                character.updated_at = datetime.datetime.now(timezone.utc)
                session.commit()
                return character.to_dict()
            return None
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error saving character backstory: {str(e)}")
            raise
        finally:
            session.close()

    def get_character_backstories(self, character_id: str) -> List[Dict[str, Any]]:
        session = self.get_session()
        try:
            backstories = session.query(CharacterBackstory).filter_by(character_id=character_id).order_by(CharacterBackstory.created_at).all()
            return [backstory.to_dict() for backstory in backstories]
        finally:
            session.close()

    def get_characters_from_codex(self, user_id: str, project_id: str):
        session = self.get_session()
        try:
            characters = session.query(CodexItem).filter_by(
                user_id=user_id, 
                project_id=project_id, 
                type='character'
            ).all()
            return [character.to_dict() for character in characters]
        finally:
            session.close()

    def mark_latest_chapter_processed(self, project_id: str, function_name: str):
        session = self.get_session()
        try:
            latest_chapter = session.query(Chapter).filter(
                Chapter.project_id == project_id
            ).order_by(Chapter.chapter_number.desc()).first()  # Changed from created_at to chapter_number

            if latest_chapter:
                processed_chapter = ProcessedChapter(
                    id=str(uuid.uuid4()),
                    chapter_id=latest_chapter.id,
                    project_id=project_id,
                    processed_at=datetime.datetime.utcnow()
                )
                session.add(processed_chapter)
                session.commit()
        finally:
            session.close()

    def get_latest_unprocessed_chapter_content(self, project_id: str, function_name: str) -> Optional[str]:
        session = self.get_session()
        try:
            # Query for the latest chapter that hasn't been processed for this function
            latest_chapter = session.query(Chapter).filter(
                Chapter.project_id == project_id,
                ~exists().where(
                    and_(
                        ProcessedChapter.chapter_id == Chapter.id,
                        ProcessedChapter.project_id == project_id
                    )
                )
            ).order_by(Chapter.chapter_number.desc()).first()  # Changed from created_at to chapter_number

            if latest_chapter:
                return latest_chapter.content
            return None
        finally:
            session.close()

    def create_character_relationship(self, character_id: str, related_character_id: str, 
                                    relationship_type: str, project_id: str, 
                                    description: Optional[str] = None) -> str:
        session = self.get_session()
        try:
            # Ensure character IDs are not None before querying
            if character_id is None or related_character_id is None:
                raise ValueError("Character IDs cannot be None")
            
            # Check if both characters exist in the codex_items table
            character = session.query(CodexItem).filter_by(id=character_id, project_id=project_id, type='character').first()
            related_character = session.query(CodexItem).filter_by(id=related_character_id, project_id=project_id, type='character').first()
            
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
            session.commit()
            return relationship.id
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error creating character relationship: {str(e)}")
            raise
        finally:
            session.close()


    def update_character_relationship(self, relationship_id: str, relationship_type: str, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session()
        try:
            relationship = session.query(CharacterRelationship).join(
                CodexItem, CharacterRelationship.character_id == CodexItem.id
            ).filter(
                CharacterRelationship.id == relationship_id,
                CodexItem.project_id == project_id,
                CodexItem.user_id == user_id
            ).first()
            if relationship:
                relationship.relationship_type = relationship_type
                session.commit()
                return relationship.to_dict()
            return None
        except Exception as e:
            session.rollback()

    def delete_character_relationship(self, relationship_id: str, user_id: str, project_id: str) -> bool:
        session = self.get_session()
        try:
            relationship = session.query(CharacterRelationship).join(
                CodexItem, CharacterRelationship.character_id == CodexItem.id
            ).filter(
                CharacterRelationship.id == relationship_id,
                CodexItem.project_id == project_id,
                CodexItem.user_id == user_id
            ).first()
            if relationship:
                session.delete(relationship)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error deleting character relationship: {str(e)}")
            raise
        finally:
            session.close()

    def save_relationship_analysis(self, character1_id: str, character2_id: str, relationship_type: str, 
                                 description: str, user_id: str, project_id: str) -> str:
        session = self.get_session()
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
            session.commit()
            return analysis.id
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error saving relationship analysis: {str(e)}")
            raise
        finally:
            session.close()


    def get_character_by_id(self, character_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session()
        try:
            character = session.query(CodexItem).filter(
                CodexItem.id == character_id,
                CodexItem.project_id == project_id,
                CodexItem.type == 'character'
            ).first()
            
            if character:
                return character.to_dict()
            return None
        finally:
            session.close()

    def get_latest_chapter_content(self, project_id: str) -> Optional[str]:
        session = self.get_session()
        try:
            latest_chapter = session.query(Chapter).filter(
                Chapter.project_id == project_id
            ).order_by(Chapter.chapter_number.desc()).first()
            
            if latest_chapter:
                return latest_chapter.content
            return None
        finally:
            session.close()

    def get_character_relationships(self, project_id: str, user_id: str) -> List[Dict[str, Any]]:
        session = self.get_session()
        try:
            relationships = (
                session.query(CharacterRelationship)
                .join(
                    CodexItem,
                    CharacterRelationship.character_id == CodexItem.id
                )
                .filter(
                    CodexItem.project_id == project_id,
                    CodexItem.user_id == user_id
                )
                .all()
            )

            result = []
            for rel in relationships:
                character1 = session.query(CodexItem).filter_by(id=rel.character_id).first()
                character2 = session.query(CodexItem).filter_by(id=rel.related_character_id).first()
                
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
            session.close()

    def update_character_backstory(self, character_id: str, backstory: str, user_id: str, project_id: str):
        session = self.get_session()
        try:
            character = session.query(CodexItem).filter(
                CodexItem.id == character_id,
                CodexItem.user_id == user_id,
                CodexItem.project_id == project_id
            ).first()
            
            if character:
                character.backstory = backstory
                session.commit()
            else:
                raise ValueError("Character not found")
        finally:
            session.close()

    def delete_character_backstory(self, character_id: str, user_id: str, project_id: str):
        session = self.get_session()
        try:
            character = session.query(CodexItem).filter(
                CodexItem.id == character_id,
                CodexItem.user_id == user_id,
                CodexItem.project_id == project_id
            ).first()
            
            if character:
                character.backstory = None
                session.commit()
            else:
                raise ValueError("Character not found")
        finally:
            session.close()

db_instance = Database()

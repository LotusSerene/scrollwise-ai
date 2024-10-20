# backend/database.py
import logging
from sqlalchemy import create_engine, Column, String, Integer, Boolean, Text, ForeignKey, JSON, UniqueConstraint, DateTime, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, joinedload
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
    target_word_count = Column(Integer, default=0) # Added target_word_count column
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc), onupdate=lambda: datetime.datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'universe_id': self.universe_id,
            'targetWordCount': self.target_word_count, # Added targetWordCount to dict
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

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'chapter_number': self.chapter_number,
            'embedding_id': self.embedding_id
        }

class ValidityCheck(Base):
    __tablename__ = 'validity_checks'
    id = Column(String, primary_key=True)
    chapter_id = Column(String, ForeignKey('chapters.id'), nullable=False)
    chapter_title = Column(String)
    is_valid = Column(Boolean)
    feedback = Column(Text)
    review = Column(Text)
    style_guide_adherence = Column(Boolean)
    style_guide_feedback = Column(Text)
    continuity = Column(Boolean)
    continuity_feedback = Column(Text)
    test_results = Column(Text)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'chapterId': self.chapter_id,
            'chapterTitle': self.chapter_title,
            'isValid': self.is_valid,
            'feedback': self.feedback,
            'review': self.review,
            'style_guide_adherence': self.style_guide_adherence,
            'style_guide_feedback': self.style_guide_feedback,
            'continuity': self.continuity,
            'continuity_feedback': self.continuity_feedback,
            'test_results': self.test_results
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

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'type': self.type,
            'subtype': self.subtype,
            'embedding_id': self.embedding_id
        }

class ChatHistory(Base):
    __tablename__ = 'chat_history'
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    messages = Column(Text, nullable=False)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)

class Preset(Base):
    __tablename__ = 'presets'
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    name = Column(String, nullable=False)
    data = Column(JSON, nullable=False)
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'name', name='_user_preset_uc'),)

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

    async def save_validity_check(self, chapter_id: str, chapter_title: str, is_valid: bool, feedback: str, review: str, style_guide_adherence: bool, style_guide_feedback: str, continuity: bool, continuity_feedback: str, test_results: str, user_id: str, project_id: str):
        return await asyncio.to_thread(self._save_validity_check, chapter_id, chapter_title, is_valid, feedback, review, style_guide_adherence, style_guide_feedback, continuity, continuity_feedback, test_results, user_id, project_id)

    def _save_validity_check(self, chapter_id: str, chapter_title: str, is_valid: bool, feedback: str, review: str, style_guide_adherence: bool, style_guide_feedback: str, continuity: bool, continuity_feedback: str, test_results: str, user_id: str, project_id: str):
        session = self.get_session()
        try:
            validity_check = ValidityCheck(
                id=str(uuid.uuid4()),
                chapter_id=chapter_id,
                chapter_title=chapter_title,
                is_valid=is_valid,
                feedback=feedback,
                review=review,
                style_guide_adherence=style_guide_adherence,
                style_guide_feedback=style_guide_feedback,
                continuity=continuity,
                continuity_feedback=continuity_feedback,
                test_results=test_results,
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
                # Delete related data in the correct order
                # First, delete validity checks
                session.query(ValidityCheck).filter_by(project_id=project_id).delete()
                
                # Then delete chapters
                session.query(Chapter).filter_by(project_id=project_id).delete()
                
                # Delete other related data
                session.query(CodexItem).filter_by(project_id=project_id).delete()
                session.query(ChatHistory).filter_by(project_id=project_id).delete()
                session.query(Preset).filter_by(project_id=project_id).delete()
                
                # Finally, delete the project
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

    def get_universe_knowledge_base(self, universe_id: str, user_id: str) -> Dict[str, List[Dict[str, Any]]]:
        session = self.get_session()
        try:
            # Fetch all projects for the given universe
            projects = session.query(Project).filter_by(universe_id=universe_id, user_id=user_id).all()
            project_ids = [project.id for project in projects]

            # Initialize the result dictionary
            knowledge_base = {project.id: [] for project in projects}

            # Fetch all chapters for these projects
            chapters = session.query(Chapter).filter(Chapter.project_id.in_(project_ids)).all()
            for chapter in chapters:
                knowledge_base[chapter.project_id].append({
                    'id': chapter.id,
                    'type': 'chapter',
                    'title': chapter.title,
                    'content': chapter.content,
                    'embedding_id': chapter.embedding_id
                })

            # Fetch all codex items for these projects
            codex_items = session.query(CodexItem).filter(CodexItem.project_id.in_(project_ids)).all()
            for item in codex_items:
                knowledge_base[item.project_id].append({
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

db_instance = Database()

def get_chapter_count(user_id):
    session = db_instance.get_session()
    try:
        return session.query(Chapter).filter_by(user_id=user_id).count()
    finally:
        session.close()


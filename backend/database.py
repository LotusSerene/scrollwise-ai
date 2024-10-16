# backend/database.py
import logging
from sqlalchemy import create_engine, Column, String, Integer, Boolean, Text, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, joinedload
from sqlalchemy.pool import QueuePool
import json
import os
from dotenv import load_dotenv
import uuid
import asyncio
load_dotenv()

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    api_key = Column(String)
    model_settings = Column(Text)

class Chapter(Base):
    __tablename__ = 'chapters'
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    chapter_number = Column(Integer, nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    embedding_id = Column(String)  # New column

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'chapter_number': self.chapter_number,
            'embedding_id': self.embedding_id  # Include embedding_id
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

class Character(Base):
    __tablename__ = 'characters'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    embedding_id = Column(String)  # New column

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'embedding_id': self.embedding_id  # Include embedding_id
        }

class ChatHistory(Base):
    __tablename__ = 'chat_history'
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    messages = Column(Text, nullable=False)

class Preset(Base): # New table for presets
    __tablename__ = 'presets'
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    name = Column(String, nullable=False)
    data = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'name', name='_user_preset_uc'),)

class Database:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is not set")
        
        self.engine = create_engine(db_url, poolclass=QueuePool, pool_size=20, max_overflow=0)
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
                    'username': user.email,  # Map email to username
                    'hashed_password': user.password,  # Use hashed_password instead of password
                    'email': user.email,
                    'api_key': user.api_key,
                    'model_settings': json.loads(user.model_settings) if user.model_settings else None
                }
            return None
        finally:
            session.close()

    def get_all_chapters(self, user_id):
        session = self.get_session()
        try:
            chapters = session.query(Chapter).filter_by(user_id=user_id).order_by(Chapter.chapter_number).all()
            return [chapter.to_dict() for chapter in chapters]
        finally:
            session.close()

    async def create_chapter(self, title, content, user_id):
        return await asyncio.to_thread(self._create_chapter, title, content, user_id)

    def _create_chapter(self, title, content, user_id, embedding_id=None):
        session = self.get_session()
        try:
            chapter_number = session.query(Chapter).filter_by(user_id=user_id).count() + 1
            chapter = Chapter(id=str(uuid.uuid4()), title=title, content=content, chapter_number=chapter_number, user_id=user_id, embedding_id=embedding_id)
            session.add(chapter)
            session.commit()
            return chapter.to_dict()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error creating chapter: {str(e)}")
            raise
        finally:
            session.close()

    def update_chapter(self, chapter_id, title, content, user_id):
        session = self.get_session()
        try:
            chapter = session.query(Chapter).filter_by(id=chapter_id, user_id=user_id).first()
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

    def delete_chapter(self, chapter_id, user_id):
        session = self.get_session()
        try:
            # First, delete related validity checks
            session.query(ValidityCheck).filter_by(chapter_id=chapter_id, user_id=user_id).delete()

            # Then, delete the chapter
            chapter = session.query(Chapter).filter_by(id=chapter_id, user_id=user_id).first()
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

    def get_chapter(self, chapter_id, user_id):
        session = self.get_session()
        try:
            chapter = session.query(Chapter).filter_by(id=chapter_id, user_id=user_id).first()
            if chapter:
                return {
                    'id': chapter.id,
                    'title': chapter.title,
                    'content': chapter.content,
                    'chapter_number': chapter.chapter_number,
                    'embedding_id': chapter.embedding_id  # Include embedding_id
                }
            return None
        finally:
            session.close()

    def get_all_validity_checks(self, user_id):
        session = self.get_session()
        try:
            checks = session.query(ValidityCheck).filter_by(user_id=user_id).all()
            return [check.to_dict() for check in checks]
        finally:
            session.close()

    def delete_validity_check(self, check_id, user_id):
        session = self.get_session()
        try:
            validity_check = session.query(ValidityCheck).filter_by(id=check_id, user_id=user_id).first()
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

    async def create_character(self, name, description, user_id):
        return await asyncio.to_thread(self._create_character, name, description, user_id)

    def _create_character(self, name, description, user_id, embedding_id=None):
        session = self.get_session()
        try:
            character = Character(id=str(uuid.uuid4()), name=name, description=description, user_id=user_id, embedding_id=embedding_id)
            session.add(character)
            session.commit()
            return character.id
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error creating character: {str(e)}")
            raise
        finally:
            session.close()

    def get_all_characters(self, user_id):
        session = self.get_session()
        try:
            characters = session.query(Character).filter_by(user_id=user_id).all()
            return [character.to_dict() for character in characters]
        finally:
            session.close()

    def update_character(self, character_id, name, description, user_id):
        session = self.get_session()
        try:
            character = session.query(Character).filter_by(id=character_id, user_id=user_id).first()
            if character:
                character.name = name
                character.description = description
                session.commit()
                return character.to_dict()
            return None
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error updating character: {str(e)}")
            raise
        finally:
            session.close()

    def delete_character(self, character_id, user_id):
        session = self.get_session()
        try:
            character = session.query(Character).filter_by(id=character_id, user_id=user_id).first()
            if character:
                session.delete(character)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error deleting character: {str(e)}")
            raise
        finally:
            session.close()

    def get_character_by_id(self, character_id, user_id):
        session = self.get_session()
        try:
            character = session.query(Character).filter_by(id=character_id, user_id=user_id).first()
            if character:
                return {
                    'id': character.id,
                    'name': character.name,
                    'description': character.description,
                    'embedding_id': character.embedding_id  # Include embedding_id
                }
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
                'characterExtractionLLM': 'gemini-1.5-pro-002',
                'knowledgeBaseQueryLLM': 'gemini-1.5-pro-002'
            }
        finally:
            session.close()

    async def save_validity_check(self, chapter_id, chapter_title, is_valid, feedback, review, style_guide_adherence, style_guide_feedback, continuity, continuity_feedback, test_results, user_id):
        return await asyncio.to_thread(self._save_validity_check, chapter_id, chapter_title, is_valid, feedback, review, style_guide_adherence, style_guide_feedback, continuity, continuity_feedback, test_results, user_id)

    def _save_validity_check(self, chapter_id, chapter_title, is_valid, feedback, review, style_guide_adherence, style_guide_feedback, continuity, continuity_feedback, test_results, user_id):
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
                user_id=user_id
            )
            session.add(validity_check)
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error saving validity check: {str(e)}")
            raise
        finally:
            session.close()

    def save_chat_history(self, user_id, messages):
        session = self.get_session()
        try:
            chat_history = session.query(ChatHistory).filter_by(user_id=user_id).first()
            if chat_history:
                chat_history.messages = json.dumps(messages)
            else:
                chat_history = ChatHistory(id=str(uuid.uuid4()), user_id=user_id, messages=json.dumps(messages))
                session.add(chat_history)
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error saving chat history: {str(e)}")
            raise
        finally:
            session.close()

    def get_chat_history(self, user_id):
        session = self.get_session()
        try:
            chat_history = session.query(ChatHistory).filter_by(user_id=user_id).first()
            return json.loads(chat_history.messages) if chat_history else []
        finally:
            session.close()

    def delete_chat_history(self, user_id):
        session = self.get_session()
        try:
            chat_history = session.query(ChatHistory).filter_by(user_id=user_id).first()
            if chat_history:
                session.delete(chat_history)
                session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error deleting chat history: {str(e)}")
            raise
        finally:
            session.close()
    def create_preset(self, user_id, name, data):
        session = self.get_session()
        try:
            # Check if a preset with the same name and user_id already exists
            existing_preset = session.query(Preset).filter_by(user_id=user_id, name=name).first()
            if existing_preset:
                raise ValueError(f"A preset with name '{name}' already exists for this user.")
            
            preset = Preset(id=str(uuid.uuid4()), user_id=user_id, name=name, data=data)
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

    def get_presets(self, user_id):
        session = self.get_session()
        try:
            presets = session.query(Preset).filter_by(user_id=user_id).all()
            return [{"id": preset.id, "name": preset.name, "data": preset.data} for preset in presets]
        finally:
            session.close()

    def delete_preset(self, preset_name, user_id):
        session = self.get_session()
        try:
            preset = session.query(Preset).filter_by(name=preset_name, user_id=user_id).first()
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

    def get_preset_by_name(self, preset_name, user_id):
        session = self.get_session()
        try:
            preset = session.query(Preset).filter_by(name=preset_name, user_id=user_id).first()
            if preset:
                return {"id": preset.id, "name": preset.name, "data": preset.data}
            return None
        finally:
            session.close()

    # Add methods to update embedding_id for existing chapters and characters 

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

    def update_character_embedding_id(self, character_id, embedding_id):
        session = self.get_session()
        try:
            character = session.query(Character).filter_by(id=character_id).first()
            if character:
                character.embedding_id = embedding_id
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error updating character embedding_id: {str(e)}")
            raise
        finally:
            session.close()


db_instance = Database()

def get_chapter_count(user_id):
    session = db_instance.get_session()
    try:
        return session.query(Chapter).filter_by(user_id=user_id).count()
    finally:
        session.close()
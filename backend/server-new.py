import asyncio
import io
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, AsyncGenerator
from asyncio import Lock
from sqlalchemy import select, and_

import os
import uuid
from models import CodexItemType, WorldbuildingSubtype # Keep specific imports
from database import User, Chapter, Project, CodexItem # Keep specific imports
from fastapi import (
    FastAPI, HTTPException, Depends, Request, File, UploadFile, Form, Body, Header, Query
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel, Field, ValidationError, EmailStr
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Import the refactored AgentManager and the new global close function
from agent_manager import AgentManager, PROCESS_TYPES, close_all_agent_managers
from api_key_manager import ApiKeyManager, SecurityManager
from database import db_instance
# Models likely needed by server endpoints too
from models import (
    CodexItemType, WorldbuildingSubtype, CodexItemGenerateRequest,
    ChapterGenerationRequest, KnowledgeBaseQuery, ChatHistoryRequest, ChatHistoryItem,
    ModelSettings, ApiKeyUpdate, UserCreate, ChapterCreate, ChapterUpdate,
    CodexItemCreate, CodexItemUpdate, PresetCreate, PresetUpdate,
    ProjectCreate, ProjectUpdate, UniverseCreate, UniverseUpdate,
    UpdateTargetWordCountRequest, BackstoryExtractionRequest
)

# PDF/DOCX processing imports
from PyPDF2 import PdfReader
import pdfplumber
from docx import Document as DocxDocument # Rename to avoid clash with langchain Document

import sys
import signal

# --- Logging Setup (Assuming setup_logging() function exists as before) ---
logger = logging.getLogger(__name__) # Use standard logger setup from previous example

# --- Global Variables ---
shutdown_event = asyncio.Event()


class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.sessions_file = 'sessions.json'  # Add this line to define the file path
        self._load_sessions()
        
    def _load_sessions(self):
        try:
            if os.path.exists(self.sessions_file) and os.path.getsize(self.sessions_file) > 0:
                with open(self.sessions_file, 'r') as f:
                    loaded_sessions = json.load(f)
                    # Convert ISO format strings back to datetime objects
                    self.sessions = {
                        sid: {
                            'user_id': session['user_id'],
                            'created_at': datetime.fromisoformat(session['created_at']),
                            'last_activity': datetime.fromisoformat(session['last_activity'])
                        }
                        for sid, session in loaded_sessions.items()
                    }
            else:
                self.sessions = {}
        except Exception as e:
            logger.error(f"Error loading sessions: {str(e)}")
            self.sessions = {}
            
    def _save_sessions(self):
        try:
            # Convert datetime objects to ISO format strings for JSON serialization
            sessions_to_save = {
                sid: {
                    'user_id': session['user_id'],
                    'created_at': session['created_at'].isoformat(),
                    'last_activity': session['last_activity'].isoformat()
                }
                for sid, session in self.sessions.items()
            }
            with open(self.sessions_file, 'w') as f:
                json.dump(sessions_to_save, f)
        except Exception as e:
            logger.error(f"Error saving sessions: {str(e)}")
        
    async def create_session(self, user_id: str) -> str:
        session_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc)  # Ensure UTC timezone
        self.sessions[session_id] = {
            'user_id': user_id,
            'created_at': current_time,  # Store as datetime object
            'last_activity': current_time  # Store as datetime object
        }
        self._save_sessions()
        return session_id
        
    async def validate_session(self, session_id: str) -> Optional[str]:
        session = self.sessions.get(session_id)
        if session:
            # Convert stored datetime to UTC if not already
            last_activity = session['last_activity']
            if not last_activity.tzinfo:
                last_activity = last_activity.replace(tzinfo=timezone.utc)
                
            if (datetime.now(timezone.utc) - last_activity).total_seconds() > MAX_INACTIVITY:
                await self.remove_session(session_id)
                return None
                
            # Update last activity with timezone-aware datetime
            session['last_activity'] = datetime.now(timezone.utc)
            self._save_sessions()
            return session['user_id']
        return None
        
    async def remove_session(self, session_id: str):
        self.sessions.pop(session_id, None)
        self._save_sessions()

    async def extend_session(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        if session:
            session['last_activity'] = datetime.now(timezone.utc)
            self._save_sessions()
            return True
        return False

# Initialize session manager
session_manager = SessionManager()


# AgentManagerStore

class AgentManagerStore:
    def __init__(self, api_key_manager: ApiKeyManager):
        self._managers = {}
        self._lock = Lock()
        self.api_key_manager = api_key_manager

    @asynccontextmanager
    async def get_or_create_manager(self, user_id: str, project_id: str) -> AsyncGenerator[AgentManager, None]:
        key = f"{user_id}_{project_id}"
        manager = None
        try:
            async with self._lock:
                manager = self._managers.get(key)
                if not manager:
                    # Pass api_key_manager when creating new manager
                    manager = await AgentManager.create(user_id, project_id, self.api_key_manager)
                    self._managers[key] = manager
            yield manager
        finally:
            if manager:
                await manager.close()
                async with self._lock:
                    self._managers.pop(key, None)

# --- Lifespan Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup
    logger.info("Starting up server...")
    cleanup_task = None
    
    try:
        # Initialize database
        logger.info("Initializing database...")
        await db_instance.initialize()
        
        # Create Qdrant data directory if it doesn't exist
        qdrant_path = Path("./qdrant_db")
        qdrant_path.mkdir(exist_ok=True)
        logger.info(f"Qdrant data directory: {qdrant_path.absolute()}")
        
        # Start session cleanup task
        async def cleanup_sessions():
            try:
                while getattr(app.state, "keep_alive", True):
                    current_time = datetime.now(timezone.utc)
                    expired_sessions = [
                        sid for sid, session in session_manager.sessions.items()
                        if (current_time - session['last_activity']).total_seconds() > MAX_INACTIVITY
                    ]
                    for sid in expired_sessions:
                        await session_manager.remove_session(sid)
                    await asyncio.sleep(300)  # Run every 5 minutes
            except asyncio.CancelledError:
                logger.info("Session cleanup task cancelled")
            except Exception as e:
                logger.error(f"Error in cleanup task: {str(e)}")
        
        cleanup_task = asyncio.create_task(cleanup_sessions())
        
        yield
        
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down server...")
        
        # Cancel cleanup task
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all agent managers to properly close vector stores
        for key, manager in list(agent_manager_store._managers.items()):
            try:
                await manager.close()
                logger.info(f"Closed agent manager for user {key[0][:8]}, project {key[1][:8]}")
            except Exception as e:
                logger.error(f"Error closing agent manager: {str(e)}")
        
        # Close database connection
        try:
            await db_instance.dispose()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {str(e)}")
    # Shutdown
    shutdown_event.set()
    logger.info("Server shutdown complete.")


# --- FastAPI App Setup ---
app = FastAPI(
    title="Scrollwise AI",
    version="1.1.0", # Increment version
    lifespan=lifespan,
    default_response_class=JSONResponse,
    default_encoding="utf-8"
)

# CORS Middleware
allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:8080').split(',')

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

MAX_INACTIVITY = 7 * 24 * 3600  # 1 week in seconds
ACTIVE_SESSION_EXTEND = 3600    # 1 hour extension when active


security_manager = SecurityManager()
api_key_manager = ApiKeyManager(security_manager)
agent_manager_store = AgentManagerStore(api_key_manager)



async def get_current_user(
    session_id: str = Header(None, alias="X-Session-ID"),
    authorization: str = Header(None)
):
    try:
        if not authorization or not session_id:
            raise HTTPException(
                status_code=401, 
                detail="Missing authentication credentials"
            )

        # Extract token from Authorization header
        token = authorization.replace("Bearer ", "")
        
        # Get user from Supabase token
        try:
            user_response = db_instance.supabase.auth.get_user(token)
        except Exception as e:
            # Try to refresh the token if possible
            try:
                refresh_response = await db_instance.supabase.auth.refresh_session()
                if refresh_response and refresh_response.user:
                    return refresh_response.user
            except:
                pass
            raise HTTPException(status_code=401, detail="Session expired. Please login again.")

        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
            
        # Check if user exists in local database
        local_user = await db_instance.get_user_by_email(user_response.user.email)
        if not local_user:
            # Only create new user if they don't exist
            try:
                local_user = await db_instance.sign_up(
                    email=user_response.user.email,
                    supabase_id=user_response.user.id,
                    password=None  # We don't need password here as user is already authenticated
                )
                if not local_user:
                    raise Exception("Failed to create local user")
            except Exception as e:
                # If creation fails (e.g. due to race condition), try getting the user again
                local_user = await db_instance.get_user_by_email(user_response.user.email)
                if not local_user:
                    raise e
            
        # Validate session
        session_user_id = await session_manager.validate_session(session_id)
        if not session_user_id or session_user_id != user_response.user.id:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        return user_response.user

    except Exception as e:
        logger.error(f"Error validating token: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

async def get_current_active_user(current_user = Depends(get_current_user)):
    try:
        # Check if user exists
        if not current_user:
            raise HTTPException(
                status_code=401,
                detail="Could not validate credentials"
            )
        
        # Check if user is active
        if not current_user.email_confirmed_at:
            raise HTTPException(
                status_code=403,
                detail="Email not verified"
            )

        return current_user
        
    except Exception as e:
        logger.error(f"Error validating active user: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        )


async def get_project_stats(project_id: str, user_id: str) -> Dict[str, int]:
    """Get statistics for a project including chapter count and word count."""
    try:
        async with db_instance.Session() as session:
            # Get chapters using SQLAlchemy
            query = select(Chapter).where(
                and_(
                    Chapter.project_id == project_id,
                    Chapter.user_id == user_id
                )
            )
            result = await session.execute(query)
            chapters = result.scalars().all()

            # Calculate stats
            chapter_count = len(chapters)
            word_count = 0
            
            # Calculate word count from all chapters
            for chapter in chapters:
                if chapter.content:
                    # Split content by whitespace and count words
                    words = chapter.content.strip().split()
                    word_count += len(words)

            return {
                "chapter_count": chapter_count,
                "word_count": word_count
            }
    except Exception as e:
        logger.error(f"Error getting project stats: {str(e)}")
        raise

async def get_universe_stats(universe_id: str, user_id: str) -> Dict[str, int]:
    """Get statistics for a universe including project count and total entries."""
    try:
        async with db_instance.Session() as session:
            # Get project count
            project_query = select(Project).where(
                and_(
                    Project.universe_id == universe_id,
                    Project.user_id == user_id
                )
            )
            result = await session.execute(project_query)
            projects = result.scalars().all()
            project_count = len(projects)

            # Get project IDs
            project_ids = [project.id for project in projects]

            # Get codex items count
            codex_count = 0
            if project_ids:
                codex_query = select(CodexItem).where(
                    and_(
                        CodexItem.project_id.in_(project_ids),
                        CodexItem.user_id == user_id
                    )
                )
                result = await session.execute(codex_query)
                codex_items = result.scalars().all()
                codex_count = len(codex_items)

            return {
                "project_count": project_count,
                "entry_count": codex_count
            }
    except Exception as e:
        logger.error(f"Error getting universe stats: {str(e)}")
        raise

# --- API Routers ---
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
chapter_router = APIRouter(prefix="/chapters", tags=["Chapters"])
codex_item_router = APIRouter(prefix="/codex-items", tags=["Codex Items"])
knowledge_base_router = APIRouter(prefix="/knowledge-base", tags=["Knowledge Base"])
settings_router = APIRouter(prefix="/settings", tags=["Settings"])
preset_router = APIRouter(prefix="/presets", tags=["Presets"])
project_router = APIRouter(prefix="/projects", tags=["Projects"])
universe_router = APIRouter(prefix="/universes", tags=["Universes"])
codex_router = APIRouter(prefix="/codex", tags=["Codex"]) # Keep if distinct from codex_item_router
relationship_router = APIRouter(prefix="/relationships", tags=["Relationships"])
event_router = APIRouter(prefix="/events", tags=["Events"])
location_router = APIRouter(prefix="/locations", tags=["Locations"])
# Add validity check router if needed
validity_router = APIRouter(prefix="/validity-checks", tags=["Validity Checks"])


# --- Project Routes ---

@project_router.put("/{project_id}/target-word-count")
async def update_project_target_word_count(
    project_id: str,
    update_data: UpdateTargetWordCountRequest,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Assuming db_instance method exists and is correct
        updated_project = await db_instance.update_project(
            project_id=project_id,
            name=None, description=None, # Only updating target word count
            user_id=current_user.id,
            universe_id=None,
            target_word_count=update_data.targetWordCount
        )
        if not updated_project:
            raise HTTPException(status_code=404, detail="Project not found")
        return updated_project
    except Exception as e:
        logger.error(f"Error updating project target word count: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@project_router.post("/{project_id}/refresh-knowledge-base")
async def refresh_project_knowledge_base(
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    logger.info(f"Starting knowledge base refresh for project {project_id}")
    added_count = 0
    skipped_count = 0
    error_count = 0

    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:

            logger.info("Resetting knowledge base via AgentManager...")
            restored_item_keys = await agent_manager.reset_knowledge_base() # Returns set of keys
            restored_count = len(restored_item_keys)
            logger.info(f"Restored {restored_count} items from backup.")

            logger.info("Fetching current project data from database...")
            chapters = await db_instance.get_all_chapters(current_user.id, project_id)
            codex_items = await db_instance.get_all_codex_items(current_user.id, project_id)
            # Fetch other potentially indexed items if needed (relationships, etc.)
            # relationships = await db_instance.get_character_relationships(project_id, current_user.id)
            # events = await db_instance.get_events(project_id, current_user.id)
            # locations = await db_instance.get_locations(current_user.id, project_id)

            logger.info(f"Re-indexing items not restored from backup...")

            # Re-index Chapters
            for chapter in chapters:
                item_key = f"chapter_{chapter['id']}"
                if item_key not in restored_item_keys:
                    try:
                        metadata = {
                            "id": chapter['id'], # Use DB ID
                            "title": chapter['title'],
                            "type": "chapter",
                            "chapter_number": chapter.get('chapter_number')
                        }
                        embedding_id = await agent_manager.add_to_knowledge_base(
                            "chapter", chapter['content'], metadata
                        )
                        if embedding_id:
                            await db_instance.update_chapter_embedding_id(chapter['id'], embedding_id)
                            added_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        logger.error(f"Error re-indexing chapter {chapter['id']}: {e}")
                        error_count += 1
                else:
                    skipped_count += 1

            # Re-index Codex Items (and Backstory if applicable)
            for item in codex_items:
                item_key = f"{item['type']}_{item['id']}" # Key based on type and ID
                if item_key not in restored_item_keys:
                    try:
                        metadata = {
                            "id": item['id'], # Use DB ID
                            "name": item['name'],
                            "type": item['type'],
                            "subtype": item.get('subtype'),
                        }
                        embedding_id = await agent_manager.add_to_knowledge_base(
                            item['type'], item['description'], metadata
                        )
                        if embedding_id:
                            await db_instance.update_codex_item_embedding_id(item['id'], embedding_id)
                            added_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        logger.error(f"Error re-indexing codex item {item['id']} ({item['type']}): {e}")
                        error_count += 1
                else:
                    skipped_count += 1

                # Handle character backstories separately if stored in KB
                if item['type'] == CodexItemType.CHARACTER.value and item.get('backstory'):
                    backstory_key = f"character_backstory_{item['id']}"
                    if backstory_key not in restored_item_keys:
                         try:
                             backstory_metadata = {
                                "id": item['id'], # Use character ID as ID for backstory? Or generate new? Check VS schema.
                                "type": "character_backstory",
                                "character_id": item['id']
                             }
                             await agent_manager.add_to_knowledge_base(
                                 "character_backstory", item['backstory'], backstory_metadata
                             )
                             added_count += 1
                             # No separate embedding ID in DB for backstory currently
                         except Exception as e:
                             logger.error(f"Error re-indexing backstory for char {item['id']}: {e}")
                             error_count += 1
                    else:
                         skipped_count += 1 # Count skipped backstories too

            # TODO: Add similar loops for Relationships, Events, Locations, Connections if they are indexed

            total_items = restored_count + added_count + skipped_count # Check this logic
            logger.info(f"Knowledge base refresh complete. Restored: {restored_count}, Added: {added_count}, Skipped (already restored): {skipped_count}, Errors: {error_count}, Total in KB: {total_items}")

            return {
                "status": "success",
                "restored_from_backup": restored_count,
                "added_from_db": added_count,
                "skipped_duplicates": skipped_count,
                "errors": error_count,
                "total_in_kb": total_items # Approximate final count
            }

    except Exception as e:
        logger.error(f"Error refreshing knowledge base for project {project_id}: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Failed to refresh knowledge base",
                "details": str(e)
            }
        )


# Universe routes
@universe_router.post("/", response_model=Dict[str, Any])
async def create_universe(
    universe: UniverseCreate, 
    current_user: User = Depends(get_current_active_user)
):
    try:
        universe_id = await db_instance.create_universe(universe.name, current_user.id)
        return {"id": universe_id, "name": universe.name}
    except Exception as e:
        logger.error(f"Error creating universe: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@universe_router.get("/{universe_id}", response_model=Dict[str, Any])
async def get_universe(
    universe_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        universe = await db_instance.get_universe(universe_id, current_user.id)
        if not universe:
            raise HTTPException(status_code=404, detail="Universe not found")
        stats = await get_universe_stats(universe_id, current_user.id)
        universe.update(stats)
        return JSONResponse(content=universe)
    except Exception as e:
            logger.error(f"Error fetching universe: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@universe_router.put("/{universe_id}", response_model=Dict[str, Any])
async def update_universe(universe_id: str, universe: UniverseUpdate, current_user: User = Depends(get_current_active_user)):
    try:
        updated_universe = await db_instance.update_universe(universe_id, universe.name, current_user.id)
        if not updated_universe:
            raise HTTPException(status_code=404, detail="Universe not found")
        return JSONResponse(content=updated_universe)
    except Exception as e:
        logger.error(f"Error updating universe: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@universe_router.delete("/{universe_id}", response_model=bool)
async def delete_universe(universe_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        success = await db_instance.delete_universe(universe_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Universe not found")
        return JSONResponse(content={"success": success})
    except Exception as e:
        logger.error(f"Error deleting universe: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@universe_router.get("/{universe_id}/codex", response_model=List[Dict[str, Any]])
async def get_universe_codex(universe_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        codex_items = await db_instance.get_universe_codex(universe_id, current_user.id)
        return JSONResponse(content=codex_items)
    except Exception as e:
            logger.error(f"Error fetching universe codex: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@universe_router.get("/{universe_id}/knowledge-base", response_model=List[Dict[str, Any]])
async def get_universe_knowledge_base(universe_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        knowledge_base_items = await db_instance.get_universe_knowledge_base(universe_id, current_user.id)
        return JSONResponse(content=knowledge_base_items)
    except Exception as e:
            logger.error(f"Error fetching universe knowledge base: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@universe_router.get("/{universe_id}/projects", response_model=List[Dict[str, Any]])
async def get_projects_by_universe(universe_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        projects = await db_instance.get_projects_by_universe(universe_id, current_user.id)
        return JSONResponse(content=projects)
    except Exception as e:
            logger.error(f"Error fetching projects by universe: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@universe_router.get("/", response_model=List[Dict[str, Any]])
async def get_universes(current_user: User = Depends(get_current_active_user)):
    try:
        universes = await db_instance.get_universes(current_user.id)
        # Add stats to each universe
        for universe in universes:
            stats = await get_universe_stats(universe['id'], current_user.id)
            universe.update(stats)
        return universes
    except Exception as e:
        logger.error(f"Error fetching universes: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Auth routes
@auth_router.post("/signup", status_code=201, response_model=dict)
async def register(user: UserCreate):
    try:
        logger.info(f"Starting registration for email: {user.email}")
        
        # Check if user already exists in local DB
        existing_user = await db_instance.get_user_by_email(user.email)
        if existing_user:
            logger.warning(f"Email already registered: {user.email}")
            raise HTTPException(status_code=400, detail="Email already registered")

        # Register using database method
        user_response = await db_instance.sign_up(
            email=user.email,
            password=user.password,
            supabase_id=user.supabase_id
        )
        
        if not user_response:
            logger.error("Registration failed: No user response")
            raise HTTPException(status_code=400, detail="Registration failed")
            
        logger.info(f"Registration successful for user ID: {user_response['id']}")
        return {
            "message": "User registered successfully", 
            "user_id": user_response["id"]
        }
    except Exception as e:
        logger.error(f"Registration error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")    


@app.post("/auth/extend-session")
async def extend_session(
    current_user: User = Depends(get_current_user),
    session_id: str = Header(None, alias="X-Session-ID")
):
    try:
        if not session_id:
            raise HTTPException(status_code=400, detail="No session ID provided")

        # Extend the session
        success = await session_manager.extend_session(session_id)
        if not success:
            raise HTTPException(status_code=401, detail="Invalid session")

        return {"message": "Session extended", "session_id": session_id}

    except Exception as e:
        logger.error(f"Error extending session: {str(e)}")
        raise HTTPException(status_code=500, detail="Error extending session")

@auth_router.post("/signin")
async def sign_in(
    credentials: Dict[str, str] = Body(..., example={"email": "user@example.com", "password": "password"})
):
    try:
        if not credentials.get('email') or not credentials.get('password'):
            raise HTTPException(
                status_code=400, 
                detail="Email and password are required"
            )
        
        try:
            auth_result = await db_instance.sign_in(
                email=credentials["email"],
                password=credentials["password"]
            )
            
            if not auth_result or not auth_result.get('user'):
                raise HTTPException(
                    status_code=401, 
                    detail="Invalid credentials"
                )
            
            # Remove approval check - all users can sign in
            session_id = await session_manager.create_session(auth_result['user'].id)
            
            return {
                "access_token": auth_result['session'].access_token,
                "session_id": session_id,
                "user": {
                    "id": auth_result['user'].id,
                    "email": auth_result['user'].email
                }
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise HTTPException(
                status_code=401,
                detail="Authentication failed"
            )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Sign in error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@auth_router.post("/signout")
async def sign_out(
    current_user: User = Depends(get_current_active_user),
    session_id: str = Header(None, alias="X-Session-ID")
):
    try:
        if not session_id:
            raise HTTPException(status_code=400, detail="No session ID provided")
            
        # First remove the session
        await session_manager.remove_session(session_id)
        
        # Then sign out from Supabase
        success = await db_instance.sign_out(session_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Sign out failed")
            
        return {"message": "Successfully signed out"}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Sign out error: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An error occurred during sign out"
        )


# --- Chapter Routes ---

@chapter_router.post("/generate")
async def generate_chapters(
    request: Request, # Keep raw request to parse JSON manually
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Parse JSON body
        body = await request.json()
        gen_request = ChapterGenerationRequest.model_validate(body) # Validate using Pydantic

        chapter_count = await db_instance.get_chapter_count(project_id, current_user.id)
        generated_chapters_details = [] # Store details of generated chapters

        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            for i in range(gen_request.numChapters):
                chapter_number = chapter_count + i + 1
                logger.info(f"Initiating generation for Chapter {chapter_number}...")

                # Call the AgentManager's graph-based generation method
                result = await agent_manager.generate_chapter(
                    chapter_number=chapter_number,
                    plot=gen_request.plot,
                    writing_style=gen_request.writing_style,
                    instructions=gen_request.instructions
                )

                # Check for errors returned by the graph
                if result.get("error"):
                    logger.error(f"Chapter {chapter_number} generation failed: {result['error']}")
                    # Decide how to handle partial failures (e.g., stop, continue, return error info)
                    # For now, let's add error info and continue
                    generated_chapters_details.append({
                        "chapter_number": chapter_number,
                        "status": "failed",
                        "error": result['error']
                    })
                    continue # Skip saving/indexing for this chapter

                # --- Process Successful Generation ---
                chapter_content = result.get("content")
                chapter_title = result.get("chapter_title")
                new_codex_items = result.get("new_codex_items", [])
                validity_check = result.get("validity_check")

                if not chapter_content or not chapter_title:
                     logger.error(f"Chapter {chapter_number} generation result missing content or title.")
                     generated_chapters_details.append({
                        "chapter_number": chapter_number,
                        "status": "failed",
                        "error": "Missing content or title in generation result."
                     })
                     continue

                # 1. Save Chapter to DB
                new_chapter_db = await db_instance.create_chapter(
                    title=chapter_title,
                    content=chapter_content,
                    project_id=project_id,
                    user_id=current_user.id
                    # chapter_number is handled by create_chapter
                )
                chapter_id = new_chapter_db['id']
                actual_chapter_number = new_chapter_db['chapter_number'] # Get actual number from DB

                # 2. Add Chapter to Knowledge Base
                chapter_metadata = {
                    "id": chapter_id,
                    "title": chapter_title,
                    "type": "chapter",
                    "chapter_number": actual_chapter_number
                }
                embedding_id = await agent_manager.add_to_knowledge_base(
                    "chapter", chapter_content, chapter_metadata
                )
                if embedding_id:
                    await db_instance.update_chapter_embedding_id(chapter_id, embedding_id)
                else:
                    logger.warning(f"Failed to add chapter {chapter_id} to knowledge base.")

                # 3. Save Validity Feedback
                if validity_check and not validity_check.get("error"):
                    try:
                        await agent_manager.save_validity_feedback(
                            result=validity_check,
                            chapter_number=actual_chapter_number,
                            chapter_id=chapter_id
                        )
                    except Exception as vf_error:
                         logger.error(f"Failed to save validity feedback for chapter {chapter_id}: {vf_error}")
                         # Non-critical error

                # 4. Process and Save New Codex Items
                saved_codex_items_info = []
                if new_codex_items:
                    logger.info(f"Processing {len(new_codex_items)} new codex items for chapter {actual_chapter_number}.")
                    for item in new_codex_items:
                        try:
                            item_id_db = await db_instance.create_codex_item(
                                name=item['name'],
                                description=item['description'],
                                type=item['type'], # Assumes validated type string
                                subtype=item.get('subtype'), # Assumes validated subtype string or None
                                user_id=current_user.id,
                                project_id=project_id
                            )
                            codex_metadata = {
                                "id": item_id_db,
                                "name": item['name'],
                                "type": item['type'],
                                "subtype": item.get('subtype')
                            }
                            codex_embedding_id = await agent_manager.add_to_knowledge_base(
                                item['type'], item['description'], codex_metadata
                            )
                            if codex_embedding_id:
                                await db_instance.update_codex_item_embedding_id(item_id_db, codex_embedding_id)
                                saved_codex_items_info.append({"id": item_id_db, "name": item['name'], "type": item['type']})
                            else:
                                logger.warning(f"Failed to add codex item '{item['name']}' to knowledge base.")
                        except Exception as ci_error:
                            logger.error(f"Failed to process/save codex item '{item.get('name', 'UNKNOWN')}': {ci_error}", exc_info=True)

                generated_chapters_details.append({
                    "chapter_number": actual_chapter_number,
                    "id": chapter_id,
                    "title": chapter_title,
                    "status": "success",
                    "embedding_id": embedding_id,
                    "new_codex_items_saved": saved_codex_items_info,
                    "validity_saved": bool(validity_check and not validity_check.get("error")),
                    "word_count": result.get("word_count", len(chapter_content.split())),
                })
                logger.info(f"Successfully processed generated Chapter {actual_chapter_number}.")

            # Update overall project chapter count after loop if needed
            # chapter_count = await db_instance.get_chapter_count(project_id, current_user.id)

            return {"generation_results": generated_chapters_details}

    except ValidationError as e:
        logger.error(f"Chapter generation request validation error: {e}", exc_info=True)
        raise HTTPException(status_code=422, detail=e.errors())
    except Exception as e:
        logger.error(f"Error during chapter generation process: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@chapter_router.get("/{chapter_id}")
async def get_chapter(
    chapter_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    # Only check project ownership
    project = await db_instance.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")
    try:
        chapter = await db_instance.get_chapter(chapter_id, current_user.id, project_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        return chapter
    except Exception as e:
        logger.error(f"Error fetching chapter: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@chapter_router.get("/")
async def get_chapters(project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        chapters = await db_instance.get_all_chapters(current_user.id, project_id)
        return {"chapters": chapters}
    except Exception as e:
        logger.error(f"Error fetching chapters: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@chapter_router.post("/")
async def create_chapter(
    chapter: ChapterCreate,
    project_id: str = Query(...), # Get project_id from query
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Create chapter in DB first
        new_chapter = await db_instance.create_chapter(
            title=chapter.title,
            content=chapter.content,
            project_id=project_id,
            user_id=current_user.id
        )
        chapter_id = new_chapter['id']
        embedding_id = None
        kb_error = None

        # Add to knowledge base
        try:
            async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
                metadata = {
                    "id": chapter_id,
                    "title": chapter.title,
                    "type": "chapter",
                    "chapter_number": new_chapter.get('chapter_number')
                }
                embedding_id = await agent_manager.add_to_knowledge_base("chapter", chapter.content, metadata)

            if embedding_id:
                await db_instance.update_chapter_embedding_id(chapter_id, embedding_id)
            else:
                kb_error = "Failed to add chapter to knowledge base."
                logger.warning(kb_error)
        except Exception as kb_e:
             kb_error = f"Error adding chapter to knowledge base: {kb_e}"
             logger.error(kb_error, exc_info=True)


        response_data = {
            "message": "Chapter created successfully" + (f" (Warning: {kb_error})" if kb_error else ""),
            "chapter": new_chapter,
            "embedding_id": embedding_id
        }
        status_code = 201 if not kb_error else 207 # Multi-Status if KB failed

        return JSONResponse(content=response_data, status_code=status_code)

    except Exception as e:
        logger.error(f"Error creating chapter: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating chapter: {str(e)}")

@chapter_router.put("/{chapter_id}")
async def update_chapter(
    chapter_id: str,
    chapter_update: ChapterUpdate,
    project_id: str = Query(...), # Get project_id from query
    current_user: User = Depends(get_current_active_user)
):
    kb_error = None
    updated_chapter = None
    try:
        # 1. Get existing chapter to find embedding_id
        existing_chapter = await db_instance.get_chapter(chapter_id, current_user.id, project_id)
        if not existing_chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        existing_embedding_id = existing_chapter.get('embedding_id')

        # 2. Update DB
        updated_chapter = await db_instance.update_chapter(
            chapter_id=chapter_id,
            title=chapter_update.title,
            content=chapter_update.content,
            user_id=current_user.id,
            project_id=project_id
        )

        # 3. Update Knowledge Base
        if existing_embedding_id:
            try:
                async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
                    metadata = {
                        "id": chapter_id,
                        "title": chapter_update.title,
                        "type": "chapter",
                        "chapter_number": updated_chapter.get('chapter_number') # Get potentially updated number
                    }
                    await agent_manager.update_or_remove_from_knowledge_base(
                        existing_embedding_id,
                        'update',
                        new_content=chapter_update.content,
                        new_metadata=metadata
                    )
            except Exception as kb_e:
                kb_error = f"Failed to update chapter in knowledge base: {kb_e}"
                logger.error(kb_error, exc_info=True)
        else:
            kb_error = "Chapter was not found in knowledge base (no embedding ID). KB not updated."
            logger.warning(kb_error)

        response_data = {
             "message": "Chapter updated successfully" + (f" (Warning: {kb_error})" if kb_error else ""),
             "chapter": updated_chapter
        }
        status_code = 200 if not kb_error else 207

        return JSONResponse(content=response_data, status_code=status_code)

    except HTTPException:
         raise # Re-raise 404 etc.
    except Exception as e:
        logger.error(f"Error updating chapter {chapter_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@chapter_router.delete("/{chapter_id}")
async def delete_chapter(
    chapter_id: str,
    project_id: str = Query(...), # Get project_id from query
    current_user: User = Depends(get_current_active_user)
):
    kb_error = None
    try:
        # 1. Get existing chapter for embedding_id
        chapter = await db_instance.get_chapter(chapter_id, current_user.id, project_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        embedding_id = chapter.get('embedding_id')

        # 2. Delete from Knowledge Base first
        if embedding_id:
            try:
                async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
                    await agent_manager.update_or_remove_from_knowledge_base(
                        embedding_id,
                        'delete'
                    )
            except Exception as kb_e:
                # Log error but proceed with DB deletion
                kb_error = f"Failed to delete chapter from knowledge base: {kb_e}"
                logger.error(kb_error, exc_info=True)
        else:
            logger.warning(f"No embedding ID found for chapter {chapter_id}. Skipping KB deletion.")

        # 3. Delete from Database
        success = await db_instance.delete_chapter(chapter_id, current_user.id, project_id)
        if not success:
            # This indicates a potential race condition or logic error if chapter was found initially
            raise HTTPException(status_code=500, detail="Failed to delete chapter from database after finding it.")

        message = "Chapter deleted successfully" + (f" (Warning: {kb_error})" if kb_error else "")
        return {"message": message}

    except HTTPException:
        raise # Re-raise 404
    except Exception as e:
        logger.error(f"Error deleting chapter {chapter_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# --- Codex Routes ---

@codex_router.post("/generate", response_model=Dict[str, Any])
async def generate_codex_item(
    request: CodexItemGenerateRequest,
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    embedding_id = None
    kb_error = None
    item_id_db = None
    generated_item = None

    try:
        # Validate type/subtype (optional, can be done in AgentManager too)
        try:
            _ = CodexItemType(request.codex_type)
            if request.subtype: _ = WorldbuildingSubtype(request.subtype)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Invalid type or subtype: {e}")

        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            # 1. Generate Item Details
            generated_item = await agent_manager.generate_codex_item(
                request.codex_type,
                request.subtype,
                request.description
            )
            if generated_item.get("name") == "Error": # Check for error marker from agent
                 raise HTTPException(status_code=500, detail=f"Codex generation failed: {generated_item.get('description')}")

            # 2. Save to Database
            item_id_db = await db_instance.create_codex_item(
                name=generated_item["name"],
                description=generated_item["description"],
                type=request.codex_type, # Use validated type
                subtype=request.subtype, # Use validated subtype
                user_id=current_user.id,
                project_id=project_id
            )

            # 3. Add to Knowledge Base
            try:
                metadata = {
                    "id": item_id_db,
                    "name": generated_item["name"],
                    "type": request.codex_type,
                    "subtype": request.subtype
                }
                embedding_id = await agent_manager.add_to_knowledge_base(
                    request.codex_type, generated_item["description"], metadata
                )
                if embedding_id:
                    await db_instance.update_codex_item_embedding_id(item_id_db, embedding_id)
                else:
                    kb_error = "Failed to add generated codex item to knowledge base."
                    logger.warning(kb_error)
            except Exception as kb_e:
                kb_error = f"Error adding generated codex item to knowledge base: {kb_e}"
                logger.error(kb_error, exc_info=True)

        response_data = {
            "message": "Codex item generated and saved successfully" + (f" (Warning: {kb_error})" if kb_error else ""),
            "item": generated_item,
            "id": item_id_db,
            "embedding_id": embedding_id
        }
        status_code = 201 if not kb_error else 207

        return JSONResponse(content=response_data, status_code=status_code)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating codex item endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# --- Codex Item CRUD ---

@codex_router.get("/characters")
async def get_characters(project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        characters = await db_instance.get_all_codex_items(current_user.id, project_id)
        # Filter only character type items
        characters = [item for item in characters if item['type'] == 'character']
        return {"characters": characters}
    except Exception as e:
        logger.error(f"Error fetching characters: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@codex_item_router.get("/") # , response_model=Dict[str, List[Dict[str, Any]]]) # Response model needs adjustment if DB returns objects
async def get_codex_items(
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        codex_items = await db_instance.get_all_codex_items(current_user.id, project_id)
        # Convert DB models to dicts if needed, or ensure db method returns dicts
        return {"codex_items": codex_items}
    except Exception as e:
        logger.error(f"Error fetching codex items: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@codex_item_router.post("/") #, response_model=Dict[str, Any])
async def create_codex_item(
    codex_item: CodexItemCreate,
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    embedding_id = None
    kb_error = None
    item_id_db = None
    try:
        # Validate type/subtype
        try:
            _ = CodexItemType(codex_item.type)
            if codex_item.subtype: _ = WorldbuildingSubtype(codex_item.subtype)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Invalid type or subtype: {e}")

        # 1. Create in DB
        item_id_db = await db_instance.create_codex_item(
            codex_item.name,
            codex_item.description,
            codex_item.type,
            codex_item.subtype,
            current_user.id,
            project_id
        )

        # 2. Add to Knowledge Base
        try:
            async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
                metadata = {
                    "id": item_id_db,
                    "name": codex_item.name,
                    "type": codex_item.type,
                    "subtype": codex_item.subtype
                }
                embedding_id = await agent_manager.add_to_knowledge_base(
                    codex_item.type, codex_item.description, metadata
                )
                if embedding_id:
                    await db_instance.update_codex_item_embedding_id(item_id_db, embedding_id)
                else:
                    kb_error = "Failed to add codex item to knowledge base."
                    logger.warning(kb_error)
        except Exception as kb_e:
            kb_error = f"Error adding codex item to knowledge base: {kb_e}"
            logger.error(kb_error, exc_info=True)

        response_data = {
            "message": "Codex item created successfully" + (f" (Warning: {kb_error})" if kb_error else ""),
            "id": item_id_db,
            "embedding_id": embedding_id
        }
        status_code = 201 if not kb_error else 207

        return JSONResponse(content=response_data, status_code=status_code)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating codex item: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@codex_item_router.put("/{item_id}")
async def update_codex_item(
    item_id: str,
    codex_item_update: CodexItemUpdate,
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    kb_error = None
    updated_item_db = None
    try:
        # Validate type/subtype
        try:
            _ = CodexItemType(codex_item_update.type)
            if codex_item_update.subtype: _ = WorldbuildingSubtype(codex_item_update.subtype)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Invalid type or subtype: {e}")

        # 1. Get existing item for embedding_id
        existing_item = await db_instance.get_codex_item_by_id(item_id, current_user.id, project_id)
        if not existing_item:
            raise HTTPException(status_code=404, detail="Codex item not found")
        existing_embedding_id = existing_item.get('embedding_id')

        # 2. Update DB
        updated_item_db = await db_instance.update_codex_item(
            item_id=item_id,
            name=codex_item_update.name,
            description=codex_item_update.description,
            type=codex_item_update.type,
            subtype=codex_item_update.subtype,
            user_id=current_user.id,
            project_id=project_id
        )

        # 3. Update Knowledge Base
        if existing_embedding_id:
            try:
                async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
                    metadata = {
                        "id": item_id,
                        "name": codex_item_update.name,
                        "type": codex_item_update.type,
                        "subtype": codex_item_update.subtype
                    }
                    await agent_manager.update_or_remove_from_knowledge_base(
                        existing_embedding_id,
                        'update',
                        new_content=codex_item_update.description,
                        new_metadata=metadata
                    )
            except Exception as kb_e:
                kb_error = f"Failed to update codex item in knowledge base: {kb_e}"
                logger.error(kb_error, exc_info=True)
        else:
            # Option: Try to add it if missing? Or just warn.
            kb_error = "Codex item was not found in knowledge base (no embedding ID). KB not updated."
            logger.warning(kb_error)


        response_data = {
             "message": "Codex item updated successfully" + (f" (Warning: {kb_error})" if kb_error else ""),
             "item": updated_item_db # Return updated DB data
        }
        status_code = 200 if not kb_error else 207

        return JSONResponse(content=response_data, status_code=status_code)

    except HTTPException:
         raise
    except Exception as e:
        logger.error(f"Error updating codex item {item_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@codex_item_router.delete("/{item_id}")
async def delete_codex_item(
    item_id: str,
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    kb_error = None
    try:
        # 1. Get existing item for embedding_id
        codex_item = await db_instance.get_codex_item_by_id(item_id, current_user.id, project_id)
        if not codex_item:
            raise HTTPException(status_code=404, detail="Codex item not found")
        embedding_id = codex_item.get('embedding_id')
        item_type = codex_item.get('type') # Needed if using dict identifier for KB delete

        # 2. Delete from Knowledge Base first
        if embedding_id:
            try:
                async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
                    # Use embedding ID directly if available
                    await agent_manager.update_or_remove_from_knowledge_base(
                        embedding_id,
                        'delete'
                    )
                    # Also delete backstory if it's a character
                    if item_type == CodexItemType.CHARACTER.value:
                         await agent_manager.update_or_remove_from_knowledge_base(
                             {"item_id": item_id, "item_type": "character_backstory"}, 'delete'
                         )
            except Exception as kb_e:
                kb_error = f"Failed to delete codex item from knowledge base: {kb_e}"
                logger.error(kb_error, exc_info=True)
        else:
            logger.warning(f"No embedding ID found for codex item {item_id}. Skipping KB deletion.")

        # 3. Delete from Database
        deleted = await db_instance.delete_codex_item(item_id, current_user.id, project_id)
        if not deleted:
             raise HTTPException(status_code=500, detail="Failed to delete codex item from database after finding it.")

        message = "Codex item deleted successfully" + (f" (Warning: {kb_error})" if kb_error else "")
        return {"message": message}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting codex item {item_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# --- Backstory & Relationship Analysis Routes ---

@codex_router.post("/characters/{character_id}/extract-backstory")
async def extract_character_backstory_endpoint( # Renamed endpoint function
    character_id: str,
    project_id: str = Query(...), # project_id from query
    # request: BackstoryExtractionRequest, # No longer needed, agent method handles finding chapters
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Verify character exists
        character = await db_instance.get_characters(current_user.id, project_id, character_id=character_id)
        if not character or character['type'] != CodexItemType.CHARACTER.value:
            raise HTTPException(status_code=404, detail="Character not found")

        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            # Agent method now handles finding unprocessed chapters and saving/adding KB
            backstory_result = await agent_manager.extract_character_backstory(character_id)

        if backstory_result is None:
             # Agent manager might return None if character check failed internally
             raise HTTPException(status_code=404, detail="Character not found during backstory extraction.")

        if backstory_result.new_backstory:
            return {"message": "Backstory extracted and updated.", "new_backstory_summary": backstory_result.new_backstory}
        else:
            # Check if this means "no new info found" vs "error" based on agent impl.
            return {"message": "No new backstory information found in unprocessed chapters.", "already_processed": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in extract character backstory endpoint for char {character_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Backstory PUT/DELETE remain the same, ensure they update/delete from KB via AgentManager

@codex_item_router.put("/characters/{character_id}/backstory")
async def update_backstory(
    character_id: str,
    project_id: str = Query(...),
    backstory_content: str = Body(..., embed=True), # Embed content in request body
    current_user: User = Depends(get_current_active_user)
):
    kb_error = None
    try:
        # 1. Update DB (assuming method exists)
        await db_instance.update_character_backstory(character_id, backstory_content, current_user.id, project_id)

        # 2. Update/Add KB
        try:
            async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
                 # Use update_or_remove, treating it as an upsert for backstory potentially
                 # Assumes backstory KB items use character_id and type identifier
                 identifier = {"item_id": character_id, "item_type": "character_backstory"}
                 metadata = {
                     "type": "character_backstory",
                     "character_id": character_id,
                     "id": character_id # Assuming backstory uses char ID as primary ID in KB
                 }
                 await agent_manager.update_or_remove_from_knowledge_base(
                     identifier, 'update', new_content=backstory_content, new_metadata=metadata
                 )
        except Exception as kb_e:
             kb_error = f"Failed to update backstory in knowledge base: {kb_e}"
             logger.error(kb_error, exc_info=True)


        message = "Backstory updated successfully" + (f" (Warning: {kb_error})" if kb_error else "")
        return {"message": message}

    except Exception as e:
        logger.error(f"Error updating backstory for char {character_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@codex_item_router.delete("/characters/{character_id}/backstory")
async def delete_backstory(
    character_id: str,
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    kb_error = None
    try:
        # 1. Delete from KB first
        try:
            async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
                 identifier = {"item_id": character_id, "item_type": "character_backstory"}
                 await agent_manager.update_or_remove_from_knowledge_base(identifier, "delete")
        except Exception as kb_e:
            kb_error = f"Failed to delete backstory from knowledge base: {kb_e}"
            logger.error(kb_error, exc_info=True)

        # 2. Delete from DB (set backstory field to None)
        await db_instance.delete_character_backstory(character_id, current_user.id, project_id)

        message = "Backstory deleted successfully" + (f" (Warning: {kb_error})" if kb_error else "")
        return {"message": message}

    except Exception as e:
        logger.error(f"Error deleting backstory for char {character_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@relationship_router.post("/analyze")
async def analyze_relationships(
    project_id: str = Query(...),
    character_ids: List[str] = Body(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        if len(character_ids) < 2:
            raise HTTPException(status_code=400, detail="At least two character IDs are required for analysis.")

        # Fetch character data from DB
        characters = []
        for char_id in character_ids:
            character = await db_instance.get_characters(current_user.id, project_id, character_id=char_id)
            if character and character['type'] == CodexItemType.CHARACTER.value:
                characters.append(character)

        if len(characters) < 2:
            raise HTTPException(status_code=404, detail="Fewer than two valid characters found for the provided IDs.")

        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            # Agent method now saves to DB and adds to KB
            relationships_analysis = await agent_manager.analyze_character_relationships(characters)

        # Return the analysis results (list of Pydantic models)
        return {"relationships": [rel.model_dump() for rel in relationships_analysis]}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing relationships endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# --- Location/Event Analysis Routes ---

@location_router.post("/analyze-chapter")
async def analyze_chapter_locations(
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Check if unprocessed chapters exist *before* getting manager? Maybe not necessary.
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            # Agent method now handles checking unprocessed, saving DB, adding KB
            new_locations = await agent_manager.analyze_unprocessed_chapter_locations()

        if not new_locations:
            # This could mean no new locations found OR no chapters to process
            # The agent log should indicate which.
            return {"message": "No new locations found or all chapters processed.", "locations": []}

        return {"locations": new_locations} # Returns list of dicts from agent method

    except Exception as e:
        logger.error(f"Error analyzing chapter locations endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@event_router.post("/analyze-chapter")
async def analyze_chapter_events(
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            # Agent method handles finding unprocessed, saving DB, adding KB
            new_events = await agent_manager.analyze_unprocessed_chapter_events()

        if not new_events:
            return {"message": "No new events found or all chapters processed.", "events": []}

        return {"events": new_events} # Returns list of dicts

    except Exception as e:
        logger.error(f"Error analyzing chapter events endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# --- Connection Analysis Routes ---

@event_router.post("/analyze-connections")
async def analyze_event_connections_endpoint( # Renamed
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            # Agent method handles analysis, saving DB, adding KB
            new_connections = await agent_manager.analyze_event_connections()

        return {"event_connections": [conn.model_dump() for conn in new_connections]}

    except Exception as e:
        logger.error(f"Error analyzing event connections endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@location_router.post("/analyze-connections")
async def analyze_location_connections_endpoint( # Renamed
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Check if enough locations exist first
        locations = await db_instance.get_locations(current_user.id, project_id)
        if len(locations) < 2:
            return {"message": "Not enough locations exist to analyze connections.", "location_connections": []}

        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            # Agent method handles analysis, saving DB, adding KB
            new_connections = await agent_manager.analyze_location_connections()

        return {"location_connections": [conn.model_dump() for conn in new_connections]}

    except Exception as e:
        logger.error(f"Error analyzing location connections endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# --- Knowledge Base Routes ---

# POST /knowledge-base/ - Needs review, depends on how AgentManager handles file vs text
@knowledge_base_router.post("/")
async def add_to_knowledge_base(
    project_id: str = Form(...),
    content_type: str = Form(...), # Require content type
    text_content: Optional[str] = Form(None),
    metadata_str: str = Form("{}"), # Default to empty JSON object string
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_user)
):
    content_to_add = None
    source_info = "text input"

    if file:
        source_info = f"file: {file.filename}"
        file_content_bytes = await file.read()
        # Basic text extraction, enhance as needed (like the /documents/extract endpoint)
        try:
            if file.filename.lower().endswith('.txt'):
                content_to_add = file_content_bytes.decode('utf-8')
            # Add more robust extraction for PDF, DOCX here if needed
            else:
                 # Try decoding as utf-8 as a fallback
                 content_to_add = file_content_bytes.decode('utf-8', errors='ignore')
                 if not content_to_add:
                      raise HTTPException(status_code=400, detail="Could not decode file content as text. Only UTF-8 text files supported directly, or use /documents/extract for PDF/DOCX.")
        except Exception as decode_err:
             raise HTTPException(status_code=400, detail=f"Error processing file {file.filename}: {decode_err}")
    elif text_content:
        content_to_add = text_content
    else:
        raise HTTPException(status_code=400, detail="No content provided (either text_content or file).")

    try:
        metadata = json.loads(metadata_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in metadata_str.")

    # Add source info to metadata
    metadata['source_info'] = source_info
    if file: metadata['filename'] = file.filename

    embedding_id = None
    kb_error = None
    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            # Use the provided content_type
            embedding_id = await agent_manager.add_to_knowledge_base(content_type, content_to_add, metadata)
        if not embedding_id:
            kb_error = "Failed to add item to knowledge base."
            logger.warning(kb_error)
    except Exception as kb_e:
        kb_error = f"Error adding item to knowledge base: {kb_e}"
        logger.error(kb_error, exc_info=True)

    if kb_error:
        raise HTTPException(status_code=500, detail=kb_error)

    return {
        "message": f"Content ({source_info}) added to knowledge base successfully.",
        "embedding_id": embedding_id,
        "content_type": content_type
     }


@app.post("/documents/extract")
async def extract_document_text(
    file: UploadFile,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        content = await file.read()
        text = ""
        
        if file.filename.lower().endswith('.pdf'):
            # Try pdfplumber first as it usually gives better results
            try:
                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    text = "\n".join(page.extract_text() for page in pdf.pages)
            except Exception as e:
                # Fallback to PyPDF2 if pdfplumber fails
                logger.warning(f"pdfplumber failed, trying PyPDF2: {str(e)}")
                pdf = PdfReader(io.BytesIO(content))
                text = "\n".join(page.extract_text() for page in pdf.pages)
                
        elif file.filename.lower().endswith(('.doc', '.docx')):
            doc = Document(io.BytesIO(content))
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Only PDF and DOC/DOCX files are supported."
            )
            
        if not text.strip():
            raise HTTPException(
                status_code=422,
                detail="Could not extract text from document. The file might be empty or corrupted."
            )
            
        return {"text": text}
        
    except Exception as e:
        logger.error(f"Error extracting text from document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing document: {str(e)}"
        )

# GET /knowledge-base/ - Calls agent_manager.get_knowledge_base_content()
@knowledge_base_router.get("/")
async def get_knowledge_base_content_endpoint( # Renamed
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            # Agent manager method gets content directly from vector store
            content = await agent_manager.get_knowledge_base_content()

            # Format for response (if needed, agent method might already format)
            # Example formatting:
            formatted_content = [
                {
                    'embedding_id': item.get('id', item.get('embedding_id')),
                    'content': item.get('page_content'),
                    'metadata': item.get('metadata', {}),
                    # Extract key fields for easier display client-side
                    'type': item.get('metadata', {}).get('type', 'Unknown'),
                    'name': item.get('metadata', {}).get('name', item.get('metadata', {}).get('title')),
                } for item in content
            ]
            return {"content": formatted_content}
    except Exception as e:
        logger.error(f"Error getting knowledge base content endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# PUT /knowledge-base/{embedding_id} - Use agent_manager method
@knowledge_base_router.put("/{embedding_id}")
async def update_knowledge_base_item(
    embedding_id: str,
    project_id: str = Query(...),
    update_data: Dict[str, Any] = Body(...), # Expect {'content': '...', 'metadata': {...}}
    current_user: User = Depends(get_current_active_user)
):
    new_content = update_data.get("content")
    new_metadata = update_data.get("metadata")
    if new_content is None and new_metadata is None:
         raise HTTPException(status_code=400, detail="Must provide 'content' and/or 'metadata' for update.")

    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            # Ensure metadata includes necessary fields if provided
            if new_metadata:
                # Ensure type is preserved or updated correctly if changed
                # existing_item = await agent_manager.vector_store.get_document_by_id(embedding_id) # Need method in VS
                # if existing_item: new_metadata['type'] = existing_item.metadata.get('type')
                 pass # Let agent handle metadata update logic

            await agent_manager.update_or_remove_from_knowledge_base(
                embedding_id,
                'update',
                new_content=new_content,
                new_metadata=new_metadata
            )
        return {"message": "Knowledge base item updated successfully"}
    except ValueError as ve: # Catch specific errors like item not found from agent
         raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error updating knowledge base item {embedding_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# DELETE /knowledge-base/{embedding_id} - Use agent_manager method
@knowledge_base_router.delete("/{embedding_id}")
async def delete_knowledge_base_item(
    embedding_id: str,
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(embedding_id, 'delete')
        return {"message": "Knowledge base item deleted successfully"}
    except ValueError as ve: # Item not found
         raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error deleting knowledge base item {embedding_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# POST /knowledge-base/query - Calls agent_manager.query_knowledge_base
@knowledge_base_router.post("/query")
async def query_knowledge_base(
    query_data: KnowledgeBaseQuery, # Use the existing Pydantic model
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            # Ensure chat history items are dicts if needed by agent method
            chat_history_dicts = [item.model_dump() for item in query_data.chatHistory]
            result = await agent_manager.query_knowledge_base(query_data.query, chat_history_dicts)
            return {"response": result}
    except Exception as e:
        logger.error(f"Error querying knowledge base: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# POST /knowledge-base/reset-chat-history - Calls agent_manager.reset_memory
@knowledge_base_router.post("/reset-chat-history")
async def reset_chat_history(
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        # AgentManager's reset_memory should handle DB deletion
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.reset_memory()
        return {"message": "Chat history reset successfully"}
    except Exception as e:
        logger.error(f"Error resetting chat history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

# GET /knowledge-base/chat-history - Calls agent_manager.get_chat_history
@knowledge_base_router.get("/chat-history")
async def get_knowledge_base_chat_history( # Renamed from app.get route
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            chat_history = await agent_manager.get_chat_history() # Agent gets from DB
            # Ensure history is a list of dicts (or whatever format client expects)
            validated_history = [ChatHistoryItem.model_validate(item).model_dump() for item in chat_history if isinstance(item, dict)]
            return {"chatHistory": validated_history}
    except Exception as e:
        logger.error(f"Error getting chat history endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving chat history")


# --- Settings Routes (Unchanged) ---
# @settings_router.post("/api-key", ...): ...
# @settings_router.get("/api-key", ...): ...
# @settings_router.delete("/api-key", ...): ...
# @settings_router.get("/model", ...): ...
# @settings_router.post("/model", ...): ...

# --- Preset Routes (Unchanged, interact with DB) ---
# @preset_router.post("", ...): ...
# @preset_router.get("", ...): ...
# @preset_router.put("/{preset_name}", ...): ...
# @preset_router.get("/{preset_name}", ...): ...
# @preset_router.delete("/{preset_name}", ...): ...

# --- Project CRUD (Minor adjustments if needed, mostly DB interaction) ---
# @project_router.put("/{project_id}/universe", ...): ...
# @project_router.post("/", ...): ...
# @project_router.get("/", ...): ...
# @project_router.get("/{project_id}", ...): ...
# @project_router.put("/{project_id}", ...): ...
# @project_router.delete("/{project_id}", ...): ...

# --- Other Endpoints (Health, Middleware, Shutdown) ---
# @app.middleware("http") async def add_security_headers(...): ...
# @app.middleware("http") async def log_requests(...): ...
# @app.get("/health") async def health_check(...): ...
# @app.post("/shutdown") async def shutdown(...): ...
# async def graceful_shutdown(): ... # Ensure this calls close_all_agent_managers()
# signal handlers

# --- CRUD for Relationships, Events, Locations, Connections ---
# These need review similar to Chapter/Codex CRUD:
# - GET: Fetch from DB.
# - POST: Create in DB, then Add to KB via agent_manager.add_to_knowledge_base.
# - PUT: Update DB, then Update KB via agent_manager.update_or_remove_from_knowledge_base(action='update').
# - DELETE: Delete from KB first via agent_manager.update_or_remove_from_knowledge_base(action='delete'), then Delete from DB.

# --- Validity Check Endpoints ---
@validity_router.get("/")
async def get_validity_checks(
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        validity_checks = await db_instance.get_all_validity_checks(current_user.id, project_id)
        return {"validityChecks": validity_checks}
    except Exception as e:
        logger.error(f"Error fetching validity checks: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@validity_router.delete("/{check_id}")
async def delete_validity_check(
    check_id: str,
    project_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Validity checks likely don't have separate KB entries, just delete from DB
        result = await db_instance.delete_validity_check(check_id, current_user.id, project_id)
        if result:
            return {"message": "Validity check deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Validity check not found")
    except Exception as e:
        logger.error(f"Error deleting validity check {check_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

# --- Include Routers ---
app.include_router(auth_router)
app.include_router(chapter_router, prefix="/projects/{project_id}") # Add project_id prefix if needed
app.include_router(codex_item_router, prefix="/projects/{project_id}")
app.include_router(event_router, prefix="/projects/{project_id}")
app.include_router(location_router, prefix="/projects/{project_id}")
app.include_router(knowledge_base_router, prefix="/projects/{project_id}")
app.include_router(settings_router) # Settings usually user-global
app.include_router(preset_router, prefix="/projects/{project_id}") # Presets per project? Check logic
app.include_router(universe_router)
app.include_router(codex_router, prefix="/projects/{project_id}")
app.include_router(relationship_router, prefix="/projects/{project_id}")
app.include_router(project_router) # No prefix for /projects/ endpoint itself
app.include_router(validity_router, prefix="/projects/{project_id}")


# --- Uvicorn Runner ---
if __name__ == "__main__":
    try:
        import uvicorn
        config = uvicorn.Config(
            "server:app", # Use the app instance directly if running this file
            host="localhost",
            port=8080,
            log_level="info", # Use info for production, debug for dev
            reload=False, # Disable reload for production stability
            workers=1, # Keep workers=1 for simplicity with in-memory state/caches
            # access_log=True, # Already handled by middleware? Check uvicorn docs
            # h11_max_incomplete_event_size=32768 # If needed for large headers/requests
        )
        server = uvicorn.Server(config)
        # Setup signal handlers for graceful shutdown (ensure they call graceful_shutdown)
        # signal.signal(...)
        server.run()
    except Exception as e:
        logger.critical(f"Server failed to start: {str(e)}", exc_info=True)
        sys.exit(1)


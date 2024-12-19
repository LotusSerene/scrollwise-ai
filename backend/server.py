import asyncio
import io
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, AsyncGenerator
from asyncio import Lock
from cryptography.fernet import Fernet
from sqlalchemy import select, and_


import json
import os
from dotenv import load_dotenv
import uuid
from typing import Optional, List, Dict, Any
from cryptography.fernet import Fernet
from contextlib import asynccontextmanager
from models import CodexItemType, WorldbuildingSubtype
from database import User, Chapter, Project, CodexItem
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Request, File, UploadFile, Form, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, ValidationError, EmailStr


from agent_manager import AgentManager, PROCESS_TYPES
from api_key_manager import ApiKeyManager, SecurityManager
from database import db_instance
from vector_store import VectorStore
from models import CodexItemType, WorldbuildingSubtype

from PyPDF2 import PdfReader
from docx import Document
import pdfplumber
import io

import sys
import subprocess
import signal
import psutil

# Load environment variables
load_dotenv()


#OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup
    logger.info("Starting up server...")
    
    try:
        # Initialize database
        logger.info("Initializing database...")
        await db_instance.initialize()
        
        # Start session cleanup task
        async def cleanup_sessions():
            while True:
                current_time = datetime.now(timezone.utc)
                expired_sessions = [
                    sid for sid, session in session_manager.sessions.items()
                    if (current_time - session['last_activity']).total_seconds() > MAX_INACTIVITY
                ]
                for sid in expired_sessions:
                    await session_manager.remove_session(sid)
                await asyncio.sleep(300)  # Run every 5 minutes
        
        cleanup_task = asyncio.create_task(cleanup_sessions())
        
        # Set keep_alive flag directly
        setattr(app.state, "keep_alive", True)
        
        yield
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise
    finally:
        # Check keep_alive flag directly
        if not getattr(app.state, "keep_alive", True):
            logger.info("Shutting down server...")
            cleanup_task.cancel()
            tasks = []
            async with agent_manager_store._lock:
                for manager in agent_manager_store._managers.values():
                    if hasattr(manager, 'vector_store'):
                        manager.vector_store.close()
                    tasks.append(manager.close())
            await asyncio.gather(*tasks)
            await db_instance.dispose()
            logger.info("Cleanup complete")

app = FastAPI(title="Novel AI API", version="1.0.0", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Add any other frontend origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  # Cache preflight requests for 10 minutes
)




MAX_INACTIVITY = 7 * 24 * 3600  # 1 week in seconds
ACTIVE_SESSION_EXTEND = 3600    # 1 hour extension when active

async def cleanup_sessions():
    while True:
        current_time = datetime.now(timezone.utc)
        expired_sessions = [
            sid for sid, session in session_manager.sessions.items()
            if (current_time - session['last_activity']).total_seconds() > MAX_INACTIVITY
        ]
        for sid in expired_sessions:
            await session_manager.remove_session(sid)
        await asyncio.sleep(300)  # Check every 5 minutes

# Pydantic models


class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str

    class Config:
        from_attributes = True

class ChapterCreate(BaseModel):
    title: str
    content: str

class ChapterUpdate(BaseModel):
    title: str
    content: str

class CodexItemCreate(BaseModel):
    name: str
    description: str
    type: str
    subtype: Optional[str] = None

class CodexItemUpdate(BaseModel):
    name: str
    description: str
    type: str
    subtype: Optional[str] = None

class ModelSettings(BaseModel):
    mainLLM: str
    checkLLM: str
    embeddingsModel: str
    titleGenerationLLM: str
    extractionLLM: str
    knowledgeBaseQueryLLM: str
    temperature: float 

class ApiKeyUpdate(BaseModel):
    apiKey: str

class KnowledgeBaseQuery(BaseModel):
    query: str
    chatHistory: List[Dict[str, str]]

class ChapterGenerationRequest(BaseModel):
    numChapters: int
    plot: str
    writingStyle: str
    instructions: Dict[str, Any]

class PresetCreate(BaseModel):
    name: str
    data: Dict[str, Any]

class PresetUpdate(BaseModel):  # New model for updating presets
    name: str
    data: ChapterGenerationRequest

class ProjectCreate(BaseModel):
    name: str
    description: str
    universe_id: Optional[str] = None  # Make universe_id optional

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    universe_id: Optional[str] = None
    target_word_count: Optional[int] = None

# Universe model
class UniverseCreate(BaseModel):
    name: str

class UniverseUpdate(BaseModel):
    name: str

class CodexItemGenerateRequest(BaseModel):
    codex_type: str  # Keep as string for now
    subtype: Optional[str] = None  # Keep as string
    description: str = Field(..., description="Description to base the codex item on")


class ChatHistoryItem(BaseModel):
    type: str
    content: str

class ChatHistoryRequest(BaseModel):
    chatHistory: List[ChatHistoryItem]

class UpdateTargetWordCountRequest(BaseModel):
    targetWordCount: int

# Add this new model
class BackstoryExtractionRequest(BaseModel):
    character_id: str
    chapter_id: str
    

#Session Manager
class SessionManager:
    def __init__(self):
        self.sessions = {}
        
    async def create_session(self, user_id: str) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            'user_id': user_id,
            'created_at': datetime.now(timezone.utc),
            'last_activity': datetime.now(timezone.utc)
        }
        return session_id
        
    async def validate_session(self, session_id: str) -> Optional[str]:
        session = self.sessions.get(session_id)
        if session:
            # Update last activity
            session['last_activity'] = datetime.now(timezone.utc)
            return session['user_id']
        return None
        
    async def remove_session(self, session_id: str):
        self.sessions.pop(session_id, None)

# Initialize session manager
session_manager = SessionManager()




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

# Initialize managers
security_manager = SecurityManager()
api_key_manager = ApiKeyManager(security_manager)
agent_manager_store = AgentManagerStore(api_key_manager)



async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session_id: str = Header(None, alias="X-Session-ID")
):
    try:
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
            # Create local user if they don't exist
            local_user = {
                "id": user_response.user.id,
                "email": user_response.user.email,
            }
            await db_instance._create_local_user(local_user)
            
        # Validate session if session_id exists
        if session_id:
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


# Create API routers
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
chapter_router = APIRouter(prefix="/chapters", tags=["Chapters"])
codex_item_router = APIRouter(prefix="/codex-items", tags=["Codex Items"])
knowledge_base_router = APIRouter(prefix="/knowledge-base", tags=["Knowledge Base"])
settings_router = APIRouter(prefix="/settings", tags=["Settings"])
preset_router = APIRouter(prefix="/presets", tags=["Presets"]) 
project_router = APIRouter(prefix="/projects", tags=["Projects"])
universe_router = APIRouter(prefix="/universes", tags=["Universes"])
codex_router = APIRouter(prefix="/codex", tags=["Codex"])
relationship_router = APIRouter(prefix="/relationships", tags=["Relationships"])
event_router = APIRouter(prefix="/events", tags=["Events"])
location_router = APIRouter(prefix="/locations", tags=["Locations"])

# Project routes
@project_router.put("/{project_id}/target-word-count")
async def update_project_target_word_count(
    project_id: str,
    update_data: UpdateTargetWordCountRequest,
    current_user: User = Depends(get_current_active_user)
):
    try:
        updated_project = await db_instance.update_project_target_word_count(
            project_id, update_data.targetWordCount, current_user.id
        )
        if not updated_project:
            raise HTTPException(status_code=404, detail="Project not found")
        return updated_project
    except Exception as e:
        logger.error(f"Error updating project target word count: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


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
@auth_router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        # Authenticate with Supabase
        auth_response = await db_instance.supabase.auth.sign_in_with_password({
            "email": form_data.username,
            "password": form_data.password
        })
        
        if not auth_response.user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Create local session
        session_id = await session_manager.create_session(auth_response.user.id)
        
        # No need to create our own JWT, just use Supabase's token
        return {
            "access_token": auth_response.session.access_token,
            "token_type": "bearer",
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=401, detail="Login failed")

@auth_router.post("/register", status_code=201, response_model=dict)
async def register(user: UserCreate):
    try:
        # Check if user already exists in local DB
        existing_user = await db_instance.get_user_by_email(user.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Register using database method
        user_id = await db_instance.sign_up(
            email=user.email,
            password=user.password
        )
        
        if not user_id:
            raise HTTPException(status_code=400, detail="Registration failed")
            
        return {
            "message": "User registered successfully", 
            "user_id": user_id,
            "needs_verification": True
        }
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))    


@app.post("/auth/extend-session")
async def extend_session(
    current_user: User = Depends(get_current_active_user),
    session_id: str = Header(None, alias="X-Session-ID")
):
    try:
        if not session_id:
            raise HTTPException(status_code=400, detail="No session ID provided")

        # Get current session
        session = session_manager.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=401, detail="Invalid session")

        # Update last activity
        session['last_activity'] = datetime.now(timezone.utc)
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
            # Use db_instance.sign_in instead of direct Supabase auth
            auth_result = await db_instance.sign_in(
                email=credentials["email"],
                password=credentials["password"]
            )
            
            if not auth_result or not auth_result.get('user'):
                raise HTTPException(
                    status_code=401, 
                    detail="Invalid credentials"
                )
            
            # Check approval status before creating session
            is_approved = await db_instance.check_user_approval(auth_result['user'].id)
            if not is_approved:
                raise HTTPException(
                    status_code=403,
                    detail="Your account is pending approval for beta testing. Please wait for admin approval."
                )
            
            # Create session only if user is approved
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

# Chapter routes


generation_tasks = {}  # Changed from defaultdict to regular dict

# Update the cancel endpoint
@chapter_router.post("/cancel")
async def cancel_chapter_generation(project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            if agent_manager:
                await agent_manager.close()
                return {"message": "Generation cancelled successfully"}
            return {"message": "No generation in progress for this project"}
    except Exception as e:
        logger.error(f"Error cancelling generation: {str(e)}")
        raise HTTPException(status_code=500, detail="Error cancelling generation")


@chapter_router.post("/generate")
async def generate_chapters(
    request: Request,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Parse and validate the request body
        body = await request.json()
        
        # Validate required fields
        required_fields = ['numChapters', 'plot', 'writingStyle', 'instructions']
        for field in required_fields:
            if field not in body:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate instructions object
        instructions = body.get('instructions', {})
        if not isinstance(instructions, dict):
            raise HTTPException(status_code=400, detail="Instructions must be an object")

        # Just get the chapter count
        chapter_count = await db_instance.get_chapter_count(project_id, current_user.id)

        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            generated_chapters = []
            for i in range(body['numChapters']):
                chapter_number = chapter_count + i + 1
                
                chapter_content = ""
                async for chunk in agent_manager.generate_chapter_stream(
                    chapter_number=chapter_number,
                    plot=body['plot'],
                    writing_style=body['writingStyle'],
                    instructions=instructions
                ):
                    if isinstance(chunk, dict) and 'content' in chunk:
                        chapter_content += chunk['content']

                    if isinstance(chunk, dict) and 'type' in chunk and chunk['type'] == 'complete':
                        # Create the chapter
                        new_chapter = await db_instance.create_chapter(
                            title=chunk.get('chapter_title', f"Chapter {chapter_number}"),
                            content=chapter_content,
                            project_id=project_id,
                            user_id=current_user.id
                        )
                        generated_chapters.append(new_chapter)

                        # Add the chapter to the knowledge base
                        embedding_id = await agent_manager.add_to_knowledge_base(
                            "chapter",
                            chapter_content,
                            {
                                "title": chunk.get('chapter_title', f"Chapter {chapter_number}"),
                                "id": new_chapter['id'],
                                "type": "chapter",
                                "chapter_number": chapter_number
                            }
                        )

                        # Update the chapter with the embedding_id
                        await db_instance.update_chapter_embedding_id(new_chapter['id'], embedding_id)

                        # Save the validity check
                        if 'validity_check' in chunk:
                            await agent_manager.save_validity_feedback(
                                result=chunk['validity_check'],
                                chapter_number=chapter_number,
                                chapter_id=new_chapter['id']
                            )

                        # Process new codex items if present
                        if 'new_codex_items' in chunk:
                            for item in chunk['new_codex_items']:
                                try:
                                    # Create codex item in DB
                                    item_id = await db_instance.create_codex_item(
                                        name=item['name'],
                                        description=item['description'],
                                        type=item['type'],
                                        subtype=item.get('subtype'),
                                        user_id=current_user.id,
                                        project_id=project_id
                                    )

                                    # Add to knowledge base with the specific type
                                    embedding_id = await agent_manager.add_to_knowledge_base(
                                        item['type'],
                                        item['description'],
                                        {
                                            "name": item['name'],
                                            "id": str(item_id),
                                            "type": item['type'],
                                            "subtype": item.get('subtype')
                                        }
                                    )

                                    await db_instance.update_codex_item_embedding_id(item_id, embedding_id)

                                except Exception as e:
                                    logger.error(f"Error processing codex item: {str(e)}")
                                    continue

            return {"generated_chapters": generated_chapters}

    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating chapters: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


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
async def create_chapter(chapter: ChapterCreate, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        # Create chapter and get full chapter data
        new_chapter = await db_instance.create_chapter(
            chapter.title,
            chapter.content,
            project_id,  # Note: Changed order to match database method
            current_user.id
        )

        # Add to knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            embedding_id = await agent_manager.add_to_knowledge_base(  
                "chapter",
                chapter.content,
                {
                    "title": chapter.title,
                    "id": new_chapter['id'],  # Use id from new_chapter
                    "type": "chapter"
                }
            )

        # Update the chapter with the embedding_id
        await db_instance.update_chapter_embedding_id(new_chapter['id'], embedding_id)
        new_chapter['embedding_id'] = embedding_id  # Update the chapter dict directly

        return {"message": "Chapter created successfully", "chapter": new_chapter, "embedding_id": embedding_id}
    except Exception as e:
        logger.error(f"Error creating chapter: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating chapter: {str(e)}")



@chapter_router.put("/{chapter_id}")
async def update_chapter(chapter_id: str, chapter: ChapterUpdate, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        existing_chapter = await db_instance.get_chapter(chapter_id, current_user.id, project_id)
        if not existing_chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")

        updated_chapter = await db_instance.update_chapter(
            chapter_id,  # Use chapter_id directly instead of embedding_id
            chapter.title,  # Access attributes directly
            chapter.content,
            current_user.id,
            project_id
        )

        # Update in knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                existing_chapter.get('embedding_id'),  # Use get() to safely access embedding_id
                'update',
                new_content=chapter.content,
                new_metadata={"title": chapter.title, "item_id": chapter_id, "item_type": "chapter"}
            )

        return updated_chapter
    except Exception as e:
        logger.error(f"Error updating chapter: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@chapter_router.delete("/{chapter_id}")
async def delete_chapter(chapter_id: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        chapter = await db_instance.get_chapter(chapter_id, current_user.id, project_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")

        # Delete from knowledge base if embedding_id exists
        if chapter.get('embedding_id'):
            async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
                await agent_manager.update_or_remove_from_knowledge_base(
                    chapter['embedding_id'],
                    'delete'
                )

        # Delete from database and ensure it's committed
        success = await db_instance.delete_chapter(chapter_id, current_user.id, project_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete chapter")

        return {"message": "Chapter deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting chapter: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Codex routes

@codex_router.post("/generate", response_model=Dict[str, Any])
async def generate_codex_item(
    request: CodexItemGenerateRequest,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Validate the type
        try:
            codex_type = CodexItemType(request.codex_type)  # Convert string to enum
            subtype = WorldbuildingSubtype(request.subtype) if request.subtype else None  # Convert string to enum if exists
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid codex type or subtype. Valid types are: {[t.value for t in CodexItemType]}")

        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            generated_item = await agent_manager.generate_codex_item(
                codex_type.value,  # Convert enum to string
                subtype.value if subtype else None,  # Convert enum to string if it exists
                request.description
            )
            
            # Save to database
            item_id = await db_instance.create_codex_item(
                generated_item["name"],
                generated_item["description"],
                codex_type.value,
                subtype.value if subtype else None,
                current_user.id,
                project_id
            )
                
            # Add to knowledge base with the specific type
            embedding_id = await agent_manager.add_to_knowledge_base(
                codex_type.value,  # Use the enum value
                generated_item["description"],
                {
                    "name": generated_item["name"],
                    "item_id": item_id,
                    "item_type": codex_type.value,
                    "subtype": subtype.value if subtype else None
                }
            )
                
            await db_instance.update_codex_item_embedding_id(item_id, embedding_id)
                
            return {
                "message": "Codex item generated successfully", 
                "item": generated_item, 
                "id": item_id, 
                "embedding_id": embedding_id
            }
    except Exception as e:
        logger.error(f"Error generating codex item: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating codex item: {str(e)}")


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

@codex_item_router.get("/")
async def get_codex_items(project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        codex_items = await db_instance.get_all_codex_items(current_user.id, project_id)
        return {"codex_items": codex_items}
    except Exception as e:
        logger.error(f"Error fetching codex items: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
        
@codex_router.post("/characters/{character_id}/extract-backstory")
async def extract_character_backstory(
    character_id: str,
    project_id: str,
    request: BackstoryExtractionRequest,
    current_user: User = Depends(get_current_active_user)
):

    try:
        character = await db_instance.get_characters(current_user.id, project_id, character_id=character_id)
        if not character or character['type'] != CodexItemType.CHARACTER.value:
            raise HTTPException(status_code=404, detail="Character not found")

        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:         
            result = await agent_manager.extract_character_backstory(character_id, request.chapter_id)

        if result and result.new_backstory:
            # Save to database
            await db_instance.save_character_backstory(
                character_id=character_id,
                content=result.new_backstory,
                user_id=current_user.id,
                project_id=project_id
            )

            # Add to knowledge base
            await agent_manager.add_to_knowledge_base(
                "character_backstory",
                result.new_backstory,
                {
                    "character_id": character_id,
                    "type": "character_backstory",
                    "name": character['name']  # Include character name for better context
                }
            )

            return {"message": "Backstory updated", "backstory": result.model_dump()}
        else:
            return {"message": "No new backstory information found", "alreadyProcessed": True}
            
    except Exception as e:
        logger.error(f"Error extracting character backstory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@codex_item_router.put("/characters/{character_id}/backstory")
async def update_backstory(
    character_id: str, 
    project_id: str, 
    backstory: str = Body(...), 
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Update in database
        await db_instance.update_character_backstory(character_id, backstory, current_user.id, project_id)
        
        # Update in knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.add_to_knowledge_base(
                "character_backstory",
                backstory,
                {
                    "character_id": character_id,
                    "type": "character_backstory"
                }
            )
            
        return {"message": "Backstory updated successfully"}
    except Exception as e:
        logger.error(f"Error updating backstory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@codex_item_router.delete("/characters/{character_id}/backstory")
async def delete_backstory(
    character_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Delete from database
        await db_instance.delete_character_backstory(character_id, current_user.id, project_id)
        
        # Delete from knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": character_id, "item_type": "character_backstory"},
                "delete"
            )
        return {"message": "Backstory deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting backstory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@codex_item_router.post("/")
async def create_codex_item(codex_item: CodexItemCreate, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        item_id = await db_instance.create_codex_item(
                codex_item.name,
                codex_item.description,
                codex_item.type,
                codex_item.subtype,
                current_user.id,
                project_id
            )

        # Add to knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            embedding_id = await agent_manager.add_to_knowledge_base(
                codex_item.type,  # Use the actual type from the codex item
                codex_item.description,
                {
                    "name": codex_item.name,
                    "item_id": item_id,
                    "item_type": codex_item.type,
                    "subtype": codex_item.subtype
                }
            )

        # Update the codex_item with the embedding_id
        await db_instance.update_codex_item_embedding_id(item_id, embedding_id)

        return {"message": "Codex item created successfully", "id": item_id, "embedding_id": embedding_id}
    except Exception as e:
        logger.error(f"Error creating codex item: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@codex_item_router.put("/{item_id}")
async def update_codex_item(item_id: str, codex_item: CodexItemUpdate, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        existing_item = await db_instance.get_codex_item_by_id(item_id, current_user.id, project_id)
        if not existing_item:
            raise HTTPException(status_code=404, detail="Codex item not found")

        updated_item = await db_instance.update_codex_item(
            item_id,
            codex_item.name,
            codex_item.description,
            codex_item.type,
            codex_item.subtype,
            current_user.id,
            project_id
        )

        # Update in knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            metadata = {
                "name": codex_item.name,
                "item_id": item_id,
                "item_type": codex_item.type,
                "subtype": codex_item.subtype
            }

            if existing_item.get('embedding_id'):
                await agent_manager.update_or_remove_from_knowledge_base(
                    existing_item['embedding_id'],
                    'update',
                    new_content=codex_item.description,
                    new_metadata=metadata
                )
            else:
                # If no embedding_id exists, create a new one with the specific type
                embedding_id = await agent_manager.add_to_knowledge_base(
                    codex_item.type,  # Use the actual type from the codex item
                    codex_item.description,
                    metadata
                )
                await db_instance.update_codex_item_embedding_id(item_id, embedding_id)

        return updated_item
    except Exception as e:
        logger.error(f"Error updating codex item: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@codex_item_router.delete("/{item_id}")
async def delete_codex_item(item_id: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        codex_item = await db_instance.get_codex_item_by_id(item_id, current_user.id, project_id)
        if not codex_item:
            raise HTTPException(status_code=404, detail="Codex item not found")

        # Delete from knowledge base if embedding_id exists
        if codex_item.get('embedding_id'):
            async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
                await agent_manager.update_or_remove_from_knowledge_base(
                    codex_item['embedding_id'],
                    'delete'
                )
        else:
            logger.warning(f"No embedding_id found for codex item {item_id}. Skipping knowledge base deletion.")

        # Delete from database
        deleted = await db_instance.delete_codex_item(item_id, current_user.id, project_id)
        if deleted:
            return {"message": "Codex item deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Codex item not found")
    except Exception as e:
        logger.error(f"Error deleting codex item: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Knowledge base routes
@knowledge_base_router.post("/")
async def add_to_knowledge_base(
    documents: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    metadata_str: Optional[str] = Form(None),
    project_id: str = Form(...),
    current_user: User = Depends(get_current_active_user)
):
    #logger.info(f"Received request to add to knowledge base. Documents: {documents}, File: {file}")
    
    async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
        if documents:
            #logger.info(f"Adding document: {documents}")
            metadata = json.loads(metadata_str) if metadata_str else {}
            await agent_manager.add_to_knowledge_base("doc", documents, metadata)
            return {"message": "Document added to the knowledge base successfully"}
        
        elif file:
            #logger.info(f"Adding file: {file.filename}")
            content = await file.read()
            metadata = json.loads(metadata_str) if metadata_str else {}
            text_content = content.decode("utf-8")
            metadata['filename'] = file.filename
            await agent_manager.add_to_knowledge_base("file", text_content, metadata)
            return {"message": "File added to the knowledge base successfully"}
        
        else:
            logger.warning("No documents or file provided")
            raise HTTPException(status_code=400, detail="No documents or file provided")
        
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

@knowledge_base_router.get("/")
async def get_knowledge_base_content(project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            content = await agent_manager.get_knowledge_base_content()
            formatted_content = [
            {
                'type': item['metadata'].get('type', 'Unknown'),
                'content': item['page_content'],
                'embedding_id': item['id'],
                'title': item['metadata'].get('title'),  # For chapters
                'name': item['metadata'].get('name'),    # For codex items
                'subtype': item['metadata'].get('subtype') # For codex items
            }
            for item in content
        ]
        return {"content": formatted_content}
    except Exception as e:
        logger.error(f"Error in get_knowledge_base_content: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@knowledge_base_router.put("/{embedding_id}")
async def update_knowledge_base_item(embedding_id: str, new_content: str, new_metadata: Dict[str, Any], project_id: str, current_user: User = Depends(get_current_active_user)):
    async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
        await agent_manager.update_or_remove_from_knowledge_base(embedding_id, 'update', new_content, new_metadata)
        return {"message": "Knowledge base item updated successfully"}

@knowledge_base_router.delete("/{embedding_id}")
async def delete_knowledge_base_item(embedding_id: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
        await agent_manager.update_or_remove_from_knowledge_base(embedding_id, 'delete')
    
    return {"message": "Knowledge base item deleted successfully"}

@knowledge_base_router.post("/query")
async def query_knowledge_base(query_data: KnowledgeBaseQuery, project_id: str, current_user: User = Depends(get_current_active_user)):
    agent_manager = None
    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            result = await agent_manager.generate_with_retrieval(query_data.query, query_data.chatHistory)
            return {"response": result}
    except Exception as e:
        logger.error(f"Error in query_knowledge_base: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@knowledge_base_router.post("/reset-chat-history")
async def reset_chat_history(project_id: str, current_user: User = Depends(get_current_active_user)):
    async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
        await agent_manager.reset_memory()
        return {"message": "Chat history reset successfully"}

# Settings routes
@settings_router.post("/api-key")
async def save_api_key(api_key_update: ApiKeyUpdate, current_user: User = Depends(get_current_active_user)):
    try:
        await api_key_manager.save_api_key(current_user.id, api_key_update.apiKey)
        return {"message": "API key saved successfully"}
    except Exception as e:
        logger.error(f"Error saving API key: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@settings_router.get("/api-key")
async def check_api_key(current_user: User = Depends(get_current_active_user)):
    try:
        api_key = await api_key_manager.get_api_key(current_user.id)
        is_set = bool(api_key)
        # Mask the API key for security
        masked_key = '*' * (len(api_key) - 4) + api_key[-4:] if is_set else None
        return {"isSet": is_set, "apiKey": masked_key}
    except Exception as e:
        logger.error(f"Error checking API key: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@settings_router.delete("/api-key")
async def remove_api_key(current_user: User = Depends(get_current_active_user)):
    try:
        await api_key_manager.save_api_key(current_user.id, None)
        return {"message": "API key removed successfully"}
    except Exception as e:
        logger.error(f"Error removing API key: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@settings_router.get("/model")
async def get_model_settings(current_user: User = Depends(get_current_active_user)):
    try:
        settings = await db_instance.get_model_settings(current_user.id)
        return settings
    except Exception as e:
        logger.error(f"Error fetching model settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@settings_router.post("/model")
async def save_model_settings(settings: ModelSettings, current_user: User = Depends(get_current_active_user)):
    try:
        await db_instance.save_model_settings(current_user.id, settings.dict())
        return {"message": "Model settings saved successfully"}
    except Exception as e:
        logger.error(f"Error saving model settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Preset routes


@preset_router.post("/")
async def create_preset(preset: PresetCreate, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        preset_id = await db_instance.create_preset(current_user.id, project_id, preset.name, preset.data)
        return {"id": preset_id, "name": preset.name, "data": preset.data}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error creating preset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@preset_router.get("/")
async def get_presets(project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        presets = await db_instance.get_presets(current_user.id, project_id)
        return presets
    except Exception as e:
        logger.error(f"Error getting presets: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@preset_router.put("/{preset_name}")  # Update route
async def update_preset(preset_name: str, preset_update: PresetUpdate, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        existing_preset = await db_instance.get_preset_by_name(preset_name, current_user.id, project_id)
        if not existing_preset:
            raise HTTPException(status_code=404, detail="Preset not found")

        # Update the preset data
        updated_data = preset_update.data.dict()
        await db_instance.update_preset(preset_name, current_user.id, project_id, updated_data)

        return {"message": "Preset updated successfully", "name": preset_name, "data": updated_data}
    except Exception as e:
        logger.error(f"Error updating preset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@preset_router.get("/{preset_name}")
async def get_preset(preset_name: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        preset = await db_instance.get_preset_by_name(preset_name, current_user.id, project_id)
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        return preset
    except Exception as e:
        logger.error(f"Error getting preset: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@preset_router.delete("/{preset_name}")
async def delete_preset(preset_name: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        deleted = await db_instance.delete_preset(preset_name, current_user.id, project_id)
        if deleted:
            return {"message": "Preset deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Preset not found")
    except Exception as e:
        logger.error(f"Error deleting preset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Project Routes

@project_router.put("/{project_id}/universe")
async def update_project_universe(project_id: str, universe: Dict[str, Any], current_user: User = Depends(get_current_active_user)):
    try:
        universe_id = universe.get('universe_id')  # This can now be None
        updated_project = await db_instance.update_project_universe(project_id, universe_id, current_user.id)
        if not updated_project:
            raise HTTPException(status_code=404, detail="Project not found")
        return updated_project
    except Exception as e:
        logger.error(f"Error updating project universe: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@project_router.post("/", response_model=Dict[str, Any])
async def create_project(
    project: ProjectCreate,
    current_user: User = Depends(get_current_active_user)
):
    try:
        project_id = await db_instance.create_project(
            name=project.name,
            description=project.description,
            user_id=current_user.id,
            universe_id=project.universe_id
        )
        
        # Fetch the created project to return its details
        new_project = await db_instance.get_project(project_id, current_user.id)
        if not new_project:
            raise HTTPException(status_code=404, detail="Project not found after creation")
            
        return {"message": "Project created successfully", "project": new_project}
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@project_router.get("/")
async def get_projects(current_user: User = Depends(get_current_active_user)):
    try:
        # Get user's own projects
        projects = await db_instance.get_projects(current_user.id)
        
        # Add stats for each project
        for project in projects:
            stats = await get_project_stats(project['id'], current_user.id)
            project.update(stats)
            
        return {"projects": projects}
    except Exception as e:
        logger.error(f"Error getting projects: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@project_router.get("/{project_id}")
async def get_project(project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        project = await db_instance.get_project(project_id, current_user.id)
        if project:
            # Add stats to the project
            stats = await get_project_stats(project_id, current_user.id)
            project.update(stats)
            return project
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception as e:
        logger.error(f"Error fetching project: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@project_router.put("/{project_id}")
async def update_project(
    project_id: str, 
    project: ProjectUpdate, 
    current_user: User = Depends(get_current_active_user)
):
    try:
        updated_project = await db_instance.update_project(
            project_id,
            project.name,
            project.description,
            current_user.id,
            project.universe_id,
            project.target_word_count
        )
        if updated_project:
            return updated_project
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception as e:
        logger.error(f"Error updating project: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@project_router.delete("/{project_id}")
async def delete_project(
    project_id: str, 
    current_user: User = Depends(get_current_active_user)
):
    try:
        success = await db_instance.delete_project(project_id, current_user.id)
        if success:
            return {"message": "Project deleted successfully"}
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception as e:
        logger.error(f"Error deleting project: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/chat-history")
async def delete_chat_history(project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        await db_instance.delete_chat_history(current_user.id, project_id)
        return {"message": "Chat history deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting chat history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/chat-history")
async def save_chat_history(chat_history: ChatHistoryRequest, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        # Convert Pydantic models to dictionaries
        chat_history_dicts = [item.dict() for item in chat_history.chatHistory]
        await db_instance.save_chat_history(current_user.id, project_id, chat_history_dicts)
        return {"message": "Chat history saved successfully"}
    except Exception as e:
        logger.error(f"Error saving chat history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/knowledge-base/chat-history")
async def get_knowledge_base_chat_history(project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            chat_history = await agent_manager.get_chat_history()
            
            # Validate chat history format
            if not isinstance(chat_history, list):
                return {"chatHistory": []}
                
            return {"chatHistory": chat_history}
    except ValidationError as ve:
        logger.error(f"Validation error in get_knowledge_base_chat_history: {str(ve)}")
        return {"chatHistory": []}
    except Exception as e:
        logger.error(f"Error in get_knowledge_base_chat_history: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving chat history")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

@app.get("/health")
async def health_check():
    try:
        # Basic health checks
        if not db_instance:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "Database not initialized"}
            )
            
        # Don't initialize VectorStore in health check
        return JSONResponse(
            status_code=200,
            content={"status": "healthy", "message": "Server is running"}
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.get("/validity-checks")
async def get_validity_checks(project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        validity_checks = await db_instance.get_all_validity_checks(current_user.id, project_id)
        return {"validityChecks": validity_checks}
    except Exception as e:
        logger.error(f"Error fetching validity checks: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/validity-checks/{check_id}")
async def delete_validity_check(check_id: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        result = await db_instance.delete_validity_check(check_id, current_user.id, project_id)
        if result:
            return {"message": "Validity check deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Validity check not found")
    except Exception as e:
        logger.error(f"Error deleting validity check: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    

@relationship_router.post("/")
async def create_relationship(
    character_id: str,
    project_id: str,
    related_character_id: str,
    relationship_type: str,
    description: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Create in database
        relationship_id = await db_instance.create_character_relationship(
            character_id, 
            related_character_id, 
            relationship_type, 
            project_id,
            description
        )
        
        # Add to knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.add_to_knowledge_base(
                "relationship",
                description or relationship_type,
                {
                    "id": relationship_id,
                    "character_id": character_id,
                    "related_character_id": related_character_id,
                    "type": "relationship",
                    "relationship_type": relationship_type
                }
            )
            
        return {"message": "Relationship created successfully", "id": relationship_id}
    except Exception as e:
        logger.error(f"Error creating relationship: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@relationship_router.get("/")
async def get_relationships(
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        relationships = await db_instance.get_character_relationships(project_id, current_user.id)
        return {"relationships": relationships}
    except Exception as e:
        logger.error(f"Error fetching relationships: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@relationship_router.put("/{relationship_id}")
async def update_relationship(
    relationship_id: str,
    project_id: str,
    relationship_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Update in database
        await db_instance.update_character_relationship(
            relationship_id,
            relationship_data['relationship_type'],
            relationship_data.get('description'),
            project_id,
            current_user.id
        )
        
        # Update in knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": relationship_id, "item_type": "relationship"},
                "update",
                new_content=relationship_data.get('description') or relationship_data['relationship_type'],
                new_metadata={
                    "relationship_type": relationship_data['relationship_type'],
                    "type": "relationship"
                }
            )
        return {"message": "Relationship updated successfully"}
    except Exception as e:
        logger.error(f"Error updating relationship: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@relationship_router.delete("/{relationship_id}")
async def delete_relationship(
    relationship_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Delete from database - reorder parameters to match method signature
        await db_instance.delete_character_relationship(relationship_id, current_user.id, project_id)
        
        # Delete from knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": relationship_id, "item_type": "relationship"},
                "delete"
            )
        return {"message": "Relationship deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting relationship: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@relationship_router.post("/analyze")
async def analyze_relationships(
    project_id: str,
    character_ids: List[str] = Body(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            # Get only the selected characters
            characters = []
            for char_id in character_ids:
                character = await db_instance.get_characters(current_user.id, project_id, character_id=char_id)
                if character and character['type'] == CodexItemType.CHARACTER.value:
                    characters.append(character)
            
            if len(characters) < 2:
                raise HTTPException(status_code=404, detail="At least two valid characters are required")
            
            # Analyze relationships for selected characters only
            relationships = await agent_manager.analyze_character_relationships(characters)
            
            return {"relationships": relationships}
    except ValueError as ve:
        return JSONResponse({"message": str(ve), "alreadyAnalyzed": True})
    except Exception as e:
        logger.error(f"Error analyzing relationships: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
# Event Connections



@event_router.post("/connections")
async def create_event_connection(
    project_id: str,
    event1_id: str,
    event2_id: str,
    connection_type: str,
    description: str,
    impact: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Create in database
        connection_id = await db_instance.create_event_connection(
            event1_id=event1_id,
            event2_id=event2_id,
            connection_type=connection_type,
            description=description,
            impact=impact,
            project_id=project_id,
            user_id=current_user.id
        )
        
        # Add to knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.add_to_knowledge_base(
                "event_connection",
                f"Connection between events: {description}\nImpact: {impact}",
                {
                    "id": connection_id,
                    "event1_id": event1_id,
                    "event2_id": event2_id,
                    "type": "event_connection",
                    "connection_type": connection_type
                }
            )
            
        return {"id": connection_id}
    except Exception as e:
        logger.error(f"Error creating event connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@event_router.put("/connections/{connection_id}")
async def update_event_connection(
    connection_id: str,
    project_id: str,
    connection_type: str,
    description: str,
    impact: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Update in database
        updated = await db_instance.update_event_connection(
            connection_id=connection_id,
            connection_type=connection_type,
            description=description,
            impact=impact,
            user_id=current_user.id,
            project_id=project_id
        )
        
        # Update in knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": connection_id, "item_type": "event_connection"},
                "update",
                new_content=f"Connection between events: {description}\nImpact: {impact}",
                new_metadata={
                    "type": "event_connection",
                    "connection_type": connection_type
                }
            )
        
        if updated:
            return updated
        raise HTTPException(status_code=404, detail="Connection not found")
    except Exception as e:
        logger.error(f"Error updating event connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@event_router.delete("/connections/{connection_id}")
async def delete_event_connection(
    connection_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Delete from database
        success = await db_instance.delete_event_connection(connection_id, current_user.id, project_id)
        
        # Delete from knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": connection_id, "item_type": "event_connection"},
                "delete"
            )
            
        if success:
            return {"message": "Connection deleted successfully"}
        raise HTTPException(status_code=404, detail="Connection not found")
    except Exception as e:
        logger.error(f"Error deleting event connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Get Event Connections
@event_router.get("/connections")
async def get_event_connections(
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        connections = await db_instance.get_event_connections(project_id, current_user.id)
        return {"event_connections": connections}
    except Exception as e:
        logger.error(f"Error fetching event connections: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")



# Update analyze event connections to save to knowledge base
@event_router.post("/analyze-connections")
async def analyze_event_connections(
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            connections = await agent_manager.analyze_event_connections()
            
            # Convert each connection to a dictionary before returning
            connection_dicts = [
                {
                    'id': getattr(conn, 'connection_id', None),
                    'event1_id': conn.event1_id,
                    'event2_id': conn.event2_id,
                    'connection_type': conn.connection_type,
                    'description': conn.description,
                    'impact': conn.impact
                }
                for conn in connections
            ]
            
            return {"event_connections": connection_dicts}
    except Exception as e:
        logger.error(f"Error analyzing event connections: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Location Connections
@location_router.post("/connections")
async def create_location_connection(
    project_id: str,
    location1_id: str,
    location2_id: str,
    connection_type: str,
    description: str,
    travel_route: Optional[str] = None,
    cultural_exchange: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Create in database
        connection_id = await db_instance.create_location_connection(
            location1_id=location1_id,
            location2_id=location2_id,
            connection_type=connection_type,
            description=description,
            travel_route=travel_route,
            cultural_exchange=cultural_exchange,
            project_id=project_id,
            user_id=current_user.id
        )
        
        # Add to knowledge base
        content = f"Connection between locations: {description}"
        if travel_route:
            content += f"\nTravel Route: {travel_route}"
        if cultural_exchange:
            content += f"\nCultural Exchange: {cultural_exchange}"
            
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.add_to_knowledge_base(
                "location_connection",
                content,
                {
                    "id": connection_id,
                    "location1_id": location1_id,
                    "location2_id": location2_id,
                    "type": "location_connection",
                    "connection_type": connection_type
                }
            )
            
        return {"id": connection_id}
    except Exception as e:
        logger.error(f"Error creating location connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@location_router.put("/connections/{connection_id}")
async def update_location_connection(
    connection_id: str,
    project_id: str,
    connection_type: str,
    description: str,
    travel_route: Optional[str] = None,
    cultural_exchange: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Update in database
        updated = await db_instance.update_location_connection(
            connection_id=connection_id,
            connection_type=connection_type,
            description=description,
            travel_route=travel_route,
            cultural_exchange=cultural_exchange,
            user_id=current_user.id,
            project_id=project_id
        )
        
        # Update in knowledge base
        content = f"Connection between locations: {description}"
        if travel_route:
            content += f"\nTravel Route: {travel_route}"
        if cultural_exchange:
            content += f"\nCultural Exchange: {cultural_exchange}"
            
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": connection_id, "item_type": "location_connection"},
                "update",
                new_content=content,
                new_metadata={
                    "type": "location_connection",
                    "connection_type": connection_type
                }
            )
        
        if updated:
            return updated
        raise HTTPException(status_code=404, detail="Connection not found")
    except Exception as e:
        logger.error(f"Error updating location connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@location_router.delete("/connections/{connection_id}")
async def delete_location_connection(
    connection_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Delete from database
        success = await db_instance.delete_location_connection(connection_id, current_user.id, project_id)
        if not success:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        # Delete from knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": connection_id, "item_type": "location_connection"},
                "delete"
            )
            # Delete any associated connections
            connections = await db_instance.get_location_connections(project_id, current_user.id)
            for conn in connections:
                if conn['location1_id'] == connection_id or conn['location2_id'] == connection_id:
                    await agent_manager.update_or_remove_from_knowledge_base(
                        {"item_id": conn['id'], "item_type": "location_connection"},
                        "delete"
                    )
        
        return {"message": "Location and associated connections deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting location connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@location_router.post("/analyze-connections")
async def analyze_location_connections(
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        locations = await db_instance.get_locations(current_user.id, project_id)
        if not locations or len(locations) < 2:
            return JSONResponse({
                "message": "Not enough locations to analyze connections", 
                "skip": True
            })

        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            connections = await agent_manager.analyze_location_connections()
            
            # Convert each connection to a dictionary before returning
            connection_dicts = [
                {
                    'id': connection.id,
                    'location1_id': connection.location1_id,
                    'location2_id': connection.location2_id,
                    'connection_type': connection.connection_type,
                    'description': connection.description,
                    'travel_route': connection.travel_route,
                    'cultural_exchange': connection.cultural_exchange
                }
                for connection in connections
            ]
            
            return {
                "location_connections": connection_dicts,
            }
    except Exception as e:
        logger.error(f"Error analyzing location connections: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@event_router.post("")
async def create_event(
    project_id: str,
    event_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Create in database
        event_id = await db_instance.create_event(
                title=event_data['title'],
                description=event_data['description'],
                date=datetime.fromisoformat(event_data['date']),
                character_id=event_data.get('character_id'),
                location_id=event_data.get('location_id'),
                project_id=project_id,
                user_id=current_user.id
            )
        
        # Add to knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.add_to_knowledge_base(
                "event",
                event_data['description'],
                {
                    "item_id": event_id,
                    "title": event_data['title'],
                    "item_type": "event",
                    "date": event_data['date'],
                    "character_id": event_data.get('character_id'),
                    "location_id": event_data.get('location_id')
                }
            )
            
        return {"id": event_id}
    except Exception as e:
        logger.error(f"Error creating event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@event_router.get("")
async def get_events(
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        events = await db_instance.get_events(project_id, current_user.id)
        return {"events": events}
    except Exception as e:
        logger.error(f"Error getting events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
@event_router.get("/{event_id}")
async def get_event(
    event_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        event = await db_instance.get_event_by_id(event_id, current_user.id, project_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        return event
    except Exception as e:
        logger.error(f"Error getting event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@event_router.put("/{event_id}")
async def update_event(
    event_id: str,
    project_id: str,
    event_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Update in database
        await db_instance.update_event(
            event_id=event_id,
            title=event_data['title'],
            description=event_data['description'],
            date=datetime.fromisoformat(event_data['date']),
            character_id=event_data.get('character_id'),
            location_id=event_data.get('location_id'),
            project_id=project_id,
            user_id=current_user.id
        )
        
        # Update in knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": event_id, "item_type": "event"},
                "update",
                new_content=event_data['description'],
                new_metadata={
                    "title": event_data['title'],
                    "type": "event",
                    "date": event_data['date'],
                    "character_id": event_data.get('character_id'),
                    "location_id": event_data.get('location_id')
                }
            )
        return {"message": "Event updated successfully"}
    except Exception as e:
        logger.error(f"Error updating event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@event_router.delete("/{event_id}")
async def delete_event(
    event_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Delete from database
        success = await db_instance.delete_event(event_id, project_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Event not found")
        
        # Delete from knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": event_id, "item_type": "event"},
                "delete"
            )
        return {"message": "Event deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    

@event_router.post("/analyze-chapter")
async def analyze_chapter_events(
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            # Analyze and get unprocessed chapter events
            events = await agent_manager.analyze_unprocessed_chapter_events()
            
            # Add events to the knowledge base
            for event in events:
                try:
                    # Create metadata with only the required fields
                    metadata = {
                        "id": event['id'],
                        "title": event['title'],
                        "type": "event"
                    }
                    
                    # Add optional fields if they exist
                    if 'date' in event:
                        metadata['date'] = event['date']
                    if 'character_id' in event:
                        metadata['character_id'] = event['character_id']
                    if 'location_id' in event:
                        metadata['location_id'] = event['location_id']

                    # Add to knowledge base
                    await agent_manager.add_to_knowledge_base(
                        "event",
                        event['description'],
                        metadata
                    )
                except Exception as e:
                    logger.error(f"Error adding event to knowledge base for event {event.get('id', 'unknown')}: {str(e)}")
                    logger.error(f"Event data: {event}")  # Log the event data for debugging
                    continue  # Continue with the next event if one fails
            
            return {"events": events}
    except ValueError as ve:
        return JSONResponse({"message": str(ve), "alreadyAnalyzed": True})
    except Exception as e:
        logger.error(f"Error analyzing chapter events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Location endpoints
@location_router.get("")
async def get_locations(
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        locations = await db_instance.get_locations(current_user.id, project_id)
        return {"locations": locations}
    except Exception as e:
        logger.error(f"Error getting locations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@location_router.post("")
async def create_location(
    project_id: str,
    location_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
):
    try:
        location_id = await db_instance.create_location(
                name=location_data['name'],
                description=location_data['description'],
                coordinates=location_data.get('coordinates'),
                user_id=current_user.id,
                project_id=project_id
            )
        return {"id": location_id}
    except Exception as e:
        logger.error(f"Error creating location: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@location_router.post("/analyze-chapter")
async def analyze_chapter_locations(
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Check if there are any unprocessed chapters
        unprocessed_chapters = await db_instance.get_latest_unprocessed_chapter_content(
            project_id,
            current_user.id,
            PROCESS_TYPES['LOCATIONS']
        )
        
        if not unprocessed_chapters:
            return JSONResponse({"message": "All chapters analyzed for locations", "alreadyAnalyzed": True})

        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            locations = await agent_manager.analyze_unprocessed_chapter_locations()
            
            # Add each location to knowledge base
            for location in locations:
                # Add to knowledge base
                await agent_manager.add_to_knowledge_base(
                    "location",
                    f"{location['name']}: {location['description']}",
                    {
                        "item_id": location['id'],  # Now using id from the location returned by agent_manager
                        "name": location['name'],
                        "item_type": "location",
                        "coordinates": location.get('coordinates')
                    }
                )
            
            return {"locations": locations}
    except Exception as e:
        logger.error(f"Error analyzing chapter locations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@location_router.get("/{location_id}")
async def get_location(
    location_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        location = await db_instance.get_location_by_id(location_id, current_user.id, project_id)
        if not location:
            #logger.warning(f"Location not found: {location_id}")
            return None
        return location
    except Exception as e:
        logger.error(f"Error getting location: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        


@location_router.put("/{location_id}")
async def update_location(
    location_id: str,
    project_id: str,
    location_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Update in database
        await db_instance.update_location(
            location_id=location_id,
            name=location_data['name'],
            description=location_data['description'],
            coordinates=location_data.get('coordinates'),
            project_id=project_id,
            user_id=current_user.id
        )
        
        # Update in knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": location_id, "item_type": "location"},
                "update",
                new_content=f"{location_data['name']}: {location_data['description']}",
                new_metadata={
                    "name": location_data['name'],
                    "type": "location",
                    "coordinates": location_data.get('coordinates')
                }
            )
        return {"message": "Location updated successfully"}
    except Exception as e:
        logger.error(f"Error updating location: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@location_router.delete("/{location_id}")
async def delete_location(
    location_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Delete from database
        success = await db_instance.delete_location(location_id, project_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Location not found")
        
        # Delete from knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": location_id, "item_type": "location"},
                "delete"
            )
            # Delete any associated connections
            connections = await db_instance.get_location_connections(project_id, current_user.id)
            for conn in connections:
                if conn['location1_id'] == location_id or conn['location2_id'] == location_id:
                    await agent_manager.update_or_remove_from_knowledge_base(
                        {"item_id": conn['id'], "item_type": "location_connection"},
                        "delete"
                    )
        
        return {"message": "Location and associated connections deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting location: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/locations/connections") 
async def get_location_connections(
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    try:
        connections = await db_instance.get_location_connections(project_id, current_user.id)
        return {"location_connections": connections} 
    except Exception as e:
        logger.error(f"Error fetching location connections: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    

@app.post("/shutdown")
async def shutdown_endpoint(current_user: User = Depends(get_current_active_user)):
    try:
        logger.info("Shutdown request received from user: %s", current_user.id)
        
        # 1. Save any pending data
        try:
            # Save any pending chat histories
            for project_id in agent_manager_store._managers.keys():
                async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
                    chat_history = await agent_manager.get_chat_history()
                    if chat_history:
                        await db_instance.save_chat_history(current_user.id, project_id, chat_history)
        except Exception as e:
            logger.error(f"Error saving pending data: {str(e)}")

        # 2. Close all active sessions
        active_sessions = list(session_manager.sessions.keys())
        for sid in active_sessions:
            await session_manager.remove_session(sid)
            logger.info(f"Closed session: {sid}")

        # 3. Close vector stores and agent managers
        async with agent_manager_store._lock:
            for manager in agent_manager_store._managers.values():
                if hasattr(manager, 'vector_store'):
                    manager.vector_store.close()
                await manager.close()
            agent_manager_store._managers.clear()

        # 4. Close database connections
        await db_instance.dispose()

        # 5. Terminate child processes
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            try:
                child.terminate()
                child.wait(timeout=3)  # Wait up to 3 seconds for each process
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                try:
                    child.kill()  # Force kill if termination fails
                except psutil.NoSuchProcess:
                    pass

        # 6. Flush logs
        for handler in logger.handlers:
            handler.flush()

        # 7. Signal the server to stop
        stop_server()  # Your existing shutdown function
        
        return {"message": "Server shutdown initiated successfully"}
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Shutdown failed: {str(e)}"
        )


# Add the router to the app
app.include_router(auth_router)
app.include_router(chapter_router)
app.include_router(codex_item_router)
app.include_router(event_router)
app.include_router(location_router)
app.include_router(knowledge_base_router)
app.include_router(settings_router)
app.include_router(preset_router)
app.include_router(universe_router)
app.include_router(codex_router)
app.include_router(relationship_router)
app.include_router(project_router)

def is_port_in_use(port: int) -> bool:
    for conn in psutil.net_connections():
        if conn.laddr.port == port:
            return True
    return False

def stop_server():
    # Cleanup and shutdown logic
    logger.info("Stopping server...")
    for process in psutil.process_iter():
        try:
            if "uvicorn" in process.name().lower():
                process.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

async def cleanup_resources():
    """Cleanup function to handle graceful shutdown"""
    logger.info("Starting cleanup process...")
    try:
        # Cleanup sessions
        for sid in list(session_manager.sessions.keys()):
            await session_manager.remove_session(sid)
        
        # Cleanup agent managers
        tasks = []
        async with agent_manager_store._lock:
            for manager in agent_manager_store._managers.values():
                if hasattr(manager, 'vector_store'):
                    manager.vector_store.close()
                tasks.append(manager.close())
        if tasks:
            await asyncio.gather(*tasks)
            
        # Cleanup database connections
        await db_instance.dispose()
        
        # Kill any remaining subprocesses
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        
        logger.info("Cleanup completed successfully")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

def signal_handler(signum, frame):
    """Handle various termination signals"""
    signal_name = signal.Signals(signum).name
    logger.info(f"Received signal {signal_name}")
    
    try:
        # Run cleanup in the event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(cleanup_resources())
        else:
            loop.run_until_complete(cleanup_resources())
            
        # Give processes a chance to cleanup (2 seconds)
        loop.run_until_complete(asyncio.sleep(2))
    except Exception as e:
        logger.error(f"Error in signal handler: {str(e)}")
    finally:
        # Force exit if cleanup takes too long
        sys.exit(0)

# Register signal handlers with platform check
signal.signal(signal.SIGINT, signal_handler)   # Handle Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Handle termination request

# Only register SIGHUP and SIGQUIT on non-Windows platforms
if hasattr(signal, 'SIGHUP'):  # Check if SIGHUP exists
    signal.signal(signal.SIGHUP, signal_handler)   # Handle terminal window closing
if hasattr(signal, 'SIGQUIT'):  # Check if SIGQUIT exists
    signal.signal(signal.SIGQUIT, signal_handler)  # Handle quit request


if __name__ == "__main__":
   try:
       import uvicorn
       config = uvicorn.Config(
           app,
           host="localhost",
           port=8080,
           log_level="debug",  # Change to debug for more info
           reload=False,
           workers=1,
           access_log=True
       )
       server = uvicorn.Server(config)
       server.run()
   except Exception as e:
       logger.error(f"Fatal error: {str(e)}", exc_info=True)
       sys.exit(1)

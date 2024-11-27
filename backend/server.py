import asyncio
import io
import json
import logging
import os
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, AsyncGenerator
from asyncio import Lock

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, File, UploadFile, Form, Body
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.routing import APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from agent_manager import AgentManager, PROCESS_TYPES
from database import db_instance, Chapter, Project, CodexItem, KnowledgeBaseItem
from vector_store import VectorStore
from models import CodexItemType, WorldbuildingSubtype

from PyPDF2 import PdfReader
from docx import Document
import pdfplumber
import io

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentManagerStore:
    def __init__(self):
        self._managers = {}
        self._lock = Lock()

    @asynccontextmanager
    async def get_or_create_manager(self, user_id: str, project_id: str) -> AsyncGenerator[AgentManager, None]:
        key = f"{user_id}_{project_id}"
        manager = None
        try:
            async with self._lock:
                # Try to get existing manager
                manager = self._managers.get(key)
                if not manager:
                    # Create new manager if none exists
                    manager = await AgentManager.create(user_id, project_id)
                    self._managers[key] = manager
            yield manager
        finally:
            if manager:
                await manager.close()
                async with self._lock:
                    self._managers.pop(key, None)

agent_manager_store = AgentManagerStore()

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    session = await db_instance.get_session()
    try:
        yield session
    finally:
        await session.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup
    logger.info("Starting up server...")
    try:
        # Initialize database
        await db_instance.initialize()
        yield
    finally:
        # Cleanup
        logger.info("Shutting down server...")
        tasks = []
        async with agent_manager_store._lock:
            for manager in agent_manager_store._managers.values():
                tasks.append(manager.close())
        await asyncio.gather(*tasks)
        await db_instance.engine.dispose()
        logger.info("Cleanup complete")

app = FastAPI(title="Novel AI API", version="1.0.0", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your frontend URL/ Ignore this config for now we'll change it later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is not set")

SECRET_KEY = str(SECRET_KEY)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Pydantic models
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[str] = None  # Add user_id to TokenData

class User(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(BaseModel):
    id: str
    username: str
    hashed_password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    api_key: Optional[str] = None
    model_settings: Optional[dict] = None

    class Config:
        protected_namespaces = ()

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
    

# Helper functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


async def get_user(username: str):
    user_dict = await db_instance.get_user_by_email(username)
    if user_dict:
        return UserInDB(**user_dict)
    return None


async def authenticate_user(username: str, password: str):
    user = await get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=150)
    to_encode.update({"exp": expire})
    try:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except JWTError as e:
        logging.error(f"Error encoding JWT: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    




async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        if username is None or user_id is None:
            raise credentials_exception
        token_data = TokenData(username=username, user_id=user_id)
    except JWTError:
        raise credentials_exception
    user = await get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_project_stats(project_id: str, user_id: str) -> Dict[str, int]:
    """Get statistics for a project including chapter count and word count."""
    async with get_db_session() as session:
        try:
            # Count chapters
            chapter_count = await session.scalar(
                select(func.count(Chapter.id))
                .where(Chapter.project_id == project_id)
                .where(Chapter.user_id == user_id)
            )

            # Get total word count from all chapters
            word_count = await session.scalar(
                select(func.sum(
                    func.array_length(
                        func.regexp_split_to_array(
                            func.regexp_replace(Chapter.content, '\s+', ' ', 'g'),
                            '\s'
                        ),
                        1
                    )
                ))
                .where(Chapter.project_id == project_id)
                .where(Chapter.user_id == user_id)
            )

            return {
                "chapter_count": chapter_count or 0,
                "word_count": word_count or 0
            }
        except Exception as e:
            logger.error(f"Error getting project stats: {str(e)}")
            raise

async def get_universe_stats(universe_id: str, user_id: str) -> Dict[str, int]:
    """Get statistics for a universe including project count and total entries."""
    async with get_db_session() as session:
        try:
            # Get project count
            project_count = await session.scalar(
                select(func.count(Project.id))
                .where(Project.universe_id == universe_id)
                .where(Project.user_id == user_id)
            )

            # Get total entries (codex items + knowledge base items)
            codex_count = await session.scalar(
                select(func.count(CodexItem.id))
                .join(Project, CodexItem.project_id == Project.id)
                .where(Project.universe_id == universe_id)
                .where(CodexItem.user_id == user_id)
            )

            kb_count = await session.scalar(
                select(func.count(KnowledgeBaseItem.id))
                .join(Project, KnowledgeBaseItem.project_id == Project.id)
                .where(Project.universe_id == universe_id)
                .where(KnowledgeBaseItem.user_id == user_id)
            )

            return {
                "project_count": project_count or 0,
                "entry_count": (codex_count or 0) + (kb_count or 0)
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
@auth_router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        user = await authenticate_user(form_data.username, form_data.password)
        if not user:
                raise HTTPException(
                    status_code=401,
                    detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
                data={"sub": user.username, "user_id": user.id}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        logger.error(f"Error in login_for_access_token: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@auth_router.post("/register", status_code=201)
async def register(user: User):
    try:
        existing_user = await get_user(user.username)
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already registered")
        hashed_password = get_password_hash(user.password)
        user_id = await db_instance.create_user(user.username, hashed_password)
        return {"message": "User registered successfully", "user_id": user_id}
    except Exception as e:
            logger.error(f"Error in register: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")


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

# Update the generate_chapters endpoint to store the AgentManager instance
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
            generated_chapter_ids = []
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
                        chapter_id = await db_instance.create_chapter(
                            title=chunk.get('chapter_title', f"Chapter {chapter_number}"),
                            content=chapter_content,
                            user_id=current_user.id,
                            project_id=project_id,
                            chapter_number=chapter_number
                        )
                        generated_chapter_ids.append(chapter_id)

                        # Add the chapter to the knowledge base
                        embedding_id = await agent_manager.add_to_knowledge_base(
                            "chapter",
                            chapter_content,
                            {
                                "title": chunk.get('chapter_title', f"Chapter {chapter_number}"),
                                "id": chapter_id,
                                "type": "chapter",
                                "chapter_number": chapter_number
                            }
                        )

                        # Update the chapter with the embedding_id
                        await db_instance.update_chapter_embedding_id(chapter_id, embedding_id)

                        # Save the validity check
                        if 'validity_check' in chunk:
                            await agent_manager.save_validity_feedback(
                                result=chunk['validity_check'],
                                chapter_number=chapter_number,
                                chapter_id=chapter_id
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
                                        item['type'],  # Use the specific type instead of "codex_item"
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

            return {"generated_chapter_ids": generated_chapter_ids}

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
        chapter_id = await db_instance.create_chapter(
                chapter.title,
                chapter.content,
                current_user.id,
                project_id
            )

        # Add to knowledge base
        async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
            embedding_id = await agent_manager.add_to_knowledge_base(  
                "chapter",
                chapter.content,
                {
                    "title": chapter.title,
                    "item_id": chapter_id,
                    "item_type": "chapter"
                }
            )

        # Update the chapter with the embedding_id
        await db_instance.update_chapter_embedding_id(chapter_id, embedding_id)

        # Fetch the created chapter to return its details
        new_chapter = await db_instance.get_chapter(chapter_id, current_user.id, project_id)

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
        await db_instance.save_api_key(current_user.id, api_key_update.apiKey)
        return {"message": "API key saved successfully"}
    except Exception as e:
        logger.error(f"Error saving API key: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@settings_router.get("/api-key")
async def check_api_key(current_user: User = Depends(get_current_active_user)):
    try:
        api_key = await db_instance.get_api_key(current_user.id)
        is_set = bool(api_key)
        masked_key = '*' * (len(api_key) - 4) + api_key[-4:] if is_set else None
        return {"isSet": is_set, "apiKey": masked_key}
    except Exception as e:
        logger.error(f"Error checking API key: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@settings_router.delete("/api-key")
async def remove_api_key(current_user: User = Depends(get_current_active_user)):
    try:
        await db_instance.remove_api_key(current_user.id)
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
    async with agent_manager_store.get_or_create_manager(current_user.id, project_id) as agent_manager:
        chat_history = await agent_manager.get_chat_history()
        return {"chatHistory": chat_history}


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
        # Vector Store Check
        try:
            vector_store = VectorStore("test_user", "test_api_key", "models/embedding-001")
            await vector_store.add_to_knowledge_base("Test content")
            test_result = await vector_store.similarity_search("test", k=1)
            
            return JSONResponse({"status": "OK", "database": "Connected", "vector_store": "Connected"})
        except Exception as e:
            logger.error(f"Vector Store check failed: {str(e)}")
            return JSONResponse({"status": "Error", "database": "Connected", "vector_store": str(e)}, status_code=500)
            
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse({"status": "Error", "error": str(e)}, status_code=500)

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
                    'id': conn.id,
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
        return {"message": "Connection deleted successfully"}
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

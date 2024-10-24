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

from agent_manager import AgentManager, PROCESS_TYPES
from database import db_instance
from vector_store import VectorStore
# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store AgentManager instances
agent_managers = {}

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
        # Clean up agent managers
        for manager in agent_managers.values():
            manager.close()
        # Close any remaining database connections
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
    codex_type: str = Field(..., description="Type of codex item (worldbuilding, character, item, lore)")
    subtype: Optional[str] = Field(None, description="Subtype of codex item (only for worldbuilding)")
    description: str = Field(..., description="Description of the codex item")

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
    async with get_db_session() as session:
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
        expire = datetime.utcnow() + timedelta(minutes=15)
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
        user_id: str = payload.get("user_id")  # Get user_id from payload
        if username is None or user_id is None:
            raise credentials_exception
        token_data = TokenData(username=username, user_id=user_id)  # Include user_id in TokenData
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


# Create API routers
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
chapter_router = APIRouter(prefix="/chapters", tags=["Chapters"])
codex_item_router = APIRouter(prefix="/codex-items", tags=["Codex Items"])
knowledge_base_router = APIRouter(prefix="/knowledge-base", tags=["Knowledge Base"])
settings_router = APIRouter(prefix="/settings", tags=["Settings"])
preset_router = APIRouter(prefix="/presets", tags=["Presets"])  # New router for presets
project_router = APIRouter(prefix="/projects", tags=["Projects"])
universe_router = APIRouter(prefix="/universes", tags=["Universes"])
codex_router = APIRouter(prefix="/codex", tags=["Codex"])  # New router for codex
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
    async with get_db_session() as session:
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
    async with get_db_session() as session:
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
    async with get_db_session() as session:
        try:
            universe = await db_instance.get_universe(universe_id, current_user.id)
            if not universe:
                raise HTTPException(status_code=404, detail="Universe not found")
            return JSONResponse(content=universe)
        except Exception as e:
            logger.error(f"Error fetching universe: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@universe_router.put("/{universe_id}", response_model=Dict[str, Any])
async def update_universe(universe_id: str, universe: UniverseUpdate, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
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
    async with get_db_session() as session:
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
    async with get_db_session() as session:
        try:
            codex_items = await db_instance.get_universe_codex(universe_id, current_user.id)
            return JSONResponse(content=codex_items)
        except Exception as e:
            logger.error(f"Error fetching universe codex: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@universe_router.get("/{universe_id}/knowledge-base", response_model=List[Dict[str, Any]])
async def get_universe_knowledge_base(universe_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            knowledge_base_items = await db_instance.get_universe_knowledge_base(universe_id, current_user.id)
            return JSONResponse(content=knowledge_base_items)
        except Exception as e:
            logger.error(f"Error fetching universe knowledge base: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@universe_router.get("/{universe_id}/projects", response_model=List[Dict[str, Any]])
async def get_projects_by_universe(universe_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            projects = await db_instance.get_projects_by_universe(universe_id, current_user.id)
            return JSONResponse(content=projects)
        except Exception as e:
            logger.error(f"Error fetching projects by universe: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@universe_router.get("/", response_model=List[Dict[str, Any]])
async def get_universes(current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            universes = await db_instance.get_universes(current_user.id)
            return JSONResponse(content=universes)
        except Exception as e:
            logger.error(f"Error fetching universes: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
    



# Auth routes
@auth_router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    async with get_db_session() as session:
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
    async with get_db_session() as session:
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

generation_tasks = defaultdict(dict)


@chapter_router.post("/generate")
async def generate_chapters(
    request: Request,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    agent_manager = None
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

        user_id = current_user.id

        if project_id in generation_tasks[user_id] and not generation_tasks[user_id][project_id].done():
            raise HTTPException(status_code=400, detail="Chapter generation already in progress for this project.")

        agent_manager = await AgentManager.create(user_id, project_id)
            
        async with get_db_session() as session:
            previous_chapters = await db_instance.get_all_chapters(current_user.id, project_id)
            codex_items = await db_instance.get_all_codex_items(current_user.id, project_id)

        async def generate():
            try:
                for i in range(body['numChapters']):
                    chapter_number = len(previous_chapters) + i + 1
                    yield json.dumps({'type': 'start', 'chapterNumber': chapter_number}) + '\n'

                    chapter_content = ""
                    async for chunk in agent_manager.generate_chapter_stream(
                        chapter_number=chapter_number,
                        plot=body['plot'],
                        writing_style=body['writingStyle'],
                        instructions=instructions,
                        previous_chapters=previous_chapters,
                        codex_items=codex_items
                    ):
                        if isinstance(chunk, dict) and 'content' in chunk:
                            chapter_content += chunk['content']
                            yield json.dumps(chunk) + '\n'

                            # Handle validity check if present
                            if 'validity_check' in chunk and 'chapter_title' in chunk:
                                # Create the chapter
                                chapter_id = await db_instance.create_chapter(
                                    title=chunk['chapter_title'],
                                    content=chapter_content,
                                    user_id=current_user.id,
                                    project_id=project_id,
                                    chapter_number=chapter_number
                                )

                                # Add the chapter to the knowledge base
                                embedding_id = await agent_manager.add_to_knowledge_base(
                                    "chapter",
                                    chapter_content,
                                    {
                                        "title": chunk['chapter_title'],
                                        "id": chapter_id,
                                        "type": "chapter",
                                        "chapter_number": chapter_number
                                    }
                                )

                                # Update the chapter with the embedding_id
                                await db_instance.update_chapter_embedding_id(chapter_id, embedding_id)

                                # Save the validity check
                                await agent_manager.save_validity_feedback(
                                    result=chunk['validity_check'],
                                    chapter_number=chapter_number,
                                    chapter_id=chapter_id
                                )

                                # Process new codex items if present
                                if 'new_codex_items' in chunk:
                                    for item in chunk['new_codex_items']:
                                        try:
                                            # First create the codex item and wait for the result
                                            item_id = await db_instance.create_codex_item(
                                                name=item['name'],
                                                description=item['description'],
                                                type=item['type'],
                                                subtype=item.get('subtype'),
                                                user_id=current_user.id,
                                                project_id=project_id
                                            )

                                            # Now use the actual item_id (not a coroutine) in the metadata
                                            metadata = {
                                                "name": item['name'],
                                                "id": str(item_id),  # Ensure ID is a string
                                                "type": item['type'],
                                                "subtype": item.get('subtype')
                                            }

                                            # Add to knowledge base with the proper metadata
                                            embedding_id = await agent_manager.add_to_knowledge_base(
                                                "codex_item",
                                                item['description'],
                                                metadata
                                            )

                                            # Update the embedding ID
                                            await db_instance.update_codex_item_embedding_id(item_id, embedding_id)

                                        except Exception as e:
                                            logger.error(f"Error processing codex item: {str(e)}")
                                            continue

                    yield json.dumps({'type': 'done'}) + '\n'

            except Exception as e:
                logger.error(f"Error in generate function: {str(e)}", exc_info=True)
                yield json.dumps({'type': 'error', 'message': str(e)}) + '\n'
            finally:
                # Cleanup
                if project_id in generation_tasks[user_id]:
                    del generation_tasks[user_id][project_id]
                if agent_manager:
                    await agent_manager.close()

        generation_task = generate()
        generation_tasks[user_id][project_id] = generation_task

        return StreamingResponse(generation_task, media_type="application/json")

    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Ensure cleanup on error
        if agent_manager:
            await agent_manager.close()
        logger.error(f"Error generating chapters: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@chapter_router.post("/cancel")
async def cancel_chapter_generation(project_id: str, current_user: User = Depends(get_current_active_user)):
    user_id = current_user.id
    if project_id in generation_tasks[user_id]:
        generation_tasks[user_id][project_id].cancel()
        del generation_tasks[user_id][project_id]
        return {"message": "Generation cancelled"}
    else:
        return {"message": "No generation in progress for this project"}


@chapter_router.get("/{chapter_id}")
async def get_chapter(chapter_id: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
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
    async with get_db_session() as session:
        try:
            chapters = await db_instance.get_all_chapters(current_user.id, project_id)
            return {"chapters": chapters}
        except Exception as e:
            logger.error(f"Error fetching chapters: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")


@chapter_router.post("/")
async def create_chapter(chapter: ChapterCreate, project_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            chapter_id = await db_instance.create_chapter(
                chapter.title,
                chapter.content,
                current_user.id,
                project_id
            )

            # Add to knowledge base
            agent_manager = await AgentManager.create(current_user.id, project_id)
            embedding_id = await agent_manager.add_to_knowledge_base(  # Remove await from here
                "chapter",
                chapter.content,
                {
                    "title": chapter.title,
                    "id": chapter_id,
                    "type": "chapter"
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
    async with get_db_session() as session:
        try:
            existing_chapter = await db_instance.get_chapter(chapter_id, current_user.id, project_id)
            if not existing_chapter:
                raise HTTPException(status_code=404, detail="Chapter not found")

            updated_chapter = await db_instance.update_chapter(
                chapter_id,
                chapter.title,  # Removed encoding/decoding
                chapter.content,  # Removed encoding/decoding
                current_user.id,
                project_id
            )

            # Update in knowledge base
            agent_manager = await AgentManager.create(current_user.id, project_id)
            await agent_manager.update_or_remove_from_knowledge_base(
                existing_chapter['embedding_id'],
                'update',
                new_content=chapter.content,
                new_metadata={"title": chapter.title, "id": chapter_id, "type": "chapter"}
            )

            return updated_chapter
        except Exception as e:
            logger.error(f"Error updating chapter: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")


@chapter_router.delete("/{chapter_id}")
async def delete_chapter(chapter_id: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            chapter = await db_instance.get_chapter(chapter_id, current_user.id, project_id)
            if not chapter:
                raise HTTPException(status_code=404, detail="Chapter not found")

            # Delete from knowledge base if embedding_id exists
            if chapter.get('embedding_id'):
                agent_manager = await AgentManager.create(current_user.id, project_id)
                await agent_manager.update_or_remove_from_knowledge_base(chapter['embedding_id'], 'delete')
            else:
                logging.warning(f"No embedding_id found for chapter {chapter_id}. Skipping knowledge base deletion.")

            # Delete from database
            await db_instance.delete_chapter(chapter_id, current_user.id, project_id)

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
    agent_manager = None
    try:
        agent_manager = await AgentManager.create(current_user.id, project_id)
        generated_item = await agent_manager.generate_codex_item(
            request.codex_type, request.subtype, request.description
        )
        
        async with get_db_session() as session:
            # Save to database
            item_id = await db_instance.create_codex_item(
                generated_item["name"],
                generated_item["description"],
                request.codex_type,
                request.subtype,
                current_user.id,
                project_id
            )
            
            # Add to knowledge base
            embedding_id = await agent_manager.add_to_knowledge_base(
                "codex_item",
                generated_item["description"],
                {
                    "name": generated_item["name"],
                    "id": item_id,
                    "type": request.codex_type,
                    "subtype": request.subtype
                }
            )
            
            await db_instance.update_codex_item_embedding_id(item_id, embedding_id)
            
            return {"message": "Codex item generated successfully", "item": generated_item, "id": item_id, "embedding_id": embedding_id}
    except Exception as e:
        logger.error(f"Error generating codex item: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating codex item: {str(e)}")
    finally:
        if agent_manager:
            await agent_manager.close()

@codex_router.get("/characters")
async def get_characters(project_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
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
    async with get_db_session() as session:
        try:
            codex_items = await db_instance.get_all_codex_items(current_user.id, project_id)
            return {"codex_items": codex_items}
        except Exception as e:
            logger.error(f"Error fetching codex items: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
        
# Add this endpoint to the codex_router section
@codex_router.post("/characters/{character_id}/extract-backstory")
async def extract_character_backstory(
    character_id: str,
    project_id: str,
    request: BackstoryExtractionRequest,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Check if the character exists and belongs to the user/project
        character = await db_instance.get_codex_item_by_id(character_id, current_user.id, project_id)
        if not character or character['type'] != 'character':
            raise HTTPException(status_code=404, detail="Character not found")

        # Check if the chapter has already been processed
        if await db_instance.is_chapter_processed_for_type(request.chapter_id, PROCESS_TYPES['BACKSTORY']):
            return JSONResponse({"message": "Chapter already analyzed for characters", "alreadyAnalyzed": True})

        agent_manager = await AgentManager.create(current_user.id, project_id)
        
        # Extract backstory
        result = await agent_manager.extract_character_backstory(character_id, request.chapter_id)

        if result and result.new_backstory:
            # Save the new backstory
            updated_character = await db_instance.save_character_backstory(
                character_id=character_id,
                content=result.new_backstory,
                user_id=current_user.id,
                project_id=project_id
            )
            return {"message": "Backstory updated", "backstory": result.dict()}
        else:
            return {"message": "No new backstory information found"}
            
    except Exception as e:
        logger.error(f"Error extracting character backstory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if agent_manager:
            await agent_manager.close()


@codex_item_router.put("/characters/{character_id}/backstory")
async def update_backstory(
    character_id: str, 
    project_id: str, 
    backstory: str = Body(...), 
    current_user: User = Depends(get_current_active_user)
):
    try:
        await db_instance.update_character_backstory(character_id, backstory, current_user.id, project_id)
        return {"message": "Backstory updated successfully"}
    except ValueError as e:
        logger.error(f"Error updating backstory: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating backstory: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@codex_item_router.delete("/characters/{character_id}/backstory")
async def delete_backstory(character_id: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
         await db_instance.delete_character_backstory(character_id, current_user.id, project_id)
         return {"message": "Backstory deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting backstory: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@codex_item_router.post("/")
async def create_codex_item(codex_item: CodexItemCreate, project_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
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
            agent_manager = await AgentManager.create(current_user.id, project_id)
            embedding_id = await agent_manager.add_to_knowledge_base(
                "codex_item",
                codex_item.description,
                {
                    "name": codex_item.name,
                    "id": item_id,
                    "type": codex_item.type,
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
    async with get_db_session() as session:
        try:
            existing_item = await db_instance.get_codex_item_by_id(item_id, current_user.id, project_id)
            if not existing_item:
                raise HTTPException(status_code=404, detail="Codex item not found")

            updated_item = await db_instance.update_codex_item(item_id, codex_item.name, codex_item.description, codex_item.type, codex_item.subtype, current_user.id, project_id)

            # Update in knowledge base
            agent_manager = await AgentManager.create(current_user.id, project_id)
            if existing_item.get('embedding_id'):
                metadata = {
                    "name": codex_item.name,
                    "id": item_id,
                    "type": codex_item.type,
                    "subtype": codex_item.subtype  # This can be None, which will remove the field if it exists
                }

                await agent_manager.update_or_remove_from_knowledge_base(
                    existing_item['embedding_id'],
                    'update',
                    new_content=codex_item.description,
                    new_metadata=metadata
                )
            else:
                # If no embedding_id exists, create a new one
                metadata = {
                    "name": codex_item.name,
                    "id": item_id,
                    "type": codex_item.type,
                    "subtype": codex_item.subtype
                }

                embedding_id = await agent_manager.add_to_knowledge_base("codex_item", codex_item.description, metadata)
                await db_instance.update_codex_item_embedding_id(item_id, embedding_id)

            return updated_item
        except Exception as e:
            logger.error(f"Error updating codex item: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")


@codex_item_router.delete("/{item_id}")
async def delete_codex_item(item_id: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            codex_item = await db_instance.get_codex_item_by_id(item_id, current_user.id, project_id)
            if not codex_item:
                raise HTTPException(status_code=404, detail="Codex item not found")

            # Delete from knowledge base if embedding_id exists
            if codex_item.get('embedding_id'):
                agent_manager = await AgentManager.create(current_user.id, project_id)
                await agent_manager.update_or_remove_from_knowledge_base(codex_item['embedding_id'], 'delete')
            else:
                logging.warning(f"No embedding_id found for codex item {item_id}. Skipping knowledge base deletion.")

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
    
    agent_manager = await AgentManager.create(current_user.id, project_id)
    
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

@knowledge_base_router.get("/")
async def get_knowledge_base_content(project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        agent_manager = await AgentManager.create(current_user.id, project_id)
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
    finally:
        if agent_manager:
            await agent_manager.close()

@knowledge_base_router.put("/{embedding_id}")
async def update_knowledge_base_item(embedding_id: str, new_content: str, new_metadata: Dict[str, Any], project_id: str, current_user: User = Depends(get_current_active_user)):
    agent_manager = await AgentManager.create(current_user.id, project_id)
    await agent_manager.update_or_remove_from_knowledge_base(embedding_id, 'update', new_content, new_metadata)
    return {"message": "Knowledge base item updated successfully"}

@knowledge_base_router.delete("/{embedding_id}")
async def delete_knowledge_base_item(embedding_id: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    agent_manager = await AgentManager.create(current_user.id, project_id)
    await agent_manager.update_or_remove_from_knowledge_base(embedding_id, 'delete')
    
    return {"message": "Knowledge base item deleted successfully"}

@knowledge_base_router.post("/query")
async def query_knowledge_base(query_data: KnowledgeBaseQuery, project_id: str, current_user: User = Depends(get_current_active_user)):
    agent_manager = None
    try:
        agent_manager = await AgentManager.create(current_user.id, project_id)
        result = await agent_manager.generate_with_retrieval(query_data.query, query_data.chatHistory)
        return {"response": result}
    except Exception as e:
        logger.error(f"Error in query_knowledge_base: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if agent_manager:
            await agent_manager.close()

@knowledge_base_router.post("/reset-chat-history")
async def reset_chat_history(project_id: str, current_user: User = Depends(get_current_active_user)):
    agent_manager = await AgentManager.create(current_user.id, project_id)
    await agent_manager.reset_memory()
    return {"message": "Chat history reset successfully"}

# Settings routes
@settings_router.post("/api-key")
async def save_api_key(api_key_update: ApiKeyUpdate, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            await db_instance.save_api_key(current_user.id, api_key_update.apiKey)
            return {"message": "API key saved successfully"}
        except Exception as e:
            logger.error(f"Error saving API key: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@settings_router.get("/api-key")
async def check_api_key(current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
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
    async with get_db_session() as session:
        try:
            await db_instance.remove_api_key(current_user.id)
            return {"message": "API key removed successfully"}
        except Exception as e:
            logger.error(f"Error removing API key: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@settings_router.get("/model")
async def get_model_settings(current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            settings = await db_instance.get_model_settings(current_user.id)
            return settings
        except Exception as e:
            logger.error(f"Error fetching model settings: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@settings_router.post("/model")
async def save_model_settings(settings: ModelSettings, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            await db_instance.save_model_settings(current_user.id, settings.dict())
            return {"message": "Model settings saved successfully"}
        except Exception as e:
            logger.error(f"Error saving model settings: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")


# Preset routes


@preset_router.post("/")
async def create_preset(preset: PresetCreate, project_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
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
    async with get_db_session() as session:
        try:
            presets = await db_instance.get_presets(current_user.id, project_id)
            return presets
        except Exception as e:
            logger.error(f"Error getting presets: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@preset_router.put("/{preset_name}")  # Update route
async def update_preset(preset_name: str, preset_update: PresetUpdate, project_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
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
    async with get_db_session() as session:
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
    async with get_db_session() as session:
        try:
            deleted = await db_instance.delete_preset(preset_name, current_user.id, project_id)
            if deleted:
                return {"message": "Preset deleted successfully"}
            raise HTTPException(status_code=404, detail="Preset not found")
        except Exception as e:
            logger.error(f"Error deleting preset: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

# Project Routes

@project_router.put("/{project_id}/universe")
async def update_project_universe(project_id: str, universe: Dict[str, Any], current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            universe_id = universe.get('universe_id')  # This can now be None
            updated_project = await db_instance.update_project_universe(project_id, universe_id, current_user.id)
            if not updated_project:
                raise HTTPException(status_code=404, detail="Project not found")
            return updated_project
        except Exception as e:
            logger.error(f"Error updating project universe: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@project_router.post("/")
async def create_project(project: ProjectCreate, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            project_id = await db_instance.create_project(project.name, project.description, current_user.id, project.universe_id)
            return {"message": "Project created successfully", "project_id": project_id}
        except Exception as e:
            logger.error(f"Error creating project: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating project: {str(e)}")

@project_router.get("/")
async def get_projects(current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            projects = await db_instance.get_projects(current_user.id)
            return {"projects": projects}
        except Exception as e:
            logger.error(f"Error fetching projects: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@project_router.get("/{project_id}")
async def get_project(project_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            project = await db_instance.get_project(project_id, current_user.id)
            if project:
                return project
            raise HTTPException(status_code=404, detail="Project not found")
        except Exception as e:
            logger.error(f"Error fetching project: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@project_router.put("/{project_id}")
async def update_project(project_id: str, project: ProjectUpdate, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
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
async def delete_project(project_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            success = await db_instance.delete_project(project_id, current_user.id)
            if success:
                return {"message": "Project deleted successfully"}
            raise HTTPException(status_code=404, detail="Project not found")
        except Exception as e:
            logger.error(f"Error deleting project: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/chat-history")
async def get_chat_history(project_id: str, current_user: User = Depends(get_current_active_user)):
    agent_manager = await AgentManager.create(current_user.id, project_id)
    chat_history = await agent_manager.get_chat_history()
    return {"chatHistory": chat_history}

@app.delete("/chat-history")
async def delete_chat_history(project_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            await db_instance.delete_chat_history(current_user.id, project_id)
            return {"message": "Chat history deleted successfully"}
        except Exception as e:
            logger.error(f"Error deleting chat history: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/chat-history")
async def save_chat_history(chat_history: ChatHistoryRequest, project_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
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
    agent_manager = await AgentManager.create(current_user.id, project_id)
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
        async with get_db_session() as session:
            # Vector Store Check
            try:
                vector_store = VectorStore("test_user", "test_api_key", "models/embedding-001")
                await vector_store.add_to_knowledge_base("Test content")
                test_result = await vector_store.similarity_search("test", k=1)
                
                return JSONResponse({"status": "OK", "database": "Connected", "vector_store": "Connected"})
            except Exception as e:
                logging.error(f"Vector Store check failed: {str(e)}")
                return JSONResponse({"status": "Error", "database": "Connected", "vector_store": str(e)}, status_code=500)
            
    except Exception as e:
        logging.error(f"Health check failed: {str(e)}")
        return JSONResponse({"status": "Error", "error": str(e)}, status_code=500)

@app.get("/validity-checks")
async def get_validity_checks(project_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            validity_checks = await db_instance.get_all_validity_checks(current_user.id, project_id)
            return {"validityChecks": validity_checks}
        except Exception as e:
            logging.error(f"Error fetching validity checks: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/validity-checks/{check_id}")
async def delete_validity_check(check_id: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    async with get_db_session() as session:
        try:
            result = await db_instance.delete_validity_check(check_id, current_user.id, project_id)
            if result:
                return {"message": "Validity check deleted successfully"}
            else:
                raise HTTPException(status_code=404, detail="Validity check not found")
        except Exception as e:
            logging.error(f"Error deleting validity check: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    

@relationship_router.post("/")
async def create_relationship(
    character_id: str,
    project_id: str,
    related_character_id: str,
    relationship_type: str,
    description: Optional[str] = None,  # Make sure this parameter is included
    current_user: User = Depends(get_current_active_user)
):
    async with get_db_session() as session:
        try:
            project = await db_instance.get_project(project_id, current_user.id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            relationship_id = await db_instance.create_character_relationship(
                character_id, 
                related_character_id, 
                relationship_type, 
                project_id,
                description  # Pass the description parameter
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
    async with get_db_session() as session:
        try:
            relationships = await db_instance.get_character_relationships(project_id, current_user.id)
            return {"relationships": relationships}
        except Exception as e:
            logger.error(f"Error fetching relationships: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@relationship_router.put("/{relationship_id}")
async def update_relationship(
    relationship_id: str,
    relationship_type: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    async with get_db_session() as session:
        try:
            updated_relationship = await db_instance.update_character_relationship(
                relationship_id, relationship_type, current_user.id, project_id
            )
            if updated_relationship:
                return {"message": "Relationship updated successfully", "relationship": updated_relationship}
            else:
                raise HTTPException(status_code=404, detail="Relationship not found")
        except Exception as e:
            logger.error(f"Error updating relationship: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@relationship_router.delete("/{relationship_id}")
async def delete_relationship(
    relationship_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    async with get_db_session() as session:
        try:
            success = await db_instance.delete_character_relationship(relationship_id, current_user.id, project_id)
            if success:
                return {"message": "Relationship deleted successfully"}
            else:
                raise HTTPException(status_code=404, detail="Relationship not found")
        except Exception as e:
            logger.error(f"Error deleting relationship: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@relationship_router.post("/analyze")
async def analyze_relationships(
    request: Request,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    chapter_id: str = 'latest'
):
    async with get_db_session() as session:
        try:
            # Get latest unprocessed chapter
            chapter_data = await db_instance.get_latest_unprocessed_chapter_content(
                project_id,
                current_user.id,
                PROCESS_TYPES['RELATIONSHIPS']
            )
            
            if not chapter_data:
                return {"message": "No unprocessed chapters to analyze", "skip": True}

            agent_manager = await AgentManager.create(current_user.id, project_id)
            characters = await db_instance.get_characters_from_codex(current_user.id, project_id)
            character_ids = [char['id'] for char in characters]
            relationships = await agent_manager.analyze_character_relationships(character_ids)
               
            return {"relationships": relationships}
        except Exception as e:
            logger.error(f"Error analyzing relationships: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@event_router.post("")
async def create_event(
    project_id: str,
    event_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
):
    async with get_db_session() as session:
        try:
            event_id = await db_instance.create_event(
                title=event_data['title'],
                description=event_data['description'],
                date=datetime.fromisoformat(event_data['date']),
                character_id=event_data.get('character_id'),
                location_id=event_data.get('location_id'),
                project_id=project_id,
                user_id=current_user.id
            )
            return {"id": event_id}
        except Exception as e:
            logger.error(f"Error creating event: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@event_router.post("/analyze-chapter")
async def analyze_chapter_events(
    project_id: str,
    chapter_id: str = 'latest',
    current_user: User = Depends(get_current_active_user)
):
    async with get_db_session() as session:
        try:
            if chapter_id == 'latest':
                latest_chapter = await db_instance.get_latest_chapter(project_id, current_user.id)
                if not latest_chapter:
                    raise HTTPException(status_code=404, detail="No chapters found")
                chapter_id = latest_chapter['id']

            if await db_instance.is_chapter_processed_for_type(chapter_id, PROCESS_TYPES['EVENTS']):
                return JSONResponse({"message": "Chapter already analyzed for events", "alreadyAnalyzed": True})

            agent_manager = await AgentManager.create(current_user.id, project_id)
            events = await agent_manager.analyze_unprocessed_chapter_events(chapter_id)  # Pass chapter_id
            
            await db_instance.mark_chapter_processed(chapter_id, current_user.id, PROCESS_TYPES['EVENTS'])
            
            return {"events": events}
        except Exception as e:
            logger.error(f"Error analyzing chapter events: {str(e)}")

            raise HTTPException(status_code=500, detail=str(e))
@event_router.get("")
async def get_events(
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    async with get_db_session() as session:
        try:
            events = await db_instance.get_events(project_id, current_user.id)
            return {"events": events}
        except Exception as e:
            logger.error(f"Error getting events: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        
@event_router.post("/analyze-connections")
async def analyze_event_connections(
    project_id: str,
    event_ids: List[str],
    current_user: User = Depends(get_current_active_user)
):
    async with get_db_session() as session:
        try:
            agent_manager = await AgentManager.create(current_user.id, project_id)
            analyses = await agent_manager.analyze_event_connections(event_ids)
            # Should convert EventAnalysis to dict
            return {"analyses": [analysis.dict() for analysis in analyses]}  # Fixed
        except Exception as e:
            logger.error(f"Error analyzing event connections: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@event_router.get("/{event_id}")
async def get_event(
    event_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    async with get_db_session() as session:
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
    async with get_db_session() as session:
        try:
            updated_event = await db_instance.update_event(event_id, current_user.id, project_id, event_data)
            if not updated_event:
                raise HTTPException(status_code=404, detail="Event not found")
            return updated_event
        except Exception as e:
            logger.error(f"Error updating event: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@event_router.delete("/{event_id}")
async def delete_event(
    event_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    async with get_db_session() as session:
        try:
            success = await db_instance.delete_event(event_id, current_user.id, project_id)
            if not success:
                raise HTTPException(status_code=404, detail="Event not found")
            return {"message": "Event deleted successfully"}
        except Exception as e:
            logger.error(f"Error deleting event: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

# Location endpoints
@location_router.get("")
async def get_locations(
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    async with get_db_session() as session:
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
    async with get_db_session() as session:
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
    chapter_id: str = 'latest',
    current_user: User = Depends(get_current_active_user)
):
    agent_manager = None
    try:
        async with get_db_session() as session:
            # If chapter_id is 'latest', get the latest chapter
            if chapter_id == 'latest':
                latest_chapter = await db_instance.get_latest_chapter(project_id, current_user.id)
                if not latest_chapter:
                    raise HTTPException(status_code=404, detail="No chapters found")
                chapter_id = latest_chapter['id']

            if await db_instance.is_chapter_processed_for_type(chapter_id, PROCESS_TYPES['LOCATIONS']):
                return JSONResponse({"message": "Chapter already analyzed for locations", "alreadyAnalyzed": True})

            agent_manager = await AgentManager.create(current_user.id, project_id)
            locations = await agent_manager.analyze_unprocessed_chapter_locations(chapter_id)  # Pass chapter_id
            
            await db_instance.mark_chapter_processed(chapter_id, current_user.id, PROCESS_TYPES['LOCATIONS'])
            
            return {"locations": locations}
    except Exception as e:
        logger.error(f"Error analyzing chapter locations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if agent_manager:
            await agent_manager.close()

@location_router.post("/analyze-connections")
async def analyze_location_connections(
    project_id: str,
    location_ids: List[str],
    current_user: User = Depends(get_current_active_user)
):
    async with get_db_session() as session:
        try:
            agent_manager = await AgentManager.create(current_user.id, project_id)
            connections = await agent_manager.analyze_location_connections(location_ids)
            # Should convert LocationConnection to dict
            return {"connections": [connection.dict() for connection in connections]}  # Fixed
        except Exception as e:
            logger.error(f"Error analyzing location connections: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@location_router.get("/{location_id}")
async def get_location(
    location_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    async with get_db_session() as session:
        try:
            location = await db_instance.get_location_by_id(location_id, current_user.id, project_id)
            if not location:
                raise HTTPException(status_code=404, detail="Location not found")
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
    async with get_db_session() as session:
        try:
            updated_location = await db_instance.update_location(location_id, current_user.id, project_id, location_data)
            if not updated_location:
                raise HTTPException(status_code=404, detail="Location not found")
            return updated_location
        except Exception as e:
            logger.error(f"Error updating location: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@location_router.delete("/{location_id}")
async def delete_location(
    location_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    async with get_db_session() as session:
        try:
            success = await db_instance.delete_location(location_id, current_user.id, project_id)
            if not success:
                raise HTTPException(status_code=404, detail="Location not found")
            return {"message": "Location deleted successfully"}
        except Exception as e:
            logger.error(f"Error deleting location: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@location_router.get("/{location_id}/events")
async def get_location_events(
    location_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    async with get_db_session() as session:
        try:
            events = await db_instance.get_events_by_location(location_id, current_user.id, project_id)
            return {"events": events}
        except Exception as e:
            logger.error(f"Error getting location events: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))



# Include routers
app.include_router(auth_router)
app.include_router(chapter_router)
app.include_router(codex_item_router)
app.include_router(event_router)
app.include_router(location_router)
app.include_router(knowledge_base_router)
app.include_router(settings_router)
app.include_router(preset_router)
app.include_router(project_router)
app.include_router(universe_router)
app.include_router(codex_router)
app.include_router(relationship_router)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

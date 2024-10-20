from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging
import asyncio
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from database import db_instance
from agent_manager import AgentManager
from vector_store import VectorStore
import uuid
import json
from dotenv import load_dotenv
import os
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.routing import APIRouter
import io
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException
from pydantic import ValidationError
from fastapi.encoders import jsonable_encoder
from collections import defaultdict

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Novel AI API", version="1.0.0")

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
    CodexExtractionLLM: str
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
    styleGuide: str
    minWordCount: int
    additionalInstructions: str
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

# Helper functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(username: str):
    user_dict = db_instance.get_user_by_email(username)
    if user_dict:
        return UserInDB(**user_dict)
    return None


def authenticate_user(username: str, password: str):
    user = get_user(username)
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
    user = get_user(username=token_data.username)
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

# Project routes with target word count update
@project_router.put("/{project_id}/target-word-count")
async def update_project_target_word_count(
    project_id: str,
    update_data: UpdateTargetWordCountRequest,
    current_user: User = Depends(get_current_active_user)
):
    try:
        updated_project = db_instance.update_project_target_word_count(
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
async def create_universe(universe: UniverseCreate, current_user: User = Depends(get_current_active_user)):
    try:
        universe_id = db_instance.create_universe(universe.name, current_user.id)
        return {"id": universe_id, "name": universe.name}
    except Exception as e:
        logger.error(f"Error creating universe: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@universe_router.get("/{universe_id}", response_model=Dict[str, Any])
async def get_universe(universe_id: str, current_user: User = Depends(get_current_active_user)):
    universe = db_instance.get_universe(universe_id, current_user.id)
    if not universe:
        raise HTTPException(status_code=404, detail="Universe not found")
    return JSONResponse(content=universe)

@universe_router.put("/{universe_id}", response_model=Dict[str, Any])
async def update_universe(universe_id: str, universe: UniverseUpdate, current_user: User = Depends(get_current_active_user)):
    updated_universe = db_instance.update_universe(universe_id, universe.name, current_user.id)
    if not updated_universe:
        raise HTTPException(status_code=404, detail="Universe not found")
    return JSONResponse(content=updated_universe)

@universe_router.delete("/{universe_id}", response_model=bool)
async def delete_universe(universe_id: str, current_user: User = Depends(get_current_active_user)):
    success = db_instance.delete_universe(universe_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Universe not found")
    return JSONResponse(content={"success": success})

@universe_router.get("/{universe_id}/codex", response_model=List[Dict[str, Any]])
async def get_universe_codex(universe_id: str, current_user: User = Depends(get_current_active_user)):
    codex_items = db_instance.get_universe_codex(universe_id, current_user.id)
    return JSONResponse(content=codex_items)

@universe_router.get("/{universe_id}/knowledge-base", response_model=List[Dict[str, Any]])
async def get_universe_knowledge_base(universe_id: str, current_user: User = Depends(get_current_active_user)):
    knowledge_base_items = db_instance.get_universe_knowledge_base(universe_id, current_user.id)
    return JSONResponse(content=knowledge_base_items)

@universe_router.get("/{universe_id}/projects", response_model=List[Dict[str, Any]])
async def get_projects_by_universe(universe_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        projects = db_instance.get_projects_by_universe(universe_id, current_user.id)
        return JSONResponse(content=projects)
    except Exception as e:
        logger.error(f"Error fetching projects by universe: {str(e)}")
        return JSONResponse(
            content=jsonable_encoder({"detail": str(e)}),
            status_code=500
        )

@universe_router.get("/", response_model=List[Dict[str, Any]])
async def get_universes(current_user: User = Depends(get_current_active_user)):
    try:
        universes = db_instance.get_universes(current_user.id)
        return JSONResponse(content=universes)
    except Exception as e:
        logger.error(f"Error fetching universes: {str(e)}")
        return JSONResponse(
            content=jsonable_encoder({"detail": str(e)}),
            status_code=500
        )
    



# Auth routes
@auth_router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        logging.debug(f"Login attempt with username: {form_data.username}")
        user = authenticate_user(form_data.username, form_data.password)
        if not user:
            logging.debug("User authentication failed")
            raise HTTPException(
                status_code=401,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id}, expires_delta=access_token_expires  # Include user_id in JWT payload
        )
        logging.debug(f"Access token created for user: {user.username}")
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        logging.error(f"Error in login_for_access_token: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@auth_router.post("/register", status_code=201)
async def register(user: User):
    existing_user = get_user(user.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(user.password)
    user_id = db_instance.create_user(user.username, hashed_password)
    return {"message": "User registered successfully", "user_id": user_id}


# Chapter routes

generation_tasks = defaultdict(dict)


@chapter_router.post("/generate")
async def generate_chapters(
    request: ChapterGenerationRequest,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    try:
        user_id = current_user.id

        if project_id in generation_tasks[user_id] and not generation_tasks[user_id][project_id].done():
            raise HTTPException(status_code=400, detail="Chapter generation already in progress for this project.")

        agent_manager = AgentManager(current_user.id, project_id)
        previous_chapters = db_instance.get_all_chapters(current_user.id, project_id)
        codex_items = db_instance.get_all_codex_items(current_user.id, project_id)

        instructions = {
            "styleGuide": request.styleGuide,
            "minWordCount": request.minWordCount,
            "additionalInstructions": request.additionalInstructions
        }

        async def generate():
            chunks = []
            try:
                for i in range(request.numChapters):
                    chapter_number = len(previous_chapters) + i + 1
                    chunks.append(json.dumps({'type': 'start', 'chapterNumber': chapter_number}))

                    chapter_content = ""
                    async for chunk in agent_manager.generate_chapter_stream(
                        chapter_number=chapter_number,
                        plot=request.plot,
                        writing_style=request.writingStyle,
                        instructions=instructions,
                        previous_chapters=previous_chapters,
                        codex_items=codex_items
                    ):
                        if isinstance(chunk, dict) and 'content' in chunk:
                            chapter_content += chunk['content']
                        chunks.append(json.dumps(chunk))

                    logging.debug(f"Chapter {chapter_number} content generated")

                    logging.debug("Generating title")
                    chapter_title = await agent_manager.generate_title(chapter_content, chapter_number)
                    logging.debug(f"Title generated: {chapter_title}")

                    logging.debug("Checking chapter")
                    validity = await agent_manager.check_chapter(chapter_content, instructions, previous_chapters)
                    logging.debug("Chapter checked")

                    logging.debug("Extracting new codex items")
                    new_codex_items = agent_manager.check_and_extract_new_codex_items(chapter_content, codex_items)
                    logging.debug(f"New codex items extracted: {new_codex_items}")

                    logging.debug("Saving new codex items")
                    for item in new_codex_items:
                        item_id = await db_instance.create_codex_item(
                            item['name'],
                            item['description'],
                            item['type'],
                            item['subtype'],
                            current_user.id,
                            project_id
                        )
                        # Add new codex item to knowledge base
                        embedding_id = agent_manager.add_to_knowledge_base(
                            "codex_item",
                            item['description'],
                            {
                                "name": item['name'],
                                "id": item_id,
                                "type": item['type'],
                                "subtype": item['subtype']
                            }
                        )
                        # Update the codex item with the embedding_id
                        db_instance.update_codex_item_embedding_id(item_id, embedding_id)
                        # Add the new codex item to the codex_items list
                        codex_items.append({
                            "id": item_id,
                            "name": item['name'],
                            "description": item['description'],
                            "type": item['type'],
                            "subtype": item['subtype'],
                            "embedding_id": embedding_id
                        })

                    logging.debug("New codex items saved and added to knowledge base")

                    logging.debug("Saving chapter")
                    new_chapter = await db_instance.create_chapter(
                        chapter_title,  # No encoding/decoding
                        chapter_content,  # No encoding/decoding
                        current_user.id,
                        project_id
                    )
                    logging.debug(f"Chapter saved with id: {new_chapter['id']}")

                    # Add generated chapter to knowledge base
                    embedding_id = agent_manager.add_to_knowledge_base(
                        "chapter",
                        chapter_content,
                        {
                            "title": chapter_title,
                            "id": new_chapter['id'],
                            "type": "chapter"
                        }
                    )

                    # Update the chapter with the embedding_id
                    db_instance.update_chapter_embedding_id(new_chapter['id'], embedding_id)

                    logging.debug("Saving validity check")
                    await db_instance.save_validity_check(
                        chapter_id=str(new_chapter['id']),
                        chapter_title=str(chapter_title),
                        is_valid=bool(validity['is_valid']),
                        feedback=str(validity['feedback']),
                        review=str(validity.get('review', '')),
                        style_guide_adherence=bool(validity['style_guide_adherence']),
                        style_guide_feedback=str(validity.get('style_guide_feedback', '')),
                        continuity=bool(validity['continuity']),
                        continuity_feedback=str(validity.get('continuity_feedback', '')),
                        test_results=str(validity.get('test_results', '')),
                        user_id=current_user.id,
                        project_id=project_id
                    )
                    logging.debug("Validity check saved")

                    logging.debug("Preparing final chunk")
                    chunks.append(json.dumps({
                        'type': 'final', 
                        'chapterId': new_chapter['id'], 
                        'title': chapter_title, 
                        'content': chapter_content,
                        'validity': validity, 
                        'newCodexItems': new_codex_items
                    }))

                chunks.append(json.dumps({'type': 'done'}))
            except Exception as e:
                logging.error(f"Error in generate function: {str(e)}")
                chunks.append(json.dumps({'type': 'error', 'message': str(e)}))
            finally:
                logging.debug(f"Generate function completed for user {user_id}, project {project_id}")
                if project_id in generation_tasks[user_id]:
                    del generation_tasks[user_id][project_id]
            
            return chunks

        generation_task = asyncio.create_task(generate())
        generation_tasks[user_id][project_id] = generation_task
        background_tasks.add_task(await_and_log_exceptions, generation_task, user_id, project_id)

        async def stream_response():
            chunks = await generation_task
            for chunk in chunks:
                yield chunk + '\n'

        return StreamingResponse(stream_response(), media_type="application/json")

    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error in generate_chapters: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def await_and_log_exceptions(task, user_id, project_id):
    try:
        await task
    except asyncio.CancelledError:
        logging.info(f"Task cancelled for user {user_id}, project {project_id}")
    except Exception as e:
        logging.error(f"Error in background task for user {user_id}, project {project_id}: {str(e)}")
    finally:
        if project_id in generation_tasks[user_id]:
            del generation_tasks[user_id][project_id]


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
    try:
        chapter = db_instance.get_chapter(chapter_id, current_user.id, project_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")


        return chapter
    except Exception as e:
        logging.error(f"Error fetching chapter: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@chapter_router.get("/")
async def get_chapters(project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        chapters = db_instance.get_all_chapters(current_user.id, project_id)
        return {"chapters": chapters}
    except Exception as e:
        logger.error(f"Error fetching chapters: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@chapter_router.post("/")
async def create_chapter(chapter: ChapterCreate, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        new_chapter = await db_instance.create_chapter(
            chapter.title,
            chapter.content,
            current_user.id,
            project_id
        )

        # Add to knowledge base
        agent_manager = AgentManager(current_user.id, project_id)
        embedding_id = agent_manager.add_to_knowledge_base(
            "chapter",
            chapter.content,
            {
                "title": chapter.title,
                "id": new_chapter['id'],
                "type": "chapter"
            }
        )

        # Update the chapter with the embedding_id
        db_instance.update_chapter_embedding_id(new_chapter['id'], embedding_id)

        return {"message": "Chapter created successfully", "chapter": new_chapter, "embedding_id": embedding_id}
    except Exception as e:
        logger.error(f"Error creating chapter: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@chapter_router.put("/{chapter_id}")
async def update_chapter(chapter_id: str, chapter: ChapterUpdate, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        existing_chapter = db_instance.get_chapter(chapter_id, current_user.id, project_id)
        if not existing_chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")

        updated_chapter = db_instance.update_chapter(
            chapter_id,
            chapter.title,  # Removed encoding/decoding
            chapter.content,  # Removed encoding/decoding
            current_user.id,
            project_id
        )

        # Update in knowledge base
        agent_manager = AgentManager(current_user.id, project_id)
        agent_manager.update_or_remove_from_knowledge_base(
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
    try:
        chapter = db_instance.get_chapter(chapter_id, current_user.id, project_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")

        # Delete from knowledge base if embedding_id exists
        if chapter.get('embedding_id'):
            agent_manager = AgentManager(current_user.id, project_id)
            agent_manager.update_or_remove_from_knowledge_base(chapter['embedding_id'], 'delete')
        else:
            logging.warning(f"No embedding_id found for chapter {chapter_id}. Skipping knowledge base deletion.")

        # Delete from database
        db_instance.delete_chapter(chapter_id, current_user.id, project_id)

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
        agent_manager = AgentManager(current_user.id, project_id)
        generated_item = await agent_manager.generate_codex_item(
            request.codex_type, request.subtype, request.description
        )
        
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
        embedding_id = agent_manager.add_to_knowledge_base(
            "codex_item",
            generated_item["description"],
            {
                "name": generated_item["name"],
                "id": item_id,
                "type": request.codex_type,
                "subtype": request.subtype
            }
        )
        
        db_instance.update_codex_item_embedding_id(item_id, embedding_id)
        
        return {"message": "Codex item generated successfully", "item": generated_item, "id": item_id, "embedding_id": embedding_id}
    except Exception as e:
        logger.error(f"Error generating codex item: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating codex item: {str(e)}")

@codex_item_router.get("/")
async def get_codex_items(project_id: str, current_user: User = Depends(get_current_active_user)):
    codex_items = db_instance.get_all_codex_items(current_user.id, project_id)
    return {"codex_items": codex_items}


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
        agent_manager = AgentManager(current_user.id, project_id)
        embedding_id = agent_manager.add_to_knowledge_base(
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
        db_instance.update_codex_item_embedding_id(item_id, embedding_id)

        return {"message": "Codex item created successfully", "id": item_id, "embedding_id": embedding_id}
    except Exception as e:
        logger.error(f"Error creating codex item: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@codex_item_router.put("/{item_id}")
async def update_codex_item(item_id: str, codex_item: CodexItemUpdate, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        existing_item = db_instance.get_codex_item_by_id(item_id, current_user.id, project_id)
        if not existing_item:
            raise HTTPException(status_code=404, detail="Codex item not found")

        updated_item = db_instance.update_codex_item(item_id, codex_item.name, codex_item.description, codex_item.type, codex_item.subtype, current_user.id, project_id)

        # Update in knowledge base
        agent_manager = AgentManager(current_user.id, project_id)
        if existing_item.get('embedding_id'):
            metadata = {
                "name": codex_item.name,
                "id": item_id,
                "type": codex_item.type,
                "subtype": codex_item.subtype  # This can be None, which will remove the field if it exists
            }

            agent_manager.update_or_remove_from_knowledge_base(
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

            embedding_id = agent_manager.add_to_knowledge_base("codex_item", codex_item.description, metadata)
            db_instance.update_codex_item_embedding_id(item_id, embedding_id)

        return updated_item
    except Exception as e:
        logger.error(f"Error updating codex item: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@codex_item_router.delete("/{item_id}")
async def delete_codex_item(item_id: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        codex_item = db_instance.get_codex_item_by_id(item_id, current_user.id, project_id)
        if not codex_item:
            raise HTTPException(status_code=404, detail="Codex item not found")

        # Delete from knowledge base if embedding_id exists
        if codex_item.get('embedding_id'):
            agent_manager = AgentManager(current_user.id, project_id)
            agent_manager.update_or_remove_from_knowledge_base(codex_item['embedding_id'], 'delete')
        else:
            logging.warning(f"No embedding_id found for codex item {item_id}. Skipping knowledge base deletion.")

        # Delete from database
        deleted = db_instance.delete_codex_item(item_id, current_user.id, project_id)
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
    logger.info(f"Received request to add to knowledge base. Documents: {documents}, File: {file}")
    
    agent_manager = AgentManager(current_user.id, project_id)
    
    if documents:
        logger.info(f"Adding document: {documents}")
        metadata = json.loads(metadata_str) if metadata_str else {}
        agent_manager.add_to_knowledge_base("doc", documents, metadata)
        return {"message": "Document added to the knowledge base successfully"}
    
    elif file:
        logger.info(f"Adding file: {file.filename}")
        content = await file.read()
        metadata = json.loads(metadata_str) if metadata_str else {}
        text_content = content.decode("utf-8") # Decode content
        metadata['filename'] = file.filename
        agent_manager.add_to_knowledge_base("file", text_content, metadata)
        return {"message": "File added to the knowledge base successfully"}
    
    else:
        logger.warning("No documents or file provided")
        raise HTTPException(status_code=400, detail="No documents or file provided")

@knowledge_base_router.get("/")
async def get_knowledge_base_content(project_id: str, current_user: User = Depends(get_current_active_user)):
    logging.debug(f"Fetching knowledge base content for user: {current_user.id}")
    agent_manager = AgentManager(current_user.id, project_id)
    content = agent_manager.get_knowledge_base_content()
    logging.debug(f"Knowledge base content fetched for user: {current_user.id}")
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
    logging.debug(f"Formatted content: {formatted_content}")
    return {"content": formatted_content}

@knowledge_base_router.put("/{embedding_id}")
async def update_knowledge_base_item(embedding_id: str, new_content: str, new_metadata: Dict[str, Any], project_id: str, current_user: User = Depends(get_current_active_user)):
    agent_manager = AgentManager(current_user.id, project_id)
    agent_manager.update_or_remove_from_knowledge_base(embedding_id, 'update', new_content, new_metadata)
    return {"message": "Knowledge base item updated successfully"}

@knowledge_base_router.delete("/{embedding_id}")
async def delete_knowledge_base_item(embedding_id: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    agent_manager = AgentManager(current_user.id, project_id)
    agent_manager.update_or_remove_from_knowledge_base(embedding_id, 'delete')
    return {"message": "Knowledge base item deleted successfully"}

@knowledge_base_router.post("/query")
async def query_knowledge_base(query_data: KnowledgeBaseQuery, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        result = await AgentManager(current_user.id, project_id).generate_with_retrieval(query_data.query, query_data.chatHistory)
        return {"response": result}
    except Exception as e:
        logger.error(f"Error in query_knowledge_base: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@knowledge_base_router.post("/reset-chat-history")
async def reset_chat_history(project_id: str, current_user: User = Depends(get_current_active_user)):
    agent_manager = AgentManager(current_user.id, project_id)
    agent_manager.reset_memory()
    return {"message": "Chat history reset successfully"}

# Settings routes
@settings_router.post("/api-key")
async def save_api_key(api_key_update: ApiKeyUpdate, current_user: User = Depends(get_current_active_user)):
    db_instance.save_api_key(current_user.id, api_key_update.apiKey)
    return {"message": "API key saved successfully"}

@settings_router.get("/api-key")
async def check_api_key(current_user: User = Depends(get_current_active_user)):
    api_key = db_instance.get_api_key(current_user.id)
    is_set = bool(api_key)
    masked_key = '*' * (len(api_key) - 4) + api_key[-4:] if is_set else None
    return {"isSet": is_set, "apiKey": masked_key}

@settings_router.delete("/api-key")
async def remove_api_key(current_user: User = Depends(get_current_active_user)):
    db_instance.remove_api_key(current_user.id)
    return {"message": "API key removed successfully"}

@settings_router.get("/model")
async def get_model_settings(current_user: User = Depends(get_current_active_user)):
    settings = db_instance.get_model_settings(current_user.id)
    return settings

@settings_router.post("/model")
async def save_model_settings(settings: ModelSettings, current_user: User = Depends(get_current_active_user)):
    db_instance.save_model_settings(current_user.id, settings.dict())
    return {"message": "Model settings saved successfully"}


# Preset routes


@preset_router.post("/")
async def create_preset(preset: PresetCreate, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        preset_id = db_instance.create_preset(current_user.id, project_id, preset.name, preset.data)
        return {"id": preset_id, "name": preset.name, "data": preset.data}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error creating preset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@preset_router.get("/")
async def get_presets(project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        presets = db_instance.get_presets(current_user.id, project_id)
        return presets
    except Exception as e:
        logger.error(f"Error getting presets: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@preset_router.put("/{preset_name}")  # Update route
async def update_preset(preset_name: str, preset_update: PresetUpdate, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        existing_preset = db_instance.get_preset_by_name(preset_name, current_user.id, project_id)
        if not existing_preset:
            raise HTTPException(status_code=404, detail="Preset not found")

        # Update the preset data
        updated_data = preset_update.data.dict()
        db_instance.update_preset(preset_name, current_user.id, project_id, updated_data)

        return {"message": "Preset updated successfully", "name": preset_name, "data": updated_data}
    except Exception as e:
        logger.error(f"Error updating preset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@preset_router.get("/{preset_name}")
async def get_preset(preset_name: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        preset = db_instance.get_preset_by_name(preset_name, current_user.id, project_id)
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        return preset
    except Exception as e:
        logger.error(f"Error getting preset: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@preset_router.delete("/{preset_name}")
async def delete_preset(preset_name: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        deleted = db_instance.delete_preset(preset_name, current_user.id, project_id)
        if deleted:
            return {"message": "Preset deleted successfully"}
        raise HTTPException(status_code=404, detail="Preset not found")
    except Exception as e:
        logger.error(f"Error deleting preset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Project Routes

@project_router.put("/{project_id}/universe")
async def update_project_universe(project_id: str, universe: Dict[str, Any], current_user: User = Depends(get_current_active_user)):
    try:
        universe_id = universe.get('universe_id')  # This can now be None
        updated_project = db_instance.update_project_universe(project_id, universe_id, current_user.id)
        if not updated_project:
            raise HTTPException(status_code=404, detail="Project not found")
        return updated_project
    except Exception as e:
        logger.error(f"Error updating project universe: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@project_router.post("/")
async def create_project(project: ProjectCreate, current_user: User = Depends(get_current_active_user)):
    try:
        project_id = db_instance.create_project(project.name, project.description, current_user.id, project.universe_id)
        return {"message": "Project created successfully", "project_id": project_id}
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating project: {str(e)}")

@project_router.get("/")
async def get_projects(current_user: User = Depends(get_current_active_user)):
    projects = db_instance.get_projects(current_user.id)
    return {"projects": projects}

@project_router.get("/{project_id}")
async def get_project(project_id: str, current_user: User = Depends(get_current_active_user)):
    project = db_instance.get_project(project_id, current_user.id)
    if project:
        return project
    raise HTTPException(status_code=404, detail="Project not found")

@project_router.put("/{project_id}")
async def update_project(project_id: str, project: ProjectUpdate, current_user: User = Depends(get_current_active_user)):
    try:
        updated_project = db_instance.update_project(
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
    success = db_instance.delete_project(project_id, current_user.id)
    if success:
        return {"message": "Project deleted successfully"}
    raise HTTPException(status_code=404, detail="Project not found")

# Include routers
app.include_router(auth_router)
app.include_router(chapter_router)
app.include_router(codex_item_router)
app.include_router(knowledge_base_router)
app.include_router(settings_router)
app.include_router(preset_router)
app.include_router(project_router)
app.include_router(universe_router)
app.include_router(codex_router)

@app.get("/chat-history")
async def get_chat_history(project_id: str, current_user: User = Depends(get_current_active_user)):
    agent_manager = AgentManager(current_user.id, project_id)
    chat_history = agent_manager.get_chat_history()
    return {"chatHistory": chat_history}

@app.post("/chat-history")
async def save_chat_history(chat_history: ChatHistoryRequest, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        # Convert Pydantic models to dictionaries
        chat_history_dicts = [item.dict() for item in chat_history.chatHistory]
        db_instance.save_chat_history(current_user.id, project_id, chat_history_dicts)
        return {"message": "Chat history saved successfully"}
    except Exception as e:
        logger.error(f"Error saving chat history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/knowledge-base/chat-history")
async def get_knowledge_base_chat_history(project_id: str, current_user: User = Depends(get_current_active_user)):
    agent_manager = AgentManager(current_user.id, project_id)
    chat_history = agent_manager.get_chat_history()
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
        db_instance.get_session()
        
        # Vector Store Check
        try:
            vector_store = VectorStore("test_user", "test_api_key", "models/embedding-001")
            vector_store.add_to_knowledge_base("Test content")
            test_result = vector_store.similarity_search("test", k=1)
            
            return JSONResponse({"status": "OK", "database": "Connected", "vector_store": "Connected"})
        except Exception as e:
            logging.error(f"Vector Store check failed: {str(e)}")
            return JSONResponse({"status": "Error", "database": "Connected", "vector_store": str(e)}, status_code=500)
        
    except Exception as e:
        logging.error(f"Health check failed: {str(e)}")
        return JSONResponse({"status": "Error", "error": str(e)}, status_code=500)

@app.get("/validity-checks")
async def get_validity_checks(project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        validity_checks = db_instance.get_all_validity_checks(current_user.id, project_id)
        return {"validityChecks": validity_checks}
    except Exception as e:
        logging.error(f"Error fetching validity checks: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/validity-checks/{check_id}")
async def delete_validity_check(check_id: str, project_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        result = db_instance.delete_validity_check(check_id, current_user.id, project_id)
        if result:
            return {"message": "Validity check deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Validity check not found")
    except Exception as e:
        logging.error(f"Error deleting validity check: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

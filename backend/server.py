from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
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
    allow_origins=["http://localhost:3000"],  # Replace with your frontend URL
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
    user_id: Optional[str] = None # Add user_id to TokenData

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

class CharacterCreate(BaseModel):
    name: str
    description: str

class CharacterUpdate(BaseModel):
    name: str
    description: str

class ModelSettings(BaseModel):
    mainLLM: str
    checkLLM: str
    embeddingsModel: str
    titleGenerationLLM: str
    characterExtractionLLM: str
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

class PresetUpdate(BaseModel): # New model for updating presets
    name: str
    data: ChapterGenerationRequest

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
        user_id: str = payload.get("user_id") # Get user_id from payload
        if username is None or user_id is None:
            raise credentials_exception
        token_data = TokenData(username=username, user_id=user_id) # Include user_id in TokenData
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
character_router = APIRouter(prefix="/characters", tags=["Characters"])
knowledge_base_router = APIRouter(prefix="/knowledge-base", tags=["Knowledge Base"])
settings_router = APIRouter(prefix="/settings", tags=["Settings"])
preset_router = APIRouter(prefix="/presets", tags=["Presets"]) # New router for presets

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
            data={"sub": user.username, "user_id": user.id}, expires_delta=access_token_expires # Include user_id in JWT payload
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

@chapter_router.post("/generate")
async def generate_chapters(
    request: ChapterGenerationRequest,
    current_user: User = Depends(get_current_active_user)
):
    try:
        agent_manager = AgentManager(current_user.id)
        previous_chapters = db_instance.get_all_chapters(current_user.id)
        characters = db_instance.get_all_characters(current_user.id)

        instructions = {
            "styleGuide": request.styleGuide,
            "minWordCount": request.minWordCount,
            "additionalInstructions": request.additionalInstructions
        }

        async def generate():
            try:
                for i in range(request.numChapters):
                    chapter_number = len(previous_chapters) + i + 1
                    try:
                        logging.debug(f"Starting generation for chapter {chapter_number}")
                        chapter_content = ""
                        async for chunk in agent_manager.generate_chapter_stream(
                            chapter_number=chapter_number,
                            plot=request.plot,
                            writing_style=request.writingStyle,
                            instructions=instructions,
                            previous_chapters=previous_chapters,
                            characters=characters
                        ):
                            if isinstance(chunk, dict) and 'content' in chunk:
                                chapter_content += chunk['content']
                            yield json.dumps(chunk) + '\n'

                        logging.debug(f"Chapter {chapter_number} content generated")

                        logging.debug("Generating title")
                        chapter_title = await agent_manager.generate_title(chapter_content, chapter_number)
                        logging.debug(f"Title generated: {chapter_title}")

                        logging.debug("Checking chapter")
                        validity = await agent_manager.check_chapter(chapter_content, instructions, previous_chapters)
                        logging.debug("Chapter checked")

                        logging.debug("Extracting new characters")
                        new_characters = agent_manager.check_and_extract_new_characters(chapter_content, characters)
                        logging.debug(f"New characters extracted: {new_characters}")

                        logging.debug("Saving new characters")
                        for char in new_characters:
                            character_id = await db_instance.create_character(char['name'], char['description'], current_user.id)
                            # Add new character to knowledge base
                            agent_manager.add_to_knowledge_base("character", char['description'], {"name": char['name'], "id": character_id, "type": "character"})
                            # Add the new character to the characters list
                            characters.append({"id": character_id, "name": char['name'], "description": char['description']})
                        logging.debug("New characters saved and added to knowledge base")

                        logging.debug("Saving chapter")
                        new_chapter = await db_instance.create_chapter(chapter_title, chapter_content, current_user.id)
                        logging.debug(f"Chapter saved with id: {new_chapter['id']}")

                        # Add generated chapter to knowledge base
                        agent_manager.add_to_knowledge_base("chapter", chapter_content, {"title": chapter_title, "id": new_chapter['id'], "type": "chapter"})

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
                            user_id=current_user.id
                        )
                        logging.debug("Validity check saved")

                        logging.debug("Preparing final chunk")
                        yield json.dumps({
                            'type': 'final', 
                            'chapterId': new_chapter['id'], 
                            'title': chapter_title, 
                            'content': chapter_content,
                            'validity': validity, 
                            'newCharacters': new_characters
                        }) + '\n'
                        logging.debug("Final chunk sent")

                    except Exception as e:
                        logging.error(f"Error generating chapter {chapter_number}: {str(e)}")
                        yield json.dumps({'error': str(e)}) + '\n'

                logging.debug("All chapters generated, sending 'done' signal")
                yield json.dumps({'type': 'done'}) + '\n'
            except Exception as e:
                logging.error(f"Unexpected error in generate function: {str(e)}")
                yield json.dumps({'error': str(e)}) + '\n'
            finally:
                logging.debug("Generate function completed")

        return StreamingResponse(generate(), media_type="application/json")
    except Exception as e:
        logging.error(f"Error in generate_chapters: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@chapter_router.post("/cancel")
async def cancel_chapter_generation(current_user: User = Depends(get_current_active_user)):
    # Implement cancellation logic here
    return {"message": "Generation cancelled"}

@chapter_router.get("/")
async def get_chapters(request: Request, current_user: User = Depends(get_current_active_user)):
    try:
        chapters = db_instance.get_all_chapters(current_user.id)
        return {"chapters": chapters}
    except Exception as e:
        logger.error(f"Error fetching chapters: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@chapter_router.post("/")
async def create_chapter(chapter: ChapterCreate, current_user: User = Depends(get_current_active_user)):
    try:
        new_chapter = await db_instance.create_chapter(chapter.title, chapter.content, current_user.id)
        
        # Add to knowledge base
        agent_manager = AgentManager(current_user.id)
        agent_manager.add_to_knowledge_base("chapter", chapter.content, {"title": chapter.title, "id": new_chapter['id'], "type": "chapter"})
        
        return {"message": "Chapter created successfully", "id": new_chapter['id']}
    except Exception as e:
        logger.error(f"Error creating chapter: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@chapter_router.put("/{chapter_id}")
async def update_chapter(chapter_id: str, chapter: ChapterUpdate, current_user: User = Depends(get_current_active_user)):
    try:
        updated_chapter = db_instance.update_chapter(chapter_id, chapter.title, chapter.content, current_user.id)
        if not updated_chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        
        # Update in knowledge base
        agent_manager = AgentManager(current_user.id)
        # First, remove the old chapter from the knowledge base
        agent_manager.update_or_remove_from_knowledge_base(chapter_id, 'delete')
        # Then, add the updated chapter to the knowledge base
        agent_manager.add_to_knowledge_base("chapter", chapter.content, {"title": chapter.title, "id": chapter_id, "type": "chapter"})
        
        return updated_chapter
    except Exception as e:
        logger.error(f"Error updating chapter: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@chapter_router.delete("/{chapter_id}")
async def delete_chapter(chapter_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        deleted = db_instance.delete_chapter(chapter_id, current_user.id)
        if deleted:
            # Remove from knowledge base
            agent_manager = AgentManager(current_user.id)
            agent_manager.update_or_remove_from_knowledge_base(chapter_id, 'delete')
            return {"message": "Chapter deleted successfully"}
        raise HTTPException(status_code=404, detail="Chapter not found")
    except Exception as e:
        logger.error(f"Error deleting chapter: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Character routes
@character_router.get("/")
async def get_characters(current_user: User = Depends(get_current_active_user)):
    characters = db_instance.get_all_characters(current_user.id)
    return {"characters": characters}

@character_router.post("/")
async def create_character(character: CharacterCreate, current_user: User = Depends(get_current_active_user)):
    try:
        character_id = await db_instance.create_character(character.name, character.description, current_user.id)
        
        # Add to knowledge base
        agent_manager = AgentManager(current_user.id)
        agent_manager.add_to_knowledge_base("character", character.description, {"name": character.name, "id": character_id, "type": "character"})
        
        return {"message": "Character created successfully", "id": character_id}
    except Exception as e:
        logger.error(f"Error creating character: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@character_router.put("/{character_id}")
async def update_character(character_id: str, character: CharacterUpdate, current_user: User = Depends(get_current_active_user)):
    try:
        updated_character = db_instance.update_character(character_id, character.name, character.description, current_user.id)
        if not updated_character:
            raise HTTPException(status_code=404, detail="Character not found")
        
        # Update in knowledge base
        agent_manager = AgentManager(current_user.id)
        # First, remove the old character from the knowledge base
        agent_manager.update_or_remove_from_knowledge_base(character_id, 'delete')
        # Then, add the updated character to the knowledge base
        agent_manager.add_to_knowledge_base("character", character.description, {"name": character.name, "id": character_id, "type": "character"})
        
        return updated_character
    except Exception as e:
        logger.error(f"Error updating character: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@character_router.delete("/{character_id}")
async def delete_character(character_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        deleted = db_instance.delete_character(character_id, current_user.id)
        if deleted:
            # Remove from knowledge base
            agent_manager = AgentManager(current_user.id)
            agent_manager.update_or_remove_from_knowledge_base(character_id, 'delete')
            return {"message": "Character deleted successfully"}
        raise HTTPException(status_code=404, detail="Character not found")
    except Exception as e:
        logger.error(f"Error deleting character: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Knowledge base routes
@knowledge_base_router.post("/")
async def add_to_knowledge_base(
    documents: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    metadata_str: Optional[str] = Form(None), # Add metadata parameter
    current_user: User = Depends(get_current_active_user)
):
    logger.info(f"Received request to add to knowledge base. Documents: {documents}, File: {file}")
    
    agent_manager = AgentManager(current_user.id)
    
    if documents:
        logger.info(f"Adding document: {documents}")
        metadata = json.loads(metadata_str) if metadata_str else {}
        agent_manager.add_to_knowledge_base("doc", documents, metadata)
        return {"message": "Document added to the knowledge base successfully"}
    
    elif file:
        logger.info(f"Adding file: {file.filename}")
        content = await file.read()
        metadata = json.loads(metadata_str) if metadata_str else {}
        metadata['filename'] = file.filename
        agent_manager.add_to_knowledge_base("file", text_content, metadata)
        return {"message": "File added to the knowledge base successfully"}
    
    else:
        logger.warning("No documents or file provided")
        raise HTTPException(status_code=400, detail="No documents or file provided")

@knowledge_base_router.get("/")
async def get_knowledge_base_content(current_user: User = Depends(get_current_active_user)):
    logging.debug(f"Fetching knowledge base content for user: {current_user.id}")
    agent_manager = AgentManager(current_user.id)
    content = agent_manager.get_knowledge_base_content()
    logging.debug(f"Knowledge base content fetched for user: {current_user.id}")
    formatted_content = [
        {
            'type': item['metadata'].get('type', 'Unknown'),
            'content': item['page_content'],
            'embedding_id': item['id']
        }
        for item in content
    ]
    logging.debug(f"Formatted content: {formatted_content}")
    return {"content": formatted_content}

@knowledge_base_router.put("/{embedding_id}")
async def update_knowledge_base_item(embedding_id: str, new_content: str, new_metadata: Dict[str, Any], current_user: User = Depends(get_current_active_user)):
    agent_manager = AgentManager(current_user.id)
    agent_manager.update_or_remove_from_knowledge_base(embedding_id, 'update', new_content, new_metadata)
    return {"message": "Knowledge base item updated successfully"}

@knowledge_base_router.delete("/{embedding_id}")
async def delete_knowledge_base_item(embedding_id: str, current_user: User = Depends(get_current_active_user)):
    agent_manager = AgentManager(current_user.id)
    agent_manager.update_or_remove_from_knowledge_base(embedding_id, 'delete')
    return {"message": "Knowledge base item deleted successfully"}

@knowledge_base_router.post("/query")
async def query_knowledge_base(query_data: KnowledgeBaseQuery, current_user: User = Depends(get_current_active_user)):
    agent_manager = AgentManager(current_user.id)
    result = await agent_manager.generate_with_retrieval(query_data.query, query_data.chatHistory)
    return {"result": result}

@knowledge_base_router.post("/reset-chat-history")
async def reset_chat_history(current_user: User = Depends(get_current_active_user)):
    agent_manager = AgentManager(current_user.id)
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

# Add this new route for chat history
@app.get("/chat-history")
async def get_chat_history(current_user: User = Depends(get_current_active_user)):
    logging.debug(f"Fetching chat history for user: {current_user.id}")
    chat_history = db_instance.get_chat_history(current_user.id)
    logging.debug(f"Chat history fetched: {len(chat_history)} messages")
    return {"chatHistory": chat_history}

# Preset routes


@preset_router.post("/", response_model=PresetCreate)
async def create_preset(preset: PresetCreate, current_user: User = Depends(get_current_active_user)):
    try:
        # Validate the preset data
        if not preset.name or not preset.data:
            raise ValueError("Preset name and data are required")

        # Ensure all required fields are present in the data
        required_fields = ['numChapters', 'plot', 'writingStyle', 'styleGuide', 'minWordCount', 'additionalInstructions', 'instructions']
        missing_fields = [field for field in required_fields if field not in preset.data]
        
        # Log the missing fields
        logger.debug(f"Missing fields: {missing_fields}")

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        # Create the preset
        preset_id = db_instance.create_preset(current_user.id, preset.name, preset.data)
        
        # Log the created preset
        #logger.info(f"Created preset with ID: {preset_id}")

        # Return the created preset
        return {"id": preset_id, "user_id": current_user.id, "name": preset.name, "data": preset.data}
    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        raise HTTPException(status_code=422, detail=str(ve))
    except ValidationError as ve:
        logger.error(f"Pydantic validation error: {str(ve)}")
        raise HTTPException(status_code=422, detail=ve.errors())
    except Exception as e:
        logger.error(f"Error creating preset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@preset_router.get("/", response_model=List[PresetCreate])
async def get_presets(current_user: User = Depends(get_current_active_user)):
    try:
        presets = db_instance.get_presets(current_user.id)
        return presets
    except Exception as e:
        logger.error(f"Error getting presets: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@preset_router.get("/{preset_name}", response_model=PresetCreate)
async def get_preset(preset_name: str, current_user: User = Depends(get_current_active_user)):
    try:
        preset = db_instance.get_preset_by_name(preset_name, current_user.id)
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        return preset
    except Exception as e:
        logger.error(f"Error getting preset: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@preset_router.delete("/{preset_name}")
async def delete_preset(preset_name: str, current_user: User = Depends(get_current_active_user)):
    try:
        deleted = db_instance.delete_preset(preset_name, current_user.id)
        if deleted:
            return {"message": "Preset deleted successfully"}
        raise HTTPException(status_code=404, detail="Preset not found")
    except Exception as e:
        logger.error(f"Error deleting preset: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Include routers
app.include_router(auth_router)
app.include_router(chapter_router)
app.include_router(character_router)
app.include_router(knowledge_base_router)
app.include_router(settings_router)
app.include_router(preset_router) # Include the preset router

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
async def get_validity_checks(current_user: User = Depends(get_current_active_user)):
    try:
        validity_checks = db_instance.get_all_validity_checks(current_user.id)
        return {"validityChecks": validity_checks}
    except Exception as e:
        logging.error(f"Error fetching validity checks: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/validity-checks/{check_id}")
async def delete_validity_check(check_id: str, current_user: User = Depends(get_current_active_user)):
    try:
        result = db_instance.delete_validity_check(check_id, current_user.id)
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

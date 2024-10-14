from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
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

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

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
    instructions: Dict[str, Any]

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
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
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
            data={"sub": user.username}, expires_delta=access_token_expires
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
            for i in range(request.numChapters):
                chapter_number = len(previous_chapters) + i + 1
                try:
                    async for chunk in agent_manager.generate_chapter_stream(
                        chapter_number=chapter_number,
                        plot=request.plot,
                        writing_style=request.writingStyle,
                        instructions=instructions,
                        previous_chapters=previous_chapters,
                        characters=characters
                    ):
                        yield json.dumps(chunk)

                    # After generation is complete, perform post-processing
                    chapter_content = chunk['content']
                    chapter_title = await agent_manager.generate_title(chapter_content, chapter_number)
                    validity = await agent_manager.check_chapter(chapter_content, request.instructions, previous_chapters)
                    new_characters = await agent_manager.check_and_extract_new_characters(chapter_content, characters)

                    # Save chapter and validity check
                    chapter_id = db_instance.create_chapter(chapter_title, chapter_content, current_user.id)
                    db_instance.save_validity_check(
                        chapter_id=str(chapter_id),
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

                    # Send final chunk with all metadata
                    yield json.dumps({'type': 'final', 'chapterId': chapter_id, 'title': chapter_title, 'validity': validity, 'newCharacters': new_characters})

                except Exception as e:
                    logging.error(f"Error generating chapter {chapter_number}: {str(e)}")
                    yield json.dumps({'error': str(e)})

            yield json.dumps({'type': 'done'})

        return StreamingResponse(generate(), media_type="text/event-stream")
    except Exception as e:
        logging.error(f"Error in generate_chapters: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@chapter_router.post("/cancel")
async def cancel_chapter_generation(current_user: User = Depends(get_current_active_user)):
    # Implement cancellation logic here
    return {"message": "Generation cancelled"}

@chapter_router.get("/")
async def get_chapters(current_user: User = Depends(get_current_active_user)):
    chapters = db_instance.get_all_chapters(current_user.id)
    return {"chapters": chapters}

@chapter_router.put("/{chapter_id}")
async def update_chapter(chapter_id: str, chapter: ChapterUpdate, current_user: User = Depends(get_current_active_user)):
    updated_chapter = db_instance.update_chapter(chapter_id, chapter.title, chapter.content, current_user.id)
    if not updated_chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return updated_chapter

@chapter_router.delete("/{chapter_id}")
async def delete_chapter(chapter_id: str, current_user: User = Depends(get_current_active_user)):
    if db_instance.delete_chapter(chapter_id, current_user.id):
        return {"message": "Chapter deleted successfully"}
    raise HTTPException(status_code=404, detail="Chapter not found")

@chapter_router.post("/")
async def create_chapter(chapter: ChapterCreate, current_user: User = Depends(get_current_active_user)):
    new_chapter = db_instance.create_chapter(chapter.title, chapter.content, current_user.id)
    return {"message": "Chapter created successfully", "id": new_chapter['id']}

@chapter_router.get("/validity-checks")
async def get_validity_checks(current_user: User = Depends(get_current_active_user)):
    validity_checks = db_instance.get_all_validity_checks(current_user.id)
    return {"validityChecks": validity_checks}

@chapter_router.delete("/validity-checks/{check_id}")
async def delete_validity_check(check_id: str, current_user: User = Depends(get_current_active_user)):
    if db_instance.delete_validity_check(check_id, current_user.id):
        return {"message": "Validity check deleted successfully"}
    raise HTTPException(status_code=404, detail="Validity check not found")

# Character routes
@character_router.get("/")
async def get_characters(current_user: User = Depends(get_current_active_user)):
    characters = db_instance.get_all_characters(current_user.id)
    return {"characters": characters}

@character_router.post("/")
async def create_character(character: CharacterCreate, current_user: User = Depends(get_current_active_user)):
    character_id = db_instance.create_character(character.name, character.description, current_user.id)
    return {"message": "Character created successfully", "id": character_id}

@character_router.put("/{character_id}")
async def update_character(character_id: str, character: CharacterUpdate, current_user: User = Depends(get_current_active_user)):
    updated_character = db_instance.update_character(character_id, character.name, character.description, current_user.id)
    if not updated_character:
        raise HTTPException(status_code=404, detail="Character not found")
    return updated_character

@character_router.delete("/{character_id}")
async def delete_character(character_id: str, current_user: User = Depends(get_current_active_user)):
    if db_instance.delete_character(character_id, current_user.id):
        return {"message": "Character deleted successfully"}
    raise HTTPException(status_code=404, detail="Character not found")

# Knowledge base routes
@knowledge_base_router.post("/")
async def add_to_knowledge_base(documents: List[str], current_user: User = Depends(get_current_active_user)):
    agent_manager = AgentManager(current_user.id)
    for doc in documents:
        agent_manager.add_to_knowledge_base("doc", doc)
    return {"message": "Documents added to the knowledge base successfully"}

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

# Include routers
app.include_router(auth_router)
app.include_router(chapter_router)
app.include_router(character_router)
app.include_router(knowledge_base_router)
app.include_router(settings_router)

@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    try:
        return await asyncio.wait_for(call_next(request), timeout=60.0)  # 60 seconds timeout
    except asyncio.TimeoutError:
        return JSONResponse({"detail": "Request timeout"}, status_code=504)

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

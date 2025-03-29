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
from models import CodexItemType, WorldbuildingSubtype
from database import User, Chapter, Project, CodexItem
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
    File,
    UploadFile,
    Form,
    Body,
    Header,
    Query,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel, Field, ValidationError, EmailStr
from logging.handlers import RotatingFileHandler
from pathlib import Path

from agent_manager import AgentManager, PROCESS_TYPES, close_all_agent_managers
from api_key_manager import ApiKeyManager, SecurityManager
from database import db_instance

# Models likely needed by server endpoints too
from models import (
    CodexItemType,
    WorldbuildingSubtype,
    CodexItemGenerateRequest,
    ChapterGenerationRequest,
    KnowledgeBaseQuery,
    ChatHistoryRequest,
    ChatHistoryItem,
    ModelSettings,
    ApiKeyUpdate,
    UserCreate,
    ChapterCreate,
    ChapterUpdate,
    CodexItemCreate,
    CodexItemUpdate,
    PresetCreate,
    PresetUpdate,
    ProjectCreate,
    ProjectUpdate,
    UniverseCreate,
    UniverseUpdate,
    UpdateTargetWordCountRequest,
    BackstoryExtractionRequest,
)

# PDF/DOCX processing imports
from PyPDF2 import PdfReader
import pdfplumber
from docx import (
    Document as DocxDocument,
)  # Rename to avoid clash with langchain Document

import sys
import signal


def setup_logging():
    """Configure logging to save to a log file and output to console"""
    try:
        # Get log directory from environment variable set by ServerManager
        log_dir = os.getenv("LOG_DIR")
        if not log_dir:
            raise ValueError("LOG_DIR environment variable not set")

        # Create logs directory if it doesn't exist
        log_dir = Path(log_dir)
        log_dir.mkdir(exist_ok=True)

        # Configure the log file path
        log_file = log_dir / "server.log"

        # If log file exists, rename it with last modified date
        if log_file.exists():
            last_modified = datetime.fromtimestamp(log_file.stat().st_mtime)
            date_str = last_modified.strftime("%Y%m%d_%H%M%S")
            archived_name = f"server_{date_str}.log"
            log_file.rename(log_dir / archived_name)

        # Create a logger
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        # Create handlers
        # RotatingFileHandler with max size of 10MB and keep 5 backup files
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"  # 10MB
        )
        console_handler = logging.StreamHandler()

        # Set handlers level
        file_handler.setLevel(logging.INFO)
        console_handler.setLevel(logging.INFO)

        # Create formatters and add it to handlers
        log_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(log_format)
        console_handler.setFormatter(log_format)

        # Add handlers to the logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        logger.info("Logging setup completed")
        return logger

    except Exception as e:
        print(f"Error setting up logging: {str(e)}")
        raise


logger = logging.getLogger(__name__)  # Use standard logger setup from previous example

# --- Global Variables ---
shutdown_event = asyncio.Event()

# --- Removed SessionManager and related cleanup task ---

# AgentManagerStore


class AgentManagerStore:
    def __init__(self, api_key_manager: ApiKeyManager):
        self._managers = {}
        self._lock = Lock()
        self.api_key_manager = api_key_manager

    @asynccontextmanager
    async def get_or_create_manager(
        self, user_id: str, project_id: str
    ) -> AsyncGenerator[AgentManager, None]:
        key = f"{user_id}_{project_id}"
        manager = None
        try:
            async with self._lock:
                manager = self._managers.get(key)
                if not manager:
                    # Pass api_key_manager when creating new manager
                    manager = await AgentManager.create(
                        user_id, project_id, self.api_key_manager
                    )
                    self._managers[key] = manager
            yield manager
        finally:
            # Note: Closing the manager immediately after use might be inefficient
            # if the same user/project makes multiple requests quickly.
            # Consider a different strategy like timed cleanup or reference counting
            # if performance becomes an issue.
            # For now, keeping the original logic:
            if manager:
                await manager.close()
                async with self._lock:
                    self._managers.pop(key, None)


# --- Lifespan Manager ---
logger = setup_logging()  # Initialize logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup
    logger.info("Starting up server...")

    try:
        # Initialize database
        logger.info("Initializing database...")
        await db_instance.initialize()

        # Create Qdrant data directory if it doesn't exist
        qdrant_path = Path("./qdrant_db")
        qdrant_path.mkdir(exist_ok=True)
        logger.info(f"Qdrant data directory: {qdrant_path.absolute()}")

        # --- Removed session cleanup task ---

        yield

    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down server...")

        # --- Removed session cleanup task cancellation ---

        # Close all agent managers to properly close vector stores
        logger.info("Closing active agent managers...")
        # Create a copy of keys to avoid modification during iteration issues
        manager_keys = list(agent_manager_store._managers.keys())
        for key in manager_keys:
            manager = agent_manager_store._managers.pop(key, None)
            if manager:
                try:
                    await manager.close()
                    user_id_part, project_id_part = key.split("_", 1)
                    logger.info(
                        f"Closed agent manager for user {user_id_part[:8]}, project {project_id_part[:8]}"
                    )
                except Exception as e:
                    logger.error(f"Error closing agent manager for key {key}: {str(e)}")

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
    version="1.1.0",  # Increment version
    lifespan=lifespan,
    default_response_class=JSONResponse,
    default_encoding="utf-8",
)

# CORS Middleware
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8080").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"], # Ensure Authorization is allowed
)

# --- Removed MAX_INACTIVITY and ACTIVE_SESSION_EXTEND ---

security_manager = SecurityManager()
api_key_manager = ApiKeyManager(security_manager)
agent_manager_store = AgentManagerStore(api_key_manager)


async def get_current_user(
    authorization: str = Header(None), # Only depend on Authorization header
):
    try:
        if not authorization:
            raise HTTPException(
                status_code=401, detail="Missing authentication credentials (Authorization header)"
            )

        # Extract token from Authorization header
        if not authorization.startswith("Bearer "):
             raise HTTPException(
                status_code=401, detail="Invalid Authorization header format. Expected 'Bearer <token>'."
            )
        token = authorization.replace("Bearer ", "")

        # Get user from Supabase token
        try:
            # Use the provided token to get the user
            user_response = db_instance.supabase.auth.get_user(token)
        except Exception as e:
            # Log the specific Supabase error if possible
            logger.warning(f"Supabase auth.get_user failed: {e}")
            # Don't attempt refresh here, let the client handle token expiry/refresh
            raise HTTPException(
                status_code=401, detail="Invalid or expired token. Please login again."
            )

        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=401, detail="Invalid authentication credentials"
            )

        # Check if user exists in local database (optional, but good for consistency)
        # This ensures that a user authenticated via Supabase also has a record
        # in our local DB for storing app-specific data like API keys, settings etc.
        local_user = await db_instance.get_user_by_email(user_response.user.email)
        if not local_user:
            # If user is authenticated via Supabase but not in local DB, create them.
            # This handles cases where a user might have been deleted locally but still has a valid Supabase session,
            # or initial signup race conditions.
            try:
                logger.info(f"User {user_response.user.email} authenticated via Supabase but not found locally. Creating local record.")
                local_user = await db_instance.sign_up(
                    email=user_response.user.email,
                    supabase_id=user_response.user.id,
                    password=None, # No password needed, already authenticated
                )
                if not local_user:
                    # This case should ideally not happen if sign_up works correctly
                    raise Exception("Failed to create local user record after Supabase authentication.")
            except Exception as e:
                logger.error(f"Failed to create local user record for {user_response.user.email}: {e}", exc_info=True)
                # If creation fails, we might still proceed if local user data isn't strictly required for the endpoint,
                # but it's safer to deny access as the system state is inconsistent.
                raise HTTPException(status_code=500, detail="Failed to synchronize user data. Please try again later.")


        # --- Removed custom session validation ---

        # Return the Supabase user object
        return user_response.user

    except HTTPException as he:
        # Re-raise HTTPExceptions directly
        raise he
    except Exception as e:
        logger.error(f"Error validating token in get_current_user: {str(e)}", exc_info=True)
        raise HTTPException(status_code=401, detail="Authentication failed")


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    # This function remains largely the same, ensuring the user fetched by get_current_user is valid and active.
    try:
        if not current_user:
            # This case should technically be caught by get_current_user raising an exception,
            # but kept for robustness.
            raise HTTPException(
                status_code=401, detail="Could not validate credentials"
            )

        # Check if user is active (e.g., email confirmed in Supabase)
        # Adjust this check based on your definition of "active"
        if not current_user.email_confirmed_at:
            raise HTTPException(status_code=403, detail="Email not verified")

        return current_user

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error validating active user: {str(e)}")
        # Ensure we return a 401 or appropriate error if activation check fails
        raise HTTPException(status_code=401, detail="User validation failed")


async def get_project_stats(project_id: str, user_id: str) -> Dict[str, int]:
    """Get statistics for a project including chapter count and word count."""
    try:
        async with db_instance.Session() as session:
            # Get chapters using SQLAlchemy
            query = select(Chapter).where(
                and_(Chapter.project_id == project_id, Chapter.user_id == user_id)
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

            return {"chapter_count": chapter_count, "word_count": word_count}
    except Exception as e:
        logger.error(f"Error getting project stats: {str(e)}")
        raise


async def get_universe_stats(universe_id: str, user_id: str) -> Dict[str, int]:
    """Get statistics for a universe including project count and total entries."""
    try:
        async with db_instance.Session() as session:
            # Get project count
            project_query = select(Project).where(
                and_(Project.universe_id == universe_id, Project.user_id == user_id)
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
                        CodexItem.user_id == user_id,
                    )
                )
                result = await session.execute(codex_query)
                codex_items = result.scalars().all()
                codex_count = len(codex_items)

            return {"project_count": project_count, "entry_count": codex_count}
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
codex_router = APIRouter(
    prefix="/codex", tags=["Codex"]
)  # Keep if distinct from codex_item_router
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
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Assuming db_instance method exists and is correct
        updated_project = await db_instance.update_project(
            project_id=project_id,
            name=None,
            description=None,  # Only updating target word count
            user_id=current_user.id,
            universe_id=None,
            target_word_count=update_data.targetWordCount,
        )
        if not updated_project:
            raise HTTPException(status_code=404, detail="Project not found")
        return updated_project
    except Exception as e:
        logger.error(
            f"Error updating project target word count: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@project_router.post("/{project_id}/refresh-knowledge-base")
async def refresh_project_knowledge_base(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    logger.info(f"Starting knowledge base refresh for project {project_id}")
    added_count = 0
    skipped_count = 0
    error_count = 0

    try:
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:

            logger.info("Resetting knowledge base via AgentManager...")
            restored_item_keys = (
                await agent_manager.reset_knowledge_base()
            )  # Returns set of keys
            restored_count = len(restored_item_keys)
            logger.info(f"Restored {restored_count} items from backup.")

            logger.info("Fetching current project data from database...")
            chapters = await db_instance.get_all_chapters(current_user.id, project_id)
            codex_items = await db_instance.get_all_codex_items(
                current_user.id, project_id
            )
            # Fetch other potentially indexed items if needed (relationships, etc.)
            relationships = await db_instance.get_character_relationships(
                project_id, current_user.id
            )
            events = await db_instance.get_events(project_id, current_user.id)
            locations = await db_instance.get_locations(current_user.id, project_id)

            logger.info(f"Re-indexing items not restored from backup...")

            # Re-index Chapters
            for chapter in chapters:
                item_key = f"chapter_{chapter['id']}"
                if item_key not in restored_item_keys:
                    try:
                        metadata = {
                            "id": chapter["id"],  # Use DB ID
                            "title": chapter["title"],
                            "type": "chapter",
                            "chapter_number": chapter.get("chapter_number"),
                        }
                        embedding_id = await agent_manager.add_to_knowledge_base(
                            "chapter", chapter["content"], metadata
                        )
                        if embedding_id:
                            await db_instance.update_chapter_embedding_id(
                                chapter["id"], embedding_id
                            )
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
                item_key = f"{item['type']}_{item['id']}"  # Key based on type and ID
                if item_key not in restored_item_keys:
                    try:
                        metadata = {
                            "id": item["id"],  # Use DB ID
                            "name": item["name"],
                            "type": item["type"],
                            "subtype": item.get("subtype"),
                        }
                        embedding_id = await agent_manager.add_to_knowledge_base(
                            item["type"], item["description"], metadata
                        )
                        if embedding_id:
                            await db_instance.update_codex_item_embedding_id(
                                item["id"], embedding_id
                            )
                            added_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        logger.error(
                            f"Error re-indexing codex item {item['id']} ({item['type']}): {e}"
                        )
                        error_count += 1
                else:
                    skipped_count += 1

                # Handle character backstories separately if stored in KB
                if item["type"] == CodexItemType.CHARACTER.value and item.get(
                    "backstory"
                ):
                    backstory_key = f"character_backstory_{item['id']}"
                    if backstory_key not in restored_item_keys:
                        try:
                            backstory_metadata = {
                                "id": item[
                                    "id"
                                ],  # Use character ID as ID for backstory? Or generate new? Check VS schema.
                                "type": "character_backstory",
                                "character_id": item["id"],
                            }
                            await agent_manager.add_to_knowledge_base(
                                "character_backstory",
                                item["backstory"],
                                backstory_metadata,
                            )
                            added_count += 1
                            # No separate embedding ID in DB for backstory currently
                        except Exception as e:
                            logger.error(
                                f"Error re-indexing backstory for char {item['id']}: {e}"
                            )
                            error_count += 1
                    else:
                        skipped_count += 1  # Count skipped backstories too

            # TODO: Add similar loops for Relationships, Events, Locations, Connections if they are indexed

            total_items = (
                restored_count + added_count + skipped_count
            )  # Check this logic
            logger.info(
                f"Knowledge base refresh complete. Restored: {restored_count}, Added: {added_count}, Skipped (already restored): {skipped_count}, Errors: {error_count}, Total in KB: {total_items}"
            )

            return {
                "status": "success",
                "restored_from_backup": restored_count,
                "added_from_db": added_count,
                "skipped_duplicates": skipped_count,
                "errors": error_count,
                "total_in_kb": total_items,  # Approximate final count
            }

    except Exception as e:
        logger.error(
            f"Error refreshing knowledge base for project {project_id}: {str(e)}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Failed to refresh knowledge base",
                "details": str(e),
            },
        )


# Universe routes
@universe_router.post("/", response_model=Dict[str, Any])
async def create_universe(
    universe: UniverseCreate, current_user: User = Depends(get_current_active_user)
):
    try:
        universe_id = await db_instance.create_universe(universe.name, current_user.id)
        return {"id": universe_id, "name": universe.name}
    except Exception as e:
        logger.error(f"Error creating universe: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@universe_router.get("/{universe_id}", response_model=Dict[str, Any])
async def get_universe(
    universe_id: str, current_user: User = Depends(get_current_active_user)
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
async def update_universe(
    universe_id: str,
    universe: UniverseUpdate,
    current_user: User = Depends(get_current_active_user),
):
    try:
        updated_universe = await db_instance.update_universe(
            universe_id, universe.name, current_user.id
        )
        if not updated_universe:
            raise HTTPException(status_code=404, detail="Universe not found")
        return JSONResponse(content=updated_universe)
    except Exception as e:
        logger.error(f"Error updating universe: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@universe_router.delete("/{universe_id}", response_model=bool)
async def delete_universe(
    universe_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        success = await db_instance.delete_universe(universe_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Universe not found")
        return JSONResponse(content={"success": success})
    except Exception as e:
        logger.error(f"Error deleting universe: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@universe_router.get("/{universe_id}/codex", response_model=List[Dict[str, Any]])
async def get_universe_codex(
    universe_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        codex_items = await db_instance.get_universe_codex(universe_id, current_user.id)
        return JSONResponse(content=codex_items)
    except Exception as e:
        logger.error(f"Error fetching universe codex: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@universe_router.get(
    "/{universe_id}/knowledge-base", response_model=List[Dict[str, Any]]
)
async def get_universe_knowledge_base(
    universe_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        knowledge_base_items = await db_instance.get_universe_knowledge_base(
            universe_id, current_user.id
        )
        return JSONResponse(content=knowledge_base_items)
    except Exception as e:
        logger.error(f"Error fetching universe knowledge base: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@universe_router.get("/{universe_id}/projects", response_model=List[Dict[str, Any]])
async def get_projects_by_universe(
    universe_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        projects = await db_instance.get_projects_by_universe(
            universe_id, current_user.id
        )
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
            stats = await get_universe_stats(universe["id"], current_user.id)
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

        # Register using database method (which now handles Supabase interaction implicitly or explicitly)
        # Ensure db_instance.sign_up creates both Supabase user and local user record
        user_response = await db_instance.sign_up(
            email=user.email, password=user.password, supabase_id=user.supabase_id # Pass supabase_id if available from client
        )

        if not user_response or not user_response.get('id'):
            logger.error("Registration failed: No user response or ID")
            raise HTTPException(status_code=400, detail="Registration failed")

        logger.info(f"Registration successful for user ID: {user_response['id']}")
        # Return only success message, no tokens or session IDs here. Client should sign in separately.
        return {
            "message": "User registered successfully. Please sign in.",
            "user_id": user_response["id"],
        }
    except HTTPException as he:
        raise he # Re-raise specific HTTP exceptions (like 400 for existing user)
    except Exception as e:
        logger.error(f"Registration error: {str(e)}", exc_info=True)
        # Provide a more generic error message to the client
        raise HTTPException(status_code=500, detail="Registration failed due to an internal error.")


# --- Removed /auth/extend-session endpoint ---


@auth_router.post("/signin")
async def sign_in(
    credentials: Dict[str, str] = Body(
        ..., example={"email": "user@example.com", "password": "password"}
    )
):
    try:
        email = credentials.get("email")
        password = credentials.get("password")
        if not email or not password:
            raise HTTPException(
                status_code=400, detail="Email and password are required"
            )

        try:
            # db_instance.sign_in should interact with Supabase
            auth_result = await db_instance.sign_in(
                email=email, password=password
            )

            if not auth_result or not auth_result.get("user") or not auth_result.get("session"):
                raise HTTPException(status_code=401, detail="Invalid credentials")

            # --- Removed custom session creation ---

            # Return Supabase access token and user info
            return {
                "access_token": auth_result["session"].access_token,
                # Optionally return refresh token if client needs to handle refresh:
                # "refresh_token": auth_result["session"].refresh_token,
                "user": {
                    "id": auth_result["user"].id,
                    "email": auth_result["user"].email,
                    # Add any other relevant user details needed by the client
                },
            }

        except HTTPException:
            # Re-raise 401 if db_instance.sign_in raises it
            raise
        except Exception as e:
            # Catch potential errors from Supabase client interaction
            logger.error(f"Supabase sign-in error: {str(e)}", exc_info=True)
            # Map common Supabase errors to HTTP 401
            if "Invalid login credentials" in str(e):
                 raise HTTPException(status_code=401, detail="Invalid credentials")
            raise HTTPException(status_code=500, detail="Authentication failed due to an internal error.")

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Sign in endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during sign in.")


@auth_router.post("/signout")
async def sign_out(
    # Depends on get_current_user to ensure a valid token is provided for sign-out
    current_user: User = Depends(get_current_user),
    authorization: str = Header(None), # Need the token to sign out from Supabase
):
    try:
        if not authorization or not authorization.startswith("Bearer "):
             raise HTTPException(
                status_code=401, detail="Valid Authorization header required for sign out."
            )
        token = authorization.replace("Bearer ", "")

        # --- Removed custom session removal ---

        # Sign out from Supabase using the provided token
        # Note: Supabase sign_out might be synchronous depending on the library version
        try:
            # Pass the JWT to sign out the specific session
            await db_instance.supabase.auth.sign_out(token)
            logger.info(f"User {current_user.email} signed out from Supabase.")
        except Exception as e:
            logger.error(f"Supabase sign out error: {str(e)}", exc_info=True)
            # Even if Supabase signout fails, proceed, but log the error.
            # Client should still discard the token.
            # Consider if a 500 error is appropriate here. Maybe just log and return success.
            # For now, let's return success but log the error.

        # No custom session to remove

        return {"message": "Successfully signed out"}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Sign out endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred during sign out")


# --- Chapter Routes ---


@chapter_router.post("/generate")
async def generate_chapters(
    request: Request,  # Keep raw request to parse JSON manually
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Parse JSON body
        body = await request.json()
        gen_request = ChapterGenerationRequest.model_validate(
            body
        )  # Validate using Pydantic

        chapter_count = await db_instance.get_chapter_count(project_id, current_user.id)
        generated_chapters_details = []  # Store details of generated chapters

        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            for i in range(gen_request.numChapters):
                chapter_number = chapter_count + i + 1
                logger.info(f"Initiating generation for Chapter {chapter_number}...")

                # Call the AgentManager's graph-based generation method
                result = await agent_manager.generate_chapter(
                    chapter_number=chapter_number,
                    plot=gen_request.plot,
                    writing_style=gen_request.writingStyle, # Use camelCase
                    instructions=gen_request.instructions,
                )

                # Check for errors returned by the graph
                if result.get("error"):
                    logger.error(
                        f"Chapter {chapter_number} generation failed: {result['error']}"
                    )
                    # Decide how to handle partial failures (e.g., stop, continue, return error info)
                    # For now, let's add error info and continue
                    generated_chapters_details.append(
                        {
                            "chapter_number": chapter_number,
                            "status": "failed",
                            "error": result["error"],
                        }
                    )
                    continue  # Skip saving/indexing for this chapter

                # --- Process Successful Generation ---
                chapter_content = result.get("content")
                chapter_title = result.get("chapter_title")
                new_codex_items = result.get("new_codex_items", [])
                validity_check = result.get("validity_check")

                if not chapter_content or not chapter_title:
                    logger.error(
                        f"Chapter {chapter_number} generation result missing content or title."
                    )
                    generated_chapters_details.append(
                        {
                            "chapter_number": chapter_number,
                            "status": "failed",
                            "error": "Missing content or title in generation result.",
                        }
                    )
                    continue

                # 1. Save Chapter to DB
                new_chapter_db = await db_instance.create_chapter(
                    title=chapter_title,
                    content=chapter_content,
                    project_id=project_id,
                    user_id=current_user.id,
                    # chapter_number is handled by create_chapter
                )
                chapter_id = new_chapter_db["id"]
                actual_chapter_number = new_chapter_db[
                    "chapter_number"
                ]  # Get actual number from DB

                # 2. Add Chapter to Knowledge Base
                chapter_metadata = {
                    "id": chapter_id,
                    "title": chapter_title,
                    "type": "chapter",
                    "chapter_number": actual_chapter_number,
                }
                embedding_id = await agent_manager.add_to_knowledge_base(
                    "chapter", chapter_content, chapter_metadata
                )
                if embedding_id:
                    await db_instance.update_chapter_embedding_id(
                        chapter_id, embedding_id
                    )
                else:
                    logger.warning(
                        f"Failed to add chapter {chapter_id} to knowledge base."
                    )

                # 3. Save Validity Feedback
                if validity_check and not validity_check.get("error"):
                    try:
                        await agent_manager.save_validity_feedback(
                            result=validity_check,
                            chapter_number=actual_chapter_number,
                            chapter_id=chapter_id,
                        )
                    except Exception as vf_error:
                        logger.error(
                            f"Failed to save validity feedback for chapter {chapter_id}: {vf_error}"
                        )
                        # Non-critical error

                # 4. Process and Save New Codex Items
                saved_codex_items_info = []
                if new_codex_items:
                    logger.info(
                        f"Processing {len(new_codex_items)} new codex items for chapter {actual_chapter_number}."
                    )
                    for item in new_codex_items:
                        try:
                            item_id_db = await db_instance.create_codex_item(
                                name=item["name"],
                                description=item["description"],
                                type=item["type"],  # Assumes validated type string
                                subtype=item.get(
                                    "subtype"
                                ),  # Assumes validated subtype string or None
                                user_id=current_user.id,
                                project_id=project_id,
                            )
                            codex_metadata = {
                                "id": item_id_db,
                                "name": item["name"],
                                "type": item["type"],
                                "subtype": item.get("subtype"),
                            }
                            codex_embedding_id = (
                                await agent_manager.add_to_knowledge_base(
                                    item["type"], item["description"], codex_metadata
                                )
                            )
                            if codex_embedding_id:
                                await db_instance.update_codex_item_embedding_id(
                                    item_id_db, codex_embedding_id
                                )
                                saved_codex_items_info.append(
                                    {
                                        "id": item_id_db,
                                        "name": item["name"],
                                        "type": item["type"],
                                    }
                                )
                            else:
                                logger.warning(
                                    f"Failed to add codex item '{item['name']}' to knowledge base."
                                )
                        except Exception as ci_error:
                            logger.error(
                                f"Failed to process/save codex item '{item.get('name', 'UNKNOWN')}': {ci_error}",
                                exc_info=True,
                            )

                generated_chapters_details.append(
                    {
                        "chapter_number": actual_chapter_number,
                        "id": chapter_id,
                        "title": chapter_title,
                        "status": "success",
                        "embedding_id": embedding_id,
                        "new_codex_items_saved": saved_codex_items_info,
                        "validity_saved": bool(
                            validity_check and not validity_check.get("error")
                        ),
                        "word_count": result.get(
                            "word_count", len(chapter_content.split())
                        ),
                    }
                )
                logger.info(
                    f"Successfully processed generated Chapter {actual_chapter_number}."
                )

            # Update overall project chapter count after loop if needed
            # chapter_count = await db_instance.get_chapter_count(project_id, current_user.id)

            return {"generation_results": generated_chapters_details}

    except ValidationError as e:
        logger.error(f"Chapter generation request validation error: {e}", exc_info=True)
        raise HTTPException(status_code=422, detail=e.errors())
    except Exception as e:
        logger.error(
            f"Error during chapter generation process: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@chapter_router.get("/{chapter_id}")
async def get_chapter(
    chapter_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    # Only check project ownership
    project = await db_instance.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this project"
        )
    try:
        chapter = await db_instance.get_chapter(chapter_id, current_user.id, project_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        return chapter
    except Exception as e:
        logger.error(f"Error fetching chapter: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@chapter_router.get("/")
async def get_chapters(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        chapters = await db_instance.get_all_chapters(current_user.id, project_id)
        return {"chapters": chapters}
    except Exception as e:
        logger.error(f"Error fetching chapters: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@chapter_router.post("/")
async def create_chapter(
    chapter: ChapterCreate,
    project_id: str,  # Get project_id from path
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Create chapter in DB first
        new_chapter = await db_instance.create_chapter(
            title=chapter.title,
            content=chapter.content,
            project_id=project_id,
            user_id=current_user.id,
        )
        chapter_id = new_chapter["id"]
        embedding_id = None
        kb_error = None

        # Add to knowledge base
        try:
            async with agent_manager_store.get_or_create_manager(
                current_user.id, project_id
            ) as agent_manager:
                metadata = {
                    "id": chapter_id,
                    "title": chapter.title,
                    "type": "chapter",
                    "chapter_number": new_chapter.get("chapter_number"),
                }
                embedding_id = await agent_manager.add_to_knowledge_base(
                    "chapter", chapter.content, metadata
                )

            if embedding_id:
                await db_instance.update_chapter_embedding_id(chapter_id, embedding_id)
            else:
                kb_error = "Failed to add chapter to knowledge base."
                logger.warning(kb_error)
        except Exception as kb_e:
            kb_error = f"Error adding chapter to knowledge base: {kb_e}"
            logger.error(kb_error, exc_info=True)

        response_data = {
            "message": "Chapter created successfully"
            + (f" (Warning: {kb_error})" if kb_error else ""),
            "chapter": new_chapter,
            "embedding_id": embedding_id,
        }
        status_code = 201 if not kb_error else 207  # Multi-Status if KB failed

        return JSONResponse(content=response_data, status_code=status_code)

    except Exception as e:
        logger.error(f"Error creating chapter: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating chapter: {str(e)}")


@chapter_router.put("/{chapter_id}")
async def update_chapter(
    chapter_id: str,
    chapter_update: ChapterUpdate,
    project_id: str,  # Get project_id from path
    current_user: User = Depends(get_current_active_user),
):
    kb_error = None
    updated_chapter = None
    try:
        # 1. Get existing chapter to find embedding_id
        existing_chapter = await db_instance.get_chapter(
            chapter_id, current_user.id, project_id
        )
        if not existing_chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        existing_embedding_id = existing_chapter.get("embedding_id")

        # 2. Update DB
        updated_chapter = await db_instance.update_chapter(
            chapter_id=chapter_id,
            title=chapter_update.title,
            content=chapter_update.content,
            user_id=current_user.id,
            project_id=project_id,
        )

        # 3. Update Knowledge Base
        if existing_embedding_id:
            try:
                async with agent_manager_store.get_or_create_manager(
                    current_user.id, project_id
                ) as agent_manager:
                    metadata = {
                        "id": chapter_id,
                        "title": chapter_update.title,
                        "type": "chapter",
                        "chapter_number": updated_chapter.get(
                            "chapter_number"
                        ),  # Get potentially updated number
                    }
                    await agent_manager.update_or_remove_from_knowledge_base(
                        existing_embedding_id,
                        "update",
                        new_content=chapter_update.content,
                        new_metadata=metadata,
                    )
            except Exception as kb_e:
                kb_error = f"Failed to update chapter in knowledge base: {kb_e}"
                logger.error(kb_error, exc_info=True)
        else:
            kb_error = "Chapter was not found in knowledge base (no embedding ID). KB not updated."
            logger.warning(kb_error)

        response_data = {
            "message": "Chapter updated successfully"
            + (f" (Warning: {kb_error})" if kb_error else ""),
            "chapter": updated_chapter,
        }
        status_code = 200 if not kb_error else 207

        return JSONResponse(content=response_data, status_code=status_code)

    except HTTPException:
        raise  # Re-raise 404 etc.
    except Exception as e:
        logger.error(f"Error updating chapter {chapter_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@chapter_router.delete("/{chapter_id}")
async def delete_chapter(
    chapter_id: str,
    project_id: str,  # Get project_id from path
    current_user: User = Depends(get_current_active_user),
):
    kb_error = None
    try:
        # 1. Get existing chapter for embedding_id
        chapter = await db_instance.get_chapter(chapter_id, current_user.id, project_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        embedding_id = chapter.get("embedding_id")

        # 2. Delete from Knowledge Base first
        if embedding_id:
            try:
                async with agent_manager_store.get_or_create_manager(
                    current_user.id, project_id
                ) as agent_manager:
                    await agent_manager.update_or_remove_from_knowledge_base(
                        embedding_id, "delete"
                    )
            except Exception as kb_e:
                # Log error but proceed with DB deletion
                kb_error = f"Failed to delete chapter from knowledge base: {kb_e}"
                logger.error(kb_error, exc_info=True)
        else:
            logger.warning(
                f"No embedding ID found for chapter {chapter_id}. Skipping KB deletion."
            )

        # 3. Delete from Database
        success = await db_instance.delete_chapter(
            chapter_id, current_user.id, project_id
        )
        if not success:
            # This indicates a potential race condition or logic error if chapter was found initially
            raise HTTPException(
                status_code=500,
                detail="Failed to delete chapter from database after finding it.",
            )

        message = "Chapter deleted successfully" + (
            f" (Warning: {kb_error})" if kb_error else ""
        )
        return {"message": message}

    except HTTPException:
        raise  # Re-raise 404
    except Exception as e:
        logger.error(f"Error deleting chapter {chapter_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# --- Codex Routes ---


@codex_router.post("/generate", response_model=Dict[str, Any])
async def generate_codex_item(
    request: CodexItemGenerateRequest,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    embedding_id = None
    kb_error = None
    item_id_db = None
    generated_item = None

    try:
        # Validate type/subtype (optional, can be done in AgentManager too)
        try:
            _ = CodexItemType(request.codex_type)
            if request.subtype:
                _ = WorldbuildingSubtype(request.subtype)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Invalid type or subtype: {e}")

        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            # 1. Generate Item Details
            generated_item = await agent_manager.generate_codex_item(
                request.codex_type, request.subtype, request.description
            )
            if (
                generated_item.get("name") == "Error"
            ):  # Check for error marker from agent
                raise HTTPException(
                    status_code=500,
                    detail=f"Codex generation failed: {generated_item.get('description')}",
                )

            # 2. Save to Database
            item_id_db = await db_instance.create_codex_item(
                name=generated_item["name"],
                description=generated_item["description"],
                type=request.codex_type,  # Use validated type
                subtype=request.subtype,  # Use validated subtype
                user_id=current_user.id,
                project_id=project_id,
            )

            # 3. Add to Knowledge Base
            try:
                metadata = {
                    "id": item_id_db,
                    "name": generated_item["name"],
                    "type": request.codex_type,
                    "subtype": request.subtype,
                }
                embedding_id = await agent_manager.add_to_knowledge_base(
                    request.codex_type, generated_item["description"], metadata
                )
                if embedding_id:
                    await db_instance.update_codex_item_embedding_id(
                        item_id_db, embedding_id
                    )
                else:
                    kb_error = "Failed to add generated codex item to knowledge base."
                    logger.warning(kb_error)
            except Exception as kb_e:
                kb_error = (
                    f"Error adding generated codex item to knowledge base: {kb_e}"
                )
                logger.error(kb_error, exc_info=True)

        response_data = {
            "message": "Codex item generated and saved successfully"
            + (f" (Warning: {kb_error})" if kb_error else ""),
            "item": generated_item,
            "id": item_id_db,
            "embedding_id": embedding_id,
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
async def get_characters(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        characters = await db_instance.get_all_codex_items(current_user.id, project_id)
        # Filter only character type items
        characters = [item for item in characters if item["type"] == "character"]
        return {"characters": characters}
    except Exception as e:
        logger.error(f"Error fetching characters: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@codex_item_router.get(
    "/"
)  # , response_model=Dict[str, List[Dict[str, Any]]]) # Response model needs adjustment if DB returns objects
async def get_codex_items(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        codex_items = await db_instance.get_all_codex_items(current_user.id, project_id)
        # Convert DB models to dicts if needed, or ensure db method returns dicts
        return {"codex_items": codex_items}
    except Exception as e:
        logger.error(f"Error fetching codex items: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@codex_item_router.post("/")  # , response_model=Dict[str, Any])
async def create_codex_item(
    codex_item: CodexItemCreate,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    embedding_id = None
    kb_error = None
    item_id_db = None
    try:
        # Validate type/subtype
        try:
            _ = CodexItemType(codex_item.type)
            if codex_item.subtype:
                _ = WorldbuildingSubtype(codex_item.subtype)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Invalid type or subtype: {e}")

        # 1. Create in DB
        item_id_db = await db_instance.create_codex_item(
            codex_item.name,
            codex_item.description,
            codex_item.type,
            codex_item.subtype,
            current_user.id,
            project_id,
        )

        # 2. Add to Knowledge Base
        try:
            async with agent_manager_store.get_or_create_manager(
                current_user.id, project_id
            ) as agent_manager:
                metadata = {
                    "id": item_id_db,
                    "name": codex_item.name,
                    "type": codex_item.type,
                    "subtype": codex_item.subtype,
                }
                embedding_id = await agent_manager.add_to_knowledge_base(
                    codex_item.type, codex_item.description, metadata
                )
                if embedding_id:
                    await db_instance.update_codex_item_embedding_id(
                        item_id_db, embedding_id
                    )
                else:
                    kb_error = "Failed to add codex item to knowledge base."
                    logger.warning(kb_error)
        except Exception as kb_e:
            kb_error = f"Error adding codex item to knowledge base: {kb_e}"
            logger.error(kb_error, exc_info=True)

        response_data = {
            "message": "Codex item created successfully"
            + (f" (Warning: {kb_error})" if kb_error else ""),
            "id": item_id_db,
            "embedding_id": embedding_id,
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
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    kb_error = None
    updated_item_db = None
    try:
        # Validate type/subtype
        try:
            _ = CodexItemType(codex_item_update.type)
            if codex_item_update.subtype:
                _ = WorldbuildingSubtype(codex_item_update.subtype)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Invalid type or subtype: {e}")

        # 1. Get existing item for embedding_id
        existing_item = await db_instance.get_codex_item_by_id(
            item_id, current_user.id, project_id
        )
        if not existing_item:
            raise HTTPException(status_code=404, detail="Codex item not found")
        existing_embedding_id = existing_item.get("embedding_id")

        # 2. Update DB
        updated_item_db = await db_instance.update_codex_item(
            item_id=item_id,
            name=codex_item_update.name,
            description=codex_item_update.description,
            type=codex_item_update.type,
            subtype=codex_item_update.subtype,
            user_id=current_user.id,
            project_id=project_id,
        )

        # 3. Update Knowledge Base
        if existing_embedding_id:
            try:
                async with agent_manager_store.get_or_create_manager(
                    current_user.id, project_id
                ) as agent_manager:
                    metadata = {
                        "id": item_id,
                        "name": codex_item_update.name,
                        "type": codex_item_update.type,
                        "subtype": codex_item_update.subtype,
                    }
                    await agent_manager.update_or_remove_from_knowledge_base(
                        existing_embedding_id,
                        "update",
                        new_content=codex_item_update.description,
                        new_metadata=metadata,
                    )
            except Exception as kb_e:
                kb_error = f"Failed to update codex item in knowledge base: {kb_e}"
                logger.error(kb_error, exc_info=True)
        else:
            # Option: Try to add it if missing? Or just warn.
            kb_error = "Codex item was not found in knowledge base (no embedding ID). KB not updated."
            logger.warning(kb_error)

        response_data = {
            "message": "Codex item updated successfully"
            + (f" (Warning: {kb_error})" if kb_error else ""),
            "item": updated_item_db,  # Return updated DB data
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
    item_id: str, project_id: str, current_user: User = Depends(get_current_active_user)
):
    kb_error = None
    try:
        # 1. Get existing item for embedding_id
        codex_item = await db_instance.get_codex_item_by_id(
            item_id, current_user.id, project_id
        )
        if not codex_item:
            raise HTTPException(status_code=404, detail="Codex item not found")
        embedding_id = codex_item.get("embedding_id")
        item_type = codex_item.get(
            "type"
        )  # Needed if using dict identifier for KB delete

        # 2. Delete from Knowledge Base first
        if embedding_id:
            try:
                async with agent_manager_store.get_or_create_manager(
                    current_user.id, project_id
                ) as agent_manager:
                    # Use embedding ID directly if available
                    await agent_manager.update_or_remove_from_knowledge_base(
                        embedding_id, "delete"
                    )
                    # Also delete backstory if it's a character
                    if item_type == CodexItemType.CHARACTER.value:
                        await agent_manager.update_or_remove_from_knowledge_base(
                            {"item_id": item_id, "item_type": "character_backstory"},
                            "delete",
                        )
            except Exception as kb_e:
                kb_error = f"Failed to delete codex item from knowledge base: {kb_e}"
                logger.error(kb_error, exc_info=True)
        else:
            logger.warning(
                f"No embedding ID found for codex item {item_id}. Skipping KB deletion."
            )

        # 3. Delete from Database
        deleted = await db_instance.delete_codex_item(
            item_id, current_user.id, project_id
        )
        if not deleted:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete codex item from database after finding it.",
            )

        message = "Codex item deleted successfully" + (
            f" (Warning: {kb_error})" if kb_error else ""
        )
        return {"message": message}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting codex item {item_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# --- Backstory & Relationship Analysis Routes ---


@codex_router.post("/characters/{character_id}/extract-backstory")
async def extract_character_backstory_endpoint(  # Renamed endpoint function
    character_id: str,
    project_id: str,  # project_id from path
    # request: BackstoryExtractionRequest, # No longer needed, agent method handles finding chapters
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Verify character exists
        character = await db_instance.get_characters(
            current_user.id, project_id, character_id=character_id
        )
        if not character or character["type"] != CodexItemType.CHARACTER.value:
            raise HTTPException(status_code=404, detail="Character not found")

        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            # Agent method now handles finding unprocessed chapters and saving/adding KB
            backstory_result = await agent_manager.extract_character_backstory(
                character_id
            )

        if backstory_result is None:
            # Agent manager might return None if character check failed internally
            raise HTTPException(
                status_code=404,
                detail="Character not found during backstory extraction.",
            )

        if backstory_result.new_backstory:
            return {
                "message": "Backstory extracted and updated.",
                "new_backstory_summary": backstory_result.new_backstory,
            }
        else:
            # Check if this means "no new info found" vs "error" based on agent impl.
            return {
                "message": "No new backstory information found in unprocessed chapters.",
                "already_processed": True,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error in extract character backstory endpoint for char {character_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Backstory PUT/DELETE remain the same, ensure they update/delete from KB via AgentManager


@codex_item_router.put("/characters/{character_id}/backstory")
async def update_backstory(
    character_id: str,
    project_id: str,
    backstory_content: str = Body(..., embed=True),  # Embed content in request body
    current_user: User = Depends(get_current_active_user),
):
    kb_error = None
    try:
        # 1. Update DB (assuming method exists)
        await db_instance.update_character_backstory(
            character_id, backstory_content, current_user.id, project_id
        )

        # 2. Update/Add KB
        try:
            async with agent_manager_store.get_or_create_manager(
                current_user.id, project_id
            ) as agent_manager:
                # Use update_or_remove, treating it as an upsert for backstory potentially
                # Assumes backstory KB items use character_id and type identifier
                identifier = {
                    "item_id": character_id,
                    "item_type": "character_backstory",
                }
                metadata = {
                    "type": "character_backstory",
                    "character_id": character_id,
                    "id": character_id,  # Assuming backstory uses char ID as primary ID in KB
                }
                await agent_manager.update_or_remove_from_knowledge_base(
                    identifier,
                    "update",
                    new_content=backstory_content,
                    new_metadata=metadata,
                )
        except Exception as kb_e:
            kb_error = f"Failed to update backstory in knowledge base: {kb_e}"
            logger.error(kb_error, exc_info=True)

        message = "Backstory updated successfully" + (
            f" (Warning: {kb_error})" if kb_error else ""
        )
        return {"message": message}

    except Exception as e:
        logger.error(
            f"Error updating backstory for char {character_id}: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@codex_item_router.delete("/characters/{character_id}/backstory")
async def delete_backstory(
    character_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    kb_error = None
    try:
        # 1. Delete from KB first
        try:
            async with agent_manager_store.get_or_create_manager(
                current_user.id, project_id
            ) as agent_manager:
                identifier = {
                    "item_id": character_id,
                    "item_type": "character_backstory",
                }
                await agent_manager.update_or_remove_from_knowledge_base(
                    identifier, "delete"
                )
        except Exception as kb_e:
            kb_error = f"Failed to delete backstory from knowledge base: {kb_e}"
            logger.error(kb_error, exc_info=True)

        # 2. Delete from DB (set backstory field to None)
        await db_instance.delete_character_backstory(
            character_id, current_user.id, project_id
        )

        message = "Backstory deleted successfully" + (
            f" (Warning: {kb_error})" if kb_error else ""
        )
        return {"message": message}

    except Exception as e:
        logger.error(
            f"Error deleting backstory for char {character_id}: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@relationship_router.post("/analyze")
async def analyze_relationships(
    project_id: str,
    character_ids: List[str] = Body(...),
    current_user: User = Depends(get_current_active_user),
):
    try:
        if len(character_ids) < 2:
            raise HTTPException(
                status_code=400,
                detail="At least two character IDs are required for analysis.",
            )

        # Fetch character data from DB
        characters = []
        for char_id in character_ids:
            character = await db_instance.get_characters(
                current_user.id, project_id, character_id=char_id
            )
            if character and character["type"] == CodexItemType.CHARACTER.value:
                characters.append(character)

        if len(characters) < 2:
            raise HTTPException(
                status_code=404,
                detail="Fewer than two valid characters found for the provided IDs.",
            )

        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            # Agent method now saves to DB and adds to KB
            relationships_analysis = (
                await agent_manager.analyze_character_relationships(characters)
            )

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
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        # Check if unprocessed chapters exist *before* getting manager? Maybe not necessary.
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            # Agent method now handles checking unprocessed, saving DB, adding KB
            new_locations = await agent_manager.analyze_unprocessed_chapter_locations()

        if not new_locations:
            # This could mean no new locations found OR no chapters to process
            # The agent log should indicate which.
            return {
                "message": "No new locations found or all chapters processed.",
                "locations": [],
            }

        return {"locations": new_locations}  # Returns list of dicts from agent method

    except Exception as e:
        logger.error(
            f"Error analyzing chapter locations endpoint: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@event_router.post("/analyze-chapter")
async def analyze_chapter_events(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            # Agent method handles finding unprocessed, saving DB, adding KB
            new_events = await agent_manager.analyze_unprocessed_chapter_events()

        if not new_events:
            return {
                "message": "No new events found or all chapters processed.",
                "events": [],
            }

        return {"events": new_events}  # Returns list of dicts

    except Exception as e:
        logger.error(
            f"Error analyzing chapter events endpoint: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# --- Connection Analysis Routes ---


@event_router.post("/analyze-connections")
async def analyze_event_connections_endpoint(  # Renamed
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            # Agent method handles analysis, saving DB, adding KB
            new_connections = await agent_manager.analyze_event_connections()

        return {"event_connections": [conn.model_dump() for conn in new_connections]}

    except Exception as e:
        logger.error(
            f"Error analyzing event connections endpoint: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@location_router.post("/analyze-connections")
async def analyze_location_connections_endpoint(  # Renamed
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        # Check if enough locations exist first
        locations = await db_instance.get_locations(current_user.id, project_id)
        if len(locations) < 2:
            return {
                "message": "Not enough locations exist to analyze connections.",
                "location_connections": [],
            }

        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            # Agent method handles analysis, saving DB, adding KB
            new_connections = await agent_manager.analyze_location_connections()

        return {"location_connections": [conn.model_dump() for conn in new_connections]}

    except Exception as e:
        logger.error(
            f"Error analyzing location connections endpoint: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# --- Knowledge Base Routes ---


# POST /knowledge-base/ - Needs review, depends on how AgentManager handles file vs text
@knowledge_base_router.post("/")
async def add_to_knowledge_base(
    project_id: str,
    content_type: str = Form(...),  # Require content type
    text_content: Optional[str] = Form(None),
    metadata_str: str = Form("{}"),  # Default to empty JSON object string
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_user),
):
    content_to_add = None
    source_info = "text input"

    if file:
        source_info = f"file: {file.filename}"
        file_content_bytes = await file.read()
        # Basic text extraction, enhance as needed (like the /documents/extract endpoint)
        try:
            if file.filename.lower().endswith(".txt"):
                content_to_add = file_content_bytes.decode("utf-8")
            # Add more robust extraction for PDF, DOCX here if needed
            else:
                # Try decoding as utf-8 as a fallback
                content_to_add = file_content_bytes.decode("utf-8", errors="ignore")
                if not content_to_add:
                    raise HTTPException(
                        status_code=400,
                        detail="Could not decode file content as text. Only UTF-8 text files supported directly, or use /documents/extract for PDF/DOCX.",
                    )
        except Exception as decode_err:
            raise HTTPException(
                status_code=400,
                detail=f"Error processing file {file.filename}: {decode_err}",
            )
    elif text_content:
        content_to_add = text_content
    else:
        raise HTTPException(
            status_code=400, detail="No content provided (either text_content or file)."
        )

    try:
        metadata = json.loads(metadata_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in metadata_str.")

    # Add source info to metadata
    metadata["source_info"] = source_info
    if file:
        metadata["filename"] = file.filename

    embedding_id = None
    kb_error = None
    try:
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            # Use the provided content_type
            embedding_id = await agent_manager.add_to_knowledge_base(
                content_type, content_to_add, metadata
            )
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
        "content_type": content_type,
    }


@app.post("/documents/extract")
async def extract_document_text(
    file: UploadFile,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        content = await file.read()
        text = ""

        if file.filename.lower().endswith(".pdf"):
            # Try pdfplumber first as it usually gives better results
            try:
                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    text = "\n".join(page.extract_text() for page in pdf.pages)
            except Exception as e:
                # Fallback to PyPDF2 if pdfplumber fails
                logger.warning(f"pdfplumber failed, trying PyPDF2: {str(e)}")
                pdf = PdfReader(io.BytesIO(content))
                text = "\n".join(page.extract_text() for page in pdf.pages)

        elif file.filename.lower().endswith((".doc", ".docx")):
            doc = DocxDocument(io.BytesIO(content))
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Only PDF and DOC/DOCX files are supported.",
            )

        if not text.strip():
            raise HTTPException(
                status_code=422,
                detail="Could not extract text from document. The file might be empty or corrupted.",
            )

        return {"text": text}

    except Exception as e:
        logger.error(f"Error extracting text from document: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error processing document: {str(e)}"
        )


# GET /knowledge-base/ - Calls agent_manager.get_knowledge_base_content()
@knowledge_base_router.get("/")
async def get_knowledge_base_content_endpoint(  # Renamed
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            # Agent manager method gets content directly from vector store
            content = await agent_manager.get_knowledge_base_content()

            # Format for response (if needed, agent method might already format)
            # Example formatting:
            formatted_content = [
                {
                    "embedding_id": item.get("id", item.get("embedding_id")),
                    "content": item.get("page_content"),
                    "metadata": item.get("metadata", {}),
                    # Extract key fields for easier display client-side
                    "type": item.get("metadata", {}).get("type", "Unknown"),
                    "name": item.get("metadata", {}).get(
                        "name", item.get("metadata", {}).get("title")
                    ),
                }
                for item in content
            ]
            return {"content": formatted_content}
    except Exception as e:
        logger.error(
            f"Error getting knowledge base content endpoint: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error")


# PUT /knowledge-base/{embedding_id} - Use agent_manager method
@knowledge_base_router.put("/{embedding_id}")
async def update_knowledge_base_item(
    embedding_id: str,
    project_id: str,
    update_data: Dict[str, Any] = Body(
        ...
    ),  # Expect {'content': '...', 'metadata': {...}}
    current_user: User = Depends(get_current_active_user),
):
    new_content = update_data.get("content")
    new_metadata = update_data.get("metadata")
    if new_content is None and new_metadata is None:
        raise HTTPException(
            status_code=400,
            detail="Must provide 'content' and/or 'metadata' for update.",
        )

    try:
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            # Ensure metadata includes necessary fields if provided
            if new_metadata:
                # Ensure type is preserved or updated correctly if changed
                # existing_item = await agent_manager.vector_store.get_document_by_id(embedding_id) # Need method in VS
                # if existing_item: new_metadata['type'] = existing_item.metadata.get('type')
                pass  # Let agent handle metadata update logic

            await agent_manager.update_or_remove_from_knowledge_base(
                embedding_id,
                "update",
                new_content=new_content,
                new_metadata=new_metadata,
            )
        return {"message": "Knowledge base item updated successfully"}
    except ValueError as ve:  # Catch specific errors like item not found from agent
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(
            f"Error updating knowledge base item {embedding_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# DELETE /knowledge-base/{embedding_id} - Use agent_manager method
@knowledge_base_router.delete("/{embedding_id}")
async def delete_knowledge_base_item(
    embedding_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                embedding_id, "delete"
            )
        return {"message": "Knowledge base item deleted successfully"}
    except ValueError as ve:  # Item not found
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(
            f"Error deleting knowledge base item {embedding_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# POST /knowledge-base/query - Calls agent_manager.query_knowledge_base
@knowledge_base_router.post("/query")
async def query_knowledge_base(
    query_data: KnowledgeBaseQuery,  # Use the existing Pydantic model
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            # chatHistory items are already dicts from the Pydantic model parsing
            chat_history_dicts = query_data.chatHistory
            result = await agent_manager.query_knowledge_base(
                query_data.query, chat_history_dicts
            )
            return {"response": result}
    except Exception as e:
        logger.error(f"Error querying knowledge base: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# POST /knowledge-base/reset-chat-history - Calls agent_manager.reset_memory
@knowledge_base_router.post("/reset-chat-history")
async def reset_chat_history(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        # AgentManager's reset_memory should handle DB deletion
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.reset_memory()
        return {"message": "Chat history reset successfully"}
    except Exception as e:
        logger.error(f"Error resetting chat history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/chat-history")
async def delete_chat_history(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        await db_instance.delete_chat_history(current_user.id, project_id)
        return {"message": "Chat history deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting chat history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/chat-history")
async def save_chat_history(
    chat_history: ChatHistoryRequest,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Convert Pydantic models to dictionaries
        chat_history_dicts = [item.model_dump() for item in chat_history.chatHistory]
        await db_instance.save_chat_history(
            current_user.id, project_id, chat_history_dicts
        )
        return {"message": "Chat history saved successfully"}
    except Exception as e:
        logger.error(f"Error saving chat history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# GET /knowledge-base/chat-history - Calls agent_manager.get_chat_history
@knowledge_base_router.get("/chat-history")
async def get_knowledge_base_chat_history(  # Renamed from app.get route
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            chat_history = await agent_manager.get_chat_history()  # Agent gets from DB
            # Ensure history is a list of dicts (or whatever format client expects)
            validated_history = [
                ChatHistoryItem.model_validate(item).model_dump()
                for item in chat_history
                if isinstance(item, dict)
            ]
            return {"chatHistory": validated_history}
    except Exception as e:
        logger.error(f"Error getting chat history endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving chat history")


# Settings routes
@settings_router.post("/api-key")
async def save_api_key(
    api_key_update: ApiKeyUpdate, current_user: User = Depends(get_current_active_user)
):
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
        masked_key = "*" * (len(api_key) - 4) + api_key[-4:] if is_set else None
        return {"isSet": is_set, "apiKey": masked_key}
    except Exception as e:
        logger.error(f"Error checking API key: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@settings_router.delete("/api-key")
async def remove_api_key(current_user: User = Depends(get_current_active_user)):
    try:
        await api_key_manager.remove_api_key(
            current_user.id
        )  # Updated to call remove_api_key
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
async def save_model_settings(
    settings: ModelSettings, current_user: User = Depends(get_current_active_user)
):
    try:
        await db_instance.save_model_settings(current_user.id, settings.model_dump())
        return {"message": "Model settings saved successfully"}
    except Exception as e:
        logger.error(f"Error saving model settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Preset routes


@preset_router.post("")
async def create_preset(
    preset: PresetCreate,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        preset_id = await db_instance.create_preset(
            current_user.id, project_id, preset.name, preset.data
        )
        return {"id": preset_id, "name": preset.name, "data": preset.data}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error creating preset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@preset_router.get("")
async def get_presets(current_user: User = Depends(get_current_active_user)):
    try:
        # Remove project_id parameter
        presets = await db_instance.get_presets(current_user.id, None)
        return {"presets": presets}
    except Exception as e:
        logger.error(f"Error getting presets: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@preset_router.put("/{preset_name}")
async def update_preset(
    preset_name: str,
    project_id: str,
    preset_update: PresetUpdate,
    current_user: User = Depends(get_current_active_user),
):
    try:
        existing_preset = await db_instance.get_preset_by_name(
            preset_name, current_user.id, project_id
        )
        if not existing_preset:
            raise HTTPException(status_code=404, detail="Preset not found")

        updated_data = preset_update.model_dump()
        await db_instance.update_preset(
            preset_name, current_user.id, project_id, updated_data
        )
        return {
            "message": "Preset updated successfully",
            "name": preset_name,
            "data": updated_data,
        }
    except Exception as e:
        logger.error(f"Error updating preset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@preset_router.get("/{preset_name}")
async def get_preset(
    preset_name: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Remove project_id from get_preset_by_name call
        preset = await db_instance.get_preset_by_name(
            preset_name, current_user.id, project_id
        )
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        return preset
    except Exception as e:
        logger.error(f"Error getting preset: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@preset_router.delete("/{preset_name}")
async def delete_preset(
    preset_name: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Remove project_id from delete_preset call
        deleted = await db_instance.delete_preset(
            preset_name, current_user.id, project_id
        )
        if deleted:
            return {"message": "Preset deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Preset not found")
    except Exception as e:
        logger.error(f"Error deleting preset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Project Routes


@project_router.put("/{project_id}/universe")
async def update_project_universe(
    project_id: str,
    universe: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
):
    try:
        universe_id = universe.get("universe_id")  # This can now be None
        updated_project = await db_instance.update_project_universe(
            project_id, universe_id, current_user.id
        )
        if not updated_project:
            raise HTTPException(status_code=404, detail="Project not found")
        return updated_project
    except Exception as e:
        logger.error(f"Error updating project universe: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@project_router.post("/", response_model=Dict[str, Any])
async def create_project(
    project: ProjectCreate, current_user: User = Depends(get_current_active_user)
):
    try:
        project_id = await db_instance.create_project(
            name=project.name,
            description=project.description,
            user_id=current_user.id,
            universe_id=project.universe_id,
        )

        # Fetch the created project to return its details
        new_project = await db_instance.get_project(project_id, current_user.id)
        if not new_project:
            raise HTTPException(
                status_code=404, detail="Project not found after creation"
            )

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
            stats = await get_project_stats(project["id"], current_user.id)
            project.update(stats)

        return {"projects": projects}
    except Exception as e:
        logger.error(f"Error getting projects: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@project_router.get("/{project_id}")
async def get_project(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
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
    current_user: User = Depends(get_current_active_user),
):
    try:
        updated_project = await db_instance.update_project(
            project_id,
            project.name,
            project.description,
            current_user.id,
            project.universe_id,
            project.target_word_count,
        )
        if updated_project:
            return updated_project
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception as e:
        logger.error(f"Error updating project: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@project_router.delete("/{project_id}")
async def delete_project(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        success = await db_instance.delete_project(project_id, current_user.id)
        if success:
            return {"message": "Project deleted successfully"}
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception as e:
        logger.error(f"Error deleting project: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Other Endpoints (Health, Middleware, Shutdown) ---
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        start_time = datetime.now()
        response = await call_next(request)
        process_time = datetime.now() - start_time

        logger.info(
            f"[{request.method}] {request.url.path} - "
            f"Client: {request.client.host if request.client else 'Unknown'} - "
            f"Status: {response.status_code} - "
            f"Process Time: {process_time.total_seconds():.3f}s"
        )

        return response
    except Exception as e:
        logger.error(f"Unhandled exception in {request.url.path}: {str(e)}")
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )


@app.get("/health")
async def health_check():
    try:
        if not db_instance:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "Database not initialized"},
            )

        # Add a simple check to Supabase connection if possible (e.g., get service status)
        # For now, just check local DB init status
        # await db_instance.supabase.rpc('health_check', {}).execute() # Example if Supabase had such a function

        return JSONResponse(
            status_code=200,
            content={"status": "healthy", "message": "Server is running"},
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=500, content={"status": "error", "message": str(e)}
        )


@app.post("/shutdown")
async def shutdown():
    """Gracefully shutdown the server"""
    logger.info("Shutdown request received")
    timeout = 30
    asyncio.create_task(graceful_shutdown())
    return JSONResponse(
        status_code=202, content={"message": "Shutdown initiated", "timeout": timeout}
    )


async def graceful_shutdown():
    """Perform graceful shutdown operations"""
    try:
        logger.info("Starting graceful shutdown...")

        # --- Removed session cleanup ---

        # Close all agent managers
        await close_all_agent_managers() # Assuming this function exists and works with the store

        # Close database connections
        await db_instance.dispose()

        # Set shutdown event
        shutdown_event.set()

        logger.info("Graceful shutdown completed")

    except Exception as e:
        logger.error(f"Error during graceful shutdown: {str(e)}")
    finally:
        # Stop the server process
        # Use a more graceful exit if possible, but os._exit ensures termination
        logger.info("Exiting server process.")
        os._exit(0)


# Signal handlers
def handle_sigterm(signum, frame):
    logger.info(f"Received signal {signum}, initiating graceful shutdown.")
    # Ensure shutdown runs in the event loop
    asyncio.ensure_future(graceful_shutdown())


signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

# --- CRUD for Relationships, Events, Locations, Connections ---
# These need review similar to Chapter/Codex CRUD:


@relationship_router.post("/")
async def create_relationship(
    project_id: str,  # Make project_id a path parameter
    data: Dict[str, Any] = Body(...),  # Accept request body as a dictionary
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Validate required fields
        required_fields = ["character_id", "related_character_id", "relationship_type"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(
                    status_code=422, detail=f"Missing required field: {field}"
                )

        # Create in database
        relationship_id = await db_instance.create_character_relationship(
            character_id=data["character_id"],
            related_character_id=data["related_character_id"],
            relationship_type=data["relationship_type"],
            project_id=project_id,
            description=data.get("description"),  # Optional field
        )

        # Add to knowledge base
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.add_to_knowledge_base(
                "relationship",
                data.get("description", "") or data["relationship_type"],
                {
                    "id": relationship_id,
                    "character_id": data["character_id"],
                    "related_character_id": data["related_character_id"],
                    "type": "relationship",
                    "relationship_type": data["relationship_type"],
                },
            )

        return {"message": "Relationship created successfully", "id": relationship_id}
    except Exception as e:
        logger.error(f"Error creating relationship: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@relationship_router.get("/")
async def get_relationships(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        relationships = await db_instance.get_character_relationships(
            project_id, current_user.id
        )
        return {"relationships": relationships}
    except Exception as e:
        logger.error(f"Error fetching relationships: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@relationship_router.put("/{relationship_id}")
async def update_relationship(
    relationship_id: str,
    project_id: str,
    relationship_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Update in database
        await db_instance.update_character_relationship(
            relationship_id,
            relationship_data["relationship_type"],
            relationship_data.get("description"),
            project_id,
            current_user.id,
        )

        # Update in knowledge base
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": relationship_id, "item_type": "relationship"},
                "update",
                new_content=relationship_data.get("description")
                or relationship_data["relationship_type"],
                new_metadata={
                    "relationship_type": relationship_data["relationship_type"],
                    "type": "relationship",
                },
            )
        return {"message": "Relationship updated successfully"}
    except Exception as e:
        logger.error(f"Error updating relationship: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@relationship_router.delete("/{relationship_id}")
async def delete_relationship(
    relationship_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Delete from database - update parameter order to match the database method
        success = await db_instance.delete_character_relationship(
            relationship_id, project_id, current_user.id  # Add project_id parameter
        )

        if not success:
            raise HTTPException(status_code=404, detail="Relationship not found")

        # Delete from knowledge base
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": relationship_id, "item_type": "relationship"}, "delete"
            )
        return {"message": "Relationship deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting relationship: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@relationship_router.post("/analyze")
async def analyze_relationships(
    project_id: str,
    character_ids: List[str] = Body(...),
    current_user: User = Depends(get_current_active_user),
):
    try:
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            # Get only the selected characters
            characters = []
            for char_id in character_ids:
                character = await db_instance.get_characters(
                    current_user.id, project_id, character_id=char_id
                )
                if character and character["type"] == CodexItemType.CHARACTER.value:
                    characters.append(character)

            if len(characters) < 2:
                raise HTTPException(
                    status_code=404, detail="At least two valid characters are required"
                )

            # Analyze relationships for selected characters only
            relationships = await agent_manager.analyze_character_relationships(
                characters
            )

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
    current_user: User = Depends(get_current_active_user),
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
            user_id=current_user.id,
        )

        # Add to knowledge base
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.add_to_knowledge_base(
                "event_connection",
                f"Connection between events: {description}\nImpact: {impact}",
                {
                    "id": connection_id,
                    "event1_id": event1_id,
                    "event2_id": event2_id,
                    "type": "event_connection",
                    "connection_type": connection_type,
                },
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
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Update in database
        updated = await db_instance.update_event_connection(
            connection_id=connection_id,
            connection_type=connection_type,
            description=description,
            impact=impact,
            user_id=current_user.id,
            project_id=project_id,
        )

        # Update in knowledge base
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": connection_id, "item_type": "event_connection"},
                "update",
                new_content=f"Connection between events: {description}\nImpact: {impact}",
                new_metadata={
                    "type": "event_connection",
                    "connection_type": connection_type,
                },
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
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Delete from database
        success = await db_instance.delete_event_connection(
            connection_id, current_user.id, project_id
        )

        # Delete from knowledge base
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": connection_id, "item_type": "event_connection"}, "delete"
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
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        connections = await db_instance.get_event_connections(
            project_id, current_user.id
        )
        return {"event_connections": connections}
    except Exception as e:
        logger.error(f"Error fetching event connections: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Update analyze event connections to save to knowledge base
@event_router.post("/analyze-connections")
async def analyze_event_connections(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            connections = await agent_manager.analyze_event_connections()

            # Convert each connection to a dictionary before returning
            connection_dicts = [
                {
                    "id": getattr(conn, "connection_id", None),
                    "event1_id": conn.event1_id,
                    "event2_id": conn.event2_id,
                    "connection_type": conn.connection_type,
                    "description": conn.description,
                    "impact": conn.impact,
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
    current_user: User = Depends(get_current_active_user),
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
            user_id=current_user.id,
        )

        # Add to knowledge base
        content = f"Connection between locations: {description}"
        if travel_route:
            content += f"\nTravel Route: {travel_route}"
        if cultural_exchange:
            content += f"\nCultural Exchange: {cultural_exchange}"

        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.add_to_knowledge_base(
                "location_connection",
                content,
                {
                    "id": connection_id,
                    "location1_id": location1_id,
                    "location2_id": location2_id,
                    "type": "location_connection",
                    "connection_type": connection_type,
                },
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
    current_user: User = Depends(get_current_active_user),
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
            project_id=project_id,
        )

        # Update in knowledge base
        content = f"Connection between locations: {description}"
        if travel_route:
            content += f"\nTravel Route: {travel_route}"
        if cultural_exchange:
            content += f"\nCultural Exchange: {cultural_exchange}"

        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": connection_id, "item_type": "location_connection"},
                "update",
                new_content=content,
                new_metadata={
                    "type": "location_connection",
                    "connection_type": connection_type,
                },
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
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Delete from database
        success = await db_instance.delete_location_connection(
            connection_id, current_user.id, project_id
        )
        if not success:
            raise HTTPException(status_code=404, detail="Connection not found")

        # Delete from knowledge base
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": connection_id, "item_type": "location_connection"}, "delete"
            )
            # Delete any associated connections
            connections = await db_instance.get_location_connections(
                project_id, current_user.id
            )
            for conn in connections:
                if (
                    conn["location1_id"] == connection_id
                    or conn["location2_id"] == connection_id
                ):
                    await agent_manager.update_or_remove_from_knowledge_base(
                        {"item_id": conn["id"], "item_type": "location_connection"},
                        "delete",
                    )

        return {"message": "Location and associated connections deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting location connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@location_router.post("/analyze-connections")
async def analyze_location_connections(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        locations = await db_instance.get_locations(current_user.id, project_id)
        if not locations or len(locations) < 2:
            return JSONResponse(
                {"message": "Not enough locations to analyze connections", "skip": True}
            )

        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            connections = await agent_manager.analyze_location_connections()

            # Convert each connection to a dictionary before returning
            connection_dicts = [
                {
                    "id": connection.id,
                    "location1_id": connection.location1_id,
                    "location2_id": connection.location2_id,
                    "connection_type": connection.connection_type,
                    "description": connection.description,
                    "travel_route": connection.travel_route,
                    "cultural_exchange": connection.cultural_exchange,
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
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Create in database
        event_id = await db_instance.create_event(
            title=event_data["title"],
            description=event_data["description"],
            date=datetime.fromisoformat(event_data["date"]),
            character_id=event_data.get("character_id"),
            location_id=event_data.get("location_id"),
            project_id=project_id,
            user_id=current_user.id,
        )

        # Add to knowledge base
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.add_to_knowledge_base(
                "event",
                event_data["description"],
                {
                    "item_id": event_id,
                    "title": event_data["title"],
                    "item_type": "event",
                    "date": event_data["date"],
                    "character_id": event_data.get("character_id"),
                    "location_id": event_data.get("location_id"),
                },
            )

        return {"id": event_id}
    except Exception as e:
        logger.error(f"Error creating event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@event_router.get("")
async def get_events(
    project_id: str, current_user: User = Depends(get_current_active_user)
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
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Update in database
        await db_instance.update_event(
            event_id=event_id,
            title=event_data["title"],
            description=event_data["description"],
            date=datetime.fromisoformat(event_data["date"]),
            character_id=event_data.get("character_id"),
            location_id=event_data.get("location_id"),
            project_id=project_id,
            user_id=current_user.id,
        )

        # Update in knowledge base
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": event_id, "item_type": "event"},
                "update",
                new_content=event_data["description"],
                new_metadata={
                    "title": event_data["title"],
                    "date": event_data["date"],
                    "character_id": event_data.get("character_id"),
                    "location_id": event_data.get("location_id"),
                    "type": "event",
                },
            )

        return {"message": "Event updated successfully"}
    except Exception as e:
        logger.error(f"Error updating event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@event_router.delete("/{event_id}")
async def delete_event(
    event_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Delete from database
        success = await db_instance.delete_event(event_id, project_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Event not found")

        # Delete from knowledge base
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": event_id, "item_type": "event"}, "delete"
            )
        return {"message": "Event deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@event_router.post("/analyze-chapter")
async def analyze_chapter_events(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            # Analyze and get unprocessed chapter events
            events = await agent_manager.analyze_unprocessed_chapter_events()

            # Add events to the knowledge base
            for event in events:
                try:
                    # Create metadata with only the required fields
                    metadata = {
                        "id": event["id"],
                        "title": event["title"],
                        "type": "event",
                    }

                    # Add optional fields if they exist
                    if "date" in event:
                        metadata["date"] = event["date"]
                    if "character_id" in event:
                        metadata["character_id"] = event["character_id"]
                    if "location_id" in event:
                        metadata["location_id"] = event["location_id"]

                    # Add to knowledge base
                    await agent_manager.add_to_knowledge_base(
                        "event", event["description"], metadata
                    )
                except Exception as e:
                    logger.error(
                        f"Error adding event to knowledge base for event {event.get('id', 'unknown')}: {str(e)}"
                    )
                    logger.error(
                        f"Event data: {event}"
                    )  # Log the event data for debugging
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
    project_id: str, current_user: User = Depends(get_current_active_user)
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
    current_user: User = Depends(get_current_active_user),
):
    try:
        location_id = await db_instance.create_location(
            name=location_data["name"],
            description=location_data["description"],
            coordinates=location_data.get("coordinates"),
            user_id=current_user.id,
            project_id=project_id,
        )
        return {"id": location_id}
    except Exception as e:
        logger.error(f"Error creating location: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@location_router.post("/analyze-chapter")
async def analyze_chapter_locations(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        # Check if there are any unprocessed chapters
        unprocessed_chapters = await db_instance.get_latest_unprocessed_chapter_content(
            project_id, current_user.id, PROCESS_TYPES["LOCATIONS"]
        )

        if not unprocessed_chapters:
            return JSONResponse(
                {
                    "message": "All chapters analyzed for locations",
                    "alreadyAnalyzed": True,
                }
            )

        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            locations = await agent_manager.analyze_unprocessed_chapter_locations()

            # Add each location to knowledge base
            for location in locations:
                # Add to knowledge base
                await agent_manager.add_to_knowledge_base(
                    "location",
                    f"{location['name']}: {location['description']}",
                    {
                        "item_id": location[
                            "id"
                        ],  # Now using id from the location returned by agent_manager
                        "name": location["name"],
                        "item_type": "location",
                        "coordinates": location.get("coordinates"),
                    },
                )

            return {"locations": locations}
    except Exception as e:
        logger.error(f"Error analyzing chapter locations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@location_router.get("/{location_id}")
async def get_location(
    location_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        location = await db_instance.get_location_by_id(
            location_id, current_user.id, project_id
        )
        if not location:
            # logger.warning(f"Location not found: {location_id}")
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
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Update in database
        await db_instance.update_location(
            location_id=location_id,
            name=location_data["name"],
            description=location_data["description"],
            project_id=project_id,
            user_id=current_user.id,
        )

        # Update in knowledge base
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": location_id, "item_type": "location"},
                "update",
                new_content=f"{location_data['name']}: {location_data['description']}",
                new_metadata={
                    "name": location_data["name"],
                    "type": "location",
                    "coordinates": location_data.get("coordinates"),
                },
            )

        return {"message": "Location updated successfully"}
    except Exception as e:
        logger.error(f"Error updating location: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@location_router.delete("/{location_id}")
async def delete_location(
    location_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Delete from database
        success = await db_instance.delete_location(
            location_id, project_id, current_user.id
        )
        if not success:
            raise HTTPException(status_code=404, detail="Location not found")

        # Delete from knowledge base
        async with agent_manager_store.get_or_create_manager(
            current_user.id, project_id
        ) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": location_id, "item_type": "location"}, "delete"
            )
            # Delete any associated connections
            connections = await db_instance.get_location_connections(
                project_id, current_user.id
            )
            for conn in connections:
                if (
                    conn["location1_id"] == location_id
                    or conn["location2_id"] == location_id
                ):
                    await agent_manager.update_or_remove_from_knowledge_base(
                        {"item_id": conn["id"], "item_type": "location_connection"},
                        "delete",
                    )

        return {"message": "Location and associated connections deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting location: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/locations/connections")
async def get_location_connections(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        connections = await db_instance.get_location_connections(
            project_id, current_user.id
        )
        return {"location_connections": connections}
    except Exception as e:
        logger.error(f"Error fetching location connections: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Validity Check Endpoints ---
@validity_router.get("/")
async def get_validity_checks(
    project_id: str, current_user: User = Depends(get_current_active_user)
):
    try:
        validity_checks = await db_instance.get_all_validity_checks(
            current_user.id, project_id
        )
        return {"validityChecks": validity_checks}
    except Exception as e:
        logger.error(f"Error fetching validity checks: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@validity_router.delete("/{check_id}")
async def delete_validity_check(
    check_id: str,
    project_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        # Validity checks likely don't have separate KB entries, just delete from DB
        result = await db_instance.delete_validity_check(
            check_id, current_user.id, project_id
        )
        if result:
            return {"message": "Validity check deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Validity check not found")
    except Exception as e:
        logger.error(
            f"Error deleting validity check {check_id}: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Include Routers ---
app.include_router(auth_router)
app.include_router(
    chapter_router, prefix="/projects/{project_id}"
)
app.include_router(codex_item_router, prefix="/projects/{project_id}")
app.include_router(event_router, prefix="/projects/{project_id}")
app.include_router(location_router, prefix="/projects/{project_id}")
app.include_router(knowledge_base_router, prefix="/projects/{project_id}")
app.include_router(settings_router)
app.include_router(
    preset_router, prefix="/projects/{project_id}"
)
app.include_router(universe_router)
app.include_router(codex_router, prefix="/projects/{project_id}")
app.include_router(relationship_router, prefix="/projects/{project_id}")
app.include_router(project_router)
app.include_router(validity_router, prefix="/projects/{project_id}")


# --- Uvicorn Runner ---
if __name__ == "__main__":
    try:
        import uvicorn

        app_instance = app

        config = uvicorn.Config(
            app_instance,
            host="localhost",
            port=8080,
            log_level="info",
            reload=False, # Disable reload for production/stable runs
            workers=1, # Adjust workers based on CPU cores if needed, but start with 1
        )
        server = uvicorn.Server(config)

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, handle_sigterm)
        signal.signal(signal.SIGINT, handle_sigterm)

        logger.info("Starting Uvicorn server...")
        server.run()

    except Exception as e:
        # Use logger if setup succeeded, otherwise print
        try:
            logger.critical(f"Server failed to start: {str(e)}", exc_info=True)
        except NameError:  # If logger setup failed very early
            print(f"CRITICAL: Server failed to start: {str(e)}", file=sys.stderr)
        sys.exit(1)


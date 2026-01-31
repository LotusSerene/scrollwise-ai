import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, AsyncGenerator, Set, Union
from enum import Enum
from asyncio import Lock, Event
import os
from models import CodexItemType, WorldbuildingSubtype
from database import Chapter, Project, CodexItem, User, GenerationHistory
from sqlalchemy import select, and_, update, func
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
    Response,
    APIRouter,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import httpx  # Add httpx for async requests
# Removed jose and JWT related imports
from fastapi.routing import APIRouter
from pydantic import ValidationError
import logging  # Keep standard logging import

# Removed RotatingFileHandler
from cachetools import TTLCache  # For caching JWKS

from agent_manager import AgentManager, PROCESS_TYPES, ChapterGenerationState
from api_key_manager import ApiKeyManager, SecurityManager
from database import db_instance
from vector_store import VectorStore

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
    CodexItemResponse,
    RelationshipUpdate,  # Added RelationshipUpdate
    PresetCreate,
    PresetUpdate,
    ProjectCreate,
    ProjectUpdate,
    UniverseCreate,
    UniverseUpdate,
    UpdateTargetWordCountRequest,
    CodexItemGenerateRequest,
    RelationshipUpdate,
    EventConnectionCreate,
    EventConnectionBase,
    EventConnectionUpdate,
    EventConnectionAnalysis,
    EventDescription,
    EventAnalysis,
    LocationConnection,
    LocationConnectionAnalysis,
    LocationAnalysis,
    LocationAnalysisList,
    RelationshipAnalysis,
    RelationshipAnalysisList,
    BackstoryExtractionRequest,
    CodexExtraction,
    LocationConnectionCreate,
    GenerationStatus,
    GenerationStatusResponse,
    ProjectStructureResponse,
    ProjectStructureUpdateRequest,
    ChapterResponse,
    ProactiveSuggestionsResponse,
    ProactiveSuggestion,
    ProactiveAssistRequest,
    TextActionRequest,
    StructureChapterItem,
    StructureFolderItem,
    ProjectStructureResponse,
)


from pydantic import BaseModel, Field
from architect_agent import ArchitectAgent  # Import the new ArchitectAgent
from models import (
    ArchitectChatRequest,
    ArchitectChatResponse,
)  # Import necessary Pydantic models
from langchain_core.language_models.chat_models import (
    BaseChatModel,
)  # Import BaseChatModel
from langchain_core.output_parsers import (
    JsonOutputParser,
    StrOutputParser,
)  # Import necessary parsers
from langchain_core.prompts import ChatPromptTemplate  # Import ChatPromptTemplate
# Removed Paddle and Billing related imports
import urllib.parse
import uuid


class OpenRouterApiKeyUpdate(BaseModel):
    openrouterApiKey: str = Field(..., description="The OpenRouter API Key")


class AnthropicApiKeyUpdate(BaseModel):
    anthropicApiKey: str = Field(..., description="The Anthropic API Key")


class OpenAIApiKeyUpdate(BaseModel):
    openAIApiKey: str = Field(..., description="The OpenAI API Key")


class OpenRouterModelPricing(BaseModel):
    prompt: str
    completion: str
    image: Optional[str] = None  # Make optional as not all models have it
    request: Optional[str] = None  # Make optional


class OpenRouterModelArchitecture(BaseModel):
    input_modalities: List[str]
    output_modalities: List[str]
    tokenizer: str


class OpenRouterTopProvider(BaseModel):
    is_moderated: Optional[bool] = None  # Make optional


class OpenRouterModel(BaseModel):
    id: str
    name: str
    description: Optional[str] = None  # Make optional
    context_length: Optional[int] = None  # Make optional
    pricing: OpenRouterModelPricing
    architecture: Optional[OpenRouterModelArchitecture] = None  # Make optional
    top_provider: Optional[OpenRouterTopProvider] = None  # Make optional
    # Add other fields if needed from the API response


class ArchitectSettingsUpdate(BaseModel):
    enabled: bool = Field(
        ..., description="Enable or disable Architect mode for the project."
    )


# Removed PaddleWebhookRequest


import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Constants ---
# Authentication disabled for local version
DISABLE_AUTH = True

# Defaults for local environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./scrollwise.db")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Vector store settings
EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "models/gemini-embedding-001")


def setup_logging():
    """Configure logging to output to console (stdout/stderr) for cloud environments."""
    try:
        # Get root logger
        logger = logging.getLogger()
        # Set desired level (e.g., INFO, DEBUG)
        log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, log_level_name, logging.INFO))

        # Remove existing handlers to avoid duplicates if called multiple times
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Create console handler (logs to stderr by default)
        console_handler = logging.StreamHandler()

        # Create formatter
        log_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(log_format)

        # Add handler to the logger
        logger.addHandler(console_handler)

        logger.info(f"Console logging setup completed. Level: {log_level_name}")
        return logger  # Return logger instance

    except Exception as e:
        # Use basic print for critical logging setup errors
        print(f"CRITICAL: Error setting up logging: {str(e)}", file=sys.stderr)
        raise


logger = logging.getLogger(__name__)  # Use standard logger setup from previous example

# --- Global Variables ---
shutdown_event = asyncio.Event()
jwks_cache = TTLCache(maxsize=1, ttl=3600)  # Cache JWKS for 1 hour

# AgentManagerStore


class AgentManagerStore:
    def __init__(self, api_key_manager: ApiKeyManager):
        self._managers: Dict[str, AgentManager] = {}
        self._lock = Lock()
        self.api_key_manager = api_key_manager
        self.cleanup_interval = 600  # Cleanup every 10 minutes
        self.idle_timeout = 900  # Close managers idle for 15 minutes (15 * 60)
        self._cleanup_task = None
        self._shutdown_event = Event()  # Event to signal shutdown for cleanup task
        # --- Add state for tracking running generations ---
        self._generating_projects: Set[str] = set()
        self._generating_projects_lock = Lock()

    # --- Add methods to manage generation status ---
    async def is_project_generating(self, project_id: str) -> bool:
        async with self._generating_projects_lock:
            return project_id in self._generating_projects

    async def start_project_generation(self, project_id: str) -> bool:
        """Marks a project as generating. Returns False if already generating."""
        async with self._generating_projects_lock:
            if project_id in self._generating_projects:
                return False
            self._generating_projects.add(project_id)
            return True

    async def finish_project_generation(self, project_id: str):
        """Removes a project from the generating set."""
        async with self._generating_projects_lock:
            self._generating_projects.discard(
                project_id
            )  # Use discard to avoid error if already removed

    async def start_cleanup_task(self):
        """Starts the background task to clean up idle AgentManagers."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._shutdown_event.clear()
            self._cleanup_task = asyncio.create_task(self._run_cleanup())
            logger.info("AgentManager cleanup task started.")
        else:
            logger.warning("Cleanup task already running or not finished cleaning up.")

    async def stop_cleanup_task(self):
        """Stops the cleanup task and closes all remaining managers."""
        logger.info("Stopping AgentManager cleanup task...")
        self._shutdown_event.set()  # Signal cleanup loop to stop
        if self._cleanup_task and not self._cleanup_task.done():
            try:
                # Wait briefly for the task to finish gracefully
                await asyncio.wait_for(
                    self._cleanup_task, timeout=self.cleanup_interval + 5
                )
            except asyncio.TimeoutError:
                logger.warning("Cleanup task did not finish gracefully, cancelling.")
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    logger.info("Cleanup task cancelled successfully.")
                except Exception as e:
                    logger.error(
                        f"Error during cleanup task shutdown: {e}", exc_info=True
                    )
            else:
                logger.info("Cleanup task was already stopped or completed.")

        self._cleanup_task = None
        # Ensure all managers are closed on final shutdown
        await self.close_all_managers()

    async def _run_cleanup(self):
        """Periodically checks for and closes idle AgentManagers."""
        while not self._shutdown_event.is_set():
            try:
                # Wait for the interval OR until shutdown is signaled
                await asyncio.wait_for(
                    self._shutdown_event.wait(), timeout=self.cleanup_interval
                )
                if self._shutdown_event.is_set():  # Check if woken by shutdown
                    logger.info("Shutdown signal received, exiting cleanup loop.")
                    break
            except asyncio.TimeoutError:
                # Timeout expired, proceed with cleanup check
                pass
            except Exception as e:
                logger.error(f"Error during cleanup sleep/wait: {e}", exc_info=True)
                # Avoid tight loop on error
                await asyncio.sleep(60)
                continue  # Skip to next loop iteration

            logger.debug("Running AgentManager cleanup check...")
            keys_to_remove = []
            now = datetime.now(timezone.utc)
            try:
                async with self._lock:  # Lock only during dictionary operations
                    manager_items = list(
                        self._managers.items()
                    )  # Get items to check outside lock if closing takes time

                closed_count = 0
                for key, manager in manager_items:
                    # Check if manager is still in the dict (might have been removed)
                    async with self._lock:
                        if key not in self._managers:
                            continue  # Already removed by another operation

                    if hasattr(manager, "last_accessed"):
                        idle_time = now - manager.last_accessed
                        if idle_time.total_seconds() > self.idle_timeout:
                            logger.info(
                                f"AgentManager {key} idle for {idle_time}, closing."
                            )
                            try:
                                await manager.close()
                                keys_to_remove.append(key)
                                closed_count += 1
                            except Exception as close_err:
                                logger.error(
                                    f"Error closing idle manager {key}: {close_err}",
                                    exc_info=True,
                                )
                                # Optionally remove anyway to prevent repeated errors
                                # keys_to_remove.append(key)
                    else:
                        logger.warning(
                            f"Manager {key} missing 'last_accessed' attribute. Cannot determine idleness."
                        )
                        # Decide policy: remove it, leave it, or log only?
                        # Removing it to prevent buildup if attribute is missing
                        # keys_to_remove.append(key)

                # Remove closed managers from the dictionary
                if keys_to_remove:
                    async with self._lock:
                        for key in keys_to_remove:
                            self._managers.pop(key, None)
                    logger.debug(
                        f"AgentManager cleanup finished. Removed {closed_count} idle managers."
                    )
                else:
                    logger.debug(
                        "AgentManager cleanup finished. No idle managers found."
                    )

            except Exception as e:
                logger.error(
                    f"Error during AgentManager cleanup run: {e}", exc_info=True
                )
                # Avoid crashing the cleanup task, wait before retrying
                await asyncio.sleep(60)

        logger.info("AgentManager cleanup task finished.")

    @asynccontextmanager
    async def get_or_create_manager(
        self, user_id: str, project_id: str
    ) -> AsyncGenerator[AgentManager, None]:
        key = f"{user_id}_{project_id}"
        manager = None
        created_new = False
        try:
            async with self._lock:
                manager = self._managers.get(key)
                if not manager:
                    logger.info(f"Creating new AgentManager for key: {key}")
                    manager = await AgentManager.create(
                        user_id, project_id, self.api_key_manager
                    )
                    # last_accessed is set in AgentManager.__init__ now
                    self._managers[key] = manager
                    created_new = True
                else:
                    logger.debug(f"Reusing existing AgentManager for key: {key}")
                    # Update last accessed time on retrieval
                    manager.last_accessed = datetime.now(timezone.utc)
            yield manager
        except Exception as e:
            logger.error(
                f"Error in get_or_create_manager for key {key}: {e}", exc_info=True
            )
            # If we created a new manager but failed before yielding, remove it
            if created_new and key in self._managers:
                logger.warning(
                    f"Removing newly created manager {key} due to yield error."
                )
                async with self._lock:
                    failed_manager = self._managers.pop(key, None)
                if failed_manager:
                    try:
                        await failed_manager.close()
                    except Exception as close_err:
                        logger.error(
                            f"Error closing manager {key} after yield error: {close_err}"
                        )
            raise  # Re-raise the exception that occurred during the yield block
        finally:
            # The manager is intentionally NOT closed or removed here.
            # The cleanup task is responsible for closing idle managers.
            logger.debug(f"Released AgentManager {key} back to the store.")

    async def invalidate_user_managers(self, user_id: str):
        """Closes and removes all managers associated with a given user_id."""
        logger.info(
            f"Invalidating all managers for user {user_id[:8]} due to settings change."
        )
        keys_to_remove = []
        managers_to_close = []
        # Lock needs to be acquired on self._lock, which is part of AgentManagerStore
        async with self._lock:  # self._lock is already defined in AgentManagerStore
            # Identify managers for the specific user
            # self._managers is an attribute of AgentManagerStore
            for key, manager in list(
                self._managers.items()
            ):  # Iterate over a copy for safe removal
                # Assuming key format is f"{user_id}_{project_id}"
                if key.startswith(f"{user_id}_"):
                    keys_to_remove.append(key)
                    managers_to_close.append(manager)

            # Remove identified managers from the store dictionary
            removed_count = 0
            for key in keys_to_remove:
                self._managers.pop(key, None)
                removed_count += 1
            logger.debug(
                f"Removed {removed_count} manager entries for user {user_id[:8]} from store dictionary."
            )

        # Close the managers outside the lock to avoid holding it during potentially long close operations
        closed_count = 0
        for manager in managers_to_close:
            try:
                await manager.close()  # Call close on the AgentManager instance
                closed_count += 1
                # Log which specific manager was closed
                project_id_log = getattr(manager, "project_id", "unknown_project")
                manager_key_log = f"{user_id}_{project_id_log}"
                logger.info(
                    f"Closed invalidated manager instance for key {manager_key_log}"
                )
            except Exception as e:
                # Log error during closing but continue trying to close others
                logger.error(
                    f"Error closing invalidated manager for user {user_id[:8]} (Project: {getattr(manager, 'project_id', 'unknown')}): {e}",
                    exc_info=True,
                )

        logger.info(
            f"Finished invalidating managers for user {user_id[:8]}. Closed {closed_count} instances."
        )

    async def invalidate_project_managers(self, project_id: str):
        """Closes and removes all managers associated with a given project_id."""
        logger.info(
            f"Invalidating all managers for project {project_id[:8]} due to structure change."
        )
        keys_to_remove = []
        managers_to_close = []

        async with self._lock:
            for key, manager in list(self._managers.items()):
                # Assuming key format is f"{user_id}_{project_id}"
                if key.endswith(f"_{project_id}"):
                    keys_to_remove.append(key)
                    managers_to_close.append(manager)

            removed_count = 0
            for key in keys_to_remove:
                self._managers.pop(key, None)
                removed_count += 1
            logger.debug(
                f"Removed {removed_count} manager entries for project {project_id[:8]} from store dictionary."
            )

        closed_count = 0
        for manager in managers_to_close:
            try:
                await manager.close()
                closed_count += 1
                # Log which specific manager was closed
                user_id_log = getattr(manager, "user_id", "unknown_user")
                manager_key_log = f"{user_id_log}_{project_id}"
                logger.info(
                    f"Closed invalidated manager instance for key {manager_key_log}"
                )
            except Exception as e:
                logger.error(
                    f"Error closing invalidated manager for project {project_id[:8]} (User: {getattr(manager, 'user_id', 'unknown')}): {e}",
                    exc_info=True,
                )

        logger.info(
            f"Finished invalidating managers for project {project_id[:8]}. Closed {closed_count} instances."
        )

    async def close_all_managers(self):
        """Closes all currently managed AgentManager instances."""
        logger.info(f"Closing all ({len(self._managers)}) active AgentManagers...")
        async with self._lock:
            manager_keys = list(self._managers.keys())
            closed_count = 0
            for key in manager_keys:
                manager = self._managers.pop(key, None)
                if manager:
                    try:
                        await manager.close()
                        logger.info(f"Closed manager for key {key}")
                        closed_count += 1
                    except Exception as e:
                        logger.error(f"Error closing manager {key}: {e}", exc_info=True)
        logger.info(f"Finished closing all managers. Closed {closed_count} instances.")


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

        # Initialize API Key Manager FIRST
        logger.info("Initializing security and API key managers...")
        security_manager_instance = SecurityManager()
        api_key_manager_instance = ApiKeyManager(security_manager_instance)
        app.state.api_key_manager = (
            api_key_manager_instance  # Store in app state if needed elsewhere
        )
        logger.info("API key manager initialized successfully")

        # Initialize agent manager store, passing the ApiKeyManager
        logger.info("Initializing agent manager store...")
        # Ensure agent_manager_store is globally accessible or passed correctly
        # For now, assuming global 'agent_manager_store' is initialized correctly below
        app.state.agent_manager_store = agent_manager_store
        logger.info("Agent manager store initialized successfully")

        # Paddle Billing initialization removed for local version
        app.state.paddle_client = None

        # Start AgentManager cleanup task
        await agent_manager_store.start_cleanup_task()

        yield

    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down server...")

        # Stop AgentManager cleanup and close managers
        await agent_manager_store.stop_cleanup_task()

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
    allow_headers=["Authorization", "Content-Type"],  # Ensure Authorization is allowed
)

# --- Removed MAX_INACTIVITY and ACTIVE_SESSION_EXTEND ---

security_manager = SecurityManager()
api_key_manager = ApiKeyManager(security_manager)
agent_manager_store = AgentManagerStore(api_key_manager)


async def get_jwks():
    """Fetches JWKS from Cognito, caching the result."""
    cached_jwks = jwks_cache.get("jwks")
    if cached_jwks:
        logger.debug("Using cached JWKS")
        return cached_jwks

    logger.info(f"Fetching JWKS from {JWKS_URL}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(JWKS_URL)
            response.raise_for_status()  # Raise exception for bad status codes
            jwks_data = response.json()
            jwks_cache["jwks"] = jwks_data  # Cache the fetched JWKS
            return jwks_data
    except httpx.RequestError as e:
        logger.error(f"Error fetching JWKS: {e}")
        raise HTTPException(
            status_code=503, detail="Could not fetch authentication keys."
        )
    except Exception as e:
        logger.error(f"Unexpected error processing JWKS: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Error processing authentication keys."
        )


async def get_public_key(token: str):
    """Finds the right public key from JWKS based on the token's header."""
    try:
        jwks = await get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header.get("kid"):
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break
        if not rsa_key:
            logger.warning(
                f"Public key not found for kid: {unverified_header.get('kid')}"
            )
            return None
        # Construct the key using python-jose's jwk module
        return jwk.construct(rsa_key, algorithm="RS256")
    except JWTError as e:
        logger.error(f"Error decoding token header: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting public key: {e}", exc_info=True)
        return None


async def get_current_user(authorization: str = Header(None)):
    """
    Local version: Always returns a default local user to bypass authentication.
    """
    # Hardcoded local user for standalone operation
    cognito_id = "local-user"
    email = "local@scrollwise.app"
    
    try:
        local_user = await db_instance.get_or_create_user(
            user_id=cognito_id, email=email
        )
        return local_user
    except Exception as e:
        logger.error(f"Error getting local user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Local database error")


async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Ensures the user obtained from the token is considered active.
    The definition of 'active' might change based on local DB flags
    or could rely solely on Cognito's user status (implicit via successful login).
    """
    # `get_current_user` now returns a dictionary representing the local User record.
    try:
        if not current_user:
            # Should be caught by get_current_user, but kept for robustness.
            raise HTTPException(
                status_code=401, detail="Could not validate credentials"
            )

        # Cognito handles email verification. If the token is valid,
        # we can generally assume the user is active in Cognito.
        # If you have an additional 'is_active' flag in your local User table,
        # you could check it here:
        # if not current_user.get('is_active', True): # Default to True if flag doesn't exist
        #     raise HTTPException(status_code=403, detail="User is not active")

        # For now, simply return the user dict obtained from get_current_user
        # Ensure downstream dependencies use dict access (e.g., current_user['id'])
        return current_user

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error validating active user: {str(e)}")
        # Ensure we return a 401 or appropriate error if activation check fails
        raise HTTPException(status_code=401, detail="User validation failed")


async def get_agent_manager_store_dependency(request: Request) -> AgentManagerStore:
    """Dependency to get the AgentManagerStore from the app state."""
    if not hasattr(request.app.state, "agent_manager_store"):
        logger.error("AgentManagerStore not found in app state. Check lifespan setup.")
        raise HTTPException(status_code=500, detail="AgentManagerStore not initialized")
    return request.app.state.agent_manager_store


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
user_router = APIRouter(
    prefix="/users", tags=["Users"], dependencies=[Depends(get_current_active_user)]
)  # New User router
chapter_router = APIRouter(prefix="/chapters", tags=["Chapters"])
codex_item_router = APIRouter(prefix="/codex-items", tags=["Codex Items"])
knowledge_base_router = APIRouter(tags=["Knowledge Base"])  # Remove prefix here
settings_router = APIRouter(prefix="/settings", tags=["Settings"])
preset_router = APIRouter(prefix="/presets", tags=["Presets"])
project_router = APIRouter(prefix="/projects", tags=["Projects"])
universe_router = APIRouter(prefix="/universes", tags=["Universes"])
codex_router = APIRouter(prefix="/codex", tags=["Codex"])
relationship_router = APIRouter(prefix="/relationships", tags=["Relationships"])
event_router = APIRouter(prefix="/events", tags=["Events"])
location_router = APIRouter(tags=["Locations"])
validity_router = APIRouter(tags=["Validity Checks"])


# --- Architect Agent Router ---
architect_router = APIRouter(
    prefix="/projects/{project_id}/architect",
    tags=["Architect Agent (Pro)"],
    dependencies=[Depends(get_current_active_user)],  # Ensure user is logged in
)


@architect_router.post("/chat", response_model=ArchitectChatResponse)
async def architect_chat_endpoint(
    project_id: str,
    chat_request: ArchitectChatRequest,
    authorization: Optional[str] = Header(
        None
    ),  # <-- Add Authorization header dependency
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),  # <-- Inject the store here
    api_key_manager_di: ApiKeyManager = Depends(lambda: api_key_manager),
):
    """Handles chat messages for the Architect Agent (Pro users only)."""
    user_id = current_user["id"]
    # All local users have Architect Access
    is_pro = True

    # 2. Check if Architect Mode is enabled for the project
    project = await db_instance.get_project(project_id, user_id)
    if not project:
        raise HTTPException(
            status_code=404, detail="Project not found or not authorized."
        )
    if not project.get("architect_mode_enabled"):
        logger.warning(
            f"User {user_id} attempted to access Architect chat for project {project_id} where it's disabled."
        )
        raise HTTPException(
            status_code=403, detail="Architect mode is not enabled for this project."
        )

    # --- Agent Interaction ---
    try:
        # Instantiate ArchitectAgent, passing the required store
        architect_agent = ArchitectAgent(
            user_id, project_id, api_key_manager_di, agent_manager_store_di
        )

        # Convert Pydantic ChatHistoryItem to simple dicts if needed by agent
        # history_dicts = (
        #    [item.model_dump() for item in chat_request.chatHistory]
        #    if chat_request.chatHistory
        #    else []
        # )

        # Call the agent's chat method, passing the auth token
        # History is now loaded inside the agent's chat method
        response_data = await architect_agent.chat(
            chat_request.message,
            # history_dicts, # Removed history from here
            auth_token=authorization,
        )

        # Validate response (simple check for now)
        if "response" not in response_data:
            raise ValueError(
                "Architect agent did not return a valid response structure."
            )

        # Return validated response
        # Assuming response_data structure matches ArchitectChatResponse Pydantic model
        return ArchitectChatResponse(
            response=response_data.get("response", "Error: No response text."),
            tool_calls=response_data.get(
                "tool_calls", []
            ),  # Handle potential missing key
        )

    except HTTPException as http_exc:
        raise http_exc  # Re-raise authorization/not found errors
    except Exception as e:
        logger.error(
            f"Error during Architect chat for project {project_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during Architect chat: {str(e)}",
        )


@architect_router.get(
    "/chat-history", response_model=List[ChatHistoryItem]
)  # Define response model
async def get_architect_chat_history_endpoint(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    """Retrieves the chat history specifically for the Architect agent."""
    user_id = current_user["id"]
    try:
        history = await db_instance.get_architect_chat_history(user_id, project_id)
        
        # Normalize content field - convert list format to string if needed
        normalized_history = []
        for msg in history:
            content = msg.get("content", "")
            
            # If content is a list (e.g., from Anthropic API with content blocks), extract text
            if isinstance(content, list):
                text_content = ""
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_content += block.get("text", "")
                content = text_content if text_content else ""
            
            normalized_history.append({
                "role": msg.get("role", "user"),
                "content": content
            })
        
        return normalized_history
    except Exception as e:
        logger.error(
            f"Error getting Architect chat history for project {project_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve Architect chat history"
        )


@architect_router.delete("/chat-history")
async def delete_architect_chat_history_endpoint(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    """Deletes the chat history specifically for the Architect agent."""
    user_id = current_user["id"]
    try:
        deleted = await db_instance.delete_architect_chat_history(user_id, project_id)
        if deleted:
            logger.info(
                f"Deleted Architect chat history for user {user_id}, project {project_id}"
            )
            return {"message": "Architect chat history deleted successfully"}
        else:
            # This might mean no history existed, which isn't strictly an error
            logger.info(
                f"No Architect chat history found to delete for user {user_id}, project {project_id}"
            )
            return {"message": "No Architect chat history found to delete"}
    except Exception as e:
        logger.error(
            f"Error deleting Architect chat history for project {project_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to delete Architect chat history"
        )






@project_router.put("/{project_id}/target-word-count")
async def update_project_target_word_count(
    project_id: str,
    update_data: UpdateTargetWordCountRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        # Assuming db_instance method exists and is correct
        updated_project = await db_instance.update_project(
            project_id=project_id,
            name=None,
            description=None,  # Only updating target word count
            user_id=current_user["id"],  # Access user ID from dict
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


# Universe routes
@universe_router.post("/", response_model=Dict[str, Any])
async def create_universe(
    universe: UniverseCreate,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        universe_id = await db_instance.create_universe(
            universe.name, current_user["id"]
        )  # Access user ID from dict
        return {"id": universe_id, "name": universe.name}
    except Exception as e:
        logger.error(f"Error creating universe: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@universe_router.get("/{universe_id}", response_model=Dict[str, Any])
async def get_universe(
    universe_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        universe = await db_instance.get_universe(
            universe_id, current_user["id"]
        )  # Access user ID from dict
        if not universe:
            raise HTTPException(status_code=404, detail="Universe not found")
        stats = await get_universe_stats(
            universe_id, current_user["id"]
        )  # Access user ID from dict
        universe.update(stats)
        return JSONResponse(content=universe)
    except Exception as e:
        logger.error(f"Error fetching universe: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@universe_router.put("/{universe_id}", response_model=Dict[str, Any])
async def update_universe(
    universe_id: str,
    universe: UniverseUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        updated_universe = await db_instance.update_universe(
            universe_id, universe.name, current_user["id"]  # Access user ID from dict
        )
        if not updated_universe:
            raise HTTPException(status_code=404, detail="Universe not found")
        return JSONResponse(content=updated_universe)
    except Exception as e:
        logger.error(f"Error updating universe: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@universe_router.delete("/{universe_id}", response_model=bool)
async def delete_universe(
    universe_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        success = await db_instance.delete_universe(
            universe_id, current_user["id"]
        )  # Access user ID from dict
        if not success:
            raise HTTPException(status_code=404, detail="Universe not found")
        return JSONResponse(content={"success": success})
    except Exception as e:
        logger.error(f"Error deleting universe: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@universe_router.get("/{universe_id}/codex", response_model=List[Dict[str, Any]])
async def get_universe_codex(
    universe_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        codex_items = await db_instance.get_universe_codex(
            universe_id, current_user["id"]
        )  # Access user ID from dict
        return JSONResponse(content=codex_items)
    except Exception as e:
        logger.error(f"Error fetching universe codex: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@universe_router.get(
    "/{universe_id}/knowledge-base",
    response_model=Dict[str, List[Dict[str, Any]]],  # Return Dict[project_id, items]
)
async def get_universe_knowledge_base(
    universe_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        knowledge_base_items = await db_instance.get_universe_knowledge_base(
            universe_id, current_user["id"]  # Access user ID from dict
        )
        return JSONResponse(content=knowledge_base_items)
    except Exception as e:
        logger.error(f"Error fetching universe knowledge base: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@universe_router.get("/{universe_id}/projects", response_model=List[Dict[str, Any]])
async def get_projects_by_universe(
    universe_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    try:
        projects = await db_instance.get_projects_by_universe(
            universe_id, current_user["id"]
        )
        # Wrap projects in a 'projects' key to match frontend expectations
        return JSONResponse(content={"projects": projects})
    except Exception as e:
        logger.error(f"Error fetching projects by universe: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@universe_router.get("/", response_model=List[Dict[str, Any]])
async def get_universes(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):  # Use Dict
    try:
        universes = await db_instance.get_universes(
            current_user["id"]
        )  # Access user ID from dict
        # Add stats to each universe
        for universe in universes:
            stats = await get_universe_stats(
                universe["id"], current_user["id"]
            )  # Access user ID from dict
            universe.update(stats)
        return universes
    except Exception as e:
        logger.error(f"Error fetching universes: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Removed Auth Routes ---
# Signup, Signin, Signout are now handled by AWS Cognito (typically via frontend SDK or Hosted UI)
# The backend only needs to validate the JWT provided by the client.


# --- Chapter Routes ---


async def run_chapter_generation_background(
    user_id: str,
    project_id: str,
    gen_request: ChapterGenerationRequest,
    agent_manager_store_di: AgentManagerStore,  # Pass the store to access status methods
    api_key_manager: ApiKeyManager,  # Pass ApiKeyManager
):
    """The actual chapter generation logic, designed to run in the background."""
    try:
        logger.info(f"Background task started for user {user_id}, project {project_id}")
        chapter_count = await db_instance.get_chapter_count(project_id, user_id)
        generated_chapters_details = []  # Store details of generated chapters
        plot_segments = None
        full_plot = gen_request.plot  # Keep original plot
        # Track previous chapters to maintain narrative continuity
        previous_chapters_content = (
            []
        )  # Store content of chapters generated in this batch

        # --- Plot Segmentation Step ---
        if gen_request.numChapters > 1:
            logger.info(
                f"Segmentation requested for {gen_request.numChapters} chapters."
            )
            try:
                # 1. Get settings and key for segmentation LLM
                seg_api_key = await api_key_manager.get_api_key(
                    user_id
                )  # Use primary key for now
                seg_openrouter_key = await api_key_manager.get_openrouter_api_key(
                    user_id
                )
                model_settings = await db_instance.get_model_settings(user_id)
                # Use checkLLM or extractionLLM - checkLLM is likely cheaper/faster
                segmentation_model_name = model_settings.get(
                    "checkLLM", "gemini-1.5-flash-latest"
                )
                temperature = float(model_settings.get("temperature", 0.7))

                # 2. Instantiate the LLM (Simplified _get_llm logic here)
                segmentation_llm: BaseChatModel
                if segmentation_model_name.startswith("openrouter/"):
                    if not seg_openrouter_key:
                        raise ValueError(
                            "OpenRouter key needed for segmentation model but not found."
                        )
                    openrouter_model_id = segmentation_model_name.split(
                        "openrouter/", 1
                    )[1]
                    from langchain_openai import ChatOpenAI  # Local import

                    segmentation_llm = ChatOpenAI(
                        model=openrouter_model_id,
                        openai_api_key=seg_openrouter_key,
                        openai_api_base="https://openrouter.ai/api/v1",
                        temperature=temperature,
                        default_headers={  # Add required OpenRouter headers
                            "HTTP-Referer": os.getenv(
                                "SCROLLWISE_SITE_URL", "https://github.com/LotusSerene/scrollwise-ai"
                            ),
                            "X-Title": os.getenv(
                                "SCROLLWISE_SITE_NAME", "ScrollWise AI"
                            ),
                        },
                    )
                else:
                    if not seg_api_key:
                        raise ValueError(
                            "Gemini key needed for segmentation model but not found."
                        )
                    from langchain_google_genai import (
                        ChatGoogleGenerativeAI,
                    )  # Local import

                    segmentation_llm = ChatGoogleGenerativeAI(
                        model=segmentation_model_name,
                        google_api_key=seg_api_key,
                        temperature=temperature,
                    )

                # 3. Define Segmentation Prompt
                segmentation_prompt = ChatPromptTemplate.from_template(
                    """You are a master story planner. Given the overall plot below, divide it into exactly {num_chapters} logical segments, where each segment represents the core events and progression for a single chapter. Ensure the segments flow logically, build upon each other in sequence, and cover the entire plot.

                    Overall Plot:
                    {full_plot}

                    Number of Chapters to Segment For: {num_chapters}

                    INSTRUCTIONS:
                    1. Create exactly {num_chapters} segments that together cover the entire plot
                    2. Make sure each segment flows naturally into the next one
                    3. Ensure narrative continuity between segments
                    4. The final segment should reach the conclusion of the story
                    5. Return ONLY a JSON array containing exactly {num_chapters} strings - nothing else

                    JSON FORMAT:
                    ```json
                    ["Segment for Chapter 1...", "Segment for Chapter 2...", ...]
                    ```

                    Your response must be ONLY valid parseable JSON. Do not include any other text, explanation, or markdown formatting.
                    """
                )

                # 4. Create Chain and Invoke
                # Use JsonOutputParser directly first
                parser = JsonOutputParser()
                chain = segmentation_prompt | segmentation_llm | parser

                logger.debug(
                    f"Invoking LLM for plot segmentation ({segmentation_model_name})..."
                )
                segmentation_result = await chain.ainvoke(
                    {
                        "num_chapters": gen_request.numChapters,
                        "full_plot": full_plot,
                    }
                )

                # 5. Validate and Store Segments
                if (
                    isinstance(segmentation_result, list)
                    and len(segmentation_result) == gen_request.numChapters
                ):
                    plot_segments = segmentation_result
                    logger.info(
                        f"Successfully segmented plot into {len(plot_segments)} parts."
                    )
                    # Log snippets for verification
                    for i, seg in enumerate(plot_segments):
                        logger.debug(f"Segment {i+1}: {seg[:100]}...")
                else:
                    logger.warning(
                        f"Segmentation result was not a list of {gen_request.numChapters} strings. Result: {segmentation_result}"
                    )
                    # Fallback: Use full plot for all chapters
                    plot_segments = None  # Indicate fallback

            except Exception as seg_error:
                logger.error(
                    f"Error during plot segmentation: {seg_error}", exc_info=True
                )
                # Fallback: Use full plot for all chapters
                plot_segments = None

        async with agent_manager_store_di.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            for i in range(gen_request.numChapters):
                chapter_number = chapter_count + i + 1
                logger.info(
                    f"Background task: Initiating generation for Chapter {chapter_number}..."
                )

                # Determine the plot to use for this specific chapter
                current_plot_segment = None
                if plot_segments:
                    try:
                        current_plot_segment = plot_segments[i]
                    except IndexError:
                        logger.warning(
                            f"Missing plot segment for chapter index {i}. Using full plot."
                        )
                        current_plot_segment = None  # Fallback for this chapter

                # Use the full plot if segmentation failed or is not applicable
                plot_for_this_chapter = (
                    current_plot_segment
                    if current_plot_segment is not None
                    else full_plot
                )

                # Prepare instructions for the agent, potentially adding segmentation info
                # Option 1: Modify instructions dict (if AgentManager expects it)
                current_instructions = (
                    gen_request.instructions.copy() if gen_request.instructions else {}
                )
                current_instructions["plot_segment"] = (
                    current_plot_segment  # Might be None
                )
                current_instructions["full_plot"] = full_plot
                current_instructions["total_chapters"] = gen_request.numChapters
                # Add original plot and writing style if they are part of instructions
                current_instructions["plot"] = (
                    full_plot  # Main plot key if needed by prompt
                )
                current_instructions["writing_style"] = gen_request.writingStyle

                # Add previous chapters content for continuity (if any)
                if previous_chapters_content:
                    current_instructions["previous_chapters"] = (
                        previous_chapters_content
                    )
                    logger.info(
                        f"Adding {len(previous_chapters_content)} previous chapters as context for Chapter {chapter_number}"
                    )

                # Call the AgentManager's graph-based generation method
                # Pass the modified/relevant information
                result = await agent_manager.generate_chapter(
                    chapter_number=chapter_number,
                    # plot=plot_for_this_chapter, # Pass specific segment/full plot here
                    # writing_style=gen_request.writingStyle, # Pass style
                    # instructions=current_instructions, # Pass modified instructions
                    # OR Adjust the signature of generate_chapter if preferred
                    # For now, assuming modification of instructions dict:
                    plot=full_plot,  # Main plot context
                    writing_style=gen_request.writingStyle,
                    instructions=current_instructions,  # Contains segment, full plot, total etc.
                )

                # Check for errors returned by the graph
                if result.get("error"):
                    logger.error(
                        f"Background task: Chapter {chapter_number} generation failed: {result['error']}"
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
                        f"Background task: Chapter {chapter_number} generation result missing content or title."
                    )
                    generated_chapters_details.append(
                        {
                            "chapter_number": chapter_number,
                            "status": "failed",
                            "error": "Missing content or title in generation result.",
                        }
                    )
                    continue

                # Add this chapter to the list of previous chapters for context in future chapters
                previous_chapters_content.append(
                    {
                        "chapter_number": chapter_number,
                        "title": chapter_title,
                        "content": chapter_content,
                    }
                )
                logger.info(
                    f"Added Chapter {chapter_number} to previous chapters context (total: {len(previous_chapters_content)})"
                )

                # 1. Save Chapter to DB
                new_chapter_db = await db_instance.create_chapter(
                    title=chapter_title,
                    content=chapter_content,
                    project_id=project_id,
                    user_id=user_id,
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
                        f"Background task: Failed to add chapter {chapter_id} to knowledge base."
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
                            f"Background task: Failed to save validity feedback for chapter {chapter_id}: {vf_error}"
                        )
                        # Non-critical error

                # 4. Process and Save New Codex Items
                saved_codex_items_info = []
                if new_codex_items:
                    logger.info(
                        f"Background task: Processing {len(new_codex_items)} new codex items for chapter {actual_chapter_number}."
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
                                user_id=user_id,
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
                                    f"Background task: Failed to add codex item '{item['name']}' to knowledge base."
                                )
                        except Exception as ci_error:
                            logger.error(
                                f"Background task: Failed to process/save codex item '{item.get('name', 'UNKNOWN')}': {ci_error}",
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
                    f"Background task: Successfully processed generated Chapter {actual_chapter_number}."
                )

        logger.info(
            f"Background task finished successfully for user {user_id}, project {project_id}. Results: {generated_chapters_details}"
        )

    except Exception as e:
        logger.error(
            f"Error during background chapter generation for user {user_id}, project {project_id}: {str(e)}",
            exc_info=True,
        )
        # Handle error reporting (e.g., update DB status, log)
    finally:
        # --- Ensure project status is cleared ---
        logger.info(
            f"Background task finalizing for project {project_id}. Clearing generation status."
        )
        await agent_manager_store_di.finish_project_generation(project_id)
        logger.info(f"Cleared generation status for project {project_id}.")


@chapter_router.post("/generate")
async def generate_chapters(
    request: Request,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
    # --- Inject ApiKeyManager ---
    api_key_manager_di: ApiKeyManager = Depends(lambda: api_key_manager),
):
    try:
        user_id = current_user["id"]
        body = await request.json()
        gen_request = ChapterGenerationRequest.model_validate(body)

        # --- Save to History ---
        try:
            async with db_instance.Session() as session:
                history_entry = GenerationHistory(
                    user_id=user_id,
                    project_id=project_id,
                    num_chapters=gen_request.numChapters,
                    word_count=gen_request.instructions.get("wordCount"),
                    plot=gen_request.plot,
                    writing_style=gen_request.writingStyle,
                    instructions=gen_request.instructions,
                )
                session.add(history_entry)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to save generation history: {e}", exc_info=True)
            # Do not block generation if history fails to save

        # --- Check if generation is already running ---
        if not await agent_manager_store_di.start_project_generation(project_id):
            logger.warning(
                f"Generation already in progress for project {project_id}. Request denied."
            )
            raise HTTPException(
                status_code=409,  # Conflict
                detail="Chapter generation is already in progress for this project.",
            )

        # --- Start Background Task ---
        try:
            asyncio.create_task(
                run_chapter_generation_background(
                    user_id=user_id,
                    project_id=project_id,
                    gen_request=gen_request,
                    agent_manager_store_di=agent_manager_store_di,  # Pass AgentManagerStore
                    api_key_manager=api_key_manager_di,  # Pass ApiKeyManager
                )
            )
            logger.info(
                f"Started background chapter generation task for user {user_id}, project {project_id}."
            )
        except Exception as task_start_error:
            # If task creation fails, ensure we clear the generation flag
            logger.error(
                f"Failed to start background task for project {project_id}: {task_start_error}",
                exc_info=True,
            )
            await agent_manager_store_di.finish_project_generation(project_id)
            raise HTTPException(
                status_code=500, detail="Failed to start generation task."
            )

        # --- Return 202 Accepted Immediately ---
        return JSONResponse(
            content={
                "message": f"Chapter generation started for {gen_request.numChapters} chapter(s)."
            },
            status_code=202,
        )

    except ValidationError as e:
        logger.error(f"Chapter generation request validation error: {e}", exc_info=True)
        # If validation fails AFTER setting the flag (though unlikely here), we should clear it.
        # However, the flag is set *after* validation in the current flow.
        raise HTTPException(status_code=422, detail=e.errors())
    except HTTPException as http_exc:  # Re-raise HTTP exceptions (like the 409)
        raise http_exc
    except Exception as e:
        logger.error(
            f"Error initiating chapter generation process: {str(e)}", exc_info=True
        )
        # Potentially clear the flag if an unexpected error occurs after setting it
        # await agent_manager_store_di.finish_project_generation(project_id) # Uncomment if necessary
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@chapter_router.get("/{chapter_id}")
async def get_chapter(
    chapter_id: str,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    user_id = current_user["id"]  # Access user ID from dict
    # Only check project ownership
    project = await db_instance.get_project(project_id, user_id)
    if not project:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this project"
        )
    try:
        chapter = await db_instance.get_chapter(chapter_id, user_id, project_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        return chapter
    except Exception as e:
        logger.error(f"Error fetching chapter: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@chapter_router.get("/")
async def get_chapters(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        chapters = await db_instance.get_all_chapters(
            current_user["id"], project_id
        )  # Access user ID from dict
        return {"chapters": chapters}
    except Exception as e:
        logger.error(f"Error fetching chapters: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@chapter_router.post("/", response_model=ChapterResponse)  # Re-add response model
async def create_chapter(
    chapter: ChapterCreate,  # Use Pydantic model for request body
    project_id: str,  # Get project_id from path
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]
        logger.info(
            f"User {user_id} creating new chapter for project {project_id} with title '{chapter.title}'"
        )

        # Create the chapter first
        new_chapter_data = await db_instance.create_chapter(
            project_id=project_id,
            user_id=user_id,
            title=chapter.title,
            content=chapter.content or "",
            structure_item_id=chapter.structure_item_id,
        )

        # If append_to_structure is true, add it to the project structure
        if chapter.append_to_structure:
            # Retrieve the current project structure
            structure_data = await db_instance.get_project_structure(
                project_id=project_id, user_id=user_id
            )

            # Gracefully handle both old (list) and new (dict) structure formats
            structure_list = []
            if isinstance(structure_data, dict):
                structure_list = structure_data.get("project_structure", [])
            elif isinstance(structure_data, list):
                # This handles legacy structures that were just a list
                structure_list = structure_data

            # Append the new chapter to the structure list
            structure_list.append(
                {
                    "id": str(new_chapter_data["id"]),
                    "type": "chapter",
                    "title": new_chapter_data["title"],
                }
            )

            # Persist the updated structure back to the database
            await db_instance.update_project_structure(
                project_id=project_id, structure=structure_list, user_id=user_id
            )

        # Invalidate manager to ensure it reloads with the new chapter list
        await agent_manager_store_di.invalidate_project_managers(project_id)

        logger.info(f"Successfully created chapter {new_chapter_data['id']}")

        # Manually add project_id and user_id to satisfy the response model
        new_chapter_data["project_id"] = project_id
        new_chapter_data["user_id"] = user_id

        # Return the chapter data directly as per the response model
        return new_chapter_data
    except Exception as e:
        logger.error(
            f"Error creating chapter for project {project_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Error creating chapter: {e}")


@chapter_router.put("/{chapter_id}")
async def update_chapter(
    chapter_id: str,
    chapter_update: ChapterUpdate,  # Use Pydantic model for request body
    project_id: str,  # Get project_id from path
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    user_id = current_user["id"]
    kb_error = None
    try:
        # 1. Get existing chapter to find embedding_id
        existing_chapter = await db_instance.get_chapter(
            chapter_id, user_id, project_id
        )
        if not existing_chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        existing_embedding_id = existing_chapter.get("embedding_id")

        # 2. Update DB
        updated_chapter = await db_instance.update_chapter(
            chapter_id=chapter_id,
            user_id=user_id,
            project_id=project_id,
            title=chapter_update.title,
            content=chapter_update.content,
            structure_item_id=chapter_update.structure_item_id,
        )

        # 3. Update KB
        if existing_embedding_id:
            try:
                async with agent_manager_store_di.get_or_create_manager(
                    user_id, project_id
                ) as agent_manager:
                    await agent_manager.update_or_remove_from_knowledge_base(
                        existing_embedding_id,
                        "update",
                        new_content=chapter_update.content,
                        new_metadata={
                            "title": chapter_update.title,
                            "structure_item_id": chapter_update.structure_item_id,
                        },
                    )
            except Exception as kb_e:
                kb_error = f"Failed to update chapter in knowledge base: {kb_e}"
                logger.error(kb_error, exc_info=True)

        # Invalidate agent manager if chapter update might change context
        await agent_manager_store_di.invalidate_project_managers(project_id)
        return JSONResponse(status_code=200, content=updated_chapter)
    except Exception as e:
        logger.error(f"Error updating chapter {chapter_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@chapter_router.delete("/{chapter_id}")
async def delete_chapter(
    chapter_id: str,
    project_id: str,  # Get project_id from path
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    kb_error = None
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # 1. Get existing chapter for embedding_id
        chapter = await db_instance.get_chapter(chapter_id, user_id, project_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        embedding_id = chapter.get("embedding_id")

        # 2. Delete from Knowledge Base first
        if embedding_id:
            try:
                async with agent_manager_store_di.get_or_create_manager(
                    user_id, project_id
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
        success = await db_instance.delete_chapter(chapter_id, user_id, project_id)
        if not success:
            # This indicates a potential race condition or logic error if chapter was found initially
            raise HTTPException(
                status_code=500,
                detail="Failed to delete chapter from database after finding it.",
            )

        # 4. Invalidate any cached managers for this project
        logger.info(
            f"Invalidating all managers for project {project_id[:8]} due to chapter deletion."
        )
        await agent_manager_store_di.invalidate_project_managers(project_id)

        message = "Chapter deleted successfully" + (
            f" (Warning: {kb_error})" if kb_error else ""
        )
        return {"message": message}

    except HTTPException:
        raise  # Re-raise 404
    except Exception as e:
        logger.error(f"Error deleting chapter {chapter_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@chapter_router.post("/{chapter_id}/text-action")
async def chapter_text_action(
    project_id: str,
    chapter_id: str,
    request_data: TextActionRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    """Handles AI-powered text actions on a selection within a chapter."""
    user_id = current_user["id"]
    try:
        async with agent_manager_store_di.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            modified_text = await agent_manager.process_text_action(
                action=request_data.action,
                selected_text=request_data.selected_text,
                full_chapter_content=request_data.full_chapter_content,
                custom_prompt=request_data.custom_prompt,
            )
            return {"modified_text": modified_text}
    except ValueError as ve:
        logger.warning(f"Text action validation error: {ve}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(
            f"Error processing text action for chapter {chapter_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="Failed to process text action."
        )


@chapter_router.post("/extract-all-codex-items")
async def extract_codex_items_from_all_chapters(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    """
    Extracts codex items from all chapters in a project, processing them in chunks.
    """
    user_id = current_user["id"]
    logger.info(
        f"Starting codex extraction for all chapters in project {project_id} for user {user_id}."
    )

    try:
        async with agent_manager_store_di.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            # 1. Fetch all chapters from the database
            all_chapters = await db_instance.get_all_chapters(
                user_id=user_id, project_id=project_id
            )

            if not all_chapters:
                logger.warning(
                    f"No chapters found for project {project_id}. Nothing to extract."
                )
                return JSONResponse(
                    status_code=404,
                    content={"message": "No chapters found in this project."},
                )

            # 2. Process in chunks
            chunk_size = 25
            all_new_items = []
            all_errors = []

            for i in range(0, len(all_chapters), chunk_size):
                chunk = all_chapters[i : i + chunk_size]
                chunk_content = " ".join(
                    [
                        chapter.get("content", "")
                        for chapter in chunk
                        if chapter.get("content")
                    ]
                )

                if not chunk_content.strip():
                    logger.info(f"Chunk {i//chunk_size + 1} is empty, skipping.")
                    continue

                logger.info(
                    f"Processing chunk {i//chunk_size + 1}/{len(all_chapters)//chunk_size + 1}..."
                )

                try:
                    # 3. Call agent manager with the chunk's content
                    # This assumes agent_manager has a method to handle content extraction.
                    # We might need to create a new method like `extract_codex_from_content`.
                    # For now, let's assume `run_codex_extraction_on_content` exists.
                    # Note: We need to implement this method in AgentManager.
                    # This method would be a refactoring of the logic previously in this endpoint.

                    # Placeholder for the actual call - this method needs to be created
                    # in AgentManager. It will take text content and return extracted items.
                    new_items = await agent_manager.extract_codex_items_from_text(
                        chunk_content
                    )

                    if new_items:
                        all_new_items.extend(new_items)
                        logger.info(
                            f"Found {len(new_items)} items in chunk {i//chunk_size + 1}."
                        )

                except Exception as e:
                    error_msg = f"Error processing chunk {i//chunk_size + 1}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    all_errors.append(error_msg)

            # 4. Consolidate and return results
            if not all_new_items and all_errors:
                raise HTTPException(
                    status_code=500, detail="Codex extraction failed for all chunks."
                )

            return JSONResponse(
                status_code=200,
                content={
                    "message": f"Codex extraction completed. Found {len(all_new_items)} items.",
                    "items": all_new_items,  # Changed "new_items" to "items" to match frontend
                    "errors": all_errors,
                },
            )

    except Exception as e:
        logger.error(
            f"Failed to extract codex items from all chapters for project {project_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error during codex extraction."
        )


@chapter_router.post("/extract-from-chapters")
async def extract_codex_items_from_chapters_endpoint(
    project_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    """
    Extracts codex items from a specified list of chapter IDs.
    Used for extracting from a folder or a selection of chapters.
    """
    user_id = current_user["id"]
    try:
        body = await request.json()
        chapter_ids = body.get("chapter_ids")
        if not chapter_ids or not isinstance(chapter_ids, list):
            raise HTTPException(
                status_code=400, detail="`chapter_ids` must be a non-empty list."
            )

        logger.info(
            f"Starting codex extraction from {len(chapter_ids)} chapters in project {project_id}."
        )

        async with agent_manager_store_di.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            # 1. Fetch content of specified chapters
            chapters_content = []
            for chapter_id in chapter_ids:
                # This fetches one by one. Consider a batch fetch method in `database.py`.
                chapter = await db_instance.get_chapter(chapter_id, user_id, project_id)
                if chapter and chapter.get("content"):
                    chapters_content.append(chapter["content"])

            if not chapters_content:
                return JSONResponse(
                    status_code=404,
                    content={"message": "No content found for the specified chapters."},
                )

            full_content = " ".join(chapters_content)

            # 2. Run extraction on the combined content
            # This uses the same new agent_manager method as the all-chapters endpoint.
            new_items = await agent_manager.extract_codex_items_from_text(full_content)

            logger.info(
                f"Successfully extracted {len(new_items)} codex items from {len(chapter_ids)} chapters."
            )
            return JSONResponse(
                status_code=200,
                content={
                    "message": f"Codex extraction successful. Found {len(new_items)} items.",
                    "items": new_items,
                },
            )

    except HTTPException as he:
        raise he  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(
            f"Failed to extract codex items from chapters for project {project_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))


@codex_router.post("/generate", response_model=Dict[str, Any])
async def generate_codex_item(
    request: CodexItemGenerateRequest,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
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

        user_id = current_user["id"]  # Access user ID from dict
        async with agent_manager_store.get_or_create_manager(
            user_id, project_id
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
                user_id=user_id,
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
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        characters = await db_instance.get_all_codex_items(
            current_user["id"], project_id
        )  # Access user ID from dict
        # Filter only character type items
        characters = [item for item in characters if item["type"] == "character"]
        return {"characters": characters}
    except Exception as e:
        logger.error(f"Error fetching characters: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@codex_item_router.post("/", response_model=CodexItemResponse)  # Changed response model
async def create_codex_item(
    codex_item_data: CodexItemCreate,  # Changed type hint
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    kb_error = None
    new_codex_item_id = None
    try:
        user_id = current_user["id"]

        # Create CodexItem in DB
        new_codex_item_id = await db_instance.create_codex_item(
            name=codex_item_data.name,
            description=codex_item_data.description,
            type=codex_item_data.type.value,  # Use .value for Enum
            subtype=codex_item_data.subtype.value if codex_item_data.subtype else None,
            backstory=(
                codex_item_data.backstory
                if hasattr(codex_item_data, "backstory")
                # Ensure backstory attribute exists and type is CHARACTER before accessing
                and codex_item_data.type == CodexItemType.CHARACTER
                and codex_item_data.backstory
                else None
            ),
            user_id=user_id,
            project_id=project_id,
        )

        embedding_id = None
        # Add to knowledge base
        try:
            async with agent_manager_store_di.get_or_create_manager(
                user_id, project_id
            ) as agent_manager:
                metadata = {
                    "id": new_codex_item_id,
                    "name": codex_item_data.name,
                    "type": codex_item_data.type.value,
                    "subtype": (
                        codex_item_data.subtype.value
                        if codex_item_data.subtype
                        else None
                    ),
                    # Add other relevant metadata for KB indexing if needed
                }
                embedding_id = await agent_manager.add_to_knowledge_base(
                    content_type=codex_item_data.type.value,
                    content=codex_item_data.description,
                    metadata=metadata,
                    db_item_id=new_codex_item_id,
                )
            if embedding_id and embedding_id == new_codex_item_id:
                await db_instance.update_codex_item_embedding_id(
                    new_codex_item_id, embedding_id
                )
            elif not embedding_id:
                kb_error = "Failed to add codex item to knowledge base (no embedding ID returned)."
                logger.warning(kb_error)
            else:
                kb_error = f"Knowledge base ID ({embedding_id}) mismatch with DB ID ({new_codex_item_id})."
                logger.error(kb_error)

        except Exception as kb_e:
            kb_error = f"Error adding codex item to knowledge base: {kb_e}"
            logger.error(kb_error, exc_info=True)

        # Handle Character Voice Profile
        if (
            codex_item_data.type == CodexItemType.CHARACTER
            and codex_item_data.voice_profile
        ):
            try:
                await db_instance.get_or_create_character_voice_profile(
                    codex_item_id=new_codex_item_id,
                    user_id=user_id,
                    project_id=project_id,
                    voice_profile_data=codex_item_data.voice_profile.model_dump(),  # Pass as dict
                )
                logger.info(
                    f"Successfully created/updated voice profile for codex item {new_codex_item_id}"
                )
            except Exception as vp_e:
                # Log error, but don't let it fail the whole codex item creation
                logger.error(
                    f"Error creating/updating voice profile for {new_codex_item_id}: {vp_e}",
                    exc_info=True,
                )
                # Optionally add to kb_error or a separate voice_profile_error
                if kb_error:
                    kb_error += f"; Voice profile error: {vp_e}"
                else:
                    kb_error = f"Voice profile error: {vp_e}"

        # Fetch the complete codex item from DB to include all fields (like voice_profile)
        # The to_dict() method in CodexItem SQLAlchemy model now includes voice_profile
        final_codex_item_data = await db_instance.get_codex_item_by_id(
            new_codex_item_id, user_id, project_id
        )
        if not final_codex_item_data:
            # This should not happen if creation was successful
            logger.error(
                f"Failed to retrieve newly created codex item {new_codex_item_id}"
            )
            raise HTTPException(
                status_code=500, detail="Failed to retrieve created codex item."
            )

        # Use CodexItemResponse for the response
        # Pydantic will automatically convert the dict from to_dict() if fields match
        response_content = CodexItemResponse(**final_codex_item_data)

        status_code = 201 if not kb_error else 207  # Multi-Status if KB or VP failed

        # Use .model_dump(mode='json') for FastAPI to handle datetime and Enum correctly
        return JSONResponse(
            content=response_content.model_dump(mode="json"), status_code=status_code
        )

    except ValidationError as e:
        logger.error(f"Codex item creation validation error: {e}", exc_info=True)
        raise HTTPException(status_code=422, detail=e.errors())
    except Exception as e:
        # Log the original new_codex_item_id if available for debugging
        error_detail = f"Error creating codex item (ID: {new_codex_item_id if new_codex_item_id else 'N/A'}): {str(e)}"
        logger.error(error_detail, exc_info=True)
        raise HTTPException(status_code=500, detail=error_detail)


@codex_item_router.put(
    "/{item_id}", response_model=CodexItemResponse
)  # Changed response model
async def update_codex_item(
    item_id: str,
    codex_item_update_data: CodexItemUpdate,  # Changed type hint
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    kb_error = None
    updated_codex_item_db = None
    try:
        user_id = current_user["id"]

        # 1. Get existing codex item to check its type and embedding_id
        existing_codex_item = await db_instance.get_codex_item_by_id(
            item_id, user_id, project_id
        )
        if not existing_codex_item:
            raise HTTPException(status_code=404, detail="Codex item not found")

        existing_embedding_id = existing_codex_item.get("embedding_id")
        original_type_str = existing_codex_item.get("type")  # Store as string
        # Convert original_type_str to CodexItemType enum if it's not None
        original_type_enum = (
            CodexItemType(original_type_str) if original_type_str else None
        )

        # Prepare data for DB update, filtering out None values to avoid overwriting with null
        # Use exclude_unset=True to only include fields explicitly provided in the request
        update_data_db = codex_item_update_data.model_dump(exclude_unset=True)

        if "type" in update_data_db and isinstance(update_data_db["type"], Enum):
            update_data_db["type"] = update_data_db["type"].value
        if "subtype" in update_data_db and isinstance(update_data_db["subtype"], Enum):
            update_data_db["subtype"] = update_data_db["subtype"].value

        # Extract voice_profile from the payload before it's passed to db_instance.update_codex_item
        voice_profile_payload = update_data_db.pop("voice_profile", None)

        # 2. Update CodexItem in DB
        # db_instance.update_codex_item expects individual fields that might be None.
        updated_codex_item_db = await db_instance.update_codex_item(
            item_id=item_id,
            name=update_data_db.get("name"),
            description=update_data_db.get("description"),
            type=update_data_db.get(
                "type"
            ),  # This will be string value of enum or None
            subtype=update_data_db.get(
                "subtype"
            ),  # This will be string value of enum or None
            backstory=update_data_db.get("backstory"),
            user_id=user_id,
            project_id=project_id,
        )
        if not updated_codex_item_db:
            # This might happen if the item_id is invalid or doesn't belong to the user/project
            raise HTTPException(
                status_code=404, detail="Codex item not found or update failed in DB."
            )

        # 3. Update Knowledge Base if description or name changed
        content_for_kb_update = None
        if "description" in update_data_db and update_data_db[
            "description"
        ] != existing_codex_item.get("description"):
            content_for_kb_update = update_data_db["description"]
        # elif "name" in update_data_db and update_data_db["name"] != existing_codex_item.get("name"):
        #    # If only name changed, and description didn't, use existing/updated description for KB
        #    content_for_kb_update = updated_codex_item_db.get("description")

        if existing_embedding_id and content_for_kb_update is not None:
            try:
                async with agent_manager_store_di.get_or_create_manager(
                    user_id, project_id
                ) as agent_manager:
                    metadata_for_kb = {
                        "id": item_id,  # Should be the DB item's ID
                        "name": updated_codex_item_db.get("name"),
                        "type": updated_codex_item_db.get("type"),
                        "subtype": updated_codex_item_db.get("subtype"),
                    }
                    await agent_manager.update_or_remove_from_knowledge_base(
                        existing_embedding_id,  # Use the embedding_id for lookup in VS
                        "update",
                        new_content=content_for_kb_update,
                        new_metadata=metadata_for_kb,
                    )
            except Exception as kb_e:
                kb_error = f"Failed to update codex item in knowledge base: {kb_e}"
                logger.error(kb_error, exc_info=True)
        elif not existing_embedding_id and content_for_kb_update is not None:
            # If it wasn't in KB before, add it now
            logger.info(
                f"Codex item {item_id} was not in knowledge base. Adding it now."
            )
            try:
                async with agent_manager_store_di.get_or_create_manager(
                    user_id, project_id
                ) as agent_manager:
                    new_embedding_id = await agent_manager.add_to_knowledge_base(
                        content_type=updated_codex_item_db.get("type"),
                        content=content_for_kb_update,
                        metadata={
                            "id": item_id,
                            "name": updated_codex_item_db.get("name"),
                            "type": updated_codex_item_db.get("type"),
                            "subtype": updated_codex_item_db.get("subtype"),
                        },
                        db_item_id=item_id,
                    )
                if new_embedding_id:
                    await db_instance.update_codex_item_embedding_id(
                        item_id, new_embedding_id
                    )
                    logger.info(
                        f"Added codex item {item_id} to KB with new embedding ID {new_embedding_id}"
                    )
                else:
                    kb_error = (
                        "Failed to add previously missing codex item to knowledge base."
                    )
                    logger.warning(kb_error)
            except Exception as add_kb_e:
                kb_error = (
                    f"Error adding codex item {item_id} to knowledge base: {add_kb_e}"
                )
                logger.error(kb_error, exc_info=True)

        # 4. Handle Character Voice Profile Update
        # Determine the type of the item after potential update
        # The type from codex_item_update_data (if provided) or original_type_enum
        current_item_type_str = update_data_db.get("type", original_type_str)
        current_item_type_enum = (
            CodexItemType(current_item_type_str) if current_item_type_str else None
        )

        if (
            current_item_type_enum == CodexItemType.CHARACTER
            and voice_profile_payload
            is not None  # voice_profile was present in the request
        ):
            try:
                vp_data_dict = (
                    voice_profile_payload
                    if isinstance(voice_profile_payload, dict)
                    else voice_profile_payload.model_dump()  # Convert Pydantic model to dict
                )
                # Use get_or_create_character_voice_profile which handles both creation and update
                await db_instance.get_or_create_character_voice_profile(
                    codex_item_id=item_id,
                    user_id=user_id,
                    project_id=project_id,
                    voice_profile_data=vp_data_dict,
                )
                logger.info(
                    f"Successfully updated/created voice profile for codex item {item_id}"
                )
            except Exception as vp_e:
                logger.error(
                    f"Error updating/creating voice profile for {item_id}: {vp_e}",
                    exc_info=True,
                )
                if kb_error:
                    kb_error += f"; Voice profile error: {vp_e}"
                else:
                    kb_error = f"Voice profile error: {vp_e}"

        # Fetch the complete updated codex item from DB to include all fields
        # This ensures the voice_profile (if any) is correctly reflected in the response.
        final_updated_codex_item_data = await db_instance.get_codex_item_by_id(
            item_id, user_id, project_id
        )
        if not final_updated_codex_item_data:
            # This should ideally not happen if the update_codex_item call was successful
            logger.error(
                f"Failed to retrieve updated codex item {item_id} after DB operations. Using potentially stale data."
            )
            # Fallback to updated_codex_item_db which might not have the latest voice profile if it was just created/updated
            final_updated_codex_item_data = updated_codex_item_db

        response_content = CodexItemResponse(**final_updated_codex_item_data)
        status_code = 200 if not kb_error else 207

        return JSONResponse(
            content=response_content.model_dump(mode="json"), status_code=status_code
        )

    except HTTPException:
        raise  # Re-raise 404 etc.
    except ValidationError as e:
        logger.error(f"Codex item update validation error: {e}", exc_info=True)
        raise HTTPException(status_code=422, detail=e.errors())
    except Exception as e:
        error_detail = f"Error updating codex item {item_id}: {str(e)}"
        logger.error(error_detail, exc_info=True)
        raise HTTPException(status_code=500, detail=error_detail)


@codex_item_router.delete("/{item_id}")
async def delete_codex_item(
    item_id: str,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    kb_error = None
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # 1. Get existing item for embedding_id
        codex_item = await db_instance.get_codex_item_by_id(
            item_id, user_id, project_id
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
                    user_id, project_id
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
        deleted = await db_instance.delete_codex_item(item_id, user_id, project_id)
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


@codex_item_router.get(
    "/{item_id}", response_model=CodexItemResponse
)  # Changed response model
async def get_codex_item(
    item_id: str,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    user_id = current_user["id"]
    # Check project ownership
    project = await db_instance.get_project(project_id, user_id)
    if not project:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access this project's codex items",
        )
    try:
        codex_item_data = await db_instance.get_codex_item_by_id(
            item_id, user_id, project_id
        )
        if not codex_item_data:
            raise HTTPException(status_code=404, detail="Codex item not found")

        # Convert to Pydantic model for response validation and serialization
        response_content = CodexItemResponse(**codex_item_data)
        return JSONResponse(content=response_content.model_dump(mode="json"))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching codex item {item_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@codex_item_router.get(
    "/", response_model=List[CodexItemResponse]
)  # Changed response model
async def get_codex_items(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    user_id = current_user["id"]
    # Check project ownership
    project = await db_instance.get_project(project_id, user_id)
    if not project:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access this project's codex items",
        )
    try:
        codex_items_data = await db_instance.get_all_codex_items(user_id, project_id)
        # Convert list of dicts to list of Pydantic models
        response_content = [CodexItemResponse(**item) for item in codex_items_data]
        return JSONResponse(
            content=[item.model_dump(mode="json") for item in response_content]
        )

    except Exception as e:
        logger.error(
            f"Error fetching codex items for project {project_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Backstory & Relationship Analysis Routes ---


@codex_item_router.put("/characters/{character_id}/backstory")
async def update_backstory(
    character_id: str,
    project_id: str,
    backstory_content: str = Body(..., embed=True),  # Embed content in request body
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    kb_error = None
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # 1. Update DB (assuming method exists)
        await db_instance.update_character_backstory(
            character_id, backstory_content, user_id, project_id
        )

        # 2. Update/Add KB
        try:
            async with agent_manager_store.get_or_create_manager(
                user_id, project_id
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
        status_code = 200 if not kb_error else 207
        return JSONResponse(
            content={"message": message}, status_code=status_code
        )  # Return simple message

    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error updating backstory for character {character_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@codex_item_router.delete("/characters/{character_id}/backstory")
async def delete_backstory(
    character_id: str,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    kb_error = None
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # 1. Delete from DB (clears the backstory field)
        await db_instance.delete_character_backstory(character_id, user_id, project_id)

        # 2. Delete from KB
        try:
            async with agent_manager_store.get_or_create_manager(
                user_id, project_id
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

        message = "Backstory deleted successfully" + (
            f" (Warning: {kb_error})" if kb_error else ""
        )
        status_code = 200 if not kb_error else 207
        return JSONResponse(
            content={"message": message}, status_code=status_code
        )  # Return simple message

    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error deleting backstory for character {character_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@codex_item_router.post(
    "/characters/{character_id}/analyze-journey", response_model=Dict[str, Any]
)
async def analyze_character_journey_endpoint(
    character_id: str,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]

        # Verify character exists
        character = await db_instance.get_codex_item_by_id(
            character_id, user_id, project_id
        )
        if not character:
            raise HTTPException(status_code=404, detail="Character not found")
        if character.get("type") != CodexItemType.CHARACTER.value:
            raise HTTPException(status_code=400, detail="Item is not a character")
        # Removed check: if not character.get("backstory"):

        # Call AgentManager method - this will now fetch chapters and generate backstory
        async with agent_manager_store.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            # Pass character_id. AgentManager will fetch name and chapters.
            analysis_result = await agent_manager.analyze_character_journey(
                character_id
            )

        if analysis_result is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate journey analysis. Agent manager returned None.",
            )

        # The result is now the generated backstory text
        return {"generated_backstory": analysis_result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error analyzing character journey for {character_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# --- Location Analysis Route ---


@location_router.post("/analyze-chapter")
async def analyze_chapter_locations(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # Check if unprocessed chapters exist *before* getting manager? Maybe not necessary.
        async with agent_manager_store.get_or_create_manager(
            user_id, project_id
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


# --- Knowledge Base Routes ---


# Move the function definition from the end of the file to here
@knowledge_base_router.get("/", response_model=List[Dict[str, Any]])
async def get_project_knowledge_base_items(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    """Retrieve all knowledge base items (chapters, codex, manual) for a project."""
    try:
        user_id = current_user["id"]
        # Use the specific DB method for KB items
        items = await db_instance.get_project_knowledge_base(user_id, project_id)
        return items
    except Exception as e:
        logger.error(
            f"Error fetching knowledge base items for project {project_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@knowledge_base_router.post("/")
async def add_to_knowledge_base(
    request: Request,  # Use Request to access headers/body
    project_id: str,
    # Form fields only for file uploads
    content_type_form: Optional[str] = Form(None),
    text_content_form: Optional[str] = Form(None),
    metadata_str_form: str = Form("{}"),
    file: Optional[UploadFile] = File(None),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    """Adds an item (manual text or uploaded file) to the knowledge base."""
    user_id = current_user["id"]
    manager_store = request.app.state.agent_manager_store
    db_item_id = None
    embedding_id = None
    item_type_for_db = None
    content_to_embed = None
    metadata_for_db = {}
    source_identifier = "unknown"

    try:
        content_type_header = request.headers.get("content-type", "").lower()
        logger.info(f"Request content type header: {content_type_header}")
        logger.info(
            f"File present: {bool(file)}, content_type_form: {content_type_form}"
        )

        async with manager_store.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            # Handle file upload
            if file:
                if not file.filename:
                    raise HTTPException(status_code=400, detail="No filename provided")

                # We need the actual content type, not the extension
                # file_ext = os.path.splitext(file.filename)[1].lower() # REMOVE or comment out
                content_type_for_extraction = (
                    file.content_type
                )  # Use the file's reported MIME type
                logger.debug(
                    f"Received file: {file.filename}, Actual Content-Type: {content_type_for_extraction}"
                )

                file_bytes = await file.read()

                if not file_bytes:
                    raise HTTPException(status_code=400, detail="Empty file uploaded")

                # Log the actual MIME type being passed
                logger.debug(
                    f"Passing content type to extract_text_from_bytes: {content_type_for_extraction!r}"
                )

                # Call AgentManager with the correct MIME type
                content_to_add = await agent_manager.extract_text_from_bytes(
                    file_bytes, content_type_for_extraction
                )

                if content_to_add is None:
                    # This case might now indicate an actual extraction problem or unsupported type
                    raise HTTPException(
                        status_code=415,  # Use 415 Unsupported Media Type
                        detail=f"Unsupported file type ({content_type_for_extraction}) or error during text extraction.",
                    )

                # Assign values for the rest of the logic
                content_to_embed = content_to_add
                item_type_for_db = "uploaded_file"
                source_identifier = (
                    file.filename
                )  # Use filename as source identifier for uploads

                # Prepare metadata (moved from later block)
                try:
                    metadata_for_db = json.loads(metadata_str_form)
                except json.JSONDecodeError:
                    metadata_for_db = {}
                    logger.warning(
                        f"Invalid JSON metadata for file {file.filename}. Using empty metadata."
                    )
                metadata_for_db["filename"] = file.filename
                # Correctly extract subtype from MIME type (e.g., 'plain' from 'text/plain')
                parts = content_type_for_extraction.split("/")
                metadata_for_db["file_type"] = (
                    parts[1] if len(parts) > 1 else content_type_for_extraction
                )

            # Handle JSON text input
            elif "application/json" in content_type_header:
                body = await request.json()
                content_to_embed = body.get("text_content")
                if not content_to_embed:
                    raise HTTPException(
                        status_code=400, detail="Missing 'text_content' in JSON body"
                    )

                item_type_for_db = body.get("content_type", "manual_text")
                try:
                    metadata_str_body = body.get("metadata_str", "{}")
                    metadata_for_db = json.loads(metadata_str_body)
                except json.JSONDecodeError:
                    raise HTTPException(
                        status_code=400, detail="Invalid JSON in metadata_str"
                    )
                source_identifier = metadata_for_db.get("source", "manual_entry")

            else:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid request. Use multipart/form-data for file upload or application/json for text content.",
                )

            if not content_to_embed or not item_type_for_db:
                raise HTTPException(
                    status_code=400, detail="Missing content or type information"
                )

            # Add common metadata
            metadata_for_db["source"] = source_identifier
            metadata_for_db["db_type"] = item_type_for_db
            metadata_for_db["created_at"] = datetime.now(timezone.utc).isoformat()

            # Save to database
            try:
                db_item_id = await db_instance.create_knowledge_base_item(
                    user_id=user_id,
                    project_id=project_id,
                    type=item_type_for_db,
                    content=content_to_embed,
                    item_metadata=metadata_for_db,
                    source=source_identifier,
                    embedding_id=None,
                )
                logger.info(f"KB Add: Initial DB record created with ID: {db_item_id}")
            except Exception as db_error:
                raise HTTPException(
                    status_code=500,
                    detail=f"Database error creating item: {str(db_error)}",
                )

            # Add to vector store
            try:
                embedding_id = await agent_manager.add_to_knowledge_base(
                    content_type=item_type_for_db,
                    content=content_to_embed,
                    metadata=metadata_for_db,
                    db_item_id=db_item_id,
                )

                if not embedding_id:
                    raise Exception("No embedding ID returned from vector store")

                # Update DB with embedding ID
                updated = await db_instance.update_knowledge_base_item_embedding_id(
                    item_id=db_item_id,
                    embedding_id=embedding_id,
                    user_id=user_id,
                    project_id=project_id,
                )
                if not updated:
                    logger.warning(
                        f"Could not update embedding ID for DB item {db_item_id}"
                    )

            except Exception as e:
                # Clean up DB entry if vector store fails
                await db_instance.delete_knowledge_base_item_by_id(
                    db_item_id, user_id, project_id
                )
                raise HTTPException(
                    status_code=500, detail=f"Error adding to vector store: {str(e)}"
                )

            return {
                "message": f"Successfully added '{source_identifier}' to knowledge base",
                "id": db_item_id,
                "embedding_id": embedding_id,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to knowledge base: {str(e)}", exc_info=True)
        if db_item_id:
            try:
                await db_instance.delete_knowledge_base_item_by_id(
                    db_item_id, user_id, project_id
                )
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
        raise HTTPException(status_code=500, detail=str(e))


@knowledge_base_router.get("/export")
async def export_knowledge_base(
    project_id: str,
    format: str = Query("json", regex="^(json|csv|txt)$"),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    """Export knowledge base items in the specified format."""
    try:
        user_id = current_user["id"]
        items = await db_instance.get_project_knowledge_base(user_id, project_id)

        if format == "json":
            # Return JSON directly
            return JSONResponse(
                content=items,
                headers={
                    "Content-Disposition": f'attachment; filename="knowledge_base_{project_id}.json"'
                },
            )

        elif format == "csv":
            # Convert to CSV
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow(["ID", "Type", "Name", "Content", "Source", "Created At"])

            # Write data
            for item in items:
                writer.writerow(
                    [
                        item.get("id", ""),
                        item.get("type", ""),
                        item.get("name", ""),
                        item.get("content", ""),
                        item.get("source", ""),
                        item.get("created_at", ""),
                    ]
                )

            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f'attachment; filename="knowledge_base_{project_id}.csv"'
                },
            )

        else:  # txt format
            # Convert to plain text
            output = []
            for item in items:
                output.extend(
                    [
                        f"ID: {item.get('id', '')}",
                        f"Type: {item.get('type', '')}",
                        f"Name: {item.get('name', '')}",
                        f"Content: {item.get('content', '')}",
                        f"Source: {item.get('source', '')}",
                        f"Created At: {item.get('created_at', '')}",
                        "-" * 80,  # Separator
                    ]
                )

            return Response(
                content="\n".join(output),
                media_type="text/plain",
                headers={
                    "Content-Disposition": f'attachment; filename="knowledge_base_{project_id}.txt"'
                },
            )

    except Exception as e:
        logger.error(f"Error exporting knowledge base: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error exporting knowledge base: {str(e)}"
        )


# PUT /knowledge-base/{embedding_id} - Use agent_manager method
@knowledge_base_router.put("/{embedding_id}")
async def update_knowledge_base_item(
    embedding_id: str,
    project_id: str,
    update_data: Dict[str, Any] = Body(
        ...
    ),  # Expect {'content': '...', 'metadata': {...}}
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    new_content = update_data.get("content")
    new_metadata = update_data.get("metadata")
    user_id = current_user["id"]  # Access user ID from dict
    if new_content is None and new_metadata is None:
        raise HTTPException(
            status_code=400,
            detail="Must provide 'content' and/or 'metadata' for update.",
        )

    try:
        async with agent_manager_store.get_or_create_manager(
            user_id, project_id
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


@knowledge_base_router.delete("/{embedding_id}")
async def delete_knowledge_base_item(
    embedding_id: str,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        vector_store_deleted = False
        db_deleted = False
        error_messages = []

        # First check if the item exists in the database
        item = await db_instance.get_knowledge_base_item_by_embedding_id(
            embedding_id, user_id, project_id
        )
        if not item:
            raise HTTPException(status_code=404, detail="Item not found in database")

        # Try to delete from vector store
        async with agent_manager_store.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            try:
                await agent_manager.update_or_remove_from_knowledge_base(
                    embedding_id, "delete"
                )
                vector_store_deleted = True
            except Exception as vs_error:
                error_messages.append(f"Vector store deletion failed: {str(vs_error)}")

        # Try to delete from database regardless of vector store result
        try:
            db_deleted = await db_instance.delete_knowledge_base_item_by_id(
                item["id"], user_id, project_id
            )
            if not db_deleted:
                error_messages.append("Database deletion failed")
        except Exception as db_error:
            error_messages.append(f"Database deletion failed: {str(db_error)}")

        # Determine response based on results
        if vector_store_deleted and db_deleted:
            return {"message": "Knowledge base item deleted successfully"}
        elif vector_store_deleted or db_deleted:
            # Partial success - item was deleted from at least one store
            return {
                "message": "Knowledge base item partially deleted",
                "warnings": error_messages,
            }
        else:
            # Neither deletion succeeded
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete item: {'; '.join(error_messages)}",
            )

    except HTTPException:
        raise
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
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        async with agent_manager_store.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            # chatHistory from query_data is already List[Dict] after Pydantic validation
            chat_history_dicts = query_data.chatHistory

            result = await agent_manager.query_knowledge_base(
                query_data.query, chat_history_dicts
            )
            # Return the result dictionary directly
            return result
    except Exception as e:
        logger.error(f"Error querying knowledge base: {str(e)}", exc_info=True)
        # Return a structured error that the frontend might be able to parse
        raise HTTPException(
            status_code=500,
            detail={"answer": f"Internal server error: {str(e)}", "sources": []},
        )


@knowledge_base_router.post("/extract-text")
async def extract_text_from_file(
    request: Request,
    project_id: str,
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    """Extract text from an uploaded file without saving it to knowledge base."""
    try:
        user_id = current_user["id"]

        logger.info(
            f"Extracting text from file {file.filename} for project {project_id}"
        )

        # Get the correct AgentManager
        async with agent_manager_store_di.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            # Read file content
            file_content = await file.read()
            content_type = file.content_type or "application/octet-stream"

            logger.info(f"File content type: {content_type}")

            # Extract text using the existing method in AgentManager
            extracted_text = await agent_manager.extract_text_from_bytes(
                file_content, content_type
            )

            if not extracted_text:
                logger.warning(
                    f"Could not extract text from file of type {content_type}"
                )
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": f"Could not extract text from file of type {content_type}"
                    },
                )

            # Return the extracted text
            logger.info(
                f"Successfully extracted {len(extracted_text)} characters from file"
            )
            return {"text": extracted_text, "filename": file.filename}
    except Exception as e:
        logger.error(f"Error extracting text from file: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, content={"detail": f"Error processing file: {str(e)}"}
        )


# POST /knowledge-base/reset-chat-history - Calls agent_manager.reset_memory
@knowledge_base_router.post("/reset-chat-history")
async def reset_chat_history(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # AgentManager's reset_memory handles DB deletion directly
        async with agent_manager_store.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            await agent_manager.reset_memory()
        return {"message": "Chat history reset successfully"}
    except Exception as e:
        logger.error(f"Error resetting chat history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/projects/{project_id}/chat-history")  # <-- Updated path
async def save_chat_history(
    project_id: str,  # project_id now comes from path
    chat_history: ChatHistoryRequest,  # Body only contains chatHistory field
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        # Convert Pydantic models (ChatHistoryItem) inside the list to dictionaries
        chat_history_dicts = [item.model_dump() for item in chat_history.chatHistory]
        await db_instance.save_chat_history(
            current_user["id"],
            project_id,  # Use project_id from path
            chat_history_dicts,
        )
        return {"message": "Chat history saved successfully"}
    except Exception as e:
        logger.error(f"Error saving chat history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# GET /knowledge-base/chat-history - Calls agent_manager.get_chat_history
@knowledge_base_router.get("/chat-history")
async def get_knowledge_base_chat_history(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        async with agent_manager_store.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            chat_history = await agent_manager.get_chat_history()  # Agent gets from DB
            # Ensure history is a list of dicts (or whatever format client expects)
            validated_history = []
            for item in chat_history:
                if isinstance(item, dict):
                    # Convert 'role' to 'type' if needed
                    if "role" in item and "type" not in item:
                        item["type"] = item["role"]
                    validated_history.append(
                        ChatHistoryItem.model_validate(item).model_dump()
                    )
            return {"chatHistory": validated_history}
    except Exception as e:
        logger.error(f"Error getting chat history endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving chat history")


# Settings routes
@settings_router.post("/api-key")
async def save_api_key(
    api_key_update: ApiKeyUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        await api_key_manager.save_api_key(
            current_user["id"], api_key_update.apiKey
        )  # Access user ID from dict
        return {"message": "API key saved successfully"}
    except Exception as e:
        logger.error(f"Error saving API key: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@settings_router.get("/api-key")
async def check_api_key(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    try:
        api_key = await api_key_manager.get_api_key(
            current_user["id"]
        )  # Access user ID from dict
        is_set = bool(api_key)
        # Mask the API key for security
        masked_key = "*" * (len(api_key) - 4) + api_key[-4:] if is_set else None
        return {"isSet": is_set, "apiKey": masked_key}
    except Exception as e:
        logger.error(f"Error checking API key: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@settings_router.delete("/api-key")
async def remove_api_key(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    try:
        await api_key_manager.remove_api_key(
            current_user["id"]  # Access user ID from dict
        )  # Updated to call remove_api_key
        return {"message": "API key removed successfully"}
    except Exception as e:
        logger.error(f"Error removing API key: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- NEW OpenRouter API Key Endpoints ---


@settings_router.post("/openrouter-api-key")
async def save_openrouter_api_key(
    api_key_update: OpenRouterApiKeyUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    """Saves the OpenRouter API key."""
    try:
        await api_key_manager.save_openrouter_api_key(
            current_user["id"], api_key_update.openrouterApiKey
        )
        return {"message": "OpenRouter API key saved successfully"}
    except Exception as e:
        logger.error(f"Error saving OpenRouter API key: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@settings_router.get("/openrouter-api-key")
async def check_openrouter_api_key(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    """Checks if the OpenRouter API key is set."""
    try:
        api_key = await api_key_manager.get_openrouter_api_key(current_user["id"])
        is_set = bool(api_key)
        masked_key = "*" * (len(api_key) - 4) + api_key[-4:] if is_set else None
        return {"isSet": is_set, "apiKey": masked_key}
    except Exception as e:
        logger.error(f"Error checking OpenRouter API key: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@settings_router.delete("/openrouter-api-key")
async def remove_openrouter_api_key(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(  # Added dependency
        get_agent_manager_store_dependency
    ),
):
    user_id = current_user["id"]
    try:
        await api_key_manager.remove_openrouter_api_key(user_id)
        await agent_manager_store_di.invalidate_user_managers(
            user_id
        )  # Added invalidation
        return {"message": "OpenRouter API key removed successfully"}
    except Exception as e:
        logger.error(f"Error removing OpenRouter API key for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@settings_router.post("/anthropic-api-key")
async def save_anthropic_api_key(
    api_key_update: AnthropicApiKeyUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    user_id = current_user["id"]
    try:
        await api_key_manager.save_anthropic_api_key(
            user_id, api_key_update.anthropicApiKey
        )
        await agent_manager_store_di.invalidate_user_managers(user_id)
        return {"message": "Anthropic API key saved successfully"}
    except Exception as e:
        logger.error(f"Error saving Anthropic API key for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@settings_router.get("/anthropic-api-key")
async def check_anthropic_api_key(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    user_id = current_user["id"]
    try:
        key = await api_key_manager.get_anthropic_api_key(user_id)
        return {
            "isSet": bool(key),
            "apiKey": "********" if key else None,  # Mask the key
        }
    except Exception as e:
        logger.error(f"Error checking Anthropic API key for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@settings_router.delete("/anthropic-api-key")
async def remove_anthropic_api_key(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    user_id = current_user["id"]
    try:
        await api_key_manager.remove_anthropic_api_key(user_id)
        await agent_manager_store_di.invalidate_user_managers(user_id)
        return {"message": "Anthropic API key removed successfully"}
    except Exception as e:
        logger.error(f"Error removing Anthropic API key for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@settings_router.post("/openai-api-key")
async def save_openai_api_key(
    api_key_update: OpenAIApiKeyUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    user_id = current_user["id"]
    try:
        await api_key_manager.save_openai_api_key(user_id, api_key_update.openAIApiKey)
        await agent_manager_store_di.invalidate_user_managers(user_id)
        return {"message": "OpenAI API key saved successfully"}
    except Exception as e:
        logger.error(f"Error saving OpenAI API key for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@settings_router.get("/openai-api-key")
async def check_openai_api_key(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    user_id = current_user["id"]
    try:
        key = await api_key_manager.get_openai_api_key(user_id)
        return {
            "isSet": bool(key),
            "apiKey": "********" if key else None,  # Mask the key
        }
    except Exception as e:
        logger.error(f"Error checking OpenAI API key for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@settings_router.delete("/openai-api-key")
async def remove_openai_api_key(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    user_id = current_user["id"]
    try:
        await api_key_manager.remove_openai_api_key(user_id)
        await agent_manager_store_di.invalidate_user_managers(user_id)
        return {"message": "OpenAI API key removed successfully"}
    except Exception as e:
        logger.error(f"Error removing OpenAI API key for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Endpoint to fetch OpenRouter models ---


@settings_router.get("/openrouter-models", response_model=List[OpenRouterModel])
async def get_openrouter_models(
    current_user: Dict[str, Any] = Depends(
        get_current_active_user
    ),  # Keep authentication
):
    """Fetches available models from OpenRouter API, excluding Gemini models."""
    OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(OPENROUTER_MODELS_URL)
            response.raise_for_status()  # Raise an exception for bad status codes
            all_models_data = response.json()

            # Filter out Gemini models (check ID or name)
            filtered_models = []
            if "data" in all_models_data and isinstance(all_models_data["data"], list):
                for model_data in all_models_data["data"]:
                    model_id = model_data.get("id", "").lower()
                    # Basic check, might need refinement based on actual OpenRouter IDs for Gemini
                    if "gemini" not in model_id:
                        try:
                            # Validate and append using the Pydantic model
                            # Only include models that pass validation
                            validated_model = OpenRouterModel.model_validate(model_data)
                            filtered_models.append(validated_model)
                        except ValidationError as e:
                            logger.warning(
                                f"Skipping model due to validation error: {model_data.get('id')}. Error: {e}"
                            )

            return filtered_models

    except httpx.RequestError as exc:
        logger.error(f"Error requesting OpenRouter models: {exc}")
        raise HTTPException(
            status_code=503, detail="Could not connect to model provider."
        )
    except httpx.HTTPStatusError as exc:
        logger.error(
            f"OpenRouter models request failed: Status {exc.response.status_code} - {exc.response.text}"
        )
        raise HTTPException(
            status_code=502, detail="Failed to retrieve models from provider."
        )
    except ValidationError as e:
        logger.error(f"Error validating OpenRouter model data: {e}", exc_info=True)
        # Return empty list or raise 500? Returning empty is safer for UI.
        # raise HTTPException(status_code=500, detail="Error processing model data from provider.")
        return []  # Return empty list if validation fails for any model
    except Exception as e:
        logger.error(f"Unexpected error fetching OpenRouter models: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error fetching models."
        )


# --- End OpenRouter Endpoints ---


@settings_router.get("/model")
async def get_model_settings(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    try:
        settings = await db_instance.get_model_settings(
            current_user["id"]
        )  # Access user ID from dict
        return settings
    except Exception as e:
        logger.error(f"Error fetching model settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@settings_router.post("/model")
async def save_model_settings(
    settings: ModelSettings,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),  # Inject store
):
    """Saves the user's model settings, preventing non-pro users from saving OpenRouter models."""
    user_id = current_user["id"]  # Access user ID from dict
    is_pro = (
        current_user.get("subscription_plan", "").lower() == "pro"
        and current_user.get("subscription_status", "").lower() == "active"
    )

    settings_dict = settings.model_dump()

    # --- Pro User Check for OpenRouter Models ---
    if not is_pro:
        for key, model_id in settings_dict.items():
            # Check fields that store model IDs
            if key in [
                "mainLLM",
                "checkLLM",
                "titleGenerationLLM",
                "extractionLLM",
                "knowledgeBaseQueryLLM",
            ]:
                if isinstance(model_id, str) and model_id.startswith("openrouter/"):
                    logger.warning(
                        f"Non-pro user {user_id} attempted to save OpenRouter model ID '{model_id}' in field '{key}'. Denying."
                    )
                    raise HTTPException(
                        status_code=403,  # Forbidden
                        detail=f"Saving OpenRouter models ({model_id}) requires a Pro subscription.",
                    )
    # --- End Pro User Check ---

    try:
        # Save settings to DB
        await db_instance.save_model_settings(
            user_id, settings_dict  # Save the validated dictionary
        )

        # --- ADDED: Invalidate existing managers for this user ---
        try:
            logger.info(
                f"Model settings updated for user {user_id[:8]}. Invalidating active AgentManagers."
            )
            await agent_manager_store_di.invalidate_user_managers(user_id)
        except Exception as invalidate_err:
            # Log the error but don't fail the request, saving settings is primary
            logger.error(
                f"Failed to invalidate managers for user {user_id[:8]} after settings change: {invalidate_err}",
                exc_info=True,
            )
        # --- END ADDED ---

        return {"message": "Model settings saved successfully"}
    except HTTPException as http_exc:  # Re-raise HTTP exceptions like 403
        raise http_exc
    except Exception as e:
        logger.error(
            f"Error saving model settings for user {user_id}: {str(e)}", exc_info=True
        )  # Log full traceback
        raise HTTPException(status_code=500, detail="Internal server error")


# Preset routes


@preset_router.post("")
async def create_preset(
    preset: PresetCreate,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        preset_id = await db_instance.create_preset(
            current_user["id"],
            project_id,
            preset.name,
            preset.data,  # Access user ID from dict
        )
        return {"id": preset_id, "name": preset.name, "data": preset.data}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error creating preset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@preset_router.get("")
async def get_presets(
    project_id: str,  # Added project_id path parameter
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    user_id = current_user["id"]
    try:
        # Remove project_id parameter from get_presets call
        presets = await db_instance.get_presets(
            user_id, project_id  # Pass project_id from path
        )
        return {"presets": presets}
    except Exception as e:
        logger.error(
            f"Error in GET /presets for project {project_id}: {str(e)}", exc_info=True
        )  # Log error details
        raise HTTPException(status_code=500, detail="Internal server error")


@preset_router.put("/{preset_id}")  # Changed from preset_name to preset_id
async def update_preset(
    preset_id: str,
    project_id: str,
    preset_update: PresetUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        user_id = current_user["id"]  # Access user ID from dict

        # Get all presets and find the one with matching ID
        all_presets = await db_instance.get_presets(user_id, project_id)
        existing_preset = next((p for p in all_presets if p["id"] == preset_id), None)

        if not existing_preset:
            raise HTTPException(status_code=404, detail="Preset not found")

        updated_data = preset_update.model_dump()
        success = await db_instance.update_preset(
            preset_id, user_id, project_id, updated_data
        )

        if not success:
            raise HTTPException(status_code=404, detail="Failed to update preset")

        return {
            "message": "Preset updated successfully",
            "id": preset_id,
            "name": updated_data.get("name", existing_preset["name"]),
            "data": updated_data.get("data", existing_preset["data"]),
        }
    except ValidationError as ve:
        # Handle validation errors specifically
        logger.error(f"Validation error updating preset: {ve}")
        raise HTTPException(status_code=422, detail=ve.errors())
    except Exception as e:
        logger.error(f"Error updating preset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@preset_router.get("/{preset_id}")
async def get_preset(
    preset_id: str,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # Remove project_id from get_preset_by_name call
        preset = await db_instance.get_preset_by_name(preset_id, user_id, project_id)
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        return preset
    except Exception as e:
        logger.error(f"Error getting preset: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@preset_router.delete("/{preset_id}")
async def delete_preset(
    preset_id: str,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # Remove project_id from delete_preset call
        deleted = await db_instance.delete_preset(preset_id, user_id, project_id)
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
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        universe_id = universe.get("universe_id")  # This can now be None
        updated_project = await db_instance.update_project_universe(
            project_id, universe_id, current_user["id"]  # Access user ID from dict
        )
        if not updated_project:
            raise HTTPException(status_code=404, detail="Project not found")
        return updated_project
    except Exception as e:
        logger.error(f"Error updating project universe: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@project_router.post("/", response_model=Dict[str, Any])
async def create_project(
    project: ProjectCreate,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        project_id = await db_instance.create_project(
            name=project.name,
            description=project.description,
            user_id=user_id,
            universe_id=project.universe_id,
        )

        # Fetch the created project to return its details
        new_project = await db_instance.get_project(project_id, user_id)
        if not new_project:
            raise HTTPException(
                status_code=404, detail="Project not found after creation"
            )

        return {"message": "Project created successfully", "project": new_project}
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@project_router.get("/")
async def get_projects(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # Get user's own projects
        projects = await db_instance.get_projects(user_id)

        # Add stats for each project
        for project in projects:
            stats = await get_project_stats(project["id"], user_id)
            project.update(stats)

        return {"projects": projects}
    except Exception as e:
        logger.error(f"Error getting projects: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@project_router.get("/{project_id}")
async def get_project(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        project = await db_instance.get_project(project_id, user_id)
        if project:
            # Add stats to the project
            stats = await get_project_stats(project_id, user_id)
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
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        updated_project = await db_instance.update_project(
            project_id,
            project.name,
            project.description,
            user_id,
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
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    user_id = current_user["id"]  # Access user ID from dict
    db_deleted = False
    vs_deleted = False
    error_message = ""

    try:
        # 1. Delete project and related data from the database
        db_deleted = await db_instance.delete_project(project_id, user_id)
        if not db_deleted:
            raise HTTPException(status_code=404, detail="Project not found in database")
        logger.info(f"Successfully deleted project {project_id} from database.")

        # 2. Delete the associated vector store collection
        try:
            # Need API key and embedding model to instantiate VectorStore
            api_key = await api_key_manager.get_api_key(user_id)
            model_settings = await db_instance.get_model_settings(user_id)
            # Provide default if settings are missing
            embedding_model = model_settings.get(
                "embeddingsModel", "models/gemini-embedding-001"
            )

            if not api_key:
                logger.error(
                    f"Cannot delete vector store for project {project_id}: API key not found for user {user_id}."
                )
                error_message = (
                    " (Warning: Vector store cleanup failed - API key missing)"
                )
            elif not embedding_model:
                logger.error(
                    f"Cannot delete vector store for project {project_id}: Embedding model not found for user {user_id}."
                )
                error_message = (
                    " (Warning: Vector store cleanup failed - Embedding model missing)"
                )
            else:
                vector_store = VectorStore(
                    user_id, project_id, api_key, embedding_model
                )
                vs_deleted = await vector_store.delete_collection()
                if vs_deleted:
                    logger.info(
                        f"Successfully deleted vector store collection for project {project_id}."
                    )
                else:
                    logger.warning(
                        f"Failed to delete vector store collection for project {project_id}."
                    )
                    error_message = " (Warning: Vector store cleanup failed)"
        except Exception as vs_error:
            logger.error(
                f"Error during vector store deletion for project {project_id}: {str(vs_error)}",
                exc_info=True,
            )
            error_message = f" (Warning: Vector store cleanup error: {str(vs_error)})"

        return {"message": f"Project deleted successfully{error_message}"}

    except HTTPException as http_exc:  # Re-raise HTTP exceptions (like 404)
        raise http_exc
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {str(e)}", exc_info=True)
        # Return 500 but indicate DB status if possible
        detail = f"Internal server error during project deletion: {str(e)}"
        if db_deleted:
            detail += (
                " (Database portion deleted, but vector store cleanup may have failed)"
            )
        raise HTTPException(status_code=500, detail=detail)


@project_router.put("/{project_id}/settings/architect")
async def update_architect_settings(
    project_id: str,
    settings: ArchitectSettingsUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    """Enables or disables Architect mode for a project (Pro users only for enabling)."""
    user_id = current_user["id"]
    is_pro = (
        current_user.get("subscription_plan", "").lower() == "pro"
        and current_user.get("subscription_status", "").lower() == "active"
    )

    # Check Pro status ONLY if enabling Architect mode
    if settings.enabled and not is_pro:
        logger.warning(
            f"Non-pro user {user_id} attempted to enable Architect mode for project {project_id}."
        )
        raise HTTPException(
            status_code=403,  # Forbidden
            detail="Architect mode requires a Pro subscription to enable.",
        )

    try:
        updated_project = await db_instance.update_project_architect_mode(
            project_id=project_id, user_id=user_id, enabled=settings.enabled
        )

        if not updated_project:
            raise HTTPException(
                status_code=404, detail="Project not found or not authorized."
            )

        action = "enabled" if settings.enabled else "disabled"
        return {
            "message": f"Architect mode successfully {action} for project {project_id}.",
            "project": updated_project,
        }

    except HTTPException as http_exc:
        raise http_exc  # Re-raise 403/404
    except Exception as e:
        logger.error(
            f"Error updating Architect settings for project {project_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error updating Architect settings."
        )


# --- NEW Endpoint: Get Generation Status ---
@project_router.get("/{project_id}/generation-status")
async def get_generation_status(
    project_id: str,
    current_user: Dict[str, Any] = Depends(
        get_current_active_user
    ),  # Ensure user owns project
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    # Verify user has access to the project (optional but good practice)
    user_id = current_user["id"]
    project = await db_instance.get_project(project_id, user_id)
    if not project:
        raise HTTPException(
            status_code=404, detail="Project not found or not authorized"
        )

    is_generating = await agent_manager_store_di.is_project_generating(project_id)
    status = GenerationStatus.RUNNING if is_generating else GenerationStatus.COMPLETED
    # Potentially add more details like current step if available
    return GenerationStatusResponse(
        status=status,
        message=f"Generation is {'running' if is_generating else 'not running'}.",
    )


@project_router.get("/{project_id}/generation-history")
async def get_generation_history(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    """Retrieves the generation history for a project."""
    user_id = current_user["id"]
    try:
        history = await db_instance.get_generation_history(project_id, user_id)
        return history
    except Exception as e:
        logger.error(
            f"Error getting generation history for project {project_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve generation history"
        )


@project_router.get(
    "/{project_id}/structure", response_model=Optional[ProjectStructureResponse]
)
async def get_project_structure(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    """
    Retrieves the hierarchical structure of a project, ensuring data consistency.

    This endpoint performs several self-healing operations:
    1.  Converts legacy list-based structures to the new dictionary format.
    2.  Finds any "orphaned" chapters (existing in the DB but not in the
        structure) and appends them to the root of the structure.
    3.  If no structure exists at all, it builds a new one from all existing
        chapters for the project.
    """
    user_id = current_user["id"]

    # Verify user has access to the project
    project = await db_instance.get_project(project_id=project_id, user_id=user_id)
    if not project:
        raise HTTPException(
            status_code=404, detail="Project not found or not authorized"
        )

    structure_data = await db_instance.get_project_structure(
        project_id=project_id, user_id=user_id
    )

    final_structure_list = None

    # Step 1: Handle different formats of stored structure data (list vs. dict)
    if isinstance(structure_data, dict):
        final_structure_list = structure_data.get("project_structure")
    elif isinstance(structure_data, list):
        logger.warning(
            f"Project {project_id} has old list-based structure. Converting and saving."
        )
        final_structure_list = structure_data
        # Self-heal: update the structure in the DB to the new format
        await db_instance.update_project_structure(
            project_id=project_id, structure=final_structure_list, user_id=user_id
        )

    # Step 2: Reconcile orphaned chapters if a structure already exists
    if final_structure_list is not None:
        all_db_chapters = await db_instance.get_all_chapters(
            user_id=user_id, project_id=project_id
        )
        all_db_chapter_ids = {str(ch["id"]) for ch in all_db_chapters}

        def get_ids_from_structure(items: List[Dict[str, Any]]) -> Set[str]:
            ids = set()
            for item in items:
                if item.get("type") == "chapter":
                    ids.add(str(item.get("id")))
                elif item.get("type") == "folder" and "children" in item:
                    ids.update(get_ids_from_structure(item.get("children", [])))
            return ids

        ids_in_structure = get_ids_from_structure(final_structure_list)
        orphaned_chapter_ids = all_db_chapter_ids - ids_in_structure

        if orphaned_chapter_ids:
            logger.warning(
                f"Found {len(orphaned_chapter_ids)} orphaned chapters for project {project_id}. Re-adding to structure."
            )
            orphaned_chapters_details = [
                ch for ch in all_db_chapters if str(ch["id"]) in orphaned_chapter_ids
            ]
            new_items_to_append = [
                {"id": str(ch["id"]), "type": "chapter", "title": ch["title"]}
                for ch in orphaned_chapters_details
            ]
            final_structure_list.extend(new_items_to_append)

            # Save the reconciled structure
            await db_instance.update_project_structure(
                project_id=project_id, structure=final_structure_list, user_id=user_id
            )

    # Step 3: If no structure exists after all checks, build it from scratch
    if not final_structure_list:
        logger.warning(
            f"Project structure not found or is empty for project {project_id}. Building from chapters."
        )
        all_db_chapters = await db_instance.get_all_chapters(
            user_id=user_id, project_id=project_id
        )
        final_structure_list = [
            {"id": str(ch["id"]), "type": "chapter", "title": ch["title"]}
            for ch in all_db_chapters
        ]
        if final_structure_list:  # Only save if chapters were found
            # Self-heal: create and save the new structure
            await db_instance.update_project_structure(
                project_id=project_id, structure=final_structure_list, user_id=user_id
            )

    # Ensure consistency between 'name' and 'title' fields for validation
    # This fixes issues with the architect agent using 'name' instead of 'title'
    if final_structure_list:

        def add_title_if_missing(items: List[Dict[str, Any]]):
            for item in items:
                if "name" in item and "title" not in item:
                    item["title"] = item["name"]
                if item.get("children"):
                    add_title_if_missing(item["children"])

        add_title_if_missing(final_structure_list)

    return {"project_structure": final_structure_list}


@project_router.post(
    "/{project_id}/proactive-assist",
    response_model=ProactiveSuggestionsResponse,
    summary="Get Proactive AI Writing Suggestions",
    description="Provides real-time writing suggestions based on recent chapter content and a user's notepad.",
    tags=["Projects", "AI"],
)
async def proactive_assist_endpoint(
    project_id: str,
    request_body: ProactiveAssistRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    """
    Handles requests for proactive AI writing assistance.

    This endpoint leverages the project's context, including recent chapters and
    a notepad, to generate relevant suggestions for the user, such as plot continuations,
    dialogue ideas, or descriptive enhancements.
    """
    user_id = current_user["id"]

    try:
        async with agent_manager_store_di.get_or_create_manager(
            user_id, project_id
        ) as manager:
            # Call the agent manager method to get suggestions
            suggestions_response = await manager.get_proactive_suggestions(
                recent_chapters_content=request_body.recent_chapters_content,
                notepad_content=request_body.notepad_content,
            )
            return suggestions_response
    except Exception as e:
        logger.error(
            f"Error during proactive assist for project {project_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while generating proactive suggestions: {str(e)}",
        )


@project_router.put("/{project_id}/structure", response_model=ProjectStructureResponse)
async def update_project_structure(
    project_id: str,
    structure_request: ProjectStructureUpdateRequest = Body(
        ...
    ),  # Changed variable name for clarity
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),  # Inject store
):
    """Updates the project's hierarchical structure (acts, stages, substages, chapters)."""
    user_id = current_user["id"]

    # Convert Pydantic models from request to a list of dictionaries for manipulation.
    structure_list = [item.model_dump() for item in structure_request.project_structure]

    try:
        # Save the new structure to the database.
        await db_instance.update_project_structure(
            project_id=project_id,
            structure=structure_list,
            user_id=user_id,
        )

        # Recursively add 'title' field from 'name' if it's missing to ensure
        # the response is valid. This handles requests from agents that may only send 'name'.
        def add_title_if_missing(items: List[Dict[str, Any]]):
            for item in items:
                if "name" in item and "title" not in item:
                    item["title"] = item["name"]
                if item.get("children"):
                    add_title_if_missing(item["children"])

        add_title_if_missing(structure_list)

        # FastAPI will automatically use this dictionary to build the ProjectStructureResponse
        return {"project_structure": structure_list}

    except Exception as e:
        logger.error(
            f"Error updating project structure for project {project_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update project structure.",
        )


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

        # Database health check (checks SQLAlchemy connection)
        # For now, just check local DB init status

        return JSONResponse(
            status_code=200,
            content={"status": "healthy", "message": "Server is running"},
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=500, content={"status": "error", "message": str(e)}
        )


# Removed /shutdown endpoint and graceful_shutdown function
# Removed signal handlers (Uvicorn/platform handles signals)

# --- CRUD for Relationships, Events, Locations, Connections ---
# These need review similar to Chapter/Codex CRUD:


@relationship_router.post("/")
async def create_relationship(
    project_id: str,  # Make project_id a path parameter
    data: Dict[str, Any] = Body(...),  # Accept request body as a dictionary
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
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
            description=data.get("description", "") or data["relationship_type"],
        )

        # Add to knowledge base
        async with agent_manager_store_di.get_or_create_manager(
            user_id, project_id
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
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        relationships = await db_instance.get_character_relationships(
            project_id, current_user["id"]  # Access user ID from dict
        )
        return {"relationships": relationships}
    except Exception as e:
        logger.error(f"Error fetching relationships: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@relationship_router.put("/{relationship_id}")
async def update_relationship(
    relationship_id: str,
    project_id: str,
    relationship_data: RelationshipUpdate,  # Use the Pydantic model for validation
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        logger.info(
            f"Attempting to update relationship {relationship_id} for user {user_id} in project {project_id}"
        )

        # Update in database using validated data
        logger.debug("Updating relationship in database...")
        await db_instance.update_character_relationship(
            relationship_id,  # 1
            relationship_data.relationship_type,  # 2
            relationship_data.description,  # 3
            user_id,  # 4 (Corrected from project_id)
            project_id,  # 5 (Corrected from user_id)
        )
        logger.debug("Database update successful.")

        # Update in knowledge base
        logger.debug("Updating relationship in knowledge base...")
        async with agent_manager_store.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            # Determine content: use description if present, otherwise type
            new_content = (
                relationship_data.description or relationship_data.relationship_type
            )
            # Prepare metadata
            new_metadata = {
                "relationship_type": relationship_data.relationship_type,
                "type": "relationship",
                # Add other relevant metadata if needed
            }
            await agent_manager.update_or_remove_from_knowledge_base(
                {
                    "item_id": relationship_id,
                    "item_type": "relationship",
                },  # Assuming this identifier is correct
                "update",
                new_content=new_content,
                new_metadata=new_metadata,
            )
        logger.debug("Knowledge base update successful.")
        logger.info(f"Successfully updated relationship {relationship_id}")
        return {"message": "Relationship updated successfully"}
    except HTTPException:  # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(
            f"Error updating relationship {relationship_id}: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to update relationship: {str(e)}"
        )


@relationship_router.delete("/{relationship_id}")
async def delete_relationship(
    relationship_id: str,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # Delete from database - fix parameter order to match the database method
        success = await db_instance.delete_character_relationship(
            relationship_id,
            user_id,
            project_id,  # Correct order: relationship_id, user_id, project_id
        )

        if not success:
            raise HTTPException(status_code=404, detail="Relationship not found")

        # Delete from knowledge base
        async with agent_manager_store_di.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": relationship_id, "item_type": "relationship"}, "delete"
            )
        return {"message": "Relationship deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting relationship: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@relationship_router.post("/analyze")  # This is the correct analyze route
async def analyze_relationships(
    project_id: str,
    character_ids: List[str] = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        async with agent_manager_store_di.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            # Get only the selected characters
            characters = []
            for char_id in character_ids:
                character = await db_instance.get_characters(
                    user_id, project_id, character_id=char_id
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
    connection_data: EventConnectionCreate = Body(...),  # Expect JSON body
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    """Create a new connection between two events."""
    user_id = current_user["id"]
    logger.info(
        f"Received request to create event connection for project {project_id} by user {user_id}"
    )
    logger.debug(f"Connection data received: {connection_data}")

    try:
        # Ensure both events exist (optional but good practice)
        event1 = await db_instance.get_event_by_id(
            connection_data.event1_id, user_id, project_id
        )
        event2 = await db_instance.get_event_by_id(
            connection_data.event2_id, user_id, project_id
        )
        if not event1 or not event2:
            raise HTTPException(status_code=404, detail="One or both events not found")

        connection_id = await db_instance.create_event_connection(
            event1_id=connection_data.event1_id,
            event2_id=connection_data.event2_id,
            connection_type=connection_data.connection_type,
            description=connection_data.description,
            impact=connection_data.impact,
            project_id=project_id,
            user_id=user_id,
        )
        logger.info(
            f"Successfully created event connection {connection_id} for project {project_id}"
        )
        return {"id": connection_id}
    except ValueError as ve:
        logger.warning(
            f"Value error creating event connection for project {project_id}: {ve}"
        )
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(
            f"Error creating event connection for project {project_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to create event connection")


@event_router.put("/connections/{connection_id}")
async def update_event_connection(
    connection_id: str,
    project_id: str,
    connection_data: EventConnectionUpdate = Body(
        ...
    ),  # Assuming EventConnectionUpdate exists or create it
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    """Update an existing event connection."""
    user_id = current_user["id"]
    logger.info(
        f"Received request to update event connection {connection_id} for project {project_id} by user {user_id}"
    )
    logger.debug(f"Update data received: {connection_data}")

    try:
        updated_connection = await db_instance.update_event_connection(
            connection_id=connection_id,
            connection_type=connection_data.connection_type,
            description=connection_data.description,
            impact=connection_data.impact,
            user_id=user_id,
            project_id=project_id,
        )
        if not updated_connection:
            raise HTTPException(status_code=404, detail="Event connection not found")
        logger.info(
            f"Successfully updated event connection {connection_id} for project {project_id}"
        )
        return updated_connection
    except HTTPException:  # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            f"Error updating event connection {connection_id} for project {project_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to update event connection")


@event_router.delete("/connections/{connection_id}")
async def delete_event_connection(
    connection_id: str,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # Delete from database
        success = await db_instance.delete_event_connection(
            connection_id, user_id, project_id
        )

        # Delete from knowledge base
        async with agent_manager_store_di.get_or_create_manager(
            user_id, project_id
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
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        connections = await db_instance.get_event_connections(
            project_id, current_user["id"]  # Access user ID from dict
        )
        # Return the list directly
        return connections
    except Exception as e:
        logger.error(f"Error fetching event connections: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Update analyze event connections to save to knowledge base
@event_router.post("/analyze-connections")  # This is the correct analyze route
async def analyze_event_connections(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        async with agent_manager_store_di.get_or_create_manager(
            user_id, project_id
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
    connection_data: LocationConnectionCreate = Body(...),  # Expect JSON body
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict

        # Fetch location names
        loc1 = await db_instance.get_location_by_id(
            connection_data.location1_id, user_id, project_id
        )
        loc2 = await db_instance.get_location_by_id(
            connection_data.location2_id, user_id, project_id
        )

        if not loc1 or not loc2:
            raise HTTPException(
                status_code=404, detail="One or both locations not found"
            )

        # Create in database using data from the model and fetched names
        connection_id = await db_instance.create_location_connection(
            location1_id=connection_data.location1_id,
            location2_id=connection_data.location2_id,
            location1_name=loc1["name"],  # Pass fetched name
            location2_name=loc2["name"],  # Pass fetched name
            connection_type=connection_data.connection_type,
            description=connection_data.description,
            travel_route=connection_data.travel_route,
            cultural_exchange=connection_data.cultural_exchange,
            project_id=project_id,
            user_id=user_id,
        )

        # Add to knowledge base
        content = f"Connection between locations: {connection_data.description}"
        if connection_data.travel_route:
            content += f"\nTravel Route: {connection_data.travel_route}"
        if connection_data.cultural_exchange:
            content += f"\nCultural Exchange: {connection_data.cultural_exchange}"

        async with agent_manager_store_di.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            await agent_manager.add_to_knowledge_base(
                "location_connection",
                content,
                {
                    "id": connection_id,
                    "location1_id": connection_data.location1_id,
                    "location2_id": connection_data.location2_id,
                    "type": "location_connection",
                    "connection_type": connection_data.connection_type,
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
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # Update in database
        updated = await db_instance.update_location_connection(
            connection_id=connection_id,
            connection_type=connection_type,
            description=description,
            travel_route=travel_route,
            cultural_exchange=cultural_exchange,
            user_id=user_id,
            project_id=project_id,
        )

        # Update in knowledge base
        content = f"Connection between locations: {description}"
        if travel_route:
            content += f"\nTravel Route: {travel_route}"
        if cultural_exchange:
            content += f"\nCultural Exchange: {cultural_exchange}"

        async with agent_manager_store_di.get_or_create_manager(
            user_id, project_id
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
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # Delete from database
        success = await db_instance.delete_location_connection(
            connection_id, user_id, project_id
        )
        if not success:
            raise HTTPException(status_code=404, detail="Connection not found")

        # Delete from knowledge base
        async with agent_manager_store_di.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": connection_id, "item_type": "location_connection"}, "delete"
            )
            # Delete any associated connections (This logic seems correct here)
            connections = await db_instance.get_location_connections(
                project_id, user_id
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


@location_router.post("/analyze-connections")  # This is the correct analyze route
async def analyze_location_connections(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        locations = await db_instance.get_locations(user_id, project_id)
        if not locations or len(locations) < 2:
            return JSONResponse(
                {"message": "Not enough locations to analyze connections", "skip": True}
            )

        async with agent_manager_store_di.get_or_create_manager(
            user_id, project_id
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
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # Create in database
        event_id = await db_instance.create_event(
            title=event_data["title"],
            description=event_data["description"],
            date=datetime.fromisoformat(event_data["date"]),
            character_id=event_data.get("character_id"),
            location_id=event_data.get("location_id"),
            project_id=project_id,
            user_id=user_id,
        )

        # Add to knowledge base
        async with agent_manager_store.get_or_create_manager(
            user_id, project_id
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
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        events = await db_instance.get_events(
            project_id, current_user["id"]
        )  # Access user ID from dict
        # Return the list directly
        return events
    except Exception as e:
        logger.error(f"Error getting events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@knowledge_base_router.post("/batch")
async def batch_upload_files(
    request: Request,
    project_id: str,
    files: List[UploadFile] = File(...),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    agent_manager_store_di: AgentManagerStore = Depends(
        get_agent_manager_store_dependency
    ),
):
    """
    Upload multiple files to the knowledge base.

    This endpoint allows batch uploading of files to be processed and added to the vector store.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    # Initialize result tracking
    results = {
        "message": f"Processed {len(files)} files",
        "successful": 0,
        "failed": 0,
        "items": [],
    }

    user_id = current_user["id"]

    async with agent_manager_store_di.get_or_create_manager(
        user_id, project_id
    ) as agent_manager:

        # Process each file
        for file in files:
            item_result = {"filename": file.filename, "success": False}

            try:
                # Similar logic to single file upload
                file_content = await file.read()

                # Basic check to prevent empty files
                if not file_content:
                    item_result["error"] = "File is empty"
                    results["items"].append(item_result)
                    results["failed"] += 1
                    continue

                # Get file extension to determine type
                filename = file.filename
                content_type = file.content_type or "application/octet-stream"

                # Extract text using agent_manager
                text_content = await agent_manager.extract_text_from_bytes(
                    file_content, content_type
                )

                if not text_content:
                    item_result["error"] = (
                        f"Could not extract text from file (type: {content_type})"
                    )
                    results["items"].append(item_result)
                    results["failed"] += 1
                    continue

                # Prepare metadata
                metadata = {
                    "source": filename,
                    "type": "uploaded_file",
                    "file_type": content_type,
                    "id": str(uuid.uuid4()),
                    "size": len(file_content),
                    "batch_upload": True,
                }

                # Add to vector store
                embedding_id = await agent_manager.add_to_knowledge_base(
                    content_type="uploaded_file",
                    content=text_content,
                    metadata=metadata,
                )

                if not embedding_id:
                    item_result["error"] = "Failed to create embedding"
                    results["items"].append(item_result)
                    results["failed"] += 1
                    continue

                # Store in database
                db_item_id = await db_instance.create_knowledge_base_item(
                    user_id=user_id,
                    project_id=project_id,
                    type="uploaded_file",
                    item_metadata=metadata,
                    source=filename,
                    content=text_content[:1000]
                    + ("..." if len(text_content) > 1000 else ""),
                    embedding_id=embedding_id,
                )

                # Record successful processing
                item_result["success"] = True
                item_result["id"] = db_item_id
                item_result["embedding_id"] = embedding_id
                results["successful"] += 1

            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {str(e)}")
                item_result["error"] = str(e)
                results["failed"] += 1

            # Add result for this file
            results["items"].append(item_result)

    # Return overall results
    return results


@event_router.get("/{event_id}")
async def get_event(
    event_id: str,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        event = await db_instance.get_event_by_id(
            event_id, current_user["id"], project_id
        )  # Access user ID from dict
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
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # Update in database
        await db_instance.update_event(
            event_id=event_id,
            title=event_data["title"],
            description=event_data["description"],
            date=datetime.fromisoformat(event_data["date"]),
            character_id=event_data.get("character_id"),
            location_id=event_data.get("location_id"),
            project_id=project_id,
            user_id=user_id,
        )

        # Update in knowledge base
        async with agent_manager_store.get_or_create_manager(
            user_id, project_id
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
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # Delete from database
        success = await db_instance.delete_event(event_id, user_id, project_id)
        if not success:
            raise HTTPException(status_code=404, detail="Event not found")

        # Delete from knowledge base
        async with agent_manager_store.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": event_id, "item_type": "event"}, "delete"
            )
        return {"message": "Event deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@event_router.post("/analyze-chapter")  # This is the correct analyze route
async def analyze_chapter_events(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        async with agent_manager_store.get_or_create_manager(
            user_id, project_id
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
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        locations = await db_instance.get_locations(
            current_user["id"], project_id
        )  # Access user ID from dict
        # Return the list directly
        return locations
    except Exception as e:
        logger.error(f"Error getting locations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@location_router.post("")
async def create_location(
    project_id: str,
    location_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        location_id = await db_instance.create_location(
            name=location_data["name"],
            description=location_data["description"],
            coordinates=location_data.get("coordinates"),
            user_id=current_user["id"],  # Access user ID from dict
            project_id=project_id,
        )
        return {"id": location_id}
    except Exception as e:
        logger.error(f"Error creating location: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@location_router.get("/connections")
async def get_location_connections(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):

    try:
        connections = await db_instance.get_location_connections(
            project_id, current_user["id"]  # Access user ID from dict
        )

        # Return the list directly
        return connections
    except Exception as e:
        # Restore logger for the error
        logger.error(f"Error fetching location connections: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@location_router.get("/{location_id}")
async def get_location(
    location_id: str,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        location = await db_instance.get_location_by_id(
            location_id, current_user["id"], project_id  # Access user ID from dict
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
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # Update in database
        await db_instance.update_location(
            location_id=location_id,
            name=location_data["name"],
            description=location_data["description"],
            project_id=project_id,  # Assuming update_location needs project_id
            user_id=user_id,  # Assuming update_location needs user_id
            location_data=location_data,  # Pass the whole dict if needed by update_location
        )

        # Update in knowledge base
        async with agent_manager_store.get_or_create_manager(
            user_id, project_id
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
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # Delete from database
        success = await db_instance.delete_location(location_id, project_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Location not found")

        # Delete from knowledge base
        async with agent_manager_store.get_or_create_manager(
            user_id, project_id
        ) as agent_manager:
            await agent_manager.update_or_remove_from_knowledge_base(
                {"item_id": location_id, "item_type": "location"}, "delete"
            )
            # Delete any associated connections (This logic seems correct here)
            connections = await db_instance.get_location_connections(
                project_id, user_id
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


# --- Validity Check Endpoints ---
@validity_router.get("/")
async def get_validity_checks(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        validity_checks = await db_instance.get_all_validity_checks(
            current_user["id"], project_id  # Access user ID from dict
        )
        # Return the list directly to match frontend expectation
        return validity_checks
    except Exception as e:
        logger.error(f"Error fetching validity checks: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@validity_router.delete("/{check_id}")
async def delete_validity_check(
    check_id: str,
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),  # Use Dict
):
    try:
        user_id = current_user["id"]  # Access user ID from dict
        # Validity checks likely don't have separate KB entries, just delete from DB
        result = await db_instance.delete_validity_check(check_id, user_id, project_id)
        if result:
            return {"message": "Validity check deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Validity check not found")
    except Exception as e:
        logger.error(
            f"Error deleting validity check {check_id}: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error")


# --- User Endpoints ---
@user_router.get("/me", response_model=Dict[str, Any])
async def get_current_user_details(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    """Returns details for the currently authenticated user."""
    # The current_user dictionary already contains the DB user details
    # including email, id, and potentially subscription info from Paddle.
    logger.info(f"Fetching details for user ID: {current_user.get('id')}")
    return current_user


@user_router.put("/me/onboarding-complete")
async def mark_onboarding_complete(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    """Marks the current user's onboarding as completed."""
    user_id = current_user["id"]
    logger.info(f"Marking onboarding complete for user ID: {user_id}")
    try:
        async with db_instance.Session() as session:
            stmt = (
                update(User)
                .where(User.id == user_id)
                .values(has_completed_onboarding=True, updated_at=func.now())
            )
            result = await session.execute(stmt)
            await session.commit()

            if result.rowcount == 0:
                logger.warning(
                    f"Attempted to mark onboarding complete for non-existent user: {user_id}"
                )
                raise HTTPException(status_code=404, detail="User not found")

            logger.info(
                f"Successfully marked onboarding complete for user ID: {user_id}"
            )
            return {"message": "Onboarding marked as complete."}

    except Exception as e:
        logger.error(
            f"Error marking onboarding complete for user {user_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="Failed to update onboarding status."
        )


# --- Include Routers ---
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(chapter_router, prefix="/projects/{project_id}")
app.include_router(codex_item_router, prefix="/projects/{project_id}")
app.include_router(event_router, prefix="/projects/{project_id}")
app.include_router(
    knowledge_base_router,
    prefix="/projects/{project_id}/knowledge-base",
)
app.include_router(settings_router)
app.include_router(preset_router, prefix="/projects/{project_id}")
app.include_router(universe_router)
app.include_router(codex_router, prefix="/projects/{project_id}")
app.include_router(relationship_router, prefix="/projects/{project_id}")
app.include_router(project_router)
app.include_router(validity_router, prefix="/projects/{project_id}/validity")
app.include_router(location_router, prefix="/projects/{project_id}/locations")
app.include_router(architect_router)

# --- Uvicorn Runner ---
if __name__ == "__main__":
    try:
        import uvicorn

        app_instance = app

        # Use 0.0.0.0 to listen on all available network interfaces, necessary for containers
        config = uvicorn.Config(
            app_instance,
            host="0.0.0.0",
            port=8080,  # Port can be configured via env var if needed
            log_level="debug",  # Log level can be controlled via setup_logging now
            reload=False,  # Disable reload for production/stable runs
            workers=int(
                os.getenv("UVICORN_WORKERS", 1)
            ),  # Allow configuring workers via env var
        )
        server = uvicorn.Server(config)

        # Removed signal handlers here, Uvicorn handles them by default

        logger.info(
            f"Starting Uvicorn server on 0.0.0.0:8080 with {config.workers} worker(s)..."
        )
        server.run()

    except Exception as e:
        # Use logger if setup succeeded, otherwise print
        try:
            logger.critical(f"Server failed to start: {str(e)}", exc_info=True)
        except NameError:  # If logger setup failed very early
            print(f"CRITICAL: Server failed to start: {str(e)}", file=sys.stderr)
        sys.exit(1)

# backend/agent_manager.py
import os
from typing import Dict, Any, List, Tuple, Optional, Union, TypedDict
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.output_parsers import PydanticOutputParser, JsonOutputParser
from langchain.docstore.document import Document
from datetime import datetime, timedelta
import logging
from cachetools import TTLCache
import json
import asyncio
from asyncio import Lock
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from google.api_core.exceptions import ResourceExhausted # Import for rate limit errors
from langgraph.graph import StateGraph, END
from langchain.chains.summarize import load_summarize_chain
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLiteCache
from langchain.output_parsers import OutputFixingParser
from pydantic import BaseModel, Field, ValidationError
from datetime import timezone
from api_key_manager import ApiKeyManager
from database import db_instance
from vector_store import VectorStore
from models import (
    ChapterValidation, CodexItem, WorldbuildingSubtype, CodexItemType, CodexExtractionTypes,
    CodexItem, CharacterBackstoryExtraction, RelationshipAnalysis, EventDescription,
    RelationshipAnalysisList, EventAnalysis, LocationConnection, LocationConnectionAnalysis,
    LocationAnalysis, LocationAnalysisList, EventConnection, EventConnectionAnalysis
)

# Load environment variables
load_dotenv()

# --- Constants ---
PROCESS_TYPES = {
    'BACKSTORY': 'backstory',
    'RELATIONSHIPS': 'relationships',
    'LOCATIONS': 'locations',
    'EVENTS': 'events',
}

# Gemini API Limits (adjust based on your plan - Pay-as-you-go recommended)
# Using conservative Pay-as-you-go limits for Pro 1.5
GEMINI_PRO_RPM = 60
GEMINI_PRO_TPM = 2_000_000 # 2 Million Tokens Per Minute
GEMINI_PRO_RPD = 10000 # Example, might be higher

# Using conservative Pay-as-you-go limits for Flash 1.5
GEMINI_FLASH_RPM = 60
GEMINI_FLASH_TPM = 2_000_000
GEMINI_FLASH_RPD = 10000 # Example, might be higher

# --- Rate Limiter ---
class StreamingRateLimiter(BaseCallbackHandler):
    """More robust rate limiter for async LLM calls."""
    def __init__(self, rpm_limit: int, tpm_limit: int, rpd_limit: int):
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        self.rpd_limit = rpd_limit

        self._minute_timestamps: List[datetime] = []
        self._day_timestamps: List[datetime] = []
        self._token_counts: List[Tuple[datetime, int]] = []
        self._lock = asyncio.Lock()

    async def _prune_timestamps(self):
        """Remove timestamps older than their respective limits."""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        day_ago = now - timedelta(days=1)

        self._minute_timestamps = [t for t in self._minute_timestamps if t > minute_ago]
        self._day_timestamps = [t for t in self._day_timestamps if t > day_ago]
        self._token_counts = [(t, c) for t, c in self._token_counts if t > minute_ago]

    async def _wait_if_needed(self, tokens_to_add: int):
        while True:
            async with self._lock:
                await self._prune_timestamps()
                now = datetime.now()

                # Check RPM
                if len(self._minute_timestamps) >= self.rpm_limit:
                    wait_rpm = (self._minute_timestamps[0] + timedelta(minutes=1) - now).total_seconds()
                else:
                    wait_rpm = 0

                # Check TPM
                current_minute_tokens = sum(count for ts, count in self._token_counts)
                if current_minute_tokens + tokens_to_add > self.tpm_limit:
                    # Estimate wait time based on oldest token count entry
                    if self._token_counts:
                        wait_tpm = (self._token_counts[0][0] + timedelta(minutes=1) - now).total_seconds()
                    else:
                        wait_tpm = 60 # Wait a full minute if list is empty but limit exceeded (unlikely)
                else:
                    wait_tpm = 0

                # Check RPD
                if len(self._day_timestamps) >= self.rpd_limit:
                    wait_rpd = (self._day_timestamps[0] + timedelta(days=1) - now).total_seconds()
                else:
                    wait_rpd = 0

                wait_time = max(wait_rpm, wait_tpm, wait_rpd)

                if wait_time <= 0:
                    # Add current request/tokens if limits not hit
                    self._minute_timestamps.append(now)
                    self._day_timestamps.append(now)
                    self._token_counts.append((now, tokens_to_add))
                    return # Exit loop, ready to proceed

            # Wait outside the lock
            if wait_time > 0:
                logging.getLogger(__name__).debug(f"Rate limiting: waiting for {wait_time:.2f} seconds.")
                await asyncio.sleep(wait_time + 0.1) # Add small buffer

    async def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        """Run when LLM starts."""
        # Estimate tokens based on prompt lengths (approximation)
        num_tokens = sum(len(p.split()) for p in prompts) # Crude token estimate
        await self._wait_if_needed(num_tokens)

    async def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        **kwargs: Any,
    ) -> None:
        """Run when Chat Model starts."""
        # Estimate tokens based on message content (approximation)
        num_tokens = 0
        for msg_list in messages:
            for msg in msg_list:
                if isinstance(msg.content, str):
                    num_tokens += len(msg.content.split())
                # Add handling for other content types if needed
        await self._wait_if_needed(num_tokens)

    # on_llm_new_token can be intensive, maybe limit based on start call only?
    # async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
    #     """Run on new LLM token. Minimal token counting for streaming."""
    #     # This can be noisy and potentially slow down streaming
    #     # Consider if tracking per-token is strictly necessary vs. just on_llm_start
    #     # await self._wait_if_needed(1)
    #     pass

# --- Pydantic Models (Minor Adjustments if needed) ---
# Assuming models from the original file are mostly correct.
# Added some missing ones for clarity.

class CodexExtraction(BaseModel):
    new_items: List[CodexItem] = Field(default_factory=list, description="List of new codex items found in the chapter")

# --- LangGraph State ---

class ChapterGenerationState(TypedDict):
    # Inputs
    user_id: str
    project_id: str
    chapter_number: int
    plot: str
    writing_style: str
    instructions: Dict[str, Any]

    # Dynamic values
    llm: ChatGoogleGenerativeAI # Main LLM
    check_llm: ChatGoogleGenerativeAI # LLM for validation/extraction
    vector_store: VectorStore
    summarize_chain: Any # Type hint could be improved

    # Intermediate results
    context: Optional[str] = None
    initial_chapter_content: Optional[str] = None
    extended_chapter_content: Optional[str] = None # Store extension result separately
    current_word_count: int = 0
    target_word_count: int = 0
    chapter_title: Optional[str] = None
    new_codex_items: Optional[List[Dict[str, Any]]] = None
    validity_check: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    # Final output (assembled at the end)
    final_chapter_content: Optional[str] = None
    final_output: Optional[Dict[str, Any]] = None


# --- Agent Manager ---

agent_managers: Dict[Tuple[str, str], 'AgentManager'] = {}

class AgentManager:
    _llm_cache = TTLCache(maxsize=100, ttl=3600)  # Class-level cache for LLM instances
    _graph_cache = {} # Cache for compiled graphs per project

    def __init__(self, user_id: str, project_id: str, api_key_manager: ApiKeyManager):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG) # Set higher level in production
        self.user_id = user_id
        self.project_id = project_id
        self.api_key_manager = api_key_manager
        self.model_settings = None
        self.MAX_INPUT_TOKENS = None
        self.MAX_OUTPUT_TOKENS = 8192 # Standard for Gemini
        self.vector_store = None
        self.summarize_chain = None
        self.agents = {} # Keep for potential future non-graph agents
        self._lock = Lock() # Lock for managing shared resources like caches
        self.chapter_generation_graph = None # Compiled LangGraph

    @classmethod
    async def create(cls, user_id: str, project_id: str, api_key_manager: ApiKeyManager) -> 'AgentManager':
        """Factory method to create and initialize AgentManager asynchronously."""
        key = (user_id, project_id)
        if key in agent_managers:
            return agent_managers[key]

        instance = cls(user_id, project_id, api_key_manager)
        await instance.initialize()
        agent_managers[key] = instance
        return instance

    async def initialize(self):
        """Initializes resources like API keys, LLMs, VectorStore, and the graph."""
        self.logger.info(f"Initializing AgentManager for User: {self.user_id[:8]}, Project: {self.project_id[:8]}")
        try:
            self.api_key = await self._get_api_key()
            self.model_settings = await self._get_model_settings() # Changed to async

            # Determine token limits based on model type (simplified)
            is_pro_model = 'pro' in self.model_settings.get('mainLLM', '')
            self.MAX_INPUT_TOKENS = 2_097_152 if is_pro_model else 1_048_576 # Gemini 1.5 limits

            self.setup_caching() # Setup global LLM caching

            # Initialize LLMs (using shared cache via _get_llm)
            self.llm = await self._get_llm(self.model_settings['mainLLM'])
            self.check_llm = await self._get_llm(self.model_settings['checkLLM'])

            # Initialize Vector Store
            self.vector_store = VectorStore(
                self.user_id,
                self.project_id,
                self.api_key,
                self.model_settings['embeddingsModel']
            )
            self.vector_store.set_llm(self.llm) # Pass LLM if needed by VS

            # Initialize Summarize Chain
            self.summarize_chain = load_summarize_chain(self.llm, chain_type="map_reduce")

            # Build and compile the chapter generation graph
            self.chapter_generation_graph = self._build_chapter_generation_graph()

            self.logger.info(f"AgentManager Initialized for User: {self.user_id[:8]}, Project: {self.project_id[:8]}")

        except Exception as e:
            self.logger.error(f"Failed to initialize AgentManager: {e}", exc_info=True)
            raise # Re-raise exception to indicate initialization failure

    async def close(self):
        """Cleans up resources like vector store connections."""
        self.logger.info(f"Closing AgentManager for User: {self.user_id[:8]}, Project: {self.project_id[:8]}")
        # Clear LLM cache entries specific to this manager if needed (though TTLCache handles expiry)
        # self._llm_cache.clear() # Or selectively remove keys

        if self.vector_store:
            try:
                # Process any pending batched items before closing (if batching implemented)
                # if hasattr(self, '_embedding_batch') and self._embedding_batch:
                #    self.logger.info(f"Processing pending items before closing")
                #    await self._process_embedding_batch() # Assuming this method exists

                if hasattr(self.vector_store, 'close') and callable(self.vector_store.close):
                    self.vector_store.close() # Qdrant client might need closing
                    self.logger.debug("Vector store closed.")
            except Exception as e:
                self.logger.error(f"Error closing vector store: {e}", exc_info=True)

        # Clear graph cache if specific to this instance (not typically needed if stateless)
        # key = (self.user_id, self.project_id)
        # AgentManager._graph_cache.pop(key, None)

        # Remove from global tracking
        key = (self.user_id, self.project_id)
        agent_managers.pop(key, None)
        self.logger.info(f"AgentManager closed for User: {self.user_id[:8]}, Project: {self.project_id[:8]}")


    @retry(
        stop=stop_after_attempt(4), # Slightly increase attempts for rate limits
        wait=wait_exponential(multiplier=1, min=4, max=30), # Increase wait times
        retry=retry_if_exception_type((Exception, ResourceExhausted)) # Retry on general exceptions and specifically on ResourceExhausted (429)
    )
    async def _get_llm(self, model_name: str) -> ChatGoogleGenerativeAI:
        """Gets or creates a ChatGoogleGenerativeAI instance with caching, rate limiting, and retry logic."""
        async with self._lock: # Protect access to the class-level cache
            if model_name in self._llm_cache:
                self.logger.debug(f"LLM Cache HIT for model: {model_name}")
                return self._llm_cache[model_name]

            self.logger.debug(f"LLM Cache MISS for model: {model_name}. Creating new instance.")

            is_pro_model = 'pro' in model_name
            rpm = GEMINI_PRO_RPM if is_pro_model else GEMINI_FLASH_RPM
            tpm = GEMINI_PRO_TPM if is_pro_model else GEMINI_FLASH_TPM
            rpd = GEMINI_PRO_RPD if is_pro_model else GEMINI_FLASH_RPD

            rate_limiter = StreamingRateLimiter(rpm, tpm, rpd)

            try:
                llm = ChatGoogleGenerativeAI(
                    model=model_name,
                    google_api_key=self.api_key,
                    temperature=float(self.model_settings.get('temperature', 0.7)), # Ensure float
                    max_output_tokens=self.MAX_OUTPUT_TOKENS,
                    # max_input_tokens not directly supported, handled via context truncation
                    convert_system_message_to_human=True, # Often needed for Gemini
                    streaming=True, # Keep streaming enabled
                    callbacks=[rate_limiter],
                    # Caching enabled globally via set_llm_cache
                )
                self._llm_cache[model_name] = llm
                self.logger.info(f"LLM instance created and cached for model: {model_name}")
                return llm
            except Exception as e:
                self.logger.error(f"Failed to create LLM instance for {model_name}: {e}", exc_info=True)
                raise # Re-raise the exception after logging


    async def _get_api_key(self) -> str:
        api_key = await self.api_key_manager.get_api_key(self.user_id)
        if not api_key:
            self.logger.error(f"API key not found for user {self.user_id}")
            raise ValueError("API key not set. Please set your API key in the settings.")
        return api_key

    async def _get_model_settings(self) -> dict:
        """Fetches model settings from the database asynchronously."""
        try:
            settings = await db_instance.get_model_settings(self.user_id)
            # Ensure temperature is float, provide defaults if missing
            defaults = {
                'mainLLM': 'gemini-1.5-flash-latest', # Default to Flash for cost/speed
                'checkLLM': 'gemini-1.5-flash-latest',
                'embeddingsModel': 'models/text-embedding-004',
                'titleGenerationLLM': 'gemini-1.5-flash-latest',
                'extractionLLM': 'gemini-1.5-flash-latest',
                'knowledgeBaseQueryLLM': 'gemini-1.5-flash-latest',
                'temperature': 0.7
            }
            settings = {**defaults, **settings} # Merge defaults with loaded settings
            settings['temperature'] = float(settings['temperature']) # Ensure float
            return settings
        except Exception as e:
            self.logger.error(f"Error getting model settings for user {self.user_id}: {e}", exc_info=True)
            raise

    def setup_caching(self):
        """Sets up global LangChain LLM caching using SQLite."""
        # Ensure directory exists
        db_path = ".cache"
        os.makedirs(db_path, exist_ok=True)
        cache_db = os.path.join(db_path, ".langchain.db")
        set_llm_cache(SQLiteCache(database_path=cache_db))
        self.logger.info(f"Global LLM caching enabled using SQLite at {cache_db}")

    def estimate_token_count(self, text: str) -> int:
        """Estimates token count using the main LLM."""
        if not text or not isinstance(text, str):
            return 0
        try:
            # Use the initialized main LLM instance
            return self.llm.get_num_tokens(text)
        except Exception as e:
            self.logger.warning(f"Could not estimate token count: {e}. Using word count approximation.")
            return len(text.split()) # Fallback approximation

    # --- LangGraph Nodes ---

    async def _construct_context_node(self, state: ChapterGenerationState) -> Dict[str, Any]:
        """Gathers context for chapter generation."""
        self.logger.debug(f"Node: Constructing Context for Chapter {state['chapter_number']}")
        try:
            plot = state['plot']
            writing_style = state['writing_style']
            vector_store = state['vector_store']
            user_id = state['user_id']
            project_id = state['project_id']

            context_parts = [f"Plot: {plot}", f"Writing Style: {writing_style}"]

            # Fetch relevant previous chapters (e.g., last 3 summaries)
            try:
                previous_chapters_data = await db_instance.get_all_chapters(user_id, project_id)
                previous_chapters_data.sort(key=lambda x: x.get('chapter_number', 0))
                recent_chapters = previous_chapters_data[-3:] # Get last 3 chapters

                if recent_chapters:
                    context_parts.append("\nRecent Chapter Summaries:")
                    for chapter in recent_chapters:
                        chap_num = chapter.get('chapter_number', 'N/A')
                        chap_title = chapter.get('title', f'Chapter {chap_num}')
                        content = chapter.get('content', '')
                        # Summarize if long
                        if self.estimate_token_count(content) > 1000: # Summarize if > 1k tokens
                             docs_to_summarize = [Document(page_content=content)]
                             summary_result = await state['summarize_chain'].arun(docs_to_summarize)
                             context_parts.append(f"- Ch {chap_num} ({chap_title}): {summary_result}")
                        else:
                             context_parts.append(f"- Ch {chap_num} ({chap_title}): {content[:2100]}...") # Truncate short ones
            except Exception as e:
                self.logger.warning(f"Could not fetch/process previous chapters: {e}")


            # Fetch relevant codex items from Vector Store
            try:
                # More specific query for relevance
                query_text = f"Details relevant to plot: {plot}"
                # Filter out chapters explicitly
                codex_filter = { "type": {"$nin": ["chapter", "relationship", "character_backstory"]} } # Example filter

                relevant_docs = await vector_store.similarity_search(
                    query_text=query_text,
                    k=20, # Fetch more potentially relevant items
                    filter=codex_filter
                )

                if relevant_docs:
                    context_parts.append("\nRelevant World Information (from Knowledge Base):")
                    items_by_type = {}
                    for doc in relevant_docs:
                        item_type = doc.metadata.get('type', 'other')
                        if item_type not in items_by_type: items_by_type[item_type] = []
                        # Limit context per item to avoid excessive length
                        name = doc.metadata.get('name', doc.metadata.get('title', 'Unnamed'))
                        content_preview = doc.page_content[:300] # Limit length
                        items_by_type[item_type].append(f"{name}: {content_preview}...")

                    for item_type, items in items_by_type.items():
                        context_parts.append(f"\n{item_type.title()}:")
                        context_parts.extend([f"- {item}" for item in items])

            except Exception as e:
                self.logger.warning(f"Could not fetch relevant documents from vector store: {e}")

            final_context = "\n".join(context_parts)

            # Truncate context if it exceeds limits (leaving room for prompt template)
            max_context_tokens = self.MAX_INPUT_TOKENS - 1000 # Reserve 1k for prompt itself
            context_tokens = self.estimate_token_count(final_context)
            if context_tokens > max_context_tokens:
                self.logger.warning(f"Context ({context_tokens} tokens) exceeds limit ({max_context_tokens}). Truncating.")
                # Simple truncation - smarter truncation might be needed
                # This requires knowing token counts accurately, which is hard without the LLM call
                # A simple character-based approximation:
                ratio = max_context_tokens / context_tokens
                final_context = final_context[:int(len(final_context) * ratio)]
                self.logger.warning(f"Context truncated to approx {self.estimate_token_count(final_context)} tokens.")


            return {"context": final_context}

        except Exception as e:
            self.logger.error(f"Error in _construct_context_node: {e}", exc_info=True)
            return {"error": f"Failed to construct context: {e}"}

    def _create_chapter_prompt(self, instructions: Dict[str, Any], context: str) -> ChatPromptTemplate:
        """Helper to create the chapter generation prompt."""
        system_template = """You are a skilled author writing a chapter ({chapter_number}) for a novel. Adhere STRICTLY to all requirements.

        **CONTEXT:**
        {context}

        **WRITING REQUIREMENTS (MANDATORY):**
        1.  **Plot/Setting:** {plot}
        2.  **Writing Style:** {writing_style} (Apply this style METICULOUSLY to every sentence.)
        3.  **Style Guide:** {style_guide} (Follow this guide EXACTLY.)
        4.  **Additional Instructions:** {additional_instructions} (Incorporate these precisely.)
        5.  **Approximate Word Count Target:** {word_count_target} words. Aim for this length naturally.

        **FORMATTING (MANDATORY):**
        *   Use clear paragraphs with double line breaks between them.
        *   Start new paragraphs for scene/time shifts, speaker changes (dialogue), location changes, perspective shifts, new ideas.
        *   Format dialogue correctly (new paragraph per speaker, quotation marks, tags/actions).
        *   Vary paragraph length.
        *   Use "***" for major scene breaks if appropriate.

        **CRITICAL RULES:**
        *   NEVER write the word "Codex".
        *   Follow the specified Writing Style and Style Guide WITHOUT FAIL.
        *   Stay EXACTLY true to the Plot/Setting.
        *   Incorporate ALL requirements.
        *   If specific sentence structures or endings are required, apply them CONSISTENTLY.

        Begin writing Chapter {chapter_number} immediately. Do not include a chapter heading like "Chapter X: Title".
        """
        human_template = "Write the chapter following all system instructions precisely."

        return ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", human_template)
        ])

    async def _generate_initial_chapter_node(self, state: ChapterGenerationState) -> Dict[str, Any]:
        """Generates the initial draft of the chapter."""
        self.logger.debug(f"Node: Generating Initial Chapter {state['chapter_number']}")
        if state.get("error"): return {} # Skip if error occurred previously

        try:
            instructions = state['instructions']
            context = state['context']
            llm = state['llm']

            prompt = self._create_chapter_prompt(instructions, context)
            chain = prompt | llm | StrOutputParser()

            target_word_count = instructions.get('wordCount', 0) # Get target WC from instructions

            chapter_content = await chain.ainvoke({
                "chapter_number": state['chapter_number'],
                "context": context,
                "plot": state['plot'],
                "writing_style": state['writing_style'],
                "style_guide": instructions.get('styleGuide', ''),
                "additional_instructions": instructions.get('additionalInstructions', ''),
                "word_count_target": target_word_count,
            })

            if not chapter_content or not chapter_content.strip():
                 raise ValueError("LLM returned empty chapter content.")

            current_word_count = len(chapter_content.split())
            self.logger.info(f"Initial chapter generated. Word count: {current_word_count}")

            return {
                "initial_chapter_content": chapter_content,
                "current_word_count": current_word_count,
                "target_word_count": target_word_count # Pass target along
            }
        except Exception as e:
            self.logger.error(f"Error in _generate_initial_chapter_node: {e}", exc_info=True)
            return {"error": f"Failed to generate initial chapter: {e}"}

    async def _extend_chapter_node(self, state: ChapterGenerationState) -> Dict[str, Any]:
        """Extends the chapter if it's too short."""
        self.logger.debug(f"Node: Extending Chapter {state['chapter_number']}")
        if state.get("error"): return {}

        try:
            # Use the most recent content (either initial or previously extended)
            previous_content = state.get("extended_chapter_content") or state["initial_chapter_content"]
            current_word_count = state["current_word_count"]
            target_word_count = state["target_word_count"]
            words_to_add = target_word_count - current_word_count

            self.logger.info(f"Extending chapter. Current: {current_word_count}, Target: {target_word_count}, Need: {words_to_add}")

            extend_prompt = ChatPromptTemplate.from_template(
                """You are an author continuing a chapter. Your task is to seamlessly extend the following chapter text while STRICTLY maintaining the established writing style, tone, and plot progression. Add approximately {words_to_add} words.

                **EXISTING CHAPTER TEXT (Continue From Here):**
                {previous_content}

                **ORIGINAL WRITING REQUIREMENTS (Maintain These):**
                *   **Writing Style:** {writing_style}
                *   **Style Guide:** {style_guide}
                *   **Plot to follow:** {plot}
                *   **Overall Context:** {context}

                **EXTENSION GUIDELINES (MANDATORY):**
                1.  Write ONLY the additional text needed to continue the story naturally.
                2.  DO NOT repeat the existing text provided above.
                3.  The new text MUST perfectly match the style, tone, vocabulary, and sentence structure of the existing text.
                4.  Continue plot points, character interactions, or descriptions logically.
                5.  Ensure the transition from the existing text to your new text is smooth and invisible.
                6.  Aim to add roughly {words_to_add} words.

                Start writing the additional text immediately.
                """
            )

            chain = extend_prompt | state['llm'] | StrOutputParser()

            extension_text = await chain.ainvoke({
                "previous_content": previous_content,
                "words_to_add": words_to_add,
                "writing_style": state['writing_style'],
                "style_guide": state['instructions'].get('styleGuide', ''),
                "plot": state['plot'],
                "context": state['context'] # Provide context again for consistency
            })

            if not extension_text or not extension_text.strip():
                self.logger.warning("LLM returned empty extension text. Stopping extension.")
                # Return state without updating content, letting the condition proceed
                return {"extended_chapter_content": previous_content, "current_word_count": current_word_count}


            # Combine and update word count
            # Ensure a space or newline separates the parts if needed
            separator = "\n\n" if "\n\n" in previous_content else " "
            full_content = previous_content.strip() + separator + extension_text.strip()
            new_word_count = len(full_content.split())

            self.logger.info(f"Chapter extended. New word count: {new_word_count}")

            return {
                "extended_chapter_content": full_content,
                "current_word_count": new_word_count,
            }

        except Exception as e:
            self.logger.error(f"Error in _extend_chapter_node: {e}", exc_info=True)
            # Return error but also the content we had before the failed extension attempt
            return {
                 "error": f"Failed to extend chapter: {e}",
                 "extended_chapter_content": state.get("extended_chapter_content") or state["initial_chapter_content"],
                 "current_word_count": state["current_word_count"]
            }

    async def _generate_title_node(self, state: ChapterGenerationState) -> Dict[str, Any]:
        """Generates the chapter title."""
        self.logger.debug(f"Node: Generating Title for Chapter {state['chapter_number']}")
        if state.get("error"): return {}

        try:
            # Use the final content after potential extension
            final_content = state.get("extended_chapter_content") or state["initial_chapter_content"]
            chapter_number = state["chapter_number"]
            llm = state["check_llm"] # Use check LLM for smaller tasks

            prompt = ChatPromptTemplate.from_template("""
            Analyze the following chapter content and generate a compelling, concise (2-6 words) title that captures its essence without spoilers. Maintain professional novel chapter naming conventions.

            Chapter Number: {chapter_number}
            Chapter Content Snippet:
            {chapter_content_snippet}

            Return ONLY the title text. Do not include "Chapter X:".
            """)

            chain = prompt | llm | StrOutputParser()

            # Provide a snippet to avoid large context for title gen
            content_snippet = final_content[:1500] + "..." if len(final_content) > 1500 else final_content

            title_text = await chain.ainvoke({
                "chapter_number": chapter_number,
                "chapter_content_snippet": content_snippet
            })

            cleaned_title = title_text.strip().replace("\"", "")
            # Basic length check/truncation
            if len(cleaned_title) > 100: cleaned_title = cleaned_title[:97]+"..."
            if not cleaned_title: cleaned_title = f"Chapter {chapter_number} Untitled"

            final_title = f"Chapter {chapter_number}: {cleaned_title}"

            return {"chapter_title": final_title}
        except Exception as e:
            self.logger.error(f"Error in _generate_title_node: {e}", exc_info=True)
            # Return a default title if generation fails
            return {
                "error": f"Failed to generate title: {e}",
                "chapter_title": f"Chapter {state['chapter_number']}"
            }

    async def _extract_codex_items_node(self, state: ChapterGenerationState) -> Dict[str, Any]:
        """Extracts new codex items from the chapter."""
        self.logger.debug(f"Node: Extracting Codex Items for Chapter {state['chapter_number']}")
        if state.get("error"): return {}

        try:
            final_content = state.get("extended_chapter_content") or state["initial_chapter_content"]
            vector_store = state['vector_store']
            check_llm = state['check_llm']

            # Get existing codex item names for filtering
            existing_items = await vector_store.similarity_search(
                query_text="*", # Broad query to get items
                filter={"type": {"$in": [t.value for t in CodexExtractionTypes]}},
                k=200 # Fetch a good number of existing items
            )
            existing_names = {doc.metadata.get('name', '').lower() for doc in existing_items if doc.metadata.get('name')}
            self.logger.debug(f"Found {len(existing_names)} existing codex item names for filtering.")

            parser = PydanticOutputParser(pydantic_object=CodexExtraction)
            # Use JsonOutputParser as a fallback if Pydantic fails hard
            # fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=check_llm)

            prompt = ChatPromptTemplate.from_template("""
                Analyze the chapter content below. Identify NEW entities (characters, items, lore, factions, worldbuilding details) introduced that are NOT in the 'Existing Item Names' list.

                Valid Types: {valid_types}
                Valid Worldbuilding Subtypes: {valid_subtypes}

                For each NEW item:
                1. Extract its Name.
                2. Write a brief Description based ONLY on the chapter text.
                3. Assign its Type (from Valid Types).
                4. Assign a Subtype (from Valid Subtypes) ONLY if Type is 'worldbuilding'.

                Chapter Content:
                {chapter_content}

                Existing Item Names (IGNORE THESE):
                {existing_names}

                Respond in JSON format matching the following schema:
                {format_instructions}

                If no new items are found, return an empty list for "new_items".
                """)

            chain = prompt | check_llm | JsonOutputParser(pydantic_object=CodexExtraction) # Try JSON parser first

            # Process in chunks if content is very large (optional, might be complex)
            # chunks = self.chunk_content(final_content, self.MAX_INPUT_TOKENS // 2)
            # all_new_items_raw = []
            # for chunk in chunks: ... invoke chain ... all_new_items_raw.extend(result['new_items'])

            try:
                result_dict = await chain.ainvoke({
                    "chapter_content": final_content, # Process full content for now
                    "existing_names": ", ".join(list(existing_names)) if existing_names else "None",
                    "valid_types": ", ".join([t.value for t in CodexExtractionTypes]),
                    "valid_subtypes": ", ".join([t.value for t in WorldbuildingSubtype]),
                    "format_instructions": parser.get_format_instructions() # Still use Pydantic for instructions
                })
                # Validate with Pydantic after JSON parsing
                validated_result = CodexExtraction.model_validate(result_dict)
                all_new_items_raw = validated_result.new_items
            except (json.JSONDecodeError, ValidationError) as parse_error:
                self.logger.warning(f"JSON/Pydantic parsing failed for codex extraction: {parse_error}. Attempting fix.")
                # Fallback to OutputFixingParser
                fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=check_llm)
                fix_chain = prompt | check_llm | fixing_parser
                validated_result = await fix_chain.ainvoke({
                    "chapter_content": final_content,
                    "existing_names": ", ".join(list(existing_names)) if existing_names else "None",
                    "valid_types": ", ".join([t.value for t in CodexExtractionTypes]),
                    "valid_subtypes": ", ".join([t.value for t in WorldbuildingSubtype]),
                    "format_instructions": parser.get_format_instructions()
                })
                all_new_items_raw = validated_result.new_items
            except Exception as invoke_error:
                 self.logger.error(f"Codex extraction LLM call failed: {invoke_error}", exc_info=True)
                 all_new_items_raw = [] # Assume no items found on error


            # Deduplicate based on name (case-insensitive) and ensure valid types/subtypes
            unique_items_dict = {}
            final_new_items = []
            valid_types_set = {t.value for t in CodexItemType}
            valid_subtypes_set = {s.value for s in WorldbuildingSubtype}

            for item in all_new_items_raw:
                 item_name_lower = item.name.strip().lower()
                 if not item_name_lower: continue # Skip empty names

                 # Validate Type
                 try:
                     item_type_enum = CodexItemType(item.type)
                 except ValueError:
                     self.logger.warning(f"Invalid codex type '{item.type}' for item '{item.name}'. Skipping.")
                     continue

                 # Validate Subtype if present
                 item_subtype_enum = None
                 if item.subtype:
                     try:
                         item_subtype_enum = WorldbuildingSubtype(item.subtype)
                         if item_type_enum != CodexItemType.WORLDBUILDING:
                              self.logger.warning(f"Subtype '{item.subtype}' provided for non-worldbuilding type '{item.type}' on item '{item.name}'. Ignoring subtype.")
                              item_subtype_enum = None # Clear invalid subtype
                     except ValueError:
                         self.logger.warning(f"Invalid worldbuilding subtype '{item.subtype}' for item '{item.name}'. Skipping subtype.")
                         # Keep item, but without subtype

                 # Check uniqueness
                 if item_name_lower not in unique_items_dict:
                      item_dict = {
                          "name": item.name.strip(),
                          "description": item.description.strip(),
                          "type": item_type_enum.value, # Store validated enum value
                          "subtype": item_subtype_enum.value if item_subtype_enum else None,
                      }
                      unique_items_dict[item_name_lower] = item_dict
                      final_new_items.append(item_dict)


            self.logger.info(f"Extracted {len(final_new_items)} unique new codex items.")
            return {"new_codex_items": final_new_items}

        except Exception as e:
            self.logger.error(f"Error in _extract_codex_items_node: {e}", exc_info=True)
            return {
                "error": f"Failed to extract codex items: {e}",
                "new_codex_items": [] # Default to empty list on error
            }

    async def _validate_chapter_node(self, state: ChapterGenerationState) -> Dict[str, Any]:
        """Validates the generated chapter."""
        self.logger.debug(f"Node: Validating Chapter {state['chapter_number']}")
        if state.get("error"): return {}

        try:
            final_content = state.get("extended_chapter_content") or state["initial_chapter_content"]
            instructions = state['instructions']
            check_llm = state['check_llm']
            vector_store = state['vector_store']
            plot = state['plot']

            # Fetch limited context for validation (e.g., plot + maybe previous chapter summary)
            # Re-using full context might be too much for validation LLM
            validation_context_docs = await vector_store.similarity_search(plot, k=3) # Get relevant docs
            validation_context = f"Plot: {plot}\nInstructions: {json.dumps(instructions)}\nRelevant Info:\n" + "\n".join([f"- {doc.page_content[:200]}..." for doc in validation_context_docs])


            parser = PydanticOutputParser(pydantic_object=ChapterValidation)
            fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=check_llm)

            prompt = ChatPromptTemplate.from_template("""
            You are an expert editor evaluating a novel chapter based on provided criteria and context.

            **Chapter Content:**
            {chapter_content}

            **Evaluation Context & Instructions:**
            {validation_context}

            **Evaluation Criteria:**
            Plot Consistency, Character Development, Pacing, Dialogue Quality, Setting Description, Writing Style Adherence, Emotional Impact, Conflict/Tension, Theme Exploration, Grammar/Syntax.

            **Task:**
            1.  Score each criterion from 1-10 (1=Poor, 10=Excellent) with a brief explanation.
            2.  Assess overall validity (true/false).
            3.  Provide an overall score (0-10).
            4.  Give scores/explanations specifically for Style Guide Adherence and Continuity.
            5.  List specific Areas for Improvement.
            6.  Write concise General Feedback.

            **Output Format (JSON):**
            {format_instructions}
            """)

            chain = prompt | check_llm | fixing_parser # Use fixing parser as fallback

            result = await chain.ainvoke({
                "chapter_content": final_content,
                "validation_context": validation_context,
                "format_instructions": parser.get_format_instructions()
            })

            # Convert Pydantic result to simple dict for state
            validity_check_dict = {
                'is_valid': result.is_valid,
                'overall_score': result.overall_score,
                'criteria_scores': {k: v.model_dump() for k, v in result.criteria_scores.items()}, # Store nested models as dicts
                'style_guide_adherence_score': result.style_guide_adherence.score,
                'style_guide_adherence_explanation': result.style_guide_adherence.explanation,
                'continuity_score': result.continuity.score,
                'continuity_explanation': result.continuity.explanation,
                'areas_for_improvement': result.areas_for_improvement,
                'general_feedback': result.general_feedback
            }

            self.logger.info(f"Chapter validation completed. Overall Score: {result.overall_score}/10")
            return {"validity_check": validity_check_dict}

        except (ValidationError, json.JSONDecodeError) as e:
             self.logger.error(f"Validation output parsing error: {e}", exc_info=True)
             return {"error": f"Failed to parse validation output: {e}"}
        except Exception as e:
            self.logger.error(f"Error in _validate_chapter_node: {e}", exc_info=True)
            return {"error": f"Failed during chapter validation: {e}"}

    async def _finalize_output_node(self, state: ChapterGenerationState) -> Dict[str, Any]:
        """Assembles the final output dictionary."""
        self.logger.debug(f"Node: Finalizing Output for Chapter {state['chapter_number']}")
        if state.get("error"):
            # Handle final error state
            return {"final_output": {"error": state["error"]}}

        final_content = state.get("extended_chapter_content") or state["initial_chapter_content"]

        final_output = {
            "content": final_content,
            "chapter_title": state.get("chapter_title", f"Chapter {state['chapter_number']}"),
            "new_codex_items": state.get("new_codex_items", []),
            "validity_check": state.get("validity_check", {"error": "Validation skipped or failed."}),
            "word_count": state.get("current_word_count", 0)
        }
        return {"final_output": final_output}

    # --- LangGraph Conditional Edges ---

    def _should_extend_chapter(self, state: ChapterGenerationState) -> str:
        """Determines if the chapter needs extension based on word count."""
        if state.get("error"):
             self.logger.warning("Error detected, skipping extension check.")
             return "proceed_to_title" # Go to final steps even if error occurred

        current_wc = state['current_word_count']
        target_wc = state['target_word_count']
        initial_content = state['initial_chapter_content']
        extended_content = state.get('extended_chapter_content')

        # Safety check: if initial generation failed, don't try to extend.
        if not initial_content:
             self.logger.error("Initial chapter generation failed, cannot extend.")
             return "proceed_to_title"

        # If we already tried extending and failed (e.g., empty response), don't loop infinitely.
        # Check if extension was attempted but didn't increase word count significantly.
        if extended_content is not None and len(extended_content.split()) <= current_wc + 10: # Allowance for minor variations
             self.logger.warning("Extension attempt did not significantly increase word count. Proceeding.")
             return "proceed_to_title"

        # Check if target word count is set and if current count is significantly lower
        # Use a threshold (e.g., 90%) to avoid unnecessary extensions for minor differences
        if target_wc > 0 and current_wc < target_wc * 0.9:
            self.logger.info(f"Word count {current_wc} is less than 90% of target {target_wc}. Extending.")
            return "extend_chapter"
        else:
            self.logger.info(f"Word count {current_wc} is sufficient (Target: {target_wc}). Proceeding.")
            return "proceed_to_title"

    # --- Graph Builder ---

    def _build_chapter_generation_graph(self) -> StateGraph:
        """Builds the LangGraph StateMachine for chapter generation."""
        graph = StateGraph(ChapterGenerationState)

        # Define nodes
        graph.add_node("construct_context", self._construct_context_node)
        graph.add_node("generate_initial_chapter", self._generate_initial_chapter_node)
        graph.add_node("extend_chapter", self._extend_chapter_node)
        graph.add_node("generate_title", self._generate_title_node)
        graph.add_node("extract_codex_items", self._extract_codex_items_node)
        graph.add_node("validate_chapter", self._validate_chapter_node)
        graph.add_node("finalize_output", self._finalize_output_node)

        # Define edges
        graph.set_entry_point("construct_context")
        graph.add_edge("construct_context", "generate_initial_chapter")

        # Conditional edge for extension
        graph.add_conditional_edges(
            "generate_initial_chapter",
            self._should_extend_chapter,
            {
                "extend_chapter": "extend_chapter",
                "proceed_to_title": "generate_title"
            }
        )
        # Loop back after extension attempt OR proceed if extension didn't work/isn't needed
        graph.add_conditional_edges(
            "extend_chapter",
             self._should_extend_chapter, # Check again after extension
             {
                "extend_chapter": "extend_chapter", # Loop if still too short and extension added words
                "proceed_to_title": "generate_title" # Proceed if count is okay or extension failed
            }
        )

        graph.add_edge("generate_title", "extract_codex_items")
        graph.add_edge("extract_codex_items", "validate_chapter")
        graph.add_edge("validate_chapter", "finalize_output")
        graph.add_edge("finalize_output", END)

        # Compile the graph
        compiled_graph = graph.compile()
        self.logger.info("Chapter generation graph compiled.")
        return compiled_graph

    # --- Public Methods ---

    async def generate_chapter(
        self,
        chapter_number: int,
        plot: str,
        writing_style: str,
        instructions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generates a chapter using the LangGraph workflow."""
        self.logger.info(f"Starting chapter generation process for Chapter {chapter_number}...")

        if not self.chapter_generation_graph:
             self.logger.error("Chapter generation graph is not initialized.")
             raise RuntimeError("AgentManager not properly initialized.")

        initial_state: ChapterGenerationState = {
            "user_id": self.user_id,
            "project_id": self.project_id,
            "chapter_number": chapter_number,
            "plot": plot,
            "writing_style": writing_style,
            "instructions": instructions,
            "llm": self.llm,
            "check_llm": self.check_llm,
            "vector_store": self.vector_store,
            "summarize_chain": self.summarize_chain,
            # Initialize others to None/default
            "context": None,
            "initial_chapter_content": None,
            "extended_chapter_content": None,
            "current_word_count": 0,
            "target_word_count": instructions.get('wordCount', 0),
            "chapter_title": None,
            "new_codex_items": None,
            "validity_check": None,
            "error": None,
            "final_chapter_content": None,
            "final_output": None,
        }

        try:
            # Stream the graph execution (or use ainvoke for final result)
            # Using ainvoke for simplicity here, streaming requires more complex handling
            final_state = await self.chapter_generation_graph.ainvoke(initial_state)

            if final_state.get("error"):
                 self.logger.error(f"Chapter generation failed with error: {final_state['error']}")
                 # Return a structured error response
                 return {
                     "error": final_state["error"],
                     "content": None,
                     "chapter_title": f"Chapter {chapter_number} (Failed)",
                     "new_codex_items": [],
                     "validity_check": None,
                 }

            if not final_state.get("final_output"):
                raise ValueError("Graph execution finished without final output.")

            self.logger.info(f"Chapter generation process completed for Chapter {chapter_number}.")
            return final_state["final_output"]

        except Exception as e:
            self.logger.error(f"Error invoking chapter generation graph: {e}", exc_info=True)
            raise # Re-raise the exception


    async def save_validity_feedback(self, result: Dict[str, Any], chapter_number: int, chapter_id: str):
        """Saves validity feedback to the database."""
        # This method remains largely the same, just ensure data format matches.
        try:
            # Get chapter title if needed (though often passed in result now)
            # chapter = await db_instance.get_chapter(chapter_id, self.user_id, self.project_id)
            chapter_title = f"Chapter {chapter_number}" # Get from state if possible later

            # Adjust keys based on the structure from _validate_chapter_node
            await db_instance.save_validity_check(
                chapter_id=chapter_id,
                chapter_title=chapter_title, # Or fetch dynamically
                is_valid=result['is_valid'],
                overall_score=result['overall_score'],
                general_feedback=result['general_feedback'],
                # Assuming criteria_scores is not directly saved, but specific scores are
                style_guide_adherence_score=result['style_guide_adherence_score'],
                style_guide_adherence_explanation=result['style_guide_adherence_explanation'],
                continuity_score=result['continuity_score'],
                continuity_explanation=result['continuity_explanation'],
                areas_for_improvement=result['areas_for_improvement'], # Should be List[str]
                user_id=self.user_id,
                project_id=self.project_id
            )
            self.logger.info(f"Validity feedback saved for chapter ID: {chapter_id}")
        except Exception as e:
            self.logger.error(f"Error saving validity feedback for chapter {chapter_id}: {e}", exc_info=True)
            # Don't raise, as saving feedback is secondary to generation


    async def add_to_knowledge_base(self, content_type: str, content: str, metadata: Dict[str, Any]) -> Optional[str]:
        """Adds content to the vector store."""
        try:
            if not self.vector_store:
                self.logger.error("Vector store not initialized.")
                return None

            # Ensure mandatory metadata
            metadata['type'] = content_type
            metadata['user_id'] = self.user_id
            metadata['project_id'] = self.project_id
            metadata['created_at'] = datetime.now(timezone.utc).isoformat()

            # Clean metadata (remove None values, ensure JSON serializable types)
            clean_metadata = {}
            for k, v in metadata.items():
                if v is not None:
                    if isinstance(v, (str, int, float, bool, list)):
                         clean_metadata[k] = v
                    elif isinstance(v, datetime):
                         clean_metadata[k] = v.isoformat()
                    # Add other serializable types if needed
                    else:
                         self.logger.warning(f"Skipping non-serializable metadata key '{k}' of type {type(v)}")


            # Use add_texts for simplicity, VectorStore handles batching if implemented
            ids = await self.vector_store.add_texts([content], [clean_metadata])
            if ids:
                 embedding_id = ids[0]
                 self.logger.debug(f"Added '{content_type}' item to KB. Embedding ID: {embedding_id}")
                 return embedding_id
            else:
                 self.logger.error("Failed to add item to knowledge base, no ID returned.")
                 return None

        except Exception as e:
            self.logger.error(f"Error adding to knowledge base: {e}", exc_info=True)
            return None # Return None on error


    async def update_or_remove_from_knowledge_base(self, identifier: Union[str, Dict[str, str]], action: str, new_content: str = None, new_metadata: Dict[str, Any] = None):
        """Updates or removes an item from the vector store by embedding ID or item details."""
        # This method interacts directly with VectorStore, no major changes needed unless VS API changes.
        if not self.vector_store:
            self.logger.error("Vector store not initialized.")
            return

        try:
            embedding_id = None
            if isinstance(identifier, str):
                embedding_id = identifier
            elif isinstance(identifier, dict) and 'item_id' in identifier and 'item_type' in identifier:
                # Find embedding ID based on item_id and item_type
                embedding_id = await self.vector_store.get_embedding_id(
                    item_id=identifier['item_id'],
                    item_type=identifier['item_type']
                )
                if not embedding_id:
                     self.logger.warning(f"Could not find embedding ID for item: {identifier}. Cannot {action}.")
                     return
            else:
                raise ValueError("Invalid identifier provided. Must be embedding ID string or dict with item_id and item_type.")

            if action == "delete":
                await self.vector_store.delete_from_knowledge_base(embedding_id)
                self.logger.info(f"Deleted item with embedding ID: {embedding_id}")
            elif action == "update":
                if new_content is None and new_metadata is None:
                    raise ValueError("Either new_content or new_metadata must be provided for update action")

                # Ensure user/project IDs are in metadata if provided
                if new_metadata:
                    new_metadata['user_id'] = self.user_id
                    new_metadata['project_id'] = self.project_id
                    new_metadata['updated_at'] = datetime.now(timezone.utc).isoformat()

                await self.vector_store.update_in_knowledge_base(embedding_id, new_content, new_metadata)
                self.logger.info(f"Updated item with embedding ID: {embedding_id}")
            else:
                raise ValueError(f"Invalid action: {action}. Must be 'delete' or 'update'.")

        except Exception as e:
            self.logger.error(f"Error in update_or_remove_from_knowledge_base (ID: {identifier}, Action: {action}): {e}", exc_info=True)
            # Avoid raising here to prevent breaking callers if KB update fails


    async def query_knowledge_base(self, query: str, chat_history: List[Dict[str, str]] = None) -> str:
        """Queries the knowledge base using RAG."""
        # This method can remain largely the same, using the initialized components.
        if not self.vector_store or not self.model_settings:
             raise RuntimeError("AgentManager not initialized properly.")

        try:
            qa_llm = await self._get_llm(self.model_settings['knowledgeBaseQueryLLM'])

            # 1. Condense Question (if history exists)
            standalone_question = query
            history_messages: List[BaseMessage] = []
            if chat_history:
                for msg in chat_history:
                    if msg["type"] == "human": history_messages.append(HumanMessage(content=msg["content"]))
                    elif msg["type"] == "ai": history_messages.append(AIMessage(content=msg["content"]))

                if history_messages:
                    condense_prompt = ChatPromptTemplate.from_messages([
                        MessagesPlaceholder(variable_name="chat_history"),
                        ("human", "Given the chat history and the follow up question, rephrase the follow up question to be a standalone question.\n\nFollow Up Question: {question}\nStandalone question:")
                    ])
                    condense_chain = condense_prompt | qa_llm | StrOutputParser()
                    standalone_question = await condense_chain.ainvoke({"chat_history": history_messages, "question": query})
                    self.logger.debug(f"Original Query: {query}, Standalone Query: {standalone_question}")


            # 2. Retrieve Documents
            retrieved_docs = await self.vector_store.similarity_search(standalone_question, k=5) # Reduced k for smaller context

            if not retrieved_docs:
                return "I couldn't find relevant information in the knowledge base to answer that question."

            # 3. Generate Answer using LLM with Context
            context_str = "\n\n---\n\n".join([f"Source {i+1} ({doc.metadata.get('type', 'doc')} - {doc.metadata.get('name', 'unnamed')}):\n{doc.page_content}" for i, doc in enumerate(retrieved_docs)])

            answer_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an assistant answering questions based SOLELY on the provided context. If the answer isn't in the context, say you don't know. Be concise."),
                ("human", "Context:\n{context}\n\nQuestion: {question}\n\nAnswer:")
            ])

            answer_chain = answer_prompt | qa_llm | StrOutputParser()
            answer = await answer_chain.ainvoke({"context": context_str, "question": standalone_question})

            # Include sources (optional, can be done client-side too)
            # sources_info = "\n\nSources Used:\n" + "\n".join([f"- {doc.metadata.get('type', 'doc')}: {doc.metadata.get('name', doc.metadata.get('title', 'Unnamed'))}" for doc in retrieved_docs])
            # return answer + sources_info

            return answer

        except Exception as e:
            self.logger.error(f"Error in query_knowledge_base: {e}", exc_info=True)
            return f"An error occurred while querying the knowledge base: {e}" # Return error message

    # --- Other Methods (Keep as needed, ensure they use async/await and initialized components) ---

    async def generate_codex_item(self, codex_type: str, subtype: Optional[str], description: str) -> Dict[str, str]:
        """Generates details for a new codex item based on a description."""
        # This can remain a separate utility, doesn't need full graph
        self.logger.debug(f"Generating codex item: Type={codex_type}, Subtype={subtype}")
        try:
            parser = PydanticOutputParser(pydantic_object=CodexItem)
            llm = await self._get_llm(self.model_settings['extractionLLM']) # Use extraction LLM
            fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=llm)

            # Fetch relevant context (existing items, chapters)
            existing_items = await db_instance.get_all_codex_items(self.user_id, self.project_id)
            existing_items_str = json.dumps([{"name": i.get('name'), "type": i.get('type'), "desc_snippet": i.get('description', '')[:50]+"..."} for i in existing_items[:20]], indent=2) # Snippets only

            relevant_chapters = await self.vector_store.similarity_search(
                query_text=description, filter={"type": "chapter"}, k=5
            )
            chapter_context = "\n\n".join(
                f"Ch {doc.metadata.get('chapter_number', 'N/A')} Snippet: {doc.page_content[:300]}..."
                for doc in relevant_chapters
            )

            prompt = ChatPromptTemplate.from_template("""
            Generate a name and detailed description for a new codex item.

            **Item Specifications:**
            *   Type: {codex_type}
            *   Subtype: {subtype}
            *   Initial Description Idea: {description}

            **Context:**
            *   Relevant Chapter Snippets: {chapter_context}
            *   Some Existing Codex Items: {existing_codex_items}

            **Task:**
            1.  Create a concise, evocative Name.
            2.  Write a comprehensive Description, expanding on the initial idea with depth and vivid details, consistent with the context.
            3.  Ensure consistency with the specified type/subtype and existing items/chapters. DO NOT contradict existing info.
            4.  Follow specific guidelines for the type (Character: appearance, personality, role; Item: origin, properties; Lore: date, impact; Worldbuilding: details based on subtype).

            **Output Format (JSON):**
            {format_instructions}
            """)

            chain = prompt | llm | fixing_parser

            result = await chain.ainvoke({
                "codex_type": codex_type,
                "subtype": subtype or "N/A",
                "description": description,
                "existing_codex_items": existing_items_str,
                "chapter_context": chapter_context,
                "format_instructions": parser.get_format_instructions()
            })

            return {"name": result.name, "description": result.description}

        except Exception as e:
            self.logger.error(f"Error generating codex item: {e}", exc_info=True)
            return {"name": "Error", "description": f"Failed to generate: {e}"}
        

    async def analyze_character_relationships(self, characters: List[Dict[str, Any]]) -> List[RelationshipAnalysis]:
        """Analyzes and potentially saves relationships between the provided characters based on project context."""
        self.logger.info(f"Analyzing relationships for {len(characters)} characters.")
        if not characters or len(characters) < 2:
            self.logger.warning("Need at least two characters to analyze relationships.")
            return []

        try:
            # Get story context (consider summarizing or selecting relevant parts if too large)
            all_chapters_data = await db_instance.get_all_chapters(self.user_id, self.project_id)
            context_content = "\n\n".join([f"Chapter {c.get('chapter_number', 'N/A')}: {c.get('content', '')[:2000]}..." for c in all_chapters_data]) # Snippets

            context_tokens = self.estimate_token_count(context_content)
            max_context_tokens = self.MAX_INPUT_TOKENS // 3 # Allocate portion for context
            if context_tokens > max_context_tokens:
                self.logger.warning(f"Relationship analysis context too large ({context_tokens} tokens). Summarizing.")
                # Summarize context (or use vector search for relevance)
                docs_to_summarize = [Document(page_content=context_content)]
                context_content = await self.summarize_chain.arun(docs_to_summarize) # Use initialized summarize chain

            parser = PydanticOutputParser(pydantic_object=RelationshipAnalysisList)
            # Use check_llm or extractionLLM as configured
            relationship_llm = await self._get_llm(self.model_settings['extractionLLM'])
            fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=relationship_llm)


            prompt = ChatPromptTemplate.from_template("""
            Analyze the relationships between the provided characters based on the story context. Focus ONLY on pairs involving the listed characters.

            Characters to Analyze:
            {characters_json}

            Story Context (Summaries/Snippets):
            {context}

            For each significant relationship pair found between the specified characters:
            1. Identify the names of both characters (character1, character2).
            2. Determine the relationship type (e.g., friend, enemy, rival, family, mentor, romantic interest, etc.).
            3. Provide a concise description summarizing their interactions and feelings towards each other based *only* on the context.

            Return ONLY the relationships between pairs of characters from the provided list. Do not infer relationships not present in the context.

            Format your response as JSON:
            {format_instructions}
            """)

            chain = prompt | relationship_llm | fixing_parser # Use fixing parser as fallback

            character_list_json = json.dumps([{"id": c.get('id'), "name": c.get('name')} for c in characters], indent=2)

            result = await chain.ainvoke({
                "characters_json": character_list_json,
                "context": context_content,
                "format_instructions": parser.get_format_instructions()
            })

            saved_relationships_output = []
            processed_pairs = set() # To avoid duplicate db entries for A-B and B-A

            if hasattr(result, 'relationships'):
                for rel in result.relationships:
                    # Find the actual character dicts from the input list
                    char1_dict = next((c for c in characters if c.get('name') == rel.character1), None)
                    char2_dict = next((c for c in characters if c.get('name') == rel.character2), None)

                    if char1_dict and char2_dict:
                        # Ensure pair uniqueness (regardless of order)
                        pair_key = tuple(sorted([char1_dict['id'], char2_dict['id']]))
                        if pair_key not in processed_pairs:
                            processed_pairs.add(pair_key)
                            try:
                                # Save to database (assuming create_character_relationship exists)
                                # Note: Original method saved to db, decide if that's desired here or just return analysis
                                relationship_id = await db_instance.create_character_relationship(
                                    character_id=char1_dict['id'],
                                    related_character_id=char2_dict['id'],
                                    relationship_type=rel.relationship_type,
                                    project_id=self.project_id,
                                    description=rel.description
                                )
                                self.logger.debug(f"Saved relationship between {rel.character1} and {rel.character2} (ID: {relationship_id})")

                                # Optionally add relationship info to knowledge base
                                relationship_content = f"Relationship between {rel.character1} and {rel.character2}: {rel.relationship_type}. {rel.description}"
                                await self.add_to_knowledge_base(
                                    "relationship",
                                    relationship_content,
                                    {
                                        "name": f"{rel.character1}-{rel.character2} relationship",
                                        "type": "relationship",
                                        "relationship_id": relationship_id, # Link to DB entry
                                        "character1_id": char1_dict['id'],
                                        "character2_id": char2_dict['id'],
                                    }
                                )
                                # Add the Pydantic model directly to the output list
                                saved_relationships_output.append(rel)

                            except Exception as db_error:
                                self.logger.error(f"Failed to save relationship between {rel.character1} and {rel.character2}: {db_error}")
                                # Continue processing other relationships
            else:
                self.logger.warning("Relationship analysis LLM call returned no 'relationships' field.")


            return saved_relationships_output

        except Exception as e:
            self.logger.error(f"Error analyzing character relationships: {e}", exc_info=True)
            raise # Re-raise the error


    async def extract_character_backstory(self, character_id: str) -> Optional[CharacterBackstoryExtraction]:
        """Extracts new backstory for a character from unprocessed chapters."""
        self.logger.info(f"Extracting backstory for character ID: {character_id}")
        try:
            character_data = await db_instance.get_characters(self.user_id, self.project_id, character_id=character_id)
            if not character_data or character_data['type'] != CodexItemType.CHARACTER.value:
                self.logger.error(f"Character {character_id} not found or not a character.")
                return None

            # Get all chapters not yet processed for backstory
            chapters_to_process = await db_instance.get_latest_unprocessed_chapter_content(
                self.project_id,
                self.user_id,
                PROCESS_TYPES['BACKSTORY'] # Use constant
            )

            if not chapters_to_process:
                self.logger.info(f"No unprocessed chapters found for backstory extraction for character {character_id}.")
                return CharacterBackstoryExtraction(character_id=character_id, new_backstory="")

            self.logger.info(f"Processing {len(chapters_to_process)} chapters for backstory of {character_data['name']}.")

            parser = PydanticOutputParser(pydantic_object=CharacterBackstoryExtraction)
            backstory_llm = await self._get_llm(self.model_settings['extractionLLM'])
            fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=backstory_llm)


            prompt = ChatPromptTemplate.from_template("""
            Analyze the chapter content below specifically for new backstory information about the character "{character_name}".
            Backstory includes past events, history, motivations revealed, origins, significant past relationships, or past experiences mentioned or strongly implied *for the first time in this chapter*.

            Character Information:
            Name: {character_name}
            Existing Description/Backstory: {existing_backstory}

            Chapter Content:
            {chapter_content}

            Extract ONLY the new backstory details revealed in this specific chapter content.
            Summarize the new findings concisely. If no new backstory is found in this chapter, return an empty string for "new_backstory".

            Respond in JSON format:
            {format_instructions}
            """)

            all_new_backstory_parts = []
            processed_chapter_ids = []

            for chapter in chapters_to_process:
                chapter_id = chapter['id']
                chapter_content = chapter['content']

                try:
                    chain = prompt | backstory_llm | fixing_parser

                    result = await chain.ainvoke({
                        "character_name": character_data['name'],
                        "existing_backstory": character_data.get('backstory', 'None provided yet.'),
                        "chapter_content": chapter_content,
                        "format_instructions": parser.get_format_instructions()
                    })

                    if result and result.new_backstory and result.new_backstory.strip():
                         all_new_backstory_parts.append(result.new_backstory.strip())
                         processed_chapter_ids.append(chapter_id)
                         self.logger.debug(f"Found new backstory in chapter {chapter_id} for {character_data['name']}")
                    # else: Chapter had no new info, implicitly processed

                except Exception as chapter_error:
                     self.logger.error(f"Error processing chapter {chapter_id} for backstory: {chapter_error}", exc_info=True)
                     # Optionally decide whether to mark as processed even on error
                     # processed_chapter_ids.append(chapter_id) # Mark even if error?

            # Mark successfully processed chapters in DB
            for ch_id in processed_chapter_ids:
                 await db_instance.mark_chapter_processed(ch_id, self.user_id, PROCESS_TYPES['BACKSTORY'])

            combined_backstory = "\n\n".join(all_new_backstory_parts)

            # Optionally save combined backstory to character's main backstory field
            if combined_backstory:
                 await db_instance.save_character_backstory(character_id, combined_backstory, self.user_id, self.project_id)
                 # Also update/add to knowledge base if needed
                 await self.add_to_knowledge_base(
                      "character_backstory",
                      combined_backstory,
                      {"character_id": character_id, "type": "character_backstory"}
                 )
                 self.logger.info(f"Updated backstory for character {character_id} with new info.")


            return CharacterBackstoryExtraction(
                character_id=character_id,
                new_backstory=combined_backstory
            )

        except Exception as e:
            self.logger.error(f"Error extracting character backstory for {character_id}: {e}", exc_info=True)
            raise


    async def analyze_unprocessed_chapter_locations(self) -> List[Dict[str, Any]]:
        """Identifies and saves new locations from unprocessed chapters."""
        self.logger.info("Analyzing unprocessed chapters for new locations...")
        try:
            # Get unprocessed chapters for 'locations' type
            chapters_to_process = await db_instance.get_latest_unprocessed_chapter_content(
                self.project_id,
                self.user_id,
                PROCESS_TYPES['LOCATIONS']
            )

            if not chapters_to_process:
                self.logger.info("No unprocessed chapters found for location analysis.")
                return []

            existing_locations_data = await db_instance.get_locations(self.user_id, self.project_id)
            existing_location_names = {loc['name'].lower() for loc in existing_locations_data}
            self.logger.debug(f"Found {len(existing_location_names)} existing locations.")

            parser = PydanticOutputParser(pydantic_object=LocationAnalysisList)
            location_llm = await self._get_llm(self.model_settings['extractionLLM'])
            fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=location_llm)


            prompt = ChatPromptTemplate.from_template("""
            Analyze the following chapter content and identify all NEW locations mentioned that are NOT in the 'Existing Location Names' list.

            Chapter Content:
            {chapter_content}

            Existing Location Names (IGNORE THESE):
            {existing_location_names_str}

            For each NEW location found:
            1. Provide a unique identifier (can be generated later, just make sure output format expects `location_id` string field, maybe set to "NEW").
            2. Extract the location's name (`location_name`).
            3. Write a brief analysis of its significance based *only* on the chapter content (`significance_analysis`).
            4. List names of any other locations it seems connected to based on the text (`connected_locations`).
            5. List names of notable events occurring there in the chapter (`notable_events`).
            6. List names of characters associated with it in the chapter (`character_associations`).

            Return ONLY new locations. If all mentioned locations are in the existing list, return an empty "locations" list.

            Format response as JSON:
            {format_instructions}
            """)

            all_new_locations = []
            processed_chapter_ids = []

            existing_names_str = ", ".join(list(existing_location_names)) if existing_location_names else "None"

            for chapter in chapters_to_process:
                chapter_id = chapter['id']
                chapter_content = chapter['content']
                new_locations_in_chapter = []

                try:
                    chain = prompt | location_llm | fixing_parser
                    result = await chain.ainvoke({
                        "chapter_content": chapter_content,
                        "existing_location_names_str": existing_names_str,
                        "format_instructions": parser.get_format_instructions()
                    })

                    if result and hasattr(result, 'locations'):
                        for loc_analysis in result.locations:
                            loc_name_lower = loc_analysis.location_name.lower()
                            # Double check against existing names (case-insensitive)
                            if loc_name_lower not in existing_location_names:
                                try:
                                    # Create new location in DB
                                    db_location_id = await db_instance.create_location(
                                        name=loc_analysis.location_name,
                                        description=loc_analysis.significance_analysis,
                                        coordinates=None, # Coordinates not extracted here
                                        user_id=self.user_id,
                                        project_id=self.project_id
                                    )

                                    # Add to knowledge base
                                    await self.add_to_knowledge_base(
                                        "location",
                                        f"{loc_analysis.location_name}: {loc_analysis.significance_analysis}",
                                        {
                                            "id": db_location_id, # Use actual DB ID
                                            "name": loc_analysis.location_name,
                                            "type": "location", # Ensure type is set correctly
                                            # Optionally add extracted connections/events/chars as metadata
                                            "connected_locations_mentioned": loc_analysis.connected_locations,
                                            "notable_events_mentioned": loc_analysis.notable_events,
                                            "character_associations_mentioned": loc_analysis.character_associations,
                                        }
                                    )

                                    # Prepare dict to return (using actual DB ID)
                                    location_dict = loc_analysis.model_dump()
                                    location_dict['id'] = db_location_id # Update dict with real ID
                                    location_dict['description'] = loc_analysis.significance_analysis # Align field name if needed
                                    new_locations_in_chapter.append(location_dict)

                                    # Add to set for checks within this run
                                    existing_location_names.add(loc_name_lower)

                                except Exception as db_kb_error:
                                    self.logger.error(f"Error saving/adding new location '{loc_analysis.location_name}': {db_kb_error}")
                                    # Continue processing other locations in the chapter

                        if new_locations_in_chapter:
                             all_new_locations.extend(new_locations_in_chapter)
                             self.logger.info(f"Found {len(new_locations_in_chapter)} new locations in chapter {chapter_id}.")

                        processed_chapter_ids.append(chapter_id) # Mark chapter as processed for locations

                except Exception as chapter_error:
                     self.logger.error(f"Error processing chapter {chapter_id} for locations: {chapter_error}", exc_info=True)
                     # Optionally mark as processed on error?

            # Mark successfully processed chapters
            for ch_id in processed_chapter_ids:
                 await db_instance.mark_chapter_processed(ch_id, self.user_id, PROCESS_TYPES['LOCATIONS'])

            self.logger.info(f"Location analysis complete. Found {len(all_new_locations)} new locations total.")
            return all_new_locations

        except Exception as e:
            self.logger.error(f"Error analyzing chapter locations: {e}", exc_info=True)
            raise


    async def analyze_unprocessed_chapter_events(self) -> List[Dict[str, Any]]:
        """Identifies and saves new events from unprocessed chapters."""
        self.logger.info("Analyzing unprocessed chapters for new events...")
        try:
            # Get unprocessed chapters for 'events' type
            chapters_to_process = await db_instance.get_latest_unprocessed_chapter_content(
                self.project_id,
                self.user_id,
                PROCESS_TYPES['EVENTS']
            )

            if not chapters_to_process:
                self.logger.info("No unprocessed chapters found for event analysis.")
                return []

            existing_events_data = await db_instance.get_events(self.project_id, self.user_id)
            existing_event_titles = {event['title'].lower() for event in existing_events_data}
            self.logger.debug(f"Found {len(existing_event_titles)} existing events.")

            parser = PydanticOutputParser(pydantic_object=EventAnalysis)
            event_llm = await self._get_llm(self.model_settings['extractionLLM'])
            fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=event_llm)

            prompt = ChatPromptTemplate.from_template("""
            Analyze the following chapter content and identify all significant NEW events described that are NOT in the 'Existing Event Titles' list.
            A significant event is something that happens which impacts the plot, characters, or world state.

            Chapter Content:
            {chapter_content}

            Existing Event Titles (IGNORE THESE):
            {existing_event_titles_str}

            For each NEW event found:
            1. Create a concise Title summarizing the event.
            2. Write a Description detailing what happened based *only* on the chapter.
            3. Describe the Impact of the event on the story or characters.
            4. List the names of characters directly involved (`involved_characters`).
            5. Identify the Location where the event primarily takes place, if mentioned (`location`).

            Return ONLY new events. If all mentioned events seem to match existing titles, return an empty "events" list.

            Format response as JSON:
            {format_instructions}
            """)

            all_new_events = []
            processed_chapter_ids = []

            existing_titles_str = ", ".join(list(existing_event_titles)) if existing_event_titles else "None"

            for chapter in chapters_to_process:
                chapter_id = chapter['id']
                chapter_content = chapter['content']
                new_events_in_chapter = []

                # Chunking for large chapters might be needed here
                # chunks = self.chunk_content(chapter_content, self.MAX_INPUT_TOKENS // 2)
                # for chunk in chunks: ... process chunk ...

                try:
                    chain = prompt | event_llm | fixing_parser
                    result = await chain.ainvoke({
                        "chapter_content": chapter_content, # Use full chapter content for now
                        "existing_event_titles_str": existing_titles_str,
                        "format_instructions": parser.get_format_instructions()
                    })

                    if result and hasattr(result, 'events'):
                        for event_desc in result.events:
                            event_title_lower = event_desc.title.lower()
                            # Double check against existing titles
                            if event_title_lower not in existing_event_titles:
                                try:
                                    # Resolve character/location IDs (optional, could be done later)
                                    character_id = None
                                    if event_desc.involved_characters:
                                        # Basic: find first character, could be more complex
                                        char_data = await db_instance.get_characters(self.user_id, self.project_id, name=event_desc.involved_characters[0])
                                        if char_data: character_id = char_data['id']

                                    location_id = None
                                    if event_desc.location:
                                        loc_data = await db_instance.get_location_by_name(event_desc.location, self.user_id, self.project_id)
                                        if loc_data: location_id = loc_data['id']

                                    # Create event in DB
                                    db_event_id = await db_instance.create_event(
                                        title=event_desc.title,
                                        description=event_desc.description,
                                        date=datetime.now(timezone.utc), # Placeholder date, needs better handling
                                        project_id=self.project_id,
                                        user_id=self.user_id,
                                        character_id=character_id,
                                        location_id=location_id
                                    )

                                    # Add to knowledge base
                                    kb_metadata = {
                                         "id": db_event_id,
                                         "title": event_desc.title,
                                         "type": "event",
                                         "impact": event_desc.impact,
                                         "involved_characters": event_desc.involved_characters,
                                         "location_name": event_desc.location, # Store name from extraction
                                         "location_id": location_id # Store resolved ID if found
                                    }
                                    await self.add_to_knowledge_base(
                                        "event",
                                        event_desc.description,
                                        kb_metadata
                                    )

                                    event_dict = event_desc.model_dump()
                                    event_dict['id'] = db_event_id # Add real ID
                                    new_events_in_chapter.append(event_dict)

                                    existing_event_titles.add(event_title_lower)

                                except Exception as db_kb_error:
                                    self.logger.error(f"Error saving/adding new event '{event_desc.title}': {db_kb_error}")

                        if new_events_in_chapter:
                             all_new_events.extend(new_events_in_chapter)
                             self.logger.info(f"Found {len(new_events_in_chapter)} new events in chapter {chapter_id}.")

                        processed_chapter_ids.append(chapter_id) # Mark chapter processed

                except Exception as chapter_error:
                     self.logger.error(f"Error processing chapter {chapter_id} for events: {chapter_error}", exc_info=True)

            # Mark successfully processed chapters
            for ch_id in processed_chapter_ids:
                 await db_instance.mark_chapter_processed(ch_id, self.user_id, PROCESS_TYPES['EVENTS'])

            self.logger.info(f"Event analysis complete. Found {len(all_new_events)} new events total.")
            return all_new_events

        except Exception as e:
            self.logger.error(f"Error analyzing chapter events: {e}", exc_info=True)
            raise


    async def analyze_event_connections(self) -> List[EventConnection]:
        """Analyzes and saves connections between existing events."""
        self.logger.info("Analyzing connections between existing events...")
        try:
            events = await db_instance.get_events(self.project_id, self.user_id, limit=100) # Limit scope
            if len(events) < 2:
                self.logger.info("Not enough events to analyze connections.")
                return []

            existing_connections_data = await db_instance.get_event_connections(self.project_id, self.user_id)
            existing_keys = {tuple(sorted([c['event1_id'], c['event2_id']])) for c in existing_connections_data}
            self.logger.debug(f"Found {len(existing_keys)} existing event connections.")

            # Early exit if all possible pairs are connected (N*(N-1)/2)
            max_possible_connections = (len(events) * (len(events) - 1)) / 2
            if len(existing_keys) >= max_possible_connections:
                 self.logger.info("All possible event connections seem to exist.")
                 # Convert existing data to EventConnection model if needed for return type consistency
                 # return [EventConnection(**conn_data) for conn_data in existing_connections_data]
                 return [] # Or return empty list as no NEW connections can be found

            parser = PydanticOutputParser(pydantic_object=EventConnectionAnalysis)
            connection_llm = await self._get_llm(self.model_settings['extractionLLM'])
            fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=connection_llm)


            prompt = ChatPromptTemplate.from_template("""
            Analyze the list of events below. Identify plausible NEW causal, consequential, thematic, or temporal connections between pairs of events that are NOT already listed in 'Existing Connections'.

            Events:
            {events_json}

            Existing Connections (Ignore pairs present here):
            {existing_connections_json}

            For each NEW connection found between two events:
            1. Provide the IDs of both events (`event1_id`, `event2_id`). Ensure this pair is new.
            2. Determine the connection type (e.g., 'cause_effect', 'leads_to', 'contrast', 'parallel', 'foreshadows', 'temporal_sequence').
            3. Describe the nature of the connection.
            4. Explain the impact or significance of this connection to the overall narrative or character arcs.
            5. (Optional) List characters involved in linking the events (`characters_involved` as string).
            6. (Optional) Describe any spatial relationship (`location_relation`).

            Focus on meaningful connections. Do not create trivial links. Return ONLY new connections.

            Format response as JSON:
            {format_instructions}
            """)

            # Process events in batches if list is very long (simplified: process all for now)
            events_json = json.dumps([{ "id": e['id'], "title": e['title'], "desc_snippet": e['description'][:100]+"..."} for e in events], indent=2)
            existing_connections_json = json.dumps([{"e1": c['event1_id'], "e2": c['event2_id'], "type": c['connection_type']} for c in existing_connections_data], indent=2)

            chain = prompt | connection_llm | fixing_parser
            result = await chain.ainvoke({
                "events_json": events_json,
                "existing_connections_json": existing_connections_json,
                "format_instructions": parser.get_format_instructions()
            })

            saved_connections_output = []
            if result and hasattr(result, 'connections'):
                # Deduplicate connections found by the LLM within this run
                deduped_result = result.deduplicate_connections()

                for conn in deduped_result.connections:
                    # Final check against existing DB keys
                    if not conn.event1_id or not conn.event2_id: continue # Skip if LLM hallucinated IDs
                    conn_key = tuple(sorted([conn.event1_id, conn.event2_id]))
                    if conn_key not in existing_keys:
                        try:
                             # Create connection in DB
                             db_conn_id = await db_instance.create_event_connection(
                                 event1_id=conn.event1_id,
                                 event2_id=conn.event2_id,
                                 connection_type=conn.connection_type,
                                 description=conn.description,
                                 impact=conn.impact,
                                 project_id=self.project_id,
                                 user_id=self.user_id
                                 # Add characters_involved, location_relation if saving them
                             )

                             # Add to KB (optional)
                             kb_content = f"Connection ({conn.connection_type}) between Event {conn.event1_id} and Event {conn.event2_id}: {conn.description}. Impact: {conn.impact}"
                             await self.add_to_knowledge_base(
                                 "event_connection",
                                 kb_content,
                                 {
                                     "id": db_conn_id,
                                     "type": "event_connection",
                                     "event1_id": conn.event1_id,
                                     "event2_id": conn.event2_id,
                                     "connection_type": conn.connection_type
                                 }
                             )

                             # Prepare output model
                             conn.id = db_conn_id # Add the generated ID
                             saved_connections_output.append(conn)
                             existing_keys.add(conn_key) # Add to set for this run

                        except Exception as db_kb_error:
                             self.logger.error(f"Error saving/adding event connection between {conn.event1_id} and {conn.event2_id}: {db_kb_error}")

            self.logger.info(f"Event connection analysis complete. Found {len(saved_connections_output)} new connections.")
            return saved_connections_output

        except Exception as e:
            self.logger.error(f"Error analyzing event connections: {e}", exc_info=True)
            raise


    async def analyze_location_connections(self) -> List[LocationConnection]:
        """Analyzes and saves connections between existing locations."""
        self.logger.info("Analyzing connections between existing locations...")
        try:
            locations = await db_instance.get_locations(self.user_id, self.project_id)
            if len(locations) < 2:
                self.logger.info("Not enough locations to analyze connections.")
                return []

            existing_connections_data = await db_instance.get_location_connections(self.project_id, self.user_id)
            existing_keys = {tuple(sorted([c['location1_id'], c['location2_id']])) for c in existing_connections_data}
            self.logger.debug(f"Found {len(existing_keys)} existing location connections.")

            max_possible_connections = (len(locations) * (len(locations) - 1)) / 2
            if len(existing_keys) >= max_possible_connections:
                 self.logger.info("All possible location connections seem to exist.")
                 return []

            parser = PydanticOutputParser(pydantic_object=LocationConnectionAnalysis)
            connection_llm = await self._get_llm(self.model_settings['extractionLLM'])
            # Note: Using base self.llm here from original code, could switch to extractionLLM
            fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=connection_llm)


            prompt = ChatPromptTemplate.from_template("""
            Analyze the list of locations below. Identify plausible NEW connections (physical adjacency, cultural links, historical ties, trade routes, travel paths) between pairs of locations that are NOT already listed in 'Existing Connections'.

            Locations:
            {locations_json}

            Existing Connections (Ignore pairs present here):
            {existing_connections_json}

            For each NEW connection found between two locations:
            1. Provide the IDs and Names of both locations (`location1_id`, `location1_name`, `location2_id`, `location2_name`). Ensure this pair is new.
            2. Determine the connection type (e.g., 'physical', 'cultural', 'historical', 'trade_route', 'travel_path').
            3. Describe the nature of the connection.
            4. Mention any notable travel routes, if applicable (`travel_route`).
            5. Describe any cultural exchanges or relationships, if applicable (`cultural_exchange`).

            Focus on meaningful connections based on potential proximity, shared history, or narrative function implied by their descriptions. Return ONLY new connections.

            Format response as JSON:
            {format_instructions}
            """)

            locations_json = json.dumps([{ "id": loc['id'], "name": loc['name'], "desc_snippet": loc['description'][:100]+"..."} for loc in locations], indent=2)
            existing_connections_json = json.dumps([{"loc1": c['location1_id'], "loc2": c['location2_id'], "type": c['connection_type']} for c in existing_connections_data], indent=2)

            chain = prompt | connection_llm | fixing_parser
            result = await chain.ainvoke({
                "locations_json": locations_json,
                "existing_connections_json": existing_connections_json,
                "format_instructions": parser.get_format_instructions()
            })

            saved_connections_output = []
            if result and hasattr(result, 'connections'):
                # Deduplicate connections found by the LLM within this run
                deduped_result = result.deduplicate_connections()

                for conn in deduped_result.connections:
                    # Final check against existing DB keys
                    if not conn.location1_id or not conn.location2_id: continue
                    conn_key = tuple(sorted([conn.location1_id, conn.location2_id]))
                    if conn_key not in existing_keys:
                        try:
                             # Ensure names are present (LLM might forget)
                             loc1 = next((l for l in locations if l['id'] == conn.location1_id), None)
                             loc2 = next((l for l in locations if l['id'] == conn.location2_id), None)
                             if not loc1 or not loc2:
                                 self.logger.warning(f"Could not find location data for IDs {conn.location1_id} or {conn.location2_id}. Skipping connection.")
                                 continue
                             conn.location1_name = loc1['name'] # Ensure correct names
                             conn.location2_name = loc2['name']

                             # Create connection in DB
                             db_conn_id = await db_instance.create_location_connection(
                                 location1_id=conn.location1_id,
                                 location2_id=conn.location2_id,
                                 location1_name=conn.location1_name,
                                 location2_name=conn.location2_name,
                                 connection_type=conn.connection_type,
                                 description=conn.description,
                                 travel_route=conn.travel_route,
                                 cultural_exchange=conn.cultural_exchange,
                                 project_id=self.project_id,
                                 user_id=self.user_id
                             )

                             # Add to KB (optional)
                             kb_content = f"Connection ({conn.connection_type}) between {conn.location1_name} and {conn.location2_name}: {conn.description}."
                             if conn.travel_route: kb_content += f" Travel: {conn.travel_route}."
                             if conn.cultural_exchange: kb_content += f" Culture: {conn.cultural_exchange}."

                             await self.add_to_knowledge_base(
                                 "location_connection",
                                 kb_content,
                                 {
                                     "id": db_conn_id,
                                     "type": "location_connection",
                                     "location1_id": conn.location1_id,
                                     "location2_id": conn.location2_id,
                                     "location1_name": conn.location1_name,
                                     "location2_name": conn.location2_name,
                                     "connection_type": conn.connection_type
                                 }
                             )

                             # Prepare output model
                             conn.id = db_conn_id # Add the generated ID
                             saved_connections_output.append(conn)
                             existing_keys.add(conn_key)

                        except Exception as db_kb_error:
                             self.logger.error(f"Error saving/adding location connection between {conn.location1_id} and {conn.location2_id}: {db_kb_error}")


            self.logger.info(f"Location connection analysis complete. Found {len(saved_connections_output)} new connections.")
            return saved_connections_output

        except Exception as e:
            self.logger.error(f"Error analyzing location connections: {e}", exc_info=True)
            raise


    async def get_chat_history(self) -> List[Dict[str, Any]]:
        """Retrieves the chat history from the database."""
        self.logger.debug(f"Retrieving chat history for project {self.project_id}")
        try:
            # Directly call the database instance method
            history = await db_instance.get_chat_history(self.user_id, self.project_id)
            # Ensure it returns a list (db method should handle None case)
            return history if isinstance(history, list) else []
        except Exception as e:
            self.logger.error(f"Error retrieving chat history: {e}", exc_info=True)
            # Return empty list on error to avoid breaking chat interfaces
            return []


    async def reset_memory(self):
         # This only affects the RunnableWithMessageHistory if used.
         # For the graph, state is passed explicitly.
         # If DB stores history, delete it there.
        await db_instance.delete_chat_history(self.user_id, self.project_id)
        self.logger.info(f"Chat history deleted for project {self.project_id}")


    async def get_knowledge_base_content(self):
        """Gets all content from the vector store for this project."""
        if not self.vector_store: raise RuntimeError("Vector store not initialized.")
        return await self.vector_store.get_knowledge_base_content()

    async def reset_knowledge_base(self):
        """Resets the vector store collection for the project."""
        if not self.vector_store: raise RuntimeError("Vector store not initialized.")
        self.logger.info(f"Resetting knowledge base for project {self.project_id}")
        restored_items = await self.vector_store.reset_knowledge_base()
        self.logger.info(f"Knowledge base reset complete. Restored {len(restored_items)} items from backup.")
        return restored_items

    # --- Utility Methods ---
    def chunk_content(self, content: str, max_chunk_size: int) -> List[str]:
        """Splits text into chunks based on estimated token count (simple version)."""
        if not content: return []
        # This is complex to do accurately without the tokenizer.
        # Simple splitting by paragraphs or sentences is often sufficient.
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        chunks = []
        current_chunk = ""
        for p in paragraphs:
            if not current_chunk:
                current_chunk = p
            elif self.estimate_token_count(current_chunk + "\n\n" + p) <= max_chunk_size:
                current_chunk += "\n\n" + p
            else:
                chunks.append(current_chunk)
                current_chunk = p
        if current_chunk:
            chunks.append(current_chunk)
        return chunks


# --- Global Cleanup ---
async def close_all_agent_managers():
    """Closes all active AgentManager instances."""
    managers_to_close = list(agent_managers.values())
    for manager in managers_to_close:
        try:
            await manager.close()
        except Exception as e:
            logging.getLogger(__name__).error(f"Error closing manager for user {manager.user_id}: {e}")

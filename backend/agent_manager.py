# backend/agent_manager.py
from typing import Dict, Any, List, Tuple, Optional, AsyncGenerator, Union
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.output_parsers import PydanticOutputParser
from langchain.docstore.document import Document
from datetime import datetime
import logging
from cachetools import TTLCache

from api_key_manager import ApiKeyManager
from database import db_instance
from pydantic import BaseModel, Field, ValidationError

import json
import re
# Load environment variables
load_dotenv()
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from vector_store import VectorStore
from langchain.output_parsers import OutputFixingParser
from langchain_community.cache import SQLiteCache
from langchain_core.globals import set_llm_cache
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain.chains.summarize import load_summarize_chain
import asyncio
from langchain.callbacks.base import BaseCallbackHandler
from datetime import timedelta
from models import ChapterValidation, CodexItem,  WorldbuildingSubtype, CodexItemType, CodexExtractionTypes

# Add at the top with other imports
PROCESS_TYPES = {
    'BACKSTORY': 'backstory',
    'RELATIONSHIPS': 'relationships',
    'LOCATIONS': 'locations',
    'EVENTS': 'events',
}

class StreamingRateLimiter(BaseCallbackHandler):
    def __init__(self, rpm_limit, tpm_limit, rpd_limit):
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        self.rpd_limit = rpd_limit
        self.request_count = 0
        self.token_count = 0
        self.daily_request_count = 0
        self.last_reset = datetime.now()
        self.last_day_reset = datetime.now().date()

    async def on_llm_start(self, serialized, prompts, **kwargs):
        await self.limit(sum(len(prompt.split()) for prompt in prompts))

    async def on_llm_new_token(self, token: str, **kwargs):
        await self.limit(1)  # Assuming each token is counted individually

    async def limit(self, token_count):
        current_time = datetime.now()
        
        if current_time - self.last_reset >= timedelta(minutes=1):
            self.request_count = 0
            self.token_count = 0
            self.last_reset = current_time

        if current_time.date() > self.last_day_reset:
            self.daily_request_count = 0
            self.last_day_reset = current_time.date()

        if (self.request_count >= self.rpm_limit or 
            self.token_count + token_count > self.tpm_limit or 
            self.daily_request_count >= self.rpd_limit):
            wait_time = 60 - (current_time - self.last_reset).total_seconds()
            await asyncio.sleep(max(0, wait_time))
            return await self.limit(token_count)

        self.token_count += token_count
        self.request_count += 1
        self.daily_request_count += 1

class CodexExtraction(BaseModel):
    new_items: List[CodexItem] = Field(default_factory=list, description="List of new codex items found in the chapter")


class GeneratedCodexItem(BaseModel):
    name: str = Field(description="Name of the codex item")
    description: str = Field(description="Detailed description of the codex item")


class CharacterBackstoryExtraction(BaseModel):
    character_id: str = Field(..., description="ID of the character")
    new_backstory: str = Field(..., description="New backstory information extracted from the chapter")



class RelationshipAnalysis(BaseModel):
    character1: str = Field(..., description="Name of the first character")
    character2: str = Field(..., description="Name of the second character")
    relationship_type: str = Field(..., description="Type of relationship between the characters")
    description: str = Field(..., description="Detailed description of the relationship")


class EventDescription(BaseModel):
    title: str = Field(..., description="Title of the event")
    description: str = Field(..., description="Detailed description of the event")
    impact: str = Field(..., description="Impact of the event on the story or characters")
    involved_characters: List[str] = Field(default_factory=list, description="Characters involved in the event")
    location: Optional[str] = Field(None, description="Location where the event takes place")

class RelationshipAnalysisList(BaseModel):
    relationships: List[RelationshipAnalysis] = Field(..., description="List of relationship analyses")

class EventAnalysis(BaseModel):
    events: List[EventDescription] = Field(..., description="List of events found in the chapter")


class LocationConnection(BaseModel):
    id: str
    location1_id: str
    location2_id: str
    location1_name: str
    location2_name: str
    connection_type: str
    description: str
    travel_route: Optional[str] = None
    cultural_exchange: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    def get_connection_key(self) -> Tuple[str, str]:
        """Get a unique key for this connection based on location IDs"""
        return tuple(sorted([self.location1_id, self.location2_id]))

class LocationConnectionAnalysis(BaseModel):
    connections: List[LocationConnection]

    def deduplicate_connections(self) -> 'LocationConnectionAnalysis':
        """Remove duplicate connections while preserving the first occurrence"""
        seen_connections = set()
        unique_connections = []
        
        for conn in self.connections:
            conn_key = conn.get_connection_key()
            if conn_key not in seen_connections:
                seen_connections.add(conn_key)
                unique_connections.append(conn)
        
        return LocationConnectionAnalysis(connections=unique_connections)


class LocationAnalysis(BaseModel):
    location_name: str
    location_id: str
    significance_analysis: str
    connected_locations: List[str]
    notable_events: List[str]
    character_associations: List[str]

class LocationAnalysisList(BaseModel):
    locations: List[LocationAnalysis]

class EventConnection(BaseModel):
    event1_id: str
    event2_id: str
    connection_type: str
    description: str
    impact: str
    characters_involved: Optional[str] = Field(default="")
    location_relation: str

    def get_connection_key(self) -> Tuple[str, str]:
        """Get a unique key for this connection based on event IDs"""
        return tuple(sorted([self.event1_id, self.event2_id]))

class EventConnectionAnalysis(BaseModel):
    connections: List[EventConnection]

    def deduplicate_connections(self) -> 'EventConnectionAnalysis':
        """Remove duplicate connections while preserving the first occurrence"""
        seen_connections = set()
        unique_connections = []
        
        for conn in self.connections:
            # Skip connections with null IDs
            if not conn.event1_id or not conn.event2_id:
                continue
                
            conn_key = conn.get_connection_key()
            if conn_key not in seen_connections:
                seen_connections.add(conn_key)
                unique_connections.append(conn)
        
        return EventConnectionAnalysis(connections=unique_connections)

class KnowledgeBaseQuery(BaseModel):
    """Query the knowledge base for relevant information"""
    query: str = Field(
        ..., 
        description="The search query to find relevant information"
    )
    type_filter: Optional[List[str]] = Field(
        None, 
        description="Types of entries to search for (e.g., ['character', 'worldbuilding', 'item', 'lore'])"
    )
    limit: int = Field(
        default=5, 
        description="Maximum number of entries to retrieve",
        ge=1,
        le=20
    )

    def run(self, query: str, type_filter: Optional[List[str]] = None, limit: int = 5) -> str:
        return f"Querying knowledge base with: {query}, types: {type_filter}, limit: {limit}"



agent_managers: Dict[Tuple[str, str], 'AgentManager'] = {}
class AgentManager:
    _llm_cache = TTLCache(maxsize=100, ttl=3600)  # Class-level cache for LLM instances

    def __init__(self, user_id: str, project_id: str, api_key_manager: ApiKeyManager):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.user_id = user_id
        self.project_id = project_id
        self.api_key_manager = api_key_manager
        self.model_settings = None
        self.MAX_INPUT_TOKENS = None
        self.MAX_OUTPUT_TOKENS = None
        self.chat_history = None
        self.vector_store = None
        self.summarize_chain = None
        self.agents = {}
        self._lock = asyncio.Lock()
    @classmethod
    async def create(cls, user_id: str, project_id: str, api_key_manager: ApiKeyManager) -> 'AgentManager':
        instance = cls(user_id, project_id, api_key_manager)
        await instance.initialize()
        return instance

    async def initialize(self):
        self.api_key = await self._get_api_key()
        self.model_settings = await self._get_model_settings()
        self.MAX_INPUT_TOKENS = 2097152 if 'pro' in self.model_settings else 1048576
        self.MAX_OUTPUT_TOKENS = 8192
        self.chat_history = await db_instance.get_chat_history(self.user_id, self.project_id)
        if self.chat_history is None:
            self.chat_history = []  # Initialize as an empty list if no history exists

        self.setup_caching()
        self.llm = await self._get_llm(self.model_settings['mainLLM'])
        self.check_llm = await self._get_llm(self.model_settings['checkLLM'])
        
        self.vector_store = VectorStore(
            self.user_id, 
            self.project_id, 
            self.api_key, 
            self.model_settings['embeddingsModel']
        )
        self.vector_store.set_llm(self.llm)
        
        self.summarize_chain = load_summarize_chain(self.llm, chain_type="map_reduce")

        # Register this instance for cleanup
        agent_managers[(self.user_id, self.project_id)] = self

    def __del__(self):
        asyncio.create_task(self.close())

    async def close(self):
        # Clean up resources
        self._llm_cache.clear()
        if self.vector_store:
            # Check if the vector_store has a close method before calling it
            if hasattr(self.vector_store, 'close') and callable(self.vector_store.close):
                self.vector_store.close()
            # If there's no close method, we might want to perform any necessary cleanup here
            # For example, if there's a client that needs to be closed:
            # if hasattr(self.vector_store, '_client') and hasattr(self.vector_store._client, 'close'):
            #     self.vector_store._client.close()
        self.chat_history = []
        self.agents.clear()
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))    
    async def _get_llm(self, model: str) -> ChatGoogleGenerativeAI:
        self.logger.debug(f"Getting LLM instance for model: {model}")
        async with self._lock:
            if model in self._llm_cache:
                return self._llm_cache[model]

            rate_limiter = StreamingRateLimiter(
                rpm_limit=2 if 'pro' in self.model_settings else 15,
                tpm_limit=32000 if 'pro' in self.model_settings else 1000000,
                rpd_limit=50 if 'pro' in self.model_settings else 1500
            )

            llm = ChatGoogleGenerativeAI(
                model=model,
                google_api_key=self.api_key,
                temperature=self.model_settings.get('temperature', 0.7),
                max_output_tokens=self.MAX_OUTPUT_TOKENS,
                max_input_tokens=self.MAX_INPUT_TOKENS,
                caching=True,
                streaming=True,
                callbacks=[rate_limiter],
            )

            self._llm_cache[model] = llm
            return llm


    async def _get_api_key(self) -> str:
        api_key = await self.api_key_manager.get_api_key(self.user_id)
        if not api_key:
            raise ValueError("API key not set. Please set your API key in the settings.")
        return api_key

    def _get_model_settings(self) -> dict:
        return db_instance.get_model_settings(self.user_id)

    def setup_caching(self):
        # Set up SQLite caching
        set_llm_cache(SQLiteCache(database_path=".langchain.db"))

    async def generate_chapter(
        self,
        chapter_number: int,
        plot: str,
        writing_style: str,
        instructions: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            # Construct context using vector store directly
            context = await self._construct_context(
                plot, 
                writing_style,
                self.vector_store,
            )
            
            # Use our existing _construct_prompt method
            prompt_template = self._construct_prompt(instructions, context)
            
            # Create the chain
            chain = (
                prompt_template | 
                self.llm | 
                StrOutputParser()
            )

            chat_history = ChatMessageHistory()
            
            # Get relevant previous chapters from vector store
            previous_chapters = await self.vector_store.similarity_search(
                query_text=plot,
                filter={"type": "chapter"},
                k=3
            )
            
            # Add relevant chapters to chat history
            for doc in previous_chapters:
                chat_history.add_user_message(doc.page_content)
                chat_history.add_ai_message("Understood.")

            chain = RunnableWithMessageHistory(
                chain,
                lambda session_id: chat_history,
                input_messages_key="context",
                history_messages_key="chat_history",
            )

            # Generate the chapter content
            chapter_content = await chain.ainvoke(
                {
                    "chapter_number": chapter_number,
                    "plot": plot,
                    "writing_style": writing_style,
                    "style_guide": instructions.get('styleGuide', ''),
                    "additional_instructions": instructions.get('additionalInstructions', ''),
                    "context": context
                },
                config={"configurable": {"session_id": f"chapter_{chapter_number}"}}
            )

            if not chapter_content:
                raise ValueError("No chapter content was generated")

            # Generate title
            chapter_title = await self.generate_title(chapter_content, chapter_number)

            # Check and extract codex items
            new_codex_items = await self.check_and_extract_new_codex_items(chapter_content)

            # Perform validity check
            validity_check = await self.check_chapter(
                chapter_content,
                instructions,
                await self.vector_store.similarity_search(plot, k=3)
            )

            # Return the complete result
            return {
                "content": chapter_content,
                "chapter_title": chapter_title,
                "new_codex_items": new_codex_items,
                "validity_check": validity_check
            }

        except Exception as e:
            self.logger.error(f"Error in generate_chapter: {str(e)}", exc_info=True)
            raise

    def _construct_prompt(self, instructions: Dict[str, Any], context: str) -> ChatPromptTemplate:
        system_template = """You are a skilled author tasked with writing a chapter for a novel. Follow these instructions EXACTLY:

        Context:
        {context}

        Writing Requirements (YOU MUST FOLLOW ALL OF THESE):
        1. Setting/Plot: {plot}
        2. Writing Style: {writing_style}
           IMPORTANT: This is a STRICT requirement. Every single sentence MUST follow this style exactly.
        3. Style Guide: {style_guide}
           IMPORTANT: This is a STRICT requirement. The entire text MUST follow this guide exactly.
        4. Additional Requirements: {additional_instructions}
           IMPORTANT: This is a STRICT requirement. The text MUST incorporate these instructions exactly.
        
        FORMATTING REQUIREMENTS (MANDATORY):
        - Divide the chapter into clear, logical paragraphs
        - Use proper spacing between paragraphs (double line breaks)
        - Start new paragraphs for:
            * New scenes or time shifts
            * Changes in speaker during dialogue
            * Changes in location
            * Shifts in perspective
            * New ideas or topics
        - Format dialogue properly:
            * Each speaker gets a new paragraph
            * Use proper quotation marks
            * Include dialogue tags and actions
        - Vary paragraph length for rhythm and pacing
        - Use scene breaks (three asterisks: ***) for major scene changes
        
        CRITICAL RULES:
        - NEVER use the word "Codex" in the story - this is a technical term
        - Follow the writing style EXACTLY as specified - no exceptions
        - Stay true to the specified setting/plot - no deviations
        - Every single requirement must be followed precisely
        - If asked to end sentences with specific words or phrases, EVERY sentence must end that way
        - If asked to write in a specific style, maintain it consistently throughout
        
        Write Chapter {chapter_number} of the novel. Start writing immediately without any preamble or chapter heading."""

        human_template = "Please write the chapter following the above requirements."
        
        return ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", human_template)
        ])

    async def _stream_chapter_generation(self, chain, variables: Dict[str, Any], config: Dict[str, Any] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream the chapter generation using the provided chain and variables.

        Args:
            chain: The LangChain chain to use for generation.
            variables (Dict[str, Any]): The variables to pass to the chain.
            config (Dict[str, Any], optional): Additional configuration for the chain.

        Yields:
            Dict[str, Any]: Chunks of generated content or error information.
        """
        try:
            #self.logger.debug(f"Starting chapter generation with variables: {variables}")
            stream_kwargs = {}
            if config:
                stream_kwargs['config'] = config

            async for chunk in chain.astream(variables, **stream_kwargs):
                if isinstance(chunk, str):
                    #self.logger.debug(f"Received chunk: {chunk[:100]}...")  # Log first 100 chars
                    yield {"type": "chunk", "content": chunk}
                else:
                   # self.logger.debug(f"Received non-string chunk: {chunk}")
                    yield chunk
        except Exception as e:
            self.logger.error(f"Error in _stream_chapter_generation: {str(e)}")
            yield {"error": str(e)}



    async def _construct_context(self, plot: str, writing_style: str, vector_store: VectorStore) -> str:
        try:
            self.logger.debug("Starting context construction")
            

            query = f"Plot: {plot}\nWriting Style: {writing_style}"
            chapters = await vector_store.similarity_search(
                query_text=query,
                filter={"type": "chapter"},
                k=5  # Increased from 3 to 5 for better context
            )
            
            context_parts = []
            context_parts.append(f"Plot: {plot}\n")
            context_parts.append(f"Writing Style: {writing_style}\n")
            
            # Process chapters
            self.logger.debug("Processing chapters...")
            for chapter in chapters:
                chapter_number = chapter.metadata.get('chapter_number', 'Unknown')
                chapter_content = chapter.page_content
                # Include chapter summary if available
                summary = chapter.metadata.get('summary', '')
                if summary:
                    context_parts.append(f"Chapter {chapter_number} Summary: {summary}\n")
                context_parts.append(f"Chapter {chapter_number}: {chapter_content}\n")
            
            self.logger.debug("Fetching relevant codex items...")
            codex_items = await vector_store.similarity_search(
                query_text=query,
                filter={"type": {"$in": [t.value for t in CodexItemType]}},
                k=10  # Increased from 5 to 10 for better coverage
            )
            
            # Add codex items to context
            if codex_items:
                context_parts.append("\nRelevant Codex Items:")
                for item in codex_items:
                    name = item.metadata.get('name', 'Unknown')
                    item_type = item.metadata.get('type', 'Unknown')
                    # Include rules and relationships if available
                    rules = item.metadata.get('rules', [])
                    relationships = item.metadata.get('relationships', {})
                    
                    context_parts.append(f"\n{name} ({item_type}): {item.page_content}")
                    if rules:
                        context_parts.append("Rules:")
                        for rule in rules:
                            context_parts.append(f"- {rule}")
                    if relationships:
                        context_parts.append("Relationships:")
                        for rel_type, rel_items in relationships.items():
                            context_parts.append(f"- {rel_type}: {', '.join(rel_items)}")
            
            final_context = "\n".join(context_parts)
            return final_context
            
        except Exception as e:
            self.logger.error(f"Error constructing context: {str(e)}", exc_info=True)
            raise

    def summarize_chapter(self, chapter_content: str) -> str:
        document = Document(page_content=chapter_content)
        summary = self.summarize_chain.run([document])
        return summary

    def estimate_token_count(self, text: str) -> int:
        if not text or not text.strip():
            return 0
        return self.llm.get_num_tokens(text)

    def get_embedding(self, text: str) -> List[float]:
        return self.embeddings.embed_query(text)

    async def check_chapter(self, chapter: str, instructions: Dict[str, Any], 
                        previous_chapters: List[Document]) -> Dict[str, Any]:
        async with self._lock:
            try:
                truncated_previous_chapters = self._truncate_previous_chapters(previous_chapters)
                
                evaluation_criteria = [
                    "Plot Consistency",
                    "Character Development",
                    "Pacing",
                    "Dialogue Quality",
                    "Setting Description",
                    "Adherence to Writing Style",
                    "Emotional Impact",
                    "Conflict and Tension",
                    "Theme Exploration",
                    "Grammar and Syntax"
                ]

                prompt = ChatPromptTemplate.from_template("""
                You are an expert editor tasked with evaluating the quality and consistency of a novel chapter. Analyze the following chapter thoroughly:

                Chapter:
                {chapter}

                Instructions:
                {instructions}

                Previous Chapters:
                {truncated_previous_chapters}
                
                Chapter words: {chapter_word_count}

                Evaluate the chapter based on the following criteria:
                {evaluation_criteria}

                For each criterion, provide a score from 1 to 10 and a brief explanation, never give a score of 0.

                Additionally, assess the following:
                1. Overall validity (Is the chapter acceptable?)
                2. Style guide adherence
                3. Continuity with previous chapters
                4. Areas for improvement

                Provide your analysis in the following format:
                {format_instructions}
                """)

                parser = PydanticOutputParser(pydantic_object=ChapterValidation)
                fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=self.check_llm)
                
                chain = prompt | self.check_llm | fixing_parser
                
                result = await chain.ainvoke({
                    "chapter": chapter,
                    "instructions": json.dumps(instructions),
                    "truncated_previous_chapters": truncated_previous_chapters,
                    "chapter_word_count": len(chapter.split()),
                    "evaluation_criteria": "\n".join(evaluation_criteria),
                    "format_instructions": parser.get_format_instructions()
                })

                # Convert the result to a dictionary format matching the database schema
                validity_check = {
                    'is_valid': result.is_valid,
                    'overall_score': result.overall_score,
                    'general_feedback': result.general_feedback,
                    'style_guide_adherence_score': result.style_guide_adherence.score,
                    'style_guide_adherence_explanation': result.style_guide_adherence.explanation,
                    'continuity_score': result.continuity.score,
                    'continuity_explanation': result.continuity.explanation,
                    'areas_for_improvement': result.areas_for_improvement
                }

                return validity_check

            except ValidationError as e:
                self.logger.error(f"Validation error in check_chapter: {e}")
                return self._create_error_response("Invalid output format from validity check.")
            except Exception as e:
                self.logger.error(f"An error occurred in check_chapter: {str(e)}", exc_info=True)
                return self._create_error_response("An error occurred during validity check.")

    def _create_error_response(self, message: str) -> Dict[str, Any]:
        """Create a standardized error response dictionary"""
        return {
            'is_valid': False,
            'overall_score': 0,
            'general_feedback': message,
            'style_guide_adherence_score': 0,
            'style_guide_adherence_explanation': 'Error occurred during validation',
            'continuity_score': 0,
            'continuity_explanation': 'Error occurred during validation',
            'areas_for_improvement': ['Unable to complete validation']
        }

    async def save_validity_feedback(self, result: Dict[str, Any], chapter_number: int, chapter_id: str):
        try:
            # Get chapter title
            chapter = await db_instance.get_chapter(chapter_id, self.user_id, self.project_id)  # Add await here
            chapter_title = chapter.get('title', f'Chapter {chapter_number}') if chapter else f'Chapter {chapter_number}'

            # Save validity check with all required parameters
            await db_instance.save_validity_check(
                chapter_id=chapter_id,
                chapter_title=chapter_title,
                is_valid=result['is_valid'],
                overall_score=result['overall_score'],
                general_feedback=result['general_feedback'],
                style_guide_adherence_score=result['style_guide_adherence_score'],
                style_guide_adherence_explanation=result['style_guide_adherence_explanation'],
                continuity_score=result['continuity_score'],
                continuity_explanation=result['continuity_explanation'],
                areas_for_improvement=result['areas_for_improvement'],
                user_id=self.user_id,
                project_id=self.project_id
            )
        except Exception as e:
            self.logger.error(f"Error saving validity feedback: {str(e)}")
            raise

    async def add_to_knowledge_base(self, content_type: str, content: str, metadata: Dict[str, Any]) -> str:
        try:
            if self.vector_store is None:
                await self.initialize()

            # Ensure metadata includes the content type
            metadata['type'] = content_type

            filtered_metadata = {k: v for k, v in metadata.items() if v is not None}

            # Batch embeddings if multiple items need to be added
            if not hasattr(self, '_embedding_batch'):
                self._embedding_batch = []
            
            self._embedding_batch.append((content, filtered_metadata))
            
            if len(self._embedding_batch) >= 10:  # Process in batches of 10
                await self._process_embedding_batch()

            # Add the content to the vector store and get the embedding ID
            embedding_id = await self.vector_store.add_to_knowledge_base(content, metadata=filtered_metadata)

            return embedding_id
        except Exception as e:
            self.logger.error(f"Error adding to knowledge base: {str(e)}", exc_info=True)
            raise
    

    async def update_or_remove_from_knowledge_base(self, identifier: Union[str, Dict[str, str]], action: str, new_content: str = None, new_metadata: Dict[str, Any] = None):
        try:
            # Handle both string embedding_id and dictionary identifier
            embedding_id = identifier if isinstance(identifier, str) else await self.vector_store.get_embedding_id(
                item_id=identifier['item_id'],
                item_type=identifier['item_type']
            )
            
            if embedding_id is None:
                self.logger.warning(f"No embedding found for identifier: {identifier}")
                return
                
            if action == "delete":
                await self.vector_store.delete_from_knowledge_base(embedding_id)
            elif action == "update":
                if new_content is None and new_metadata is None:
                    raise ValueError("Either new_content or new_metadata must be provided for update action")
                await self.vector_store.update_in_knowledge_base(embedding_id, new_content, new_metadata)
            else:
                raise ValueError(f"Invalid action: {action}. Must be either 'delete' or 'update'")
                
        except Exception as e:
            self.logger.error(f"Error in update_or_remove_from_knowledge_base: {str(e)}")
            raise

    async def query_knowledge_base(self, query: str, chat_history: List[Dict[str, str]] = None) -> str:
        try:

            docs = await self.vector_store.similarity_search(
                query_text=query,
                k=20  # Increased from 5 to 20 as per recommendation
            )
            
            if not docs:
                return "I don't have enough information to answer that question."

            # Include metadata in context
            context_parts = []
            for doc in docs:
                content = doc.page_content
                metadata = doc.metadata
                
                # Add document type and name if available
                doc_type = metadata.get('type', 'Unknown')
                doc_name = metadata.get('name', '')
                if doc_name:
                    context_parts.append(f"\n{doc_type.capitalize()}: {doc_name}")
                
                # Add summary if available
                summary = metadata.get('summary', '')
                if summary:
                    context_parts.append(f"Summary: {summary}")
                
                # Add rules if available
                rules = metadata.get('rules', [])
                if rules:
                    context_parts.append("Rules:")
                    for rule in rules:
                        context_parts.append(f"- {rule}")
                
                # Add relationships if available
                relationships = metadata.get('relationships', {})
                if relationships:
                    context_parts.append("Related Items:")
                    for rel_type, rel_items in relationships.items():
                        context_parts.append(f"- {rel_type}: {', '.join(rel_items)}")
                
                # Add the main content
                context_parts.append(content)
                context_parts.append("---")

            context = "\n".join(context_parts)

            messages = []
            if chat_history:
                for msg in chat_history:
                    if msg["type"] == "human":
                        messages.append(HumanMessage(content=msg["content"]))
                    else:
                        messages.append(AIMessage(content=msg["content"]))

            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a helpful AI assistant answering questions about a story. 
                Use the provided context to answer questions. The context includes various types of information:
                - Document content
                - Summaries
                - Rules and constraints
                - Relationships between items
                
                Use all available information to provide comprehensive answers.
                If you cannot answer based on the context, say so.
                
                Context: {context}"""),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{question}")
            ])

            llm = await self._get_llm(self.model_settings['knowledgeBaseQueryLLM'])
            chain = prompt | llm | StrOutputParser()
            
            return await chain.ainvoke({
                "context": context,
                "chat_history": messages,
                "question": query
            })

        except Exception as e:
            self.logger.error(f"Error in query_knowledge_base: {str(e)}", exc_info=True)
            raise

    async def generate_with_retrieval(self, query: str, chat_history: List[Dict[str, str]]) -> str:
        try:
            qa_llm = await self._get_llm(self.model_settings['knowledgeBaseQueryLLM'])
            
            # Create a history-aware retriever function
            async def retrieve_with_history(query: str) -> List[Document]:
                # Use the condense question prompt to get the standalone question
                condense_question_prompt = ChatPromptTemplate.from_messages([
                    ("human", "Given a chat history and the latest user question which might reference context in the chat history, formulate a standalone question which can be understood without the chat history. Do NOT answer the question, just reformulate it if needed and otherwise return it as is."),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{input}"),
                ])
                
                # Prepare chat history - ensure alternating human/ai messages
                messages = []
                for i, message in enumerate(chat_history):
                    if isinstance(message, dict):
                        if message.get('type') == 'human':
                            messages.append(HumanMessage(content=message['content']))
                        elif message.get('type') == 'ai':
                            # Only add AI message if previous message was human
                            if messages and isinstance(messages[-1], HumanMessage):
                                messages.append(AIMessage(content=message['content']))
                    elif isinstance(message, (HumanMessage, AIMessage)):
                        if isinstance(message, HumanMessage) or (messages and isinstance(messages[-1], HumanMessage)):
                            messages.append(message)
                    
                # Get the standalone question
                chain = condense_question_prompt | qa_llm | StrOutputParser()
                standalone_question = await chain.ainvoke({
                    "input": query,
                    "chat_history": messages
                })
                
                # Use similarity search instead of retriever
                return await self.vector_store.similarity_search(standalone_question, k=5)

            # Create the QA chain with proper message ordering
            qa_prompt = ChatPromptTemplate.from_messages([
                ("human", "You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question. If you don't know the answer, say that you don't know. Use three sentences maximum and keep the answer concise."),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                ("human", "Context: {context}"),
            ])
            
            # Get relevant documents using our history-aware retriever
            documents = await retrieve_with_history(query)
            
            # Format documents for the context
            context = "\n\n".join(doc.page_content for doc in documents)
            
            # Prepare chat history for QA
            messages = []
            for message in chat_history:
                if isinstance(message, dict):
                    if message.get('type') == 'human':
                        messages.append(HumanMessage(content=message['content']))
                    elif message.get('type') == 'ai':
                        messages.append(AIMessage(content=message['content']))
                elif isinstance(message, (HumanMessage, AIMessage)):
                    messages.append(message)
            
            # Get the answer
            chain = qa_prompt | qa_llm | StrOutputParser()
            answer = await chain.ainvoke({
                "input": query,
                "chat_history": messages,
                "context": context
            })

            # Format the response with source information
            response = f"{answer}\n\nSources:\n"
            for i, doc in enumerate(documents, 1):
                source_info = f"Type: {doc.metadata.get('type', 'Unknown')}"
                if 'name' in doc.metadata:
                    source_info += f", Name: {doc.metadata['name']}"
                response += f"{i}. {source_info}\n"

            return response

        except Exception as e:
            self.logger.error(f"Error in generate_with_retrieval: {str(e)}")
            return f"An error occurred while processing your query: {str(e)}"

    def _construct_query_context(self, relevant_docs: List[Document]) -> str:
        context = "\n".join([doc.page_content for doc in relevant_docs])
        return self._truncate_context(context)

    def _truncate_context(self, context: str) -> str:
        max_tokens = self.MAX_INPUT_TOKENS // 2  # Reserve half of the tokens for context
        summary = self.summarize_context(context)
        if self.estimate_token_count(summary) > max_tokens:
            return ' '.join(summary.split()[:max_tokens]) + "..."
        return context

    def get_existing_chapter_content(self, chapter_number: int, previous_chapters: List[Dict[str, Any]]) -> Optional[str]:
        existing_content = ""
        total_tokens = 0

        for chapter in previous_chapters:
            chapter_content = chapter['content']
            chapter_tokens = self.estimate_token_count(chapter_content)

            if total_tokens + chapter_tokens > self.MAX_INPUT_TOKENS // 2:
                break

            existing_content = f"Chapter {chapter['chapter_number']}: {chapter_content}\n" + existing_content
            total_tokens += chapter_tokens

        return existing_content if existing_content else None


    def _truncate_previous_chapters(self, previous_chapters: List[Document]) -> str:
        """Truncate previous chapters to fit within token limit"""
        try:
            truncated_content = []
            total_tokens = 0
            max_tokens = self.MAX_INPUT_TOKENS // 2  # Use half of max tokens for previous chapters
            
            for i, chapter in enumerate(previous_chapters):
                chapter_num = chapter.metadata.get('chapter_number', i + 1)  # Use metadata, fallback to index+1
                chapter_content = chapter.page_content
                
                # Estimate tokens for this chapter
                chapter_tokens = self.estimate_token_count(chapter_content)
                
                if total_tokens + chapter_tokens > max_tokens:
                    # If adding this chapter would exceed limit, summarize it
                    summary = self.summarize_content(chapter_content)
                    truncated_content.append(f"Chapter {chapter_num} (Summary): {summary}")
                    total_tokens += self.estimate_token_count(summary)
                else:
                    # Add full chapter if within limit
                    truncated_content.append(f"Chapter {chapter_num}: {chapter_content}")
                    total_tokens += chapter_tokens
                
                # Stop if we've reached token limit
                if total_tokens >= max_tokens:
                    break
            
            return "\n\n".join(truncated_content)
            
        except Exception as e:
            self.logger.error(f"Error truncating previous chapters: {str(e)}")
            raise

    async def generate_title(self, chapter_content: str, chapter_number: int) -> str:
        try:
            prompt = ChatPromptTemplate.from_template("""
            Generate a concise, engaging title for Chapter {chapter_number}. 
            The title should be brief (maximum 50 characters) but capture the essence of the chapter.
            
            Chapter content:
            {chapter_content}
            
            Return only the title, without "Chapter X:" prefix.
            """)
            
            llm = await self._get_llm(self.model_settings['titleGenerationLLM']) 
            chain = prompt | llm | StrOutputParser()
            
            title = await chain.ainvoke({
                "chapter_number": chapter_number,
                "chapter_content": chapter_content
            })
            
            # Clean and format the title
            title = title.strip()
            if len(title) > 200:  # Leave room for "Chapter X: " prefix
                title = title[:197] + "..."
                
            return f"Chapter {chapter_number}: {title}"
            
        except Exception as e:
            self.logger.error(f"Error generating title: {str(e)}")
            return f"Chapter {chapter_number}"

    async def get_knowledge_base_content(self):
        return await self.vector_store.get_knowledge_base_content()

    async def reset_memory(self):
        self.chat_history = []
        await db_instance.delete_chat_history(self.user_id, self.project_id)
        #self.logger.info("Chat history has been reset.")

    async def get_chat_history(self):
        return await db_instance.get_chat_history(self.user_id, self.project_id)

    def chunk_content(self, content: str, max_tokens: int) -> List[str]:
        if not content or not content.strip():
            return []
        
        chunks = []
        current_chunk = ""
        current_tokens = 0
        
        # Split by sentences but filter out empty ones
        sentences = [s.strip() for s in content.split('.') if s.strip()]
        
        for sentence in sentences:
            # Add the period back since we split it off
            sentence = sentence + '.'
            try:
                sentence_tokens = self.estimate_token_count(sentence)
                if current_tokens + sentence_tokens > max_tokens:
                    if current_chunk:  # Only append non-empty chunks
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence
                    current_tokens = sentence_tokens
                else:
                    current_chunk += ' ' + sentence if current_chunk else sentence
                    current_tokens += sentence_tokens
            except ValueError:
                # Skip empty sentences that might cause token counting errors
                continue
        
        # Add the last chunk if it exists
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    async def check_and_extract_new_codex_items(self, chapter: str) -> List[Dict[str, str]]:
        """Extract new codex items from a chapter"""
        try:
            if not chapter or not chapter.strip():
                self.logger.warning("Empty chapter content provided to check_and_extract_new_codex_items")
                return []

            # Get existing codex items from vector store for comparison
            existing_items = await self.vector_store.similarity_search(
                query_text=chapter,
                filter={"type": {"$in": [t.value for t in CodexExtractionTypes]}},
                k=50
            )
            
            existing_names = {doc.metadata.get('name') for doc in existing_items if doc.metadata.get('name')}
            
            chunks = self.chunk_content(chapter, self.MAX_INPUT_TOKENS // 2)
            all_new_items = []
            
            for chunk in chunks:
                parser = PydanticOutputParser(pydantic_object=CodexExtraction)
                fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=self.check_llm)
                
                prompt = ChatPromptTemplate.from_template("""
                    You are an expert at identifying new codex items in a story. Your task is to analyze 
                    the following chapter and identify ANY new codex items that are not in the provided 
                    list of existing codex items.

                    Valid types are: {valid_types}
                    For worldbuilding items, valid subtypes are: {valid_subtypes}

                    For each new codex item you find:
                    1. Provide its name
                    2. Write a brief description based on information in the chapter
                    3. Determine the type from the valid types listed above
                    4. If the type is "worldbuilding", determine the subtype from the valid subtypes listed above

                    Chapter:
                    {chapter}

                    Existing Item Names:
                    {existing_names}

                    Remember to include ANY new codex item not in the existing names list.
                    Be thorough and precise in your analysis.

                    {format_instructions}
                    """)

                codex_llm = await self._get_llm(self.model_settings['extractionLLM'])
                extraction_chain = prompt | codex_llm | fixing_parser
                
                result = await extraction_chain.ainvoke({
                    "chapter": chunk,
                    "existing_names": ", ".join(existing_names),
                    "valid_types": ", ".join([t.value for t in CodexExtractionTypes]),  # Use CodexExtractionTypes
                    "valid_subtypes": ", ".join([t.value for t in WorldbuildingSubtype]),
                    "format_instructions": parser.get_format_instructions()
                })
                
                all_new_items.extend(result.new_items)

            # Remove duplicates based on name
            seen_names = set()
            unique_items = []
            for item in all_new_items:
                if item.name not in seen_names:
                    seen_names.add(item.name)
                    unique_items.append(item)

            return [item.dict() for item in unique_items]
            
        except Exception as e:
            self.logger.error(f"Error in check_and_extract_new_codex_items: {str(e)}")
            raise

    async def analyze_character_relationships(self, characters: List[Dict[str, Any]]) -> List[RelationshipAnalysis]:
        """Analyze relationships between the provided characters"""
        try:
            # Get story context from chapters
            context = await db_instance.get_all_chapters(self.project_id, self.user_id)

            # Summarize context if it's too large
            if self.estimate_token_count(json.dumps(context)) > self.MAX_INPUT_TOKENS // 4:
                context = self.summarize_context(json.dumps(context))

            saved_relationships = []
            batch_size = 10  # Process 10 character pairs at a time
            
            for i in range(0, len(characters), batch_size):
                batch_characters = characters[i:i+batch_size]

                
                prompt = ChatPromptTemplate.from_template("""
                Analyze the relationships between these specific characters:

                Characters:
                {characters}

                Story Context:
                {context}

                For each pair of characters, provide:
                1. The names of both characters
                2. The type of relationship (family, friend, enemy, mentor, etc.)
                3. A detailed description of their relationship and interactions

                {format_instructions}
                """)

                parser = PydanticOutputParser(pydantic_object=RelationshipAnalysisList)
                llmRelationship = await self._get_llm(self.model_settings['extractionLLM'])
                chain = prompt | llmRelationship | parser

                result = await chain.ainvoke({
                    "characters": json.dumps(batch_characters, indent=2),
                    "context": context,
                    "format_instructions": parser.get_format_instructions()
                })


                if hasattr(result, 'relationships'):
                    for relationship in result.relationships:
                        # Verify both characters exist and are of type CHARACTER
                        char1 = next((c for c in characters 
                                    if c.get('name') == relationship.character1 
                                    and c['type'] == CodexItemType.CHARACTER.value), None)
                        char2 = next((c for c in characters 
                                    if c.get('name') == relationship.character2 
                                    and c['type'] == CodexItemType.CHARACTER.value), None)
                        
                        if char1 and char2:
                            # Create the relationship in the database
                            relationship_id = await db_instance.create_character_relationship(
                                character_id=char1['id'],
                                related_character_id=char2['id'],
                                relationship_type=relationship.relationship_type,
                                project_id=self.project_id,
                                description=relationship.description
                            )

                            # Add relationship info to knowledge base
                            relationship_content = (
                                f"Relationship between {relationship.character1} and {relationship.character2}: "
                                f"{relationship.relationship_type}. {relationship.description}"
                            )

                            await self.add_to_knowledge_base(
                                "relationship",
                                relationship_content,
                                {
                                    "name": f"{relationship.character1}-{relationship.character2} relationship",
                                    "type": "relationship",
                                    "relationship_id": relationship_id
                                }
                            )

                            saved_relationships.append(relationship)

            return saved_relationships

        except Exception as e:
            self.logger.error(f"Error analyzing character relationships: {str(e)}")
            raise

    async def generate_codex_item(self, codex_type: str, subtype: Optional[str], description: str) -> Dict[str, str]:
        #self.logger.debug(f"Generating codex item of type: {codex_type}, subtype: {subtype}, description: {description}")
        try:
            parser = PydanticOutputParser(pydantic_object=GeneratedCodexItem)
            llm = await self._get_llm(self.model_settings['mainLLM'])
            fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=llm)
            
            # Fetch all existing codex items for the user and project
            existing_codex_items = await db_instance.get_all_codex_items(self.user_id, self.project_id)
            
            prompt = ChatPromptTemplate.from_template("""
            You are a master storyteller and world-builder, tasked with creating rich, detailed codex items for an immersive narrative universe. Your expertise spans across various domains, including history, culture, geography, character development, and artifact creation. Your goal is to craft a new codex item that seamlessly integrates into the story world.

            Create a new codex item based on the following specifications:

            Type: {codex_type}
            Subtype: {subtype}
            Initial Description: {description}

            Existing Codex Items:
            {existing_codex_items}

            Your task:
            1. Devise a concise, evocative name for the codex item that captures its essence.
            2. Craft a comprehensive description that expands significantly on the initial description, adding depth, context, and vivid details.
            3. Ensure perfect consistency between the name, description, and the specified type and subtype.
            4. Make sure the new codex item is consistent with and complements the existing codex items. Do not contradict or duplicate information from existing items.

            Specific guidelines based on codex type:
            - Lore: Include a precise date or time period for the event. Describe its historical significance and lasting impact on the world.
            - Character: Detail the character's age, gender, physical appearance, personality traits, motivations, and role in the story world.
            - Item: Elaborate on the item's appearance, materials, origin, magical or technological properties, cultural significance, and any legends associated with it.
            - Worldbuilding: 
              * History: Describe key events, eras, or figures that shaped this aspect of the world.
              * Culture: Detail customs, beliefs, social structures, or artistic expressions.
              * Geography: Paint a vivid picture of the landscape, climate, flora, fauna, and how it influences the inhabitants.

            Remember to interweave the codex item seamlessly with existing world elements, hinting at connections to other potential codex items. Your description should ignite curiosity and invite further exploration of the story world.

            Types: worldbuilding, character, item, lore
            Subtypes (for worldbuilding only): history, culture, geography

            {format_instructions}
            """)
            
            llm = await self._get_llm(self.model_settings['mainLLM'])
            chain = prompt | llm | fixing_parser
            
            result = await chain.ainvoke({
                "codex_type": codex_type,
                "subtype": subtype or "N/A",
                "description": description,
                "existing_codex_items": json.dumps(existing_codex_items, indent=2),
                "format_instructions": parser.get_format_instructions()
            })
            
            #self.logger.debug(f"Generated codex item: {result}")
            
            if not isinstance(result, GeneratedCodexItem):
                raise ValueError("Invalid result type from chain.invoke")
            
            return {"name": result.name, "description": result.description}

        except Exception as e:
            self.logger.error(f"Error generating codex item: {str(e)}", exc_info=True)
            return {
                "name": "Error generating codex item",
                "description": f"An error occurred: {str(e)}"
            }



    async def extract_character_backstory(self, character_id: str, chapter_id: str):
        try:
            character = await db_instance.get_characters(self.user_id, self.project_id, character_id=character_id)
            
            # Get all unprocessed chapters
            chapters_data = await db_instance.get_latest_unprocessed_chapter_content(
                self.project_id,
                self.user_id,
                PROCESS_TYPES['BACKSTORY']
            )
            
            # If no unprocessed chapters, return early
            if not chapters_data:
                return CharacterBackstoryExtraction(
                    character_id=character_id,
                    new_backstory=""
                )

            all_backstory = []
            # Process each chapter
            for chapter in chapters_data:
                chapter_id = chapter['id']
                chapter_content = chapter['content']

                prompt = ChatPromptTemplate.from_template("""
                Given the following information about a character and a new chapter, extract any new backstory information for the character.
                Only include information that is explicitly mentioned or strongly implied in the chapter.

                Character Information:
                {character_info}

                Chapter Content:
                {chapter_content}

                Extract new backstory information for the character, their history, and their background. Provide their journey over the course of the story. If no new information is found, return an empty string.

                Use the following format for your response:
                {format_instructions}
                """)
                
                parser = PydanticOutputParser(pydantic_object=CharacterBackstoryExtraction)
                llmBackstory = await self._get_llm(self.model_settings['extractionLLM'])
                chain = prompt | llmBackstory | parser
                
                result = await chain.ainvoke({
                    "character_info": json.dumps(character),
                    "chapter_content": chapter_content,
                    "format_instructions": parser.get_format_instructions()
                })

                if result.new_backstory:
                    all_backstory.append(result.new_backstory)
                    # Mark each chapter as processed
                    await db_instance.mark_chapter_processed(chapter_id, self.user_id, PROCESS_TYPES['BACKSTORY'])

            # Combine all backstory information
            return CharacterBackstoryExtraction(
                character_id=character_id,
                new_backstory="\n\n".join(all_backstory)
            )
        except Exception as e:
            self.logger.error(f"Error extracting character backstory: {str(e)}")
            raise

 
    async def summarize_project(self) -> str:
        try:
            # Use the wrapper method instead of direct vector store calls
            characters = await self.query_knowledge_base("type:character", k=100)
            events = await self.query_knowledge_base("type:event", k=100)
            locations = await self.query_knowledge_base("type:location", k=100)
            
            prompt = ChatPromptTemplate.from_template("""
            Create a concise summary of the project based on the following information:

            Characters:
            {characters}

            Events:
            {events}

            Locations:
            {locations}

            Summarize the key elements of the story, including main characters, major events, and important locations.
            Limit your response to 500 words.
            """)
            
            chain = prompt | self.check_llm | StrOutputParser()
            
            result = await chain.ainvoke({
                "characters": json.dumps([doc.page_content for doc in characters], indent=2),
                "events": json.dumps([doc.page_content for doc in events], indent=2),
                "locations": json.dumps([doc.page_content for doc in locations], indent=2)
            })
            
            return result
        except Exception as e:
            self.logger.error(f"Error generating project summary: {str(e)}")
            raise

    async def check_and_extend_chapter(self, chapter_content: str, instructions: Dict[str, Any], context: str, expected_word_count: int) -> str:
        current_word_count = len(re.findall(r'\w+', chapter_content))
        
        if current_word_count >= expected_word_count:
            return chapter_content

        #self.logger.info(f"Chapter word count ({current_word_count}) is below expected ({expected_word_count}). Extending chapter.")
        
        return await self.extend_chapter(chapter_content, instructions, context, expected_word_count, current_word_count)

    async def extend_chapter(self, chapter_content: str, instructions: Dict[str, Any], context: str, expected_word_count: int, current_word_count: int) -> str:
        prompt = ChatPromptTemplate.from_template("""
        You are tasked with extending the following chapter to reach the expected word count. The current chapter is:

        {chapter_content}

        Context:
        {context}

        Instructions:
        {instructions}

        Current word count: {current_word_count}
        Expected word count: {expected_word_count}

        Please extend the chapter, maintaining consistency with the existing content and adhering to the provided instructions and context. Add approximately {words_to_add} words to reach the expected word count. Ensure the additions flow naturally and enhance the narrative. Start writing immediately without any introductory phrases or chapter numbers.

        """)

        llmExtend = await self._get_llm(self.model_settings['mainLLM'])
        chain =  prompt | llmExtend | StrOutputParser()

        while current_word_count < expected_word_count:
            words_to_add = expected_word_count - current_word_count

            extended_content = await chain.ainvoke({
                "chapter_content": chapter_content,
                "context": context,
                "instructions": json.dumps(instructions),
                "current_word_count": current_word_count,
                "expected_word_count": expected_word_count,
                "words_to_add": words_to_add
            })

            chapter_content += "\n" + extended_content
            current_word_count = len(re.findall(r'\w+', chapter_content))

            # Add a safety check to prevent infinite loops
            if len(extended_content.split()) < 10:  # If less than 10 words were added
                break

        return chapter_content


    async def analyze_unprocessed_chapter_locations(self) -> List[Dict[str, Any]]:
        try:
            # Get unprocessed chapters
            unprocessed_chapters = await db_instance.get_latest_unprocessed_chapter_content(
                self.project_id,
                self.user_id,
                PROCESS_TYPES['LOCATIONS']
            )
            
            if not unprocessed_chapters:
                return []

            existing_locations = await db_instance.get_locations(self.user_id, self.project_id)
            # Create set of existing location names for faster lookup
            existing_names = {loc['name'].lower() for loc in existing_locations}

            # Create the prompt
            prompt = ChatPromptTemplate.from_template("""
                Analyze the following chapter and identify all NEW locations mentioned that are not in the existing locations list.

                EXISTING Locations (DO NOT recreate these):
                {existing_locations}

                Chapter:
                {chapter_content}

                For each NEW location (not in existing list) provide:
                1. A unique identifier (location_id)
                2. The name of the location (location_name)
                3. An analysis of its significance to the story
                4. Any connected locations
                5. Notable events that occurred there
                6. Characters associated with this location

                Only return locations that are NOT in the existing locations list.
                If all locations mentioned already exist, return an empty locations list.

                {format_instructions}
            """)

            parser = PydanticOutputParser(pydantic_object=LocationAnalysisList)
            fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=self.check_llm)

            chain = prompt | self.llm | fixing_parser

            locations = []
            for chapter in unprocessed_chapters:
                result = await chain.ainvoke({
                    "chapter_content": chapter['content'],
                    "existing_locations": json.dumps(existing_locations, indent=2),
                    "format_instructions": parser.get_format_instructions()
                })

                # Process each location
                for location in result.locations:
                    # Skip if location already exists
                    if location.location_name.lower() in existing_names:
                        existing_location = next(
                            loc for loc in existing_locations 
                            if loc['name'].lower() == location.location_name.lower()
                        )
                        locations.append({
                            **existing_location,
                            'connected_locations': location.connected_locations,
                            'notable_events': location.notable_events,
                            'character_associations': location.character_associations
                        })
                        continue

                    # Create new location if it doesn't exist
                    location_id = await db_instance.create_location(
                        name=location.location_name,
                        description=location.significance_analysis,
                        coordinates=None,
                        user_id=self.user_id,
                        project_id=self.project_id
                    )

                    locations.append({
                        'id': location_id,
                        'name': location.location_name,
                        'description': location.significance_analysis,
                        'coordinates': None,
                        'connected_locations': location.connected_locations,
                        'notable_events': location.notable_events,
                        'character_associations': location.character_associations
                    })

                # Mark chapter as processed for locations
                await db_instance.mark_chapter_processed(
                    chapter['id'],
                    self.user_id,
                    PROCESS_TYPES['LOCATIONS']
                )

            return locations

        except Exception as e:
            self.logger.error(f"Error analyzing locations: {str(e)}")
            raise


    async def analyze_unprocessed_chapter_events(self):
        try:
            chapters_data = await db_instance.get_latest_unprocessed_chapter_content(
                self.project_id,
                self.user_id,
                PROCESS_TYPES['EVENTS']
            )
            if not chapters_data:
                raise ValueError("No unprocessed chapters found for events analysis")

            existing_events = await db_instance.get_events(self.project_id, self.user_id)
            existing_titles = {event['title'].lower() for event in existing_events}

            all_events = []
            for chapter in chapters_data:
                chapter_id = chapter['id']
                chapter_content = chapter['content']

                # Use chunking for large chapters
                chunks = self.chunk_content(chapter_content, self.MAX_INPUT_TOKENS // 2)
                chapter_events = []

                for chunk in chunks:
                    parser = PydanticOutputParser(pydantic_object=EventAnalysis)
                    fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=self.check_llm)
                    
                    prompt = ChatPromptTemplate.from_template("""
                    Analyze the following chapter content and identify all significant events. For each event, provide:
                    1. A title
                    2. A description
                    3. The impact on the story or characters
                    4. List of involved characters
                    5. Location where it takes place (if mentioned)
                                                              
                    Existing Events (DO NOT recreate these):
                    {existing_events}

                    Chapter Content:
                    {chapter_content}

                    Format your response as a dictionary with a single key 'events' containing a list of events.
                    {format_instructions}
                    """)

                    llmAnalysis = await self._get_llm(self.model_settings['extractionLLM'])
                    chain = prompt | llmAnalysis | fixing_parser

                    result = await chain.ainvoke({
                        "chapter_content": chunk,
                        "existing_events": json.dumps(existing_events, indent=2),
                        "format_instructions": parser.get_format_instructions()
                    })

                    # Process events from this chunk
                    for event in result.events:
                        # Skip if event already exists
                        if event.title.lower() in existing_titles:
                            existing_event = next(
                                e for e in existing_events 
                                if e['title'].lower() == event.title.lower()
                            )
                            chapter_events.append({"id": existing_event['id'], **event.dict()})
                            continue

                        # Get character ID for the first involved character (if any)
                        character_id = None
                        if event.involved_characters:
                            character = await db_instance.get_characters(
                                self.user_id, 
                                self.project_id, 
                                name=event.involved_characters[0]
                            )
                            if character:
                                character_id = character['id']

                        # Get location ID if location is specified
                        location_id = None
                        if event.location:
                            location = await db_instance.get_location_by_name(
                                event.location, 
                                self.user_id, 
                                self.project_id
                            )
                            if location:
                                location_id = location['id']

                        event_id = await db_instance.create_event(
                            title=event.title,
                            description=event.description,
                            date=datetime.now(),
                            project_id=self.project_id,
                            user_id=self.user_id,
                            character_id=character_id,
                            location_id=location_id
                        )
                        chapter_events.append({
                            "id": event_id,
                            **event.dict()
                        })

                if chapter_events:
                    all_events.extend(chapter_events)
                    await db_instance.mark_chapter_processed(chapter_id, self.user_id, PROCESS_TYPES['EVENTS'])

            return all_events
        except Exception as e:
            self.logger.error(f"Error analyzing events: {str(e)}")
            raise

    async def analyze_event_connections(self) -> List[EventConnection]:
        try:
            events = await db_instance.get_events(self.project_id, self.user_id, limit=100)
            characters = await db_instance.get_characters(self.user_id, self.project_id)
            locations = await db_instance.get_locations(self.user_id, self.project_id)
            existing_connections = await db_instance.get_event_connections(self.project_id, self.user_id)

            # Early return if all possible connections exist
            if len(existing_connections) >= (len(events) * (len(events) - 1)) / 2:
                self.logger.info("All possible event connections already exist")
                return existing_connections

            saved_connections = []
            batch_size = 10

            # Convert existing connections to a set of keys for faster lookup
            existing_keys = {
                tuple(sorted([conn['event1_id'], conn['event2_id']])) 
                for conn in existing_connections
            }

            for i in range(0, len(events), batch_size):
                batch_events = events[i:i+batch_size]
                
                prompt = ChatPromptTemplate.from_template("""
                Analyze ONLY NEW connections between events that are not in the existing connections list.

                Characters:
                {characters}
                                                   
                Locations:
                {locations}

                Events to Analyze:
                {events}

                EXISTING Connections (DO NOT recreate these):
                {existing_connections}

                For each NEW connection between events, provide:
                1. Event_1_ID and Event_2_ID (must not match any existing connection pairs)
                2. Connection_Type (cause_effect, parallel, contrast, etc.)
                3. Description of how they are connected
                4. Impact this connection has on the story
                5. Characters_Involved (as a comma-separated string)
                6. Location_Relation describing where these events occur

                Only return connections that are NOT in the existing connections list.
                If all possible connections already exist, return an empty connections list.

                {format_instructions}
                """)

                parser = PydanticOutputParser(pydantic_object=EventConnectionAnalysis)
                llmEvent = await self._get_llm(self.model_settings['extractionLLM'])
                chain = prompt | llmEvent | parser

                result = await chain.ainvoke({
                    "events": json.dumps(batch_events, indent=2),
                    "characters": json.dumps(characters, indent=2),
                    "locations": json.dumps(locations, indent=2),
                    "existing_connections": json.dumps(existing_connections, indent=2),
                    "format_instructions": parser.get_format_instructions()
                })

                if result.connections:
                    # Deduplicate connections
                    deduped_result = result.deduplicate_connections()
                    
                    for connection in deduped_result.connections:
                        # Skip if connection already exists
                        conn_key = tuple(sorted([connection.event1_id, connection.event2_id]))
                        if conn_key in existing_keys:
                            continue

                        # Create new connection
                        connection_id = await db_instance.create_event_connection(
                            event1_id=connection.event1_id,
                            event2_id=connection.event2_id,
                            connection_type=connection.connection_type,
                            description=connection.description,
                            impact=connection.impact,
                            project_id=self.project_id,
                            user_id=self.user_id
                        )

                        saved_connection = EventConnection(
                            id=connection_id,
                            **connection.dict()
                        )
                        saved_connections.append(saved_connection)

            return saved_connections
        except ValidationError as e:
            self.logger.error(f"Error analyzing event connections: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Error analyzing event connections: {str(e)}")
            raise

    async def analyze_location_connections(self) -> List[LocationConnection]:
        try:
            locations = await db_instance.get_locations(self.user_id, self.project_id)
            existing_connections = await db_instance.get_location_connections(self.project_id, self.user_id)

            # Early return if all possible connections exist
            if len(existing_connections) >= (len(locations) * (len(locations) - 1)) / 2:
                self.logger.info("All possible location connections already exist")
                return existing_connections

            # Convert existing connections to a set of keys for faster lookup
            existing_keys = {
                tuple(sorted([conn['location1_id'], conn['location2_id']])) 
                for conn in existing_connections
            }

            saved_connections = []
            batch_size = 10

            for i in range(0, len(locations), batch_size):
                batch_locations = locations[i:i+batch_size]
                
                prompt = ChatPromptTemplate.from_template("""
                    Analyze ONLY NEW connections between locations that are not in the existing connections list.

                    Locations to Analyze:
                    {locations}

                    EXISTING Connections (DO NOT recreate these):
                    {existing_connections}

                    For each NEW connection between locations, provide:
                    1. The IDs and names of the two connected locations (must not match any existing connection pairs)
                    2. The type of connection (physical, cultural, historical)
                    3. A description of how they are connected
                    4. Any notable travel routes between them
                    5. Any cultural exchanges or relationships

                    Only return connections that are NOT in the existing connections list.
                    If all possible connections already exist, return an empty connections list.

                    {format_instructions}
                """)

                parser = PydanticOutputParser(pydantic_object=LocationConnectionAnalysis)
                chain = prompt | self.llm | parser

                result = await chain.ainvoke({
                    "locations": json.dumps(batch_locations, indent=2),
                    "existing_connections": json.dumps(existing_connections, indent=2),
                    "format_instructions": parser.get_format_instructions()
                })

                if result.connections:
                    # Deduplicate connections
                    deduped_result = result.deduplicate_connections()
                    
                    for connection in deduped_result.connections:
                        # Skip if connection already exists
                        conn_key = tuple(sorted([connection.location1_id, connection.location2_id]))
                        if conn_key in existing_keys:
                            continue

                        # Create new connection
                        connection_id = await db_instance.create_location_connection(
                            location1_id=connection.location1_id,
                            location2_id=connection.location2_id,
                            location1_name=connection.location1_name,
                            location2_name=connection.location2_name,
                            connection_type=connection.connection_type,
                            description=connection.description,
                            travel_route=connection.travel_route,
                            cultural_exchange=connection.cultural_exchange,
                            project_id=self.project_id,
                            user_id=self.user_id
                        )

                        saved_connection = LocationConnection(
                            id=connection_id,
                            **connection.dict()
                        )
                        saved_connections.append(saved_connection)

            return saved_connections

        except Exception as e:
            self.logger.error(f"Error analyzing location connections: {str(e)}")
            return []

    async def _process_embedding_batch(self):
        """Process a batch of embeddings and add them to the vector store."""
        try:
            if not self._embedding_batch:
                return
            
            # Process all items in the current batch
            for content, metadata in self._embedding_batch:
                await self.vector_store.add_to_knowledge_base(content, metadata=metadata)
            
            # Clear the batch after processing
            self._embedding_batch = []
            
        except Exception as e:
            self.logger.error(f"Error processing embedding batch: {str(e)}")
            # Clear the batch even if there's an error to prevent getting stuck
            self._embedding_batch = []
            raise

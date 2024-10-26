# backend/agent_manager.py
import os
from typing import Dict, Any, List, Tuple, Optional, AsyncGenerator
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import StrOutputParser
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.output_parsers import PydanticOutputParser
from langchain.docstore.document import Document
from datetime import datetime
import logging
from cachetools import TTLCache

import uuid
from database import db_instance
from pydantic import BaseModel, Field, ValidationError

import json
import re
# Load environment variables
load_dotenv()
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from vector_store import VectorStore
from langchain.output_parsers import OutputFixingParser
from langchain_community.cache import SQLiteCache
from langchain_core.globals import set_llm_cache
from langchain_core.rate_limiters import InMemoryRateLimiter
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain.chains.summarize import load_summarize_chain
import asyncio
from models import ChapterValidation, CodexItem, CriterionScore

# Add at the top with other imports
PROCESS_TYPES = {
    'LOCATIONS': 'analyze_locations',
    'EVENTS': 'analyze_events',
    'RELATIONSHIPS': 'analyze_relationships',
    'BACKSTORY': 'extract_backstory'
}

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

class LocationDescription(BaseModel):
    name: str = Field(..., description="Name of the location")
    description: str = Field(..., description="Detailed description of the location")
    significance: str = Field(..., description="Significance of the location in the story")

class TaskState(BaseModel):
    task_type: str
    current_position: int
    intermediate_results: List[Any]

class Subtask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    status: str = "pending"
    result: Optional[Any] = None

class ComplexTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    subtasks: List[Subtask]
    status: str = "pending"
    result: Optional[Any] = None

class LocationAnalysis(BaseModel):
    location_id: str
    significance_analysis: str
    connected_locations: List[str]
    notable_events: List[str]
    character_associations: List[str]

class EventConnectionAnalysis(BaseModel):
    event_id: str
    impact_analysis: str
    connected_events: List[str]
    involved_characters: List[str]
    location_significance: str

class LocationConnection(BaseModel):
    location1_id: str
    location2_id: str
    connection_type: str
    description: str
    travel_routes: Optional[str] = None
    cultural_influences: Optional[str] = None

# Add at the top with other imports
agent_managers: Dict[Tuple[str, str], 'AgentManager'] = {}
class AgentManager:
    _llm_cache = TTLCache(maxsize=100, ttl=3600)  # Class-level cache for LLM instances

    def __init__(self, user_id: str, project_id: str):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.user_id = user_id
        self.project_id = project_id
        self.api_key = None
        self.model_settings = None
        self.MAX_INPUT_TOKENS = None
        self.MAX_OUTPUT_TOKENS = None
        self.chat_history = None
        self.vector_store = None
        self.summarize_chain = None
        self.task_states = {}
        self.agents = {}
        self.complex_tasks = {}
        self.lock = asyncio.Lock()
    @classmethod
    async def create(cls, user_id: str, project_id: str):
        instance = cls(user_id, project_id)
        await instance.initialize()
        return instance

    async def initialize(self):
        self.api_key = await self._get_api_key()
        self.model_settings = await self._get_model_settings()
        self.MAX_INPUT_TOKENS = 2097152 if 'pro' in self.model_settings['mainLLM'] else 1048576
        self.MAX_OUTPUT_TOKENS = 8192
        self.chat_history = await db_instance.get_chat_history(self.user_id, self.project_id)
        if self.chat_history is None:
            self.chat_history = []  # Initialize as an empty list if no history exists

        self.setup_caching()
        self.setup_rate_limiter()
        self.llm = await self._get_llm(self.model_settings['mainLLM'])
        self.check_llm = await self._get_llm(self.model_settings['checkLLM'])
        self.vector_store = VectorStore(self.user_id, self.project_id, self.api_key, self.model_settings['embeddingsModel'])
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
        self.task_states.clear()
        self.agents.clear()
        self.complex_tasks.clear()
        self.lock = None
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))    
    async def _get_llm(self, model: str) -> ChatGoogleGenerativeAI:
        async with self.lock:
            if model in self._llm_cache:
                return self._llm_cache[model]

            llm = ChatGoogleGenerativeAI(
                model=model,
                google_api_key=self.api_key,
                temperature=0.7,
                max_output_tokens=self.MAX_OUTPUT_TOKENS,
                max_input_tokens=self.MAX_INPUT_TOKENS,
                caching=True,
                rate_limiter=self.rate_limiter,
                streaming=True,
            )

            self._llm_cache[model] = llm
            return llm

    def _get_api_key(self) -> str:
        api_key = db_instance.get_api_key(self.user_id)
        if not api_key:
            raise ValueError("API key not set. Please set your API key in the settings.")
        return api_key

    def _get_model_settings(self) -> dict:
        return db_instance.get_model_settings(self.user_id)

    def setup_caching(self):
        # Set up SQLite caching
        set_llm_cache(SQLiteCache(database_path=".langchain.db"))

    def setup_rate_limiter(self):
        # Set up rate limiter based on model tier
        if 'pro' in self.model_settings['mainLLM']:
            self.rate_limiter = InMemoryRateLimiter(
                requests_per_second=1/30,  # 2 requests per minute = 1 request per 30 seconds
                check_every_n_seconds=0.1,
                max_bucket_size=2
            )
        else:
            self.rate_limiter = InMemoryRateLimiter(
                requests_per_second=0.25,  # 15 requests per minute = 1 request per 4 seconds
                check_every_n_seconds=0.1,
                max_bucket_size=15
            )


    async def generate_chapter_stream(
        self,
        chapter_number: int,
        plot: str,
        writing_style: str,
        instructions: Dict[str, Any],
        previous_chapters: List[Dict[str, Any]],
        codex_items: List[Dict[str, Any]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            # Construct context from previous chapters and codex items
            context = self._construct_context(
                plot, 
                writing_style, 
                {item['name']: item['description'] for item in codex_items}, 
                previous_chapters
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
            total_tokens = 0
            max_history_tokens = self.MAX_INPUT_TOKENS // 4
            
            # Add relevant previous chapters to chat history
            for i, chapter in enumerate(reversed(previous_chapters), 1):
                chapter_content = f"Chapter {chapter.get('chapter_number', i)}: {chapter['content']}"
                chapter_tokens = self.estimate_token_count(chapter_content)
                if total_tokens + chapter_tokens > max_history_tokens:
                    break
                chat_history.add_user_message(chapter_content)
                chat_history.add_ai_message("Understood.")
                total_tokens += chapter_tokens

            chain = RunnableWithMessageHistory(
                chain,
                lambda session_id: chat_history,
                input_messages_key="context",
                history_messages_key="chat_history",
            )

            # Collect the full chapter content
            chapter_content = ""
            async for chunk in self._stream_chapter_generation(
                chain,
                {
                    "chapter_number": chapter_number,
                    "plot": plot,
                    "writing_style": writing_style,
                    "style_guide": instructions.get('styleGuide', ''),
                    "additional_instructions": instructions.get('additionalInstructions', ''),
                    "context": context
                },
                config={"configurable": {"session_id": f"chapter_{chapter_number}"}}
            ):
                if isinstance(chunk, dict) and "content" in chunk:
                    chapter_content += chunk["content"]
                yield chunk

            if not chapter_content:
                raise ValueError("No chapter content was generated")

            # Generate title before returning
            chapter_title = await self.generate_title(chapter_content, chapter_number)

            # Check and extend chapter if necessary
            expected_word_count = instructions.get('minWordCount', 0)
            if expected_word_count > 0:
                chapter_content = await self.check_and_extend_chapter(
                    chapter_content, 
                    instructions, 
                    context, 
                    expected_word_count
                )

            # Run validity check
            validity_result = await self.check_chapter(
                chapter_content,
                instructions,
                previous_chapters
            )

            # Extract and process new codex items
            new_codex_items = await self.check_and_extract_new_codex_items(chapter_content, codex_items)

            # Return the chapter content and metadata without saving
            yield {
                "type": "complete",
                "content": chapter_content,
                "chapter_title": chapter_title,
                "new_codex_items": new_codex_items,
                "validity_check": validity_result
            }

        except Exception as e:
            self.logger.error(f"Error in generate_chapter_stream: {str(e)}", exc_info=True)
            yield {"error": str(e)}

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
            stream_kwargs = {}
            if config:
                stream_kwargs['config'] = config

            async for chunk in chain.astream(variables, **stream_kwargs):
                if isinstance(chunk, str):
                    yield {"type": "chunk", "content": chunk}
                else:
                    yield chunk
        except Exception as e:
            self.logger.error(f"Error in _stream_chapter_generation: {str(e)}")
            yield {"error": str(e)}



    def _construct_context(self, plot: str, writing_style: str, 
                           codex_items: Dict[str, str], previous_chapters: List[Dict[str, Any]]) -> str:
        context = ""
        context += "Codex Items:\n"
        for name, description in codex_items.items():
            context += f"{name}: {description}\n"
        context += "\n"
        
        context += "Previous Chapters:\n"
        chapters_content = ""
        total_tokens = self.estimate_token_count(context)
        max_chapter_tokens = self.MAX_INPUT_TOKENS // 2  # Reserve half of the tokens for previous chapters

        for i, chapter in enumerate(reversed(previous_chapters), 1):
            chapter_num = chapter.get('chapter_number', i)  # Use index as fallback
            chapter_content = f"Chapter {chapter_num}: {chapter['content']}\n"
            chapter_tokens = self.estimate_token_count(chapter_content)

            if total_tokens + chapter_tokens > max_chapter_tokens:
                # Summarize the chapter if it exceeds the token limit
                chapter_content = self.summarize_chapter(chapter_content)
                chapter_tokens = self.estimate_token_count(chapter_content)

            if total_tokens + chapter_tokens > max_chapter_tokens:
                break

            chapters_content = chapter_content + chapters_content
            total_tokens += chapter_tokens

        context += chapters_content

        return context

    def summarize_chapter(self, chapter_content: str) -> str:
        document = Document(page_content=chapter_content)
        summary = self.summarize_chain.run([document])
        return summary

    def estimate_token_count(self, text: str) -> int:
        # Gemini models use about 4 characters per token
        return self.llm.get_num_tokens(text)

    def get_embedding(self, text: str) -> List[float]:
        return self.embeddings.embed_query(text)

    async def check_chapter(self, chapter: str, instructions: Dict[str, Any], 
                        previous_chapters: List[Dict[str, Any]]) -> Dict[str, Any]:
        async with self.lock:
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

            # Add the content to the vector store and get the embedding ID
            embedding_id = await self.vector_store.add_to_knowledge_base(content, metadata=filtered_metadata)

            return embedding_id
        except Exception as e:
            self.logger.error(f"Error adding to knowledge base: {str(e)}", exc_info=True)
            raise
    

    async def update_or_remove_from_knowledge_base(self, identifier, action, new_content=None, new_metadata=None):
        if self.vector_store is None:
            await self.initialize()
        try:
            if isinstance(identifier, str):
                embedding_id = identifier
            elif isinstance(identifier, dict) and 'item_id' in identifier and 'item_type' in identifier:
                embedding_id = await self.vector_store.get_embedding_id(identifier['item_id'], identifier['item_type'])
            else:
                raise ValueError("Invalid identifier. Must be embedding_id or dict with item_id and item_type")

            if action == 'delete':
                await self.vector_store.delete_from_knowledge_base(embedding_id)
            elif action == 'update':
                if new_content is None and new_metadata is None:
                    raise ValueError("Either new_content or new_metadata must be provided for update action")
                await self.vector_store.update_in_knowledge_base(embedding_id, new_content, new_metadata)
            else:
                raise ValueError("Invalid action. Must be 'delete' or 'update'")
            
        except Exception as e:
            self.logger.error(f"Error in update_or_remove_from_knowledge_base: {str(e)}", exc_info=True)
            raise

    async def query_knowledge_base(self, query: str, k: int = 5) -> List[Document]:
        """
        Query the knowledge base using the vector store.
        
        Args:
            query: The search query string
            k: Number of results to return (default=5)
            
        Returns:
            List of Document objects containing the search results
        """
        try:
            # Create a filter dict for the vector store query
            filter_dict = {
                "user_id": self.user_id,
                "project_id": self.project_id
            }
            
            # Use the vector store's query method with the filter
            results = await self.vector_store.similarity_search(
                query_text=query,
                filter=filter_dict,
                k=k
            )
            
            return results
        except Exception as e:
            self.logger.error(f"Error in query_knowledge_base: {str(e)}")
            raise

    async def generate_with_retrieval(self, query: str, chat_history: List[Dict[str, str]]) -> str:
        qa_llm = await self._get_llm(self.model_settings['knowledgeBaseQueryLLM'])
        
        # Create a history-aware retriever function
        async def retrieve_with_history(query: str) -> List[Document]:
            # Use the condense question prompt to get the standalone question
            condense_question_prompt = ChatPromptTemplate.from_messages([
                ("system", "Given a chat history and the latest user question which might reference context in the chat history, formulate a standalone question which can be understood without the chat history. Do NOT answer the question, just reformulate it if needed and otherwise return it as is."),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ])
            
            # Prepare chat history
            messages = []
            for message in chat_history:
                if isinstance(message, dict):
                    if message.get('type') == 'human':
                        messages.append(HumanMessage(content=message['content']))
                    elif message.get('type') == 'ai':
                        messages.append(AIMessage(content=message['content']))
                elif isinstance(message, (HumanMessage, AIMessage)):
                    messages.append(message)
                    
            # Get the standalone question
            chain = condense_question_prompt | qa_llm | StrOutputParser()
            standalone_question = await chain.ainvoke({
                "input": query,
                "chat_history": messages
            })
            
            # Use similarity search instead of retriever
            return await self.vector_store.similarity_search(standalone_question, k=5)

        # Create the QA chain
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question. If you don't know the answer, say that you don't know. Use three sentences maximum and keep the answer concise."),
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
        response = f"{answer}\n\n\n"
        for i, doc in enumerate(documents, 1):
            response += f"{i}. {doc.metadata.get('source', 'Unknown source')}\n"

        return response

    def _construct_query_context(self, relevant_docs: List[Document]) -> str:
        context = "\n".join([doc.page_content for doc in relevant_docs])
        return self._truncate_context(context)

    def _truncate_context(self, context: str) -> str:
        max_tokens = self.MAX_INPUT_TOKENS // 2  # Reserve half of the tokens for context
        if self.estimate_token_count(context) > max_tokens:
            return ' '.join(context.split()[:max_tokens]) + "..."
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


    def _truncate_previous_chapters(self, previous_chapters: List[Dict[str, Any]]) -> str:
        truncated = ""
        total_tokens = 0
        max_tokens = self.MAX_INPUT_TOKENS // 4  # Reserve a quarter of the tokens for previous chapters
        for i, chapter in enumerate(reversed(previous_chapters), 1):
            chapter_num = chapter.get('chapter_number', i)  # Use index as fallback
            chapter_content = f"Chapter {chapter_num}: {chapter['content']}\n"
            chapter_tokens = self.estimate_token_count(chapter_content)

            if total_tokens + chapter_tokens > max_tokens:
                # Summarize the chapter if it exceeds the token limit
                chapter_content = self.summarize_chapter(chapter_content)
                chapter_tokens = self.estimate_token_count(chapter_content)

            if total_tokens + chapter_tokens > max_tokens:
                break

            truncated = chapter_content + truncated
            total_tokens += chapter_tokens
        return truncated

    async def generate_title(self, chapter_content: str, chapter_number: int) -> str:
        try:
            prompt = ChatPromptTemplate.from_template("""
            Generate a concise, engaging title for Chapter {chapter_number}. 
            The title should be brief (maximum 50 characters) but capture the essence of the chapter.
            
            Chapter content:
            {chapter_content}
            
            Return only the title, without "Chapter X:" prefix.
            """)
            
            llm = await self._get_llm(self.model_settings['titleGenerationLLM'])  # Add await here
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
        chunks = []
        current_chunk = ""
        current_tokens = 0
        
        for sentence in content.split('.'):
            sentence_tokens = self.estimate_token_count(sentence)
            if current_tokens + sentence_tokens > max_tokens:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
                current_tokens = sentence_tokens
            else:
                current_chunk += sentence + '.'
                current_tokens += sentence_tokens
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    async def process_large_content(self, content: str, task_type: str, process_func: callable):
        chunks = self.chunk_content(content, self.MAX_INPUT_TOKENS // 2)
        state = self.task_states.get(task_type, TaskState(task_type=task_type, current_position=0, intermediate_results=[]))
        
        for i, chunk in enumerate(chunks[state.current_position:], start=state.current_position):
            result = await process_func(chunk)
            state.intermediate_results.extend(result)
            state.current_position = i + 1
            self.task_states[task_type] = state
        
        return state.intermediate_results

    def decompose_task(self, task: str) -> ComplexTask:
        prompt = ChatPromptTemplate.from_template("""
        You are an expert task manager. Your job is to decompose a complex task into smaller, manageable subtasks.
        
        Complex task: {task}
        
        Break this task down into 3-5 subtasks. For each subtask, provide:
        1. A brief description of the subtask
        2. The expected output or result of the subtask
        
        Format your response as a JSON object with the following structure:
        {{
            "description": "overall task description",
            "subtasks": [
                {{
                    "description": "subtask 1 description"
                }},
                ...
            ]
        }}
        """)

        chain = prompt | self.llm | StrOutputParser()
        result = chain.invoke({"task": task})
        
        task_dict = json.loads(result)
        complex_task = ComplexTask(
            description=task_dict["description"],
            subtasks=[Subtask(**subtask) for subtask in task_dict["subtasks"]]
        )
        self.complex_tasks[complex_task.id] = complex_task
        return complex_task

    async def process_subtask(self, subtask: Subtask) -> Any:
        prompt = ChatPromptTemplate.from_template("""
        Process the following subtask:
        
        Subtask: {subtask_description}
        
        Provide a detailed response or solution for this subtask.
        """)

        chain = prompt | self.llm | StrOutputParser()
        result = await chain.ainvoke({"subtask_description": subtask.description})
        
        return result

    async def process_complex_task(self, task_id: str) -> ComplexTask:
        complex_task = self.complex_tasks.get(task_id)
        if not complex_task:
            raise ValueError(f"No complex task found with id: {task_id}")

        for subtask in complex_task.subtasks:
            if subtask.status == "pending":
                subtask.result = await self.process_subtask(subtask)
                subtask.status = "completed"

        complex_task.result = await self.aggregate_results(complex_task)
        complex_task.status = "completed"
        return complex_task

    async def aggregate_results(self, complex_task: ComplexTask) -> Any:
        prompt = ChatPromptTemplate.from_template("""
        You are tasked with aggregating the results of multiple subtasks into a coherent final result.
        
        Original task: {task_description}
        
        Subtask results:
        {subtask_results}
        
        Please provide a comprehensive summary that combines all subtask results into a final, cohesive output for the original task.
        """)

        subtask_results = "\n".join([f"Subtask {i+1}: {subtask.result}" for i, subtask in enumerate(complex_task.subtasks)])

        chain = prompt | self.llm | StrOutputParser()
        result = await chain.ainvoke({
            "task_description": complex_task.description,
            "subtask_results": subtask_results
        })
        
        return result

    async def handle_complex_task(self, task: str) -> Any:
        complex_task = self.decompose_task(task)
        processed_task = await self.process_complex_task(complex_task.id)
        return processed_task.result

    def register_agent(self, agent_name: str, agent: Any):
        self.agents[agent_name] = agent

    async def allocate_task(self, task: str):
        # Implement task allocation logic
        for agent_name, agent in self.agents.items():
            if agent.can_handle(task):
                return await agent.process(task)
        raise ValueError(f"No agent can handle task: {task}")

    async def check_and_extract_new_codex_items(self, chapter: str, codex_items: List[Dict[str, str]]) -> List[Dict[str, str]]:
        try:
            chunks = self.chunk_content(chapter, self.MAX_INPUT_TOKENS // 2)
            all_new_items = []

            for chunk in chunks:
                parser = PydanticOutputParser(pydantic_object=CodexExtraction)
                fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=self.check_llm)
                
                prompt = ChatPromptTemplate.from_template("""
                You are an expert at identifying new codex items in a story. Your task is to analyze the following chapter and identify ANY new codex items that are not in the provided list of existing codex items.

                For each new codex item you find:
                1. Provide its name
                2. Write a brief description of the codex item based on information in the chapter
                3. Determine the type of codex item (lore, worldbuilding, item, character)
                4. If the type is "worldbuilding", determine the subtype (history, culture, geography)

                IMPORTANT: Even if a codex item is only mentioned briefly or seems minor, include it in your list if it's not in the existing codex items. Pay special attention to names, pronouns, and any descriptive phrases that might indicate a new codex item.

                If you truly find no new codex items after a thorough analysis, return an empty list.

                Chapter:
                {chapter}

                Existing Codex Items:
                {codex_items}

                Remember, include ANY codex item that is not in the list of existing codex items, no matter how minor they might seem. Be thorough and precise in your analysis.

                {format_instructions}
                """)
                Codexllm = await self._get_llm(self.model_settings['extractionLLM'])
                
                extraction_chain = prompt | Codexllm | fixing_parser

                result = await extraction_chain.ainvoke({
                    "chapter": chunk,
                    "codex_items": ", ".join([item['name'] for item in codex_items]),
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
            return []

    async def analyze_character_relationships(self, character_ids: List[str]) -> List[Dict[str, Any]]:
        try:
            character_data = {}
            for char_id in character_ids:
                char = await db_instance.get_codex_item_by_id(char_id, self.user_id, self.project_id)
                if char and char['type'] == 'character':
                    # Store full character info
                    character_data[char_id] = {
                        'id': char_id,
                        'name': char['name'].split(',')[0].strip(),  # Split and strip to handle commas
                        'description': char.get('description', ''),
                        'full_name': char['name']
                    }
                else:
                    self.logger.warning(f"Character not found for ID: {char_id}")

            if not character_data:
                self.logger.warning("No valid characters found")
                return []

            # Create pairs of characters for analysis
            character_pairs = [(a, b) for i, a in enumerate(character_ids) for b in character_ids[i+1:]]

            # Get the latest chapter content
            chapter_data = await db_instance.get_latest_unprocessed_chapter_content(
                self.project_id,
                self.user_id,
                PROCESS_TYPES['RELATIONSHIPS']
            )
            
            if not chapter_data:
                return []
            chapter_id = chapter_data['id']
            chapter_content = chapter_data['content']
            
            if not chapter_content:
                self.logger.warning("No chapter content found for analysis")
                return []

            # Format character pairs using cleaned names
            formatted_pairs = [
                f"{character_data[pair[0]]['name']} and {character_data[pair[1]]['name']}"
                for pair in character_pairs
            ]
            
            valid_characters = [char['name'] for char in character_data.values()]

            prompt = ChatPromptTemplate.from_template("""
                Analyze the relationships between the following character pairs based on the given chapter content.
                
                IMPORTANT: Only analyze relationships between these specific characters:
                {valid_characters}
                Do not include any other characters in your analysis.

                Character Pairs to Analyze:
                {character_pairs}

                Chapter Content:
                {chapter_content}

                Character descriptions:
                {character_descriptions}

                IMPORTANT: Only analyze relationships between the characters listed above. Do not include any other characters in your analysis.

                                                      

                For each pair of characters, provide:
                1. The nature of their relationship (e.g., friends, rivals, family, none)
                2. A brief description of their relationship
                3. Any significant interactions or events from the chapter that define their relationship

                RULES:
                - Only analyze relationships between the characters listed above
                - Do not introduce or mention any characters not in the provided list
                - If you can't determine a relationship between characters, use "unknown" as the relationship type
                
                Format each relationship analysis as a list of dictionaries with these exact keys:
                {format_instructions}
                """)

            parser = PydanticOutputParser(pydantic_object=RelationshipAnalysisList)
            llmRelationship = await self._get_llm(self.model_settings['extractionLLM'])
            chain = prompt | llmRelationship | parser

            character_descriptions = "\n".join(
                f"{char['name']}: {char['description']}" for char in character_data.values()
            )

            result = await chain.ainvoke({
                "valid_characters": ", ".join(valid_characters),
                "character_pairs": ", ".join(formatted_pairs),
                "chapter_content": chapter_content,
                "character_descriptions": character_descriptions,
                "format_instructions": parser.get_format_instructions()
            })

            name_to_id = {v['name']: k for k, v in character_data.items()}
            relationships = []
            
            for rel in result.relationships:
                if rel.character1 not in valid_characters or rel.character2 not in valid_characters:
                    self.logger.warning(f"Skipping invalid relationship with characters: {rel.character1}, {rel.character2}")
                    continue
                
                char1_id = name_to_id[rel.character1]
                char2_id = name_to_id[rel.character2]
                
                # Save to relationship analysis table
                analysis_id = await db_instance.save_relationship_analysis(
                    character1_id=char1_id,
                    character2_id=char2_id,
                    relationship_type=rel.relationship_type,
                    description=rel.description,
                    user_id=self.user_id,
                    project_id=self.project_id
                )
                
                # Also save to character relationships table
                relationship_id = await db_instance.create_character_relationship(
                    char1_id,
                    char2_id,
                    rel.relationship_type,
                    self.project_id,
                    description=rel.description
                )
                
                relationship_dict = {
                    'character1_id': char1_id,
                    'character2_id': char2_id,
                    'character1_name': character_data[char1_id]['full_name'],
                    'character2_name': character_data[char2_id]['full_name'],
                    'character1_description': character_data[char1_id]['description'],
                    'character2_description': character_data[char2_id]['description'],
                    'relationship_type': rel.relationship_type,
                    'description': rel.description
                }
                relationship_dict['id'] = relationship_id
                relationship_dict['analysis_id'] = analysis_id
                
                relationships.append(relationship_dict)
                
            if relationships:
                await db_instance.mark_chapter_processed(chapter_id, self.user_id, PROCESS_TYPES['RELATIONSHIPS'])
            return relationships
        except Exception as e:
            self.logger.error(f"Error analyzing relationships: {str(e)}", exc_info=True)
            return []

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
            character = await db_instance.get_codex_item_by_id(character_id, self.user_id, self.project_id)
            if not character or character['type'] != 'character':
                raise ValueError(f"Character with ID {character_id} not found")
            
            # Get the chapter content
            chapter_data = await db_instance.get_latest_unprocessed_chapter_content(
                self.project_id,
                self.user_id,
                PROCESS_TYPES['BACKSTORY']
            )
            
            # If no unprocessed chapters, return early with empty result
            if not chapter_data:
                return CharacterBackstoryExtraction(
                    character_id=character_id,
                    new_backstory=""
                )

            chapter_id = chapter_data['id']
            chapter_content = chapter_data['content']

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
                # Mark the chapter as processed with the correct process type
                await db_instance.mark_chapter_processed(chapter_id, self.user_id, PROCESS_TYPES['BACKSTORY'])

            return result
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

    def _parse_location_result(self, result: str) -> List[Dict[str, Any]]:
        """Parse the location analysis result string into structured data.
        
        Args:
            result: String containing location information in a semi-structured format
            
        Returns:
            List of dictionaries containing parsed location data
        """
        locations = []
        current_location = {}
        
        # Split the result into lines and process each line
        lines = result.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if this line starts a new location
            if line.startswith('- ') or line.startswith('* '):
                # Save the previous location if it exists
                if current_location:
                    locations.append(current_location)
                current_location = {'name': line[2:].strip(), 'description': '', 'coordinates': None}
                continue
                
            # Look for specific location details
            lower_line = line.lower()
            if 'description:' in lower_line:
                current_location['description'] = line.split(':', 1)[1].strip()
            elif 'coordinates:' in lower_line or 'location:' in lower_line:
                current_location['coordinates'] = line.split(':', 1)[1].strip()
            elif current_location:  # Append to description if no specific marker
                if current_location['description']:
                    current_location['description'] += ' ' + line
                else:
                    current_location['description'] = line
        
        # Add the last location if it exists
        if current_location:
            locations.append(current_location)
            
        return locations

    async def analyze_unprocessed_chapter_locations(self, chapter_id: str):
        self.logger.info("Starting location analysis for chapter")
        try:
            # Get the chapter content
            chapter_data = await db_instance.get_latest_unprocessed_chapter_content(
                self.project_id,
                self.user_id,
                PROCESS_TYPES['LOCATIONS']
            )
            if not chapter_data:
                raise ValueError("No unprocessed chapter found for location analysis")
            
            chapter_id = chapter_data['id']
            chapter_content = chapter_data['content']
            self.logger.info("Retrieved chapter content")
            
            if not chapter_content:
                self.logger.info("No chapter content found")
                return []

            prompt = ChatPromptTemplate.from_template("""
            Analyze the following chapter content and identify any locations mentioned or described.
            For each location, provide details in the following format:

            * [Location Name]
            Description: [Detailed description of the location]
            Coordinates/Location: [Any geographical details or relative position]

            Chapter Content:
            {chapter_content}

            Only include locations that are explicitly mentioned or described in the chapter.
            Be specific and detailed in the descriptions.
            """)
            llmLocation = await self._get_llm(self.model_settings['extractionLLM'])
            chain = prompt | llmLocation | StrOutputParser()
            
            result = await chain.ainvoke({"chapter_content": chapter_content})
            
            # Parse the locations from the result
            location_list = self._parse_location_result(result)
            
            # Process and save the locations
            locations = []
            for location_data in location_list:
                try:
                    # Check if the location already exists
                    existing_location = await db_instance.get_location_by_name(location_data['name'], self.user_id, self.project_id)
                    if existing_location:
                        self.logger.info(f"Location {location_data['name']} already exists, skipping save.")
                        locations.append({"id": existing_location['id'], **location_data})
                        continue

                    location_id = await db_instance.create_location(
                        name=location_data['name'],
                        description=location_data['description'],
                        coordinates=location_data.get('coordinates'),
                        user_id=self.user_id,
                        project_id=self.project_id
                    )
                    locations.append({"id": location_id, **location_data})
                except Exception as e:
                    self.logger.error(f"Error saving location {location_data['name']}: {str(e)}")
                    continue

            # Mark the chapter as processed for location analysis
            if locations:
                await db_instance.mark_chapter_processed(chapter_id, self.user_id, PROCESS_TYPES['LOCATIONS'])
            
            self.logger.info(f"Location analysis completed. Found {len(locations)} locations")
            return locations
        except Exception as e:
            self.logger.error(f"Error analyzing locations: {str(e)}")
            raise


    async def analyze_unprocessed_chapter_events(self, chapter_id: str):
        try:
            chapter_data = await db_instance.get_latest_unprocessed_chapter_content(
                self.project_id,
                self.user_id,
                PROCESS_TYPES['EVENTS']
            )
            if not chapter_data:
                raise ValueError(f"No unprocessed chapter found for events analysis")

            chapter_id = chapter_data['id']
            chapter_content = chapter_data['content']

            parser = PydanticOutputParser(pydantic_object=EventAnalysis)
            fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=self.check_llm)
            
            prompt = ChatPromptTemplate.from_template("""
            Analyze the following chapter and identify all significant events. For each event, provide:
            1. A title
            2. A description
            3. The impact on the story or characters
            4. List of involved characters
            5. Location where it takes place (if mentioned)

            Chapter Content:
            {chapter_content}

            Format your response as a dictionary with a single key 'events' containing a list of events.
            {format_instructions}
            """)

            llmAnalysis = await self._get_llm(self.model_settings['extractionLLM'])
            chain = prompt | llmAnalysis | fixing_parser

            result = await chain.ainvoke({
                "chapter_content": chapter_content,
                "format_instructions": parser.get_format_instructions()
            })

            # Process and store the events
            stored_events = []
            for event in result.events:
                # Get character ID for the first involved character (if any)
                character_id = None
                if event.involved_characters:
                    character = await db_instance.get_characters(self.user_id, self.project_id, name=event.involved_characters[0])
                    if character:
                        character_id = character['id']

                # Get location ID if location is specified
                location_id = None
                if event.location:
                    location = await db_instance.get_location_by_name(event.location, self.user_id, self.project_id)
                    if location:
                        location_id = location['id']

                # Check if the event already exists
                existing_event = await db_instance.get_event_by_title(event.title, self.user_id, self.project_id)
                if existing_event:
                    self.logger.info(f"Event {event.title} already exists, skipping save.")
                    stored_events.append({"id": existing_event['id'], **event.dict()})
                    continue

                event_id = await db_instance.create_event(
                    title=event.title,
                    description=event.description,
                    date=datetime.now(),  # You might want to extract or compute this
                    project_id=self.project_id,
                    user_id=self.user_id,
                    character_id=character_id,
                    location_id=location_id
                )
                stored_events.append({
                    "id": event_id,
                    **event.dict()
                })

            # Mark the chapter as processed for events
            if stored_events:
                await db_instance.mark_chapter_processed(chapter_id, self.user_id, PROCESS_TYPES['EVENTS'])

            return stored_events
        except Exception as e:
            self.logger.error(f"Error analyzing events: {str(e)}")
            raise

    async def analyze_event_connections(self, event_ids: List[str]) -> List[EventConnectionAnalysis]:
        try:
            events = [await db_instance.get_event_by_id(event_id, self.user_id, self.project_id) for event_id in event_ids]
            events = [e for e in events if e]  # Filter out None values

            prompt = ChatPromptTemplate.from_template("""
            Analyze the following events and their connections:

            Events:
            {events}

            For each event, provide:
            1. The impact on the story and characters
            2. Connected events and their relationships
            3. All characters involved and their roles
            4. The significance of the location where it occurred

            Use the following format for your response:
            {format_instructions}
            """)

            parser = PydanticOutputParser(pydantic_object=EventConnectionAnalysis)
            llmEvent = await self._get_llm(self.model_settings['extractionLLM'])
            chain = prompt | llmEvent | parser

            analyses = []
            for event in events:
                result = await chain.ainvoke({
                    "events": json.dumps(events, indent=2),
                    "format_instructions": parser.get_format_instructions()
                })
                analyses.append(result)

            return analyses
        except Exception as e:
            self.logger.error(f"Error analyzing event connections: {str(e)}")
            raise

    async def analyze_location_connections(self, location_ids: List[str]) -> List[LocationConnection]:
        try:
            locations = [await db_instance.get_location_by_id(loc_id, self.user_id, self.project_id) for loc_id in location_ids]
            locations = [l for l in locations if l]  # Filter out None values

            prompt = ChatPromptTemplate.from_template("""
            Analyze the connections between the following locations:

            Locations:
            {locations}

            For each pair of locations, provide:
            1. The type of connection (geographical, historical, cultural, etc.)
            2. A detailed description of how they are connected
            3. Any travel routes between them
            4. Cultural influences and exchanges

            Use the following format for your response:
            {format_instructions}
            """)

            parser = PydanticOutputParser(pydantic_object=LocationConnection)
            llmLocationConnection = await self._get_llm(self.model_settings['extractionLLM'])
            chain = prompt | llmLocationConnection | parser

            connections = []
            for i, loc1 in enumerate(locations):
                for loc2 in locations[i+1:]:
                    result = await chain.ainvoke({
                        "locations": json.dumps([loc1, loc2], indent=2),
                        "format_instructions": parser.get_format_instructions()
                    })
                    connections.append(result)

            return connections
        except Exception as e:
            self.logger.error(f"Error analyzing location connections: {str(e)}")
            raise















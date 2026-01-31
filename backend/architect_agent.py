import logging
import json
import asyncio
import httpx
from typing import Dict, Any, List, Optional, Annotated
from langchain_google_genai import ChatGoogleGenerativeAI
import google.generativeai as genai
from google.generativeai import caching
from datetime import timedelta
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_classic.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_classic.output_parsers import PydanticOutputParser
from agent_manager import (
    AgentManager,
    OPENROUTER_API_BASE,
    SITE_URL,
    SITE_NAME,
)
from models import (
    ChapterGenerationRequest,
    CodexItemType,
    WorldbuildingSubtype,
    CodexItemCreate,
    CharacterVoiceProfileData,
    CodexItemUpdate,
)
from pydantic import BaseModel, Field, ValidationError
from langchain_classic.tools import StructuredTool
import os

# Assuming these are available and setup correctly
from database import db_instance
from api_key_manager import ApiKeyManager
from models import ProjectStructureUpdateRequest

logger = logging.getLogger(__name__)


# --- Pydantic Model for Parsing Chapter Details ---
# Define a model to help the LLM structure the chapter details
class ChapterDetailsInput(BaseModel):
    plot: str = Field(
        ..., description="The core plot points or summary for the chapter."
    )
    writing_style: str = Field(
        ...,
        description="The desired writing style (e.g., concise, descriptive, character-focused).",
    )
    num_chapters: int = Field(
        1,
        description="Number of chapters to generate based on these details (usually 1).",
    )
    word_count: Optional[int] = Field(
        None, description="Approximate target word count for the chapter."
    )
    style_guide: Optional[str] = Field(
        None,
        description="Specific style guide instructions (e.g., sentence structure, tone).",
    )
    additional_instructions: Optional[str] = Field(
        None, description="Any other specific instructions."
    )


# Tool arguments schema for all tools
class GenerateChapterToolArgs(BaseModel):
    chapter_details: str = Field(
        ...,
        description="A string containing the plot points, writing style, and any specific instructions for the chapter",
    )
    count: int = Field(3, description="Number of recent chapters to summarize")


class QueryCodexToolArgs(BaseModel):
    query: str = Field(
        ..., description="The search query to look up in the knowledge base"
    )
    k: int = Field(5, description="Number of results to return")


class GetProjectDetailsToolArgs(BaseModel):
    pass


class GetChapterListToolArgs(BaseModel):
    pass


class ReadChapterToolArgs(BaseModel):
    chapter_number: int = Field(..., description="The chapter number to read")


class GetRecentChaptersSummaryToolArgs(BaseModel):
    count: int = Field(3, description="Number of recent chapters to summarize")


class GetProjectStructureToolArgs(BaseModel):
    pass


class UpdateProjectStructureToolArgs(BaseModel):
    project_structure_json: str = Field(
        ...,
        description='A JSON string representing the entire project structure. This should be a dictionary with a single key \'project_structure\' whose value is a list of acts, stages, and substages, each with \'id\', \'name\', \'type\', and \'children\' keys. For example: \'{"project_structure": [{"id": "act1", "name": "Act 1", "type": "act", "children": []}]}\'',
    )


class UpdateTargetWordCountToolArgs(BaseModel):
    word_count: int = Field(
        ..., description="The target word count for chapters in the project."
    )


class CreateCodexItemToolArgs(BaseModel):
    name: str = Field(..., description="Name of the codex item to create")
    description: str = Field(..., description="Detailed description of the codex item")
    type: str = Field(
        ...,
        description="Type of codex item (character, worldbuilding, item, lore, faction, location, event, relationship)",
    )
    subtype: Optional[str] = Field(
        None,
        description="Subtype for worldbuilding items (history, culture, geography)",
    )
    backstory: Optional[str] = Field(
        None, description="Optional backstory for character items"
    )
    vocabulary: Optional[str] = Field(
        None,
        description="Character's vocabulary style, word choice patterns, and common phrases (for character items only)",
    )
    sentence_structure: Optional[str] = Field(
        None,
        description="Character's typical sentence structures, paragraph patterns, and linguistic style (for character items only)",
    )
    speech_patterns_tics: Optional[str] = Field(
        None,
        description="Character's verbal tics, speech quirks, and linguistic habits (for character items only)",
    )
    tone: Optional[str] = Field(
        None,
        description="Character's general tone, emotional expressiveness in language (for character items only)",
    )
    habits_mannerisms: Optional[str] = Field(
        None,
        description="Character's verbal and non-verbal habits in communication (for character items only)",
    )


class BatchCreateCodexItemsToolArgs(BaseModel):
    items: List[Dict[str, Any]] = Field(
        ...,
        description="List of codex items to create in batch. Each item must have name, description, and type fields. For character items, can include backstory and voice profile fields (vocabulary, sentence_structure, speech_patterns_tics, tone, habits_mannerisms).",
    )


class UpdateCodexItemToolArgs(BaseModel):
    item_id: str = Field(..., description="ID of the codex item to update")
    name: Optional[str] = Field(None, description="Updated name of the codex item")
    description: Optional[str] = Field(
        None, description="Updated detailed description of the codex item"
    )
    type: Optional[str] = Field(
        None,
        description="Updated type of codex item (character, worldbuilding, item, lore, faction, location, event, relationship)",
    )
    subtype: Optional[str] = Field(
        None,
        description="Updated subtype for worldbuilding items (history, culture, geography, other)",
    )
    backstory: Optional[str] = Field(
        None, description="Updated backstory for character items"
    )
    vocabulary: Optional[str] = Field(
        None,
        description="Updated character's vocabulary style and word choice patterns (for character items only)",
    )
    sentence_structure: Optional[str] = Field(
        None,
        description="Updated character's typical sentence structures, paragraph patterns, and linguistic style (for character items only)",
    )
    speech_patterns_tics: Optional[str] = Field(
        None,
        description="Updated character's verbal tics, speech quirks, and linguistic habits (for character items only)",
    )
    tone: Optional[str] = Field(
        None,
        description="Updated character's general tone, emotional expressiveness in language (for character items only)",
    )
    habits_mannerisms: Optional[str] = Field(
        None,
        description="Updated character's verbal and non-verbal habits during communication (for character items only)",
    )


class ArchitectAgent:
    """
    An AI agent specifically designed to assist with high-level project management,
    planning, and potentially automated generation tasks within a project context.
    Requires Pro subscription.
    """

    def __init__(
        self,
        user_id: str,
        project_id: str,
        api_key_manager: ApiKeyManager,
        agent_manager: AgentManager,
    ):
        self.logger = logging.getLogger(__name__)
        self.user_id = user_id
        self.project_id = project_id
        self.api_key_manager = api_key_manager
        self.agent_manager = agent_manager
        self.llm: Optional[BaseChatModel] = None
        self.parsing_llm: Optional[BaseChatModel] = None
        self.agent_executor: Optional[AgentExecutor] = None
        self.model_settings: Optional[Dict[str, Any]] = None
        self.project_context: Optional[Dict[str, Any]] = None
        self.auth_token: Optional[str] = None

        self.tools = [
            StructuredTool.from_function(
                name="generate_chapter_tool",
                description="Generates a new chapter based on the provided details. The agent already knows the project ID.",
                func=None,
                coroutine=self.generate_chapter_tool,
                args_schema=GenerateChapterToolArgs,
            ),
            StructuredTool.from_function(
                name="query_codex_tool",
                description="Searches the project's knowledge base for relevant information based on the query. The agent knows the project ID.",
                func=None,
                coroutine=self.query_codex_tool,
                args_schema=QueryCodexToolArgs,
            ),
            StructuredTool.from_function(
                name="get_project_details_tool",
                description="Fetches the basic details of the current project (name, description). The agent knows the project ID.",
                func=None,
                coroutine=self.get_project_details_tool,
                args_schema=GetProjectDetailsToolArgs,
            ),
            StructuredTool.from_function(
                name="get_chapter_list_tool",
                description="Fetches a list of all chapters (number and title) for the current project. The agent knows the project ID.",
                func=None,
                coroutine=self.get_chapter_list_tool,
                args_schema=GetChapterListToolArgs,
            ),
            StructuredTool.from_function(
                name="read_chapter_tool",
                description="Reads the full content of a specific chapter number. The agent knows the project ID.",
                func=None,
                coroutine=self.read_chapter_tool,
                args_schema=ReadChapterToolArgs,
            ),
            StructuredTool.from_function(
                name="get_recent_chapters_summary_tool",
                description="Fetches and summarizes the most recent chapters (default is 3). The agent knows the project ID.",
                func=None,
                coroutine=self.get_recent_chapters_summary_tool,
                args_schema=GetRecentChaptersSummaryToolArgs,
            ),
            StructuredTool.from_function(
                name="get_project_structure_tool",
                description="Fetches the current project's story structure (acts, stages, substages) as a JSON string. The agent knows the project ID.",
                func=None,
                coroutine=self.get_project_structure_tool,
                args_schema=GetProjectStructureToolArgs,
            ),
            StructuredTool.from_function(
                name="update_project_structure_tool",
                description="Updates or sets the project's story structure (acts, stages, substages). Requires the complete desired structure as a JSON string under the key 'project_structure'.",
                func=None,
                coroutine=self.update_project_structure_tool,
                args_schema=UpdateProjectStructureToolArgs,
            ),
            StructuredTool.from_function(
                name="update_target_word_count_tool",
                description="Sets or updates the target word count for chapters in the project.",
                func=None,
                coroutine=self.update_target_word_count_tool,
                args_schema=UpdateTargetWordCountToolArgs,
            ),
            StructuredTool.from_function(
                name="create_codex_item_tool",
                description="Creates a new codex item (character, location, etc.) in the project's knowledge base. The agent knows the project ID.",
                func=None,
                coroutine=self.create_codex_item_tool,
                args_schema=CreateCodexItemToolArgs,
            ),
            StructuredTool.from_function(
                name="batch_create_codex_items_tool",
                description="Creates multiple codex items at once in the project's knowledge base. Use this for efficiently adding multiple related items. The agent knows the project ID.",
                func=None,
                coroutine=self.batch_create_codex_items_tool,
                args_schema=BatchCreateCodexItemsToolArgs,
            ),
            StructuredTool.from_function(
                name="update_codex_item_tool",
                description="Updates a codex item in the project's knowledge base. The agent knows the project ID.",
                func=None,
                coroutine=self.update_codex_item_tool,
                args_schema=UpdateCodexItemToolArgs,
            ),
        ]

        self.logger.info(
            f"ArchitectAgent instantiated for Project: {project_id}, User: {user_id}"
        )

    async def _get_or_create_gemini_cache(
        self,
        cache_name: str,
        system_instruction: str,
        contents: List[str] = None,
        ttl_minutes: int = 60,
    ) -> str:
        """
        Creates or retrieves a Gemini context cache.
        Returns the cache name (resource name).
        """
        try:
            # List caches to find one with the matching display_name
            existing_cache = None
            async for c in caching.CachedContent.list_async():
                if c.display_name == cache_name:
                    existing_cache = c
                    break

            if existing_cache:
                self.logger.info(f"Found existing Gemini cache: {existing_cache.name}")
                # Update TTL
                existing_cache.update(ttl=timedelta(minutes=ttl_minutes))
                return existing_cache.name

            self.logger.info(f"Creating new Gemini cache: {cache_name}")
            
            # Create the cache
            cached_content = await caching.CachedContent.create_async(
                model="models/gemini-1.5-pro-001", # Default or passed in?
                display_name=cache_name,
                system_instruction=system_instruction,
                contents=contents if contents else [],
                ttl=timedelta(minutes=ttl_minutes),
            )
            return cached_content.name

        except Exception as e:
            self.logger.error(f"Error creating Gemini cache: {e}")
            return None

    async def _initialize(self):
        """Asynchronously initializes LLM, context, and agent executor."""
        if self.agent_executor:
            self.logger.debug("ArchitectAgent already initialized.")
            return

        self.logger.info(
            f"Initializing ArchitectAgent for Project: {self.project_id}..."
        )
        try:
            self.model_settings = await self._get_model_settings()
            gemini_api_key = await self.api_key_manager.get_api_key(self.user_id)
            openrouter_api_key = await self.api_key_manager.get_openrouter_api_key(
                self.user_id
            )

            architect_model_name = self.model_settings.get(
                "mainLLM", "gemini-1.5-flash-latest"
            )
            
            # Prepare system message first
            project_data = await db_instance.get_project(self.project_id, self.user_id)
            if not project_data:
                raise ValueError(
                    f"Project {self.project_id} not found during Architect init."
                )
            self.project_context = {
                "name": project_data.get("name"),
                "description": project_data.get("description"),
            }

            system_message = (
                f"You are the Architect AI, an expert writing assistant for the project: '{self.project_context['name']}'.\\n"
                f"Project Description: '{self.project_context['description']}'.\\n"
                f"You are operating within the context of Project ID: {self.project_id}. You do NOT need to ask for or specify this ID when using tools, as it's automatically handled.\\n\\n"
                f"Your primary functions are:\\n"
                f"- High-level planning and outlining of the story.\\n"
                f"- Analyzing project content (chapters, codex) to answer user questions or provide insights.\\n"
                f"- Generating new content, such as chapter drafts, based on user instructions and project context.\\n"
                f"- Creating and maintaining the project's knowledge base, including character profiles, worldbuilding elements, and more.\\n\\n"
                f"Available tools:\\n"
                f"- `get_project_details_tool`: Get overall project details and context.\\n"
                f"- `get_chapter_list_tool`: Get a list of all chapters in the project.\\n"
                f"- `read_chapter_tool`: Read a specific chapter by number.\\n"
                f"- `get_recent_chapters_summary_tool`: Get a summary of recent chapters (default: last 3).\\n"
                f"- `generate_chapter_tool`: Generate a new chapter draft based on provided details.\\n"
                f"- `query_codex_tool`: Search the project's knowledge base (characters, worldbuilding, etc).\\n"
                f"- `get_project_structure_tool`: Get the project's folder structure for organizing chapters.\\n"
                f"- `update_project_structure_tool`: Updates the project's folder structure. Requires a JSON string containing the full desired structure under a 'project_structure' key. Each folder item should have type 'folder', and chapter items should have type 'chapter'.\n"
                f"- `update_target_word_count_tool`: Sets a default target word count for all chapters in the project.\\n"
                f"- `create_codex_item_tool`: Creates a new codex item in the project's knowledge base. Requires name, description, type (character, worldbuilding, item, lore, faction, location, event, relationship), and optional subtype (history, culture, geography, other - for worldbuilding only) and backstory (for characters only). For character items, you can also provide voice profile details (vocabulary, sentence_structure, speech_patterns_tics, tone, habits_mannerisms) to define how the character speaks and communicates.\\n"
                f"- `batch_create_codex_items_tool`: Creates multiple codex items at once. Requires a list of items, where each item must have name, description, and type fields. For character items, you can include backstory and voice profile details. You can use this to efficiently create sets of related items like multiple characters, locations, or worldbuilding elements in a single operation.\\n"
                f"- `update_codex_item_tool`: Updates an existing codex item in the project's knowledge base. Requires item_id and at least one of: name, description, type, subtype, backstory, or character voice profile details (vocabulary, sentence_structure, speech_patterns_tics, tone, habits_mannerisms). Only the fields you provide will be updated.\\n\\n"
                f"Guidelines:\\n"
                f"- Be proactive and insightful. Offer suggestions if appropriate.\\n"
                f"- Maintain a professional, helpful tone.\\n"
                f"- When asked to generate content, ensure you have sufficient detail (plot, style). Use the `generate_chapter_tool` specifically for chapter generation.\\n"
                f"- When creating codex items, ensure types are valid and subtypes are only used with worldbuilding items.\\n"
                f"- Character backstories should only be provided for items of type 'character'.\\n"
                f"- Voice profile information (vocabulary, sentence structure, speech patterns, tone, habits/mannerisms) should only be provided for character items.\\n"
                f"- When using tools, provide clear and accurate arguments, ensuring all required parameters specified in the tool's description and `args_schema` are included with their correct names and values. Use `query_codex_tool` to gather information before answering complex questions about the project.\\n"
                f"- Think step-by-step before acting."
                f"- If you need to generate multiple related codex items (like several characters or locations), use the batch_create_codex_items_tool for efficiency.\\n"
                f"- When discussing story beats or narrative decisions, support your suggestions with established narrative principles, but be adaptable to the user's vision.\\n\\n"
                f"IMPORTANT: Your role is as an intelligent creative assistant. The user is always in control and makes the final decisions for their project."
            )

            # Handle Caching for Gemini
            cached_content_name = None
            if "gemini" in architect_model_name.lower():
                # Create a unique cache name for this project's architect system prompt
                # Sanitize project_id for cache name (must be alphanumeric/dashes)
                safe_project_id = "".join(c for c in self.project_id if c.isalnum() or c in "-_")
                cache_display_name = f"architect_sys_{safe_project_id}"
                
                cached_content_name = await self._get_or_create_gemini_cache(
                    cache_name=cache_display_name,
                    system_instruction=system_message
                )

            self.llm = await self._get_llm_instance(
                architect_model_name, gemini_api_key, openrouter_api_key, cached_content_name
            )
            # Construct System Message Object
            final_system_message_content = system_message if not cached_content_name else "You are the Architect AI. Use the cached context."
            system_msg_obj = SystemMessage(content=final_system_message_content)
            
            # Apply Anthropic Caching if applicable
            if "anthropic" in architect_model_name.lower() and not cached_content_name:
                 # Cache the system prompt for Anthropic
                 system_msg_obj.additional_kwargs["cache_control"] = {"type": "ephemeral"}

            prompt = ChatPromptTemplate.from_messages(
                [
                    system_msg_obj,
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{input}"),
                    MessagesPlaceholder(variable_name="agent_scratchpad"),
                ]
            )

            if not self.llm:
                raise ValueError("LLM initialization failed.")

            agent = create_openai_tools_agent(self.llm, self.tools, prompt)
            self.agent_executor = AgentExecutor(
                agent=agent, tools=self.tools, verbose=False
            )
            self.logger.info(
                f"ArchitectAgent initialized successfully for Project: {self.project_id}"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to initialize ArchitectAgent: {e}", exc_info=True
            )
            self.agent_executor = None
            self.llm = None
            raise

    async def _get_model_settings(self) -> dict:
        try:
            settings = await db_instance.get_model_settings(self.user_id)
            defaults = {
                "mainLLM": "gemini-1.5-flash-latest",
                "temperature": 0.7,
            }
            final_settings = {**defaults}
            if settings:
                final_settings.update(
                    {k: v for k, v in settings.items() if v is not None}
                )
            final_settings["temperature"] = float(final_settings["temperature"])
            self.logger.debug(f"Architect using model settings: {final_settings}")
            return final_settings
        except Exception as e:
            self.logger.error(
                f"Error getting model settings for Architect: {e}", exc_info=True
            )
            raise

    async def _get_llm_instance(
        self,
        model_name: str,
        gemini_key: Optional[str],
        openrouter_key: Optional[str],
        cached_content_name: Optional[str] = None,
    ) -> BaseChatModel:
        self.logger.debug(f"Creating LLM instance for Architect: {model_name}")
        try:
            llm_instance: BaseChatModel
            temperature = float(self.model_settings.get("temperature", 0.7))

            if model_name.startswith("openrouter/"):
                if not openrouter_key:
                    raise ValueError(
                        "OpenRouter API key is required but not configured."
                    )
                openrouter_model_id = model_name.split("openrouter/", 1)[1]
                llm_instance = ChatOpenAI(
                    model=openrouter_model_id,
                    openai_api_key=openrouter_key,
                    openai_api_base=OPENROUTER_API_BASE,
                    temperature=temperature,
                    default_headers={
                        "HTTP-Referer": SITE_URL,
                        "X-Title": SITE_NAME,
                    },
                )
            else:
                if not gemini_key:
                    raise ValueError("Gemini API key is required but not configured.")
                llm_instance = ChatGoogleGenerativeAI(
                    model=model_name,
                    google_api_key=gemini_key,
                    temperature=temperature,
                    cached_content=cached_content_name,
                    convert_system_message_to_human=True,
                )
            self.logger.info(f"Architect LLM instance created: {model_name}")
            return llm_instance
        except Exception as e:
            self.logger.error(
                f"Failed to create LLM instance for Architect ({model_name}): {e}",
                exc_info=True,
            )
            raise

    async def chat(
        self,
        message: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        auth_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            self.auth_token = auth_token

            if not self.agent_executor:
                await self._initialize()
                if not self.agent_executor:
                    raise RuntimeError("ArchitectAgent could not be initialized.")

            self.logger.debug(f"Architect received message: '{message[:50]}...'")

            loaded_history = await db_instance.get_architect_chat_history(
                self.user_id, self.project_id
            )

            if not isinstance(loaded_history, list):
                self.logger.warning(
                    f"Loaded history is not a list: {type(loaded_history)}. Using empty list instead."
                )
                loaded_history = []

            # Normalize loaded history - convert list format content to strings
            normalized_history = []
            for msg in loaded_history:
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

            formatted_history = []
            for msg in normalized_history:
                role = msg.get("role")
                content = msg.get("content", "")
                if role == "user":
                    formatted_history.append(HumanMessage(content=content))
                elif role == "assistant":
                    formatted_history.append(AIMessage(content=content))

            response = await self.agent_executor.ainvoke(
                {
                    "input": message,
                    "chat_history": formatted_history,
                }
            )

            # Extract the response content, handling both string and list formats
            raw_output = response.get("output", "Agent did not return an output.")
            
            # If output is a list (e.g., from Anthropic API with content blocks), extract text
            if isinstance(raw_output, list):
                ai_response_content = ""
                for block in raw_output:
                    if isinstance(block, dict) and block.get("type") == "text":
                        ai_response_content += block.get("text", "")
                if not ai_response_content:
                    ai_response_content = "Agent did not return valid text content."
            else:
                ai_response_content = raw_output

            new_history_entry_user = {"role": "user", "content": message}
            new_history_entry_ai = {"role": "assistant", "content": ai_response_content}
            updated_history = normalized_history + [
                new_history_entry_user,
                new_history_entry_ai,
            ]

            try:
                await db_instance.save_architect_chat_history(
                    self.user_id, self.project_id, updated_history
                )
            except Exception as db_save_error:
                self.logger.error(
                    f"Failed to save Architect chat history: {db_save_error}",
                    exc_info=True,
                )

            return {
                "response": ai_response_content,
                "tool_calls": response.get("tool_calls", []),
            }

        except Exception as e:
            self.logger.error(
                f"Error during Architect chat execution: {e}", exc_info=True
            )
            return {
                "response": f"An error occurred while processing your request: {str(e)}",
                "tool_calls": [],
            }
        finally:
            self.auth_token = None

    # --- Tool Implementations (as async methods) ---

    async def generate_chapter_tool(self, chapter_details: str) -> str:
        """Generates a new chapter based on provided details (plot, style, instructions). Parses the details and initiates the background generation task."""
        project_id = self.project_id
        self.logger.info(
            f"[Architect Tool] generate_chapter_tool called for project {project_id}"
        )
        try:
            if not self.llm or not self.model_settings:
                await self._initialize()
                if not self.llm or not self.model_settings:
                    return "Error: Architect Agent not properly initialized."

            parsing_llm_name = self.model_settings.get(
                "checkLLM", "gemini-1.5-flash-latest"
            )
            if not self.parsing_llm or self.parsing_llm.model != parsing_llm_name:
                gemini_key = await self.api_key_manager.get_api_key(self.user_id)
                or_key = await self.api_key_manager.get_openrouter_api_key(self.user_id)
                self.parsing_llm = await self._get_llm_instance(
                    parsing_llm_name, gemini_key, or_key
                )

            parser = PydanticOutputParser(pydantic_object=ChapterDetailsInput)
            prompt = ChatPromptTemplate.from_template(
                "Parse the following chapter generation request into a structured format. Extract the plot, writing style, and any other instructions mentioned.\\nRequest: {request}\\n{format_instructions}"
            )
            chain = prompt | self.parsing_llm | parser

            try:
                parsed_input: ChapterDetailsInput = await chain.ainvoke(
                    {
                        "request": chapter_details,
                        "format_instructions": parser.get_format_instructions(),
                    }
                )
            except Exception as parse_error:
                self.logger.error(
                    f"Failed to parse chapter details with LLM: {parse_error}"
                )
                return f"Error: Could not understand the chapter details provided. Please structure them clearly (plot, style, instructions). Error: {parse_error}"

            target_word_count = (
                parsed_input.word_count
                if parsed_input.word_count is not None
                else self.project_context.get("target_word_count", 0)
            )
            instructions = {
                "wordCount": target_word_count,
                "styleGuide": parsed_input.style_guide or "",
                "additionalInstructions": parsed_input.additional_instructions or "",
                "project_name": self.project_context.get("name", ""),
                "project_description": self.project_context.get("description", ""),
            }

            gen_request_data = {
                "plot": parsed_input.plot,
                "writingStyle": parsed_input.writing_style,
                "numChapters": parsed_input.num_chapters,
                "instructions": instructions,
            }
            gen_request = ChapterGenerationRequest.model_validate(gen_request_data)

            if not self.auth_token:
                return "Error: Could not get authentication token to initiate chapter generation."

            backend_base_url = os.getenv(
                "BACKEND_INTERNAL_URL", "http://localhost:8080"
            )
            generate_url = f"{backend_base_url}/projects/{project_id}/chapters/generate"

            headers = {
                "Authorization": self.auth_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        generate_url,
                        json=gen_request.model_dump(),
                        headers=headers,
                        timeout=30.0,
                    )

                    if response.status_code == 202:
                        return f"Successfully initiated generation for {gen_request.numChapters} chapter(s). Check progress in the generation tab."
                    elif response.status_code == 409:
                        logger.warning(
                            f"Chapter generation API returned 409 for project {project_id}"
                        )
                        return "Error: Chapter generation is already in progress for this project."
                    else:
                        response_detail = response.text
                        try:
                            response_json = response.json()
                            response_detail = response_json.get("detail", response.text)
                        except Exception:
                            pass
                        logger.error(
                            f"Chapter generation API call failed (Status: {response.status_code}): {response_detail}"
                        )
                        return f"Error: Failed to start chapter generation (Status: {response.status_code}). Details: {response_detail}"

                except httpx.RequestError as exc:
                    logger.error(
                        f"HTTP Request Error calling generation endpoint: {exc}",
                        exc_info=True,
                    )
                    return f"Error: Could not connect to the generation service: {exc}"
                except Exception as api_call_error:
                    logger.error(
                        f"Unexpected error during API call to generation endpoint: {api_call_error}",
                        exc_info=True,
                    )
                    return f"Error: An unexpected error occurred while starting generation: {api_call_error}"

        except Exception as e:
            self.logger.error(f"Error in generate_chapter_tool: {e}", exc_info=True)
            return f"Error executing chapter generation tool: {str(e)}"

    async def query_codex_tool(self, query: str, k: int = 5) -> str:
        """Searches the project's knowledge base (codex, chapters, etc.) for relevant information based on the query."""
        project_id = self.project_id
        self.logger.info(
            f"[Architect Tool] query_codex_tool called for project {project_id} with query: '{query[:50]}...' (k={k})"
        )
        try:
            if not self.agent_manager:
                return "Error: AgentManager not available to query_codex_tool"

            async with self.agent_manager.get_or_create_manager(
                self.user_id, project_id
            ) as agent_manager_instance:
                if not agent_manager_instance.vector_store:
                    return "Error: Vector store not available for this project."

                results = await agent_manager_instance.vector_store.similarity_search(
                    query, k=k
                )
                if not results:
                    return "No relevant information found in the knowledge base for that query."

                formatted_results = []
                for i, doc in enumerate(results):
                    metadata = doc.metadata or {}
                    item_type = metadata.get("type", "Unknown")
                    name = metadata.get("name", metadata.get("title", ""))
                    item_id = metadata.get("id", "Unknown ID")
                    codex_item_id = metadata.get("codex_item_id", item_id)
                    content_preview = doc.page_content[:200] + (
                        "..." if len(doc.page_content) > 200 else ""
                    )
                    formatted_results.append(
                        f"{i+1}. Type: {item_type}, Name: {name}, ID: {codex_item_id}, Content: {content_preview}"
                    )

                result_text = "\n".join(formatted_results)
                return result_text

        except Exception as e:
            self.logger.error(f"Error in query_codex_tool: {e}", exc_info=True)
            return f"Error querying knowledge base: {str(e)}"

    async def get_project_details_tool(self) -> str:
        """Fetches the basic details of the current project (name, description)."""
        project_id = self.project_id
        self.logger.info(
            f"[Architect Tool] get_project_details_tool called for project {project_id}"
        )
        try:
            if not self.project_context:
                await self._initialize()
                if not self.project_context:
                    return "Error: Could not load project context."

            return json.dumps(self.project_context, indent=2)
        except Exception as e:
            self.logger.error(f"Error in get_project_details_tool: {e}", exc_info=True)
            return f"Error fetching project details: {str(e)}"

    async def get_chapter_list_tool(self) -> str:
        """Fetches a list of all chapters (number and title) for the current project."""
        project_id = self.project_id
        self.logger.info(
            f"[Architect Tool] get_chapter_list_tool called for project {project_id}"
        )
        try:
            chapters = await db_instance.get_all_chapters(self.user_id, project_id)
            if not chapters:
                return "No chapters found for this project."

            chapter_list = [
                f"Ch {c.get('chapter_number', 'N/A')}: {c.get('title', 'Untitled')}"
                for c in chapters
            ]
            return "\\n".join(chapter_list)
        except Exception as e:
            self.logger.error(f"Error in get_chapter_list_tool: {e}", exc_info=True)
            return f"Error fetching chapter list: {str(e)}"

    async def read_chapter_tool(self, chapter_number: int) -> str:
        """Reads the full content of a specific chapter number."""
        project_id = self.project_id
        self.logger.info(
            f"[Architect Tool] read_chapter_tool called for project {project_id}, chapter {chapter_number}"
        )
        try:
            chapter = await db_instance.get_chapter_by_number(
                project_id, self.user_id, chapter_number
            )
            if not chapter:
                return f"Error: Chapter number {chapter_number} not found."
            return chapter.get("content", "Error: Chapter content not found.")
        except Exception as e:
            self.logger.error(f"Error in read_chapter_tool: {e}", exc_info=True)
            return f"Error reading chapter {chapter_number}: {str(e)}"

    async def get_recent_chapters_summary_tool(self, count: int = 3) -> str:
        """Fetches and summarizes the most recent chapters (default is 3)."""
        project_id = self.project_id
        self.logger.info(
            f"[Architect Tool] get_recent_chapters_summary_tool called for project {project_id} (count={count})"
        )
        try:
            if not self.agent_manager:
                return "Error: AgentManager not available to get_recent_chapters_summary_tool"

            async with self.agent_manager.get_or_create_manager(
                self.user_id, project_id
            ) as agent_manager_instance:
                if not agent_manager_instance.summarize_chain:
                    return "Error: Summarization chain not available."

                chapters_data = await db_instance.get_all_chapters(
                    self.user_id, project_id
                )
                if not chapters_data:
                    return "No chapters found to summarize."

                chapters_data.sort(key=lambda x: x.get("chapter_number", 0))
                recent_chapters = chapters_data[-count:]

                summaries = []
                for chapter in recent_chapters:
                    chap_num = chapter.get("chapter_number", "N/A")
                    chap_title = chapter.get("title", f"Chapter {chap_num}")
                    content = chapter.get("content", "")
                    if not content:
                        summaries.append(f"Ch {chap_num} ({chap_title}): [No content]")
                        continue

                    from langchain_core.documents import Document

                    docs_to_summarize = [Document(page_content=content)]
                    summary_result = (
                        await agent_manager_instance.summarize_chain.ainvoke(
                            {"input_documents": docs_to_summarize}
                        )
                    )
                    summary_text = summary_result.get(
                        "output_text", "[Summary unavailable]"
                    )
                    summaries.append(f"Ch {chap_num} ({chap_title}): {summary_text}")

                return "\\n\\n".join(summaries)

        except Exception as e:
            self.logger.error(
                f"Error in get_recent_chapters_summary_tool: {e}", exc_info=True
            )
            return f"Error summarizing recent chapters: {str(e)}"

    async def get_project_structure_tool(self) -> str:
        """Fetches the current project story structure (acts, stages, substages) as a JSON string."""
        project_id = self.project_id
        user_id = self.user_id
        self.logger.info(
            f"[Architect Tool] get_project_structure_tool called for project {project_id}"
        )
        try:
            structure_data = await db_instance.get_project_structure(
                project_id, user_id
            )
            if not structure_data:
                return "No project structure found or it is empty."

            # Normalize folder types to match frontend expectations
            def normalize_folder_types(items: List[Dict[str, Any]]):
                for item in items:
                    if item.get("type") != "chapter":
                        # Convert any act, stage, substage to "folder" to match frontend expectations
                        item["type"] = "folder"

                    # Process children recursively
                    if "children" in item and isinstance(item["children"], list):
                        normalize_folder_types(item["children"])

            # Apply type normalization if structure exists
            if (
                isinstance(structure_data, dict)
                and "project_structure" in structure_data
            ):
                normalize_folder_types(structure_data["project_structure"])

            # The structure_data from get_project_structure is already a dict like {'project_structure': [...]}
            # or None. If it has data, it should be JSON serializable directly.
            return json.dumps(structure_data, indent=2)

        except Exception as e:
            self.logger.error(
                f"Error in get_project_structure_tool: {e}", exc_info=True
            )
            return f"Error fetching project structure: {str(e)}"

    async def update_project_structure_tool(self, project_structure_json: str) -> str:
        """
        Updates the project's hierarchical structure (acts, stages, substages).
        The input is a JSON string representing the new structure.
        """
        project_id = self.project_id
        user_id = self.user_id
        self.logger.info(
            f"[Architect Tool] update_project_structure_tool called for project {project_id}"
        )
        try:
            # Attempt to parse the JSON string from the LLM
            data = json.loads(project_structure_json)

            # The LLM might provide the data directly as a list, or nested under a 'project_structure' key.
            if isinstance(data, dict) and "project_structure" in data:
                structure_list = data["project_structure"]
            elif isinstance(data, list):
                structure_list = data
            else:
                return "Error: project_structure_json must be a JSON array of structure items, or a JSON object with a 'project_structure' key."

            # Recursive function to filter out chapters and keep only folders (acts, stages, etc.)
            def filter_folders(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
                folder_items = []
                for item in items:
                    # The structure can contain 'chapter' type items from get_project_structure_tool,
                    # but the update endpoint only accepts act, stage, substage. We filter chapters out.
                    if item.get("type") != "chapter":
                        folder_item = item.copy()
                        if "children" in folder_item and isinstance(
                            folder_item["children"], list
                        ):
                            folder_item["children"] = filter_folders(
                                folder_item["children"]
                            )
                        folder_items.append(folder_item)
                return folder_items

            # Filter out any non-folder items (like chapters) from the structure
            filtered_structure = filter_folders(structure_list)

            # Normalize folder types to match frontend expectations
            def normalize_folder_types(items: List[Dict[str, Any]]):
                for item in items:
                    if item.get("type") != "chapter":
                        # Convert any act, stage, substage to "folder" to match frontend expectations
                        item["type"] = "folder"

                    # Process children recursively
                    if "children" in item and isinstance(item["children"], list):
                        normalize_folder_types(item["children"])

            # Apply type normalization to ensure all non-chapter items are "folder" type
            normalize_folder_types(filtered_structure)

            # Ensure consistency between 'name' and 'title' fields
            def ensure_field_consistency(items: List[Dict[str, Any]]):
                for item in items:
                    # Make sure both name and title fields exist and have the same value
                    if "name" in item and "title" not in item:
                        item["title"] = item["name"]
                    elif "title" in item and "name" not in item:
                        item["name"] = item["title"]

                    # Process children recursively
                    if "children" in item and isinstance(item["children"], list):
                        ensure_field_consistency(item["children"])

            # Apply field consistency to the structure
            ensure_field_consistency(filtered_structure)

            # Validate the structure data against the Pydantic model
            try:
                ProjectStructureUpdateRequest.model_validate(
                    {"project_structure": filtered_structure}
                )
            except ValidationError as e:
                self.logger.error(
                    f"Invalid project structure format from LLM for project {project_id}: {e}"
                )
                error_details = [
                    f"Field '...{'.'.join(map(str, error['loc']))}': {error['msg']}"
                    for error in e.errors()
                ]
                return (
                    f"Error: The provided structure is invalid. Details: {'; '.join(error_details)}. "
                    "Ensure all items have 'id', 'name', 'type' ('folder' for hierarchical items, 'chapter' for chapters), "
                    "and 'children' fields for folder items."
                )

            # If validation passes, proceed to call the database function
            updated_structure = await db_instance.update_project_structure(
                project_id=project_id,
                structure=filtered_structure,  # Pass the filtered structure
                user_id=user_id,
            )

            if updated_structure is not None:
                if self.agent_manager:
                    # Invalidate the agent manager's cache for this specific project
                    await self.agent_manager.invalidate_project_managers(
                        self.project_id
                    )
                return "Project structure updated successfully."
            else:
                self.logger.error(
                    f"DB update for project structure returned None for project {project_id}."
                )
                return "Error: Failed to update project structure in the database. The project might not exist or the data was invalid."

        except json.JSONDecodeError:
            self.logger.warning(
                f"Invalid JSON for project structure update (project {project_id}): {project_structure_json}"
            )
            return "Error: Invalid JSON format provided. Please provide a valid JSON string."
        except Exception as e:
            self.logger.exception(
                f"Unexpected error in update_project_structure_tool for project {project_id}: {e}"
            )
            return f"An unexpected error occurred: {str(e)}"

    async def update_target_word_count_tool(self, word_count: int) -> str:
        """Sets or updates the target word count for the entire project."""
        project_id = self.project_id
        user_id = self.user_id
        self.logger.info(
            f"[Architect Tool] update_target_word_count_tool called for project {project_id} with word_count: {word_count}"
        )
        try:
            success = await db_instance.update_project_target_word_count(
                project_id=project_id,
                user_id=user_id,
                target_word_count=word_count,
            )
            if success:
                # Update project_context in memory as well
                if self.project_context:
                    self.project_context["target_word_count"] = word_count
                return (
                    f"Successfully updated project target word count to {word_count}."
                )
            else:
                return "Error: Failed to update project target word count. The project may not exist."
        except Exception as e:
            self.logger.error(
                f"Error in update_target_word_count_tool: {e}", exc_info=True
            )
            return f"An unexpected error occurred while updating the target word count: {str(e)}"

    async def create_codex_item_tool(
        self,
        name: str,
        description: str,
        type: str,
        subtype: Optional[str] = None,
        backstory: Optional[str] = None,
        vocabulary: Optional[str] = None,
        sentence_structure: Optional[str] = None,
        speech_patterns_tics: Optional[str] = None,
        tone: Optional[str] = None,
        habits_mannerisms: Optional[str] = None,
    ) -> str:
        """Creates a new codex item in the project knowledge base."""
        project_id = self.project_id
        user_id = self.user_id
        self.logger.info(
            f"[Architect Tool] create_codex_item_tool called for project {project_id}: {name} ({type})"
        )

        try:
            # Validate the type and subtype
            try:
                codex_type_enum = CodexItemType(type)
                subtype_enum = None
                if subtype:
                    if codex_type_enum != CodexItemType.WORLDBUILDING:
                        return f"Error: Subtype '{subtype}' can only be specified for worldbuilding items, not {type}."
                    subtype_enum = WorldbuildingSubtype(subtype)
            except ValueError:
                valid_types = ", ".join([t.value for t in CodexItemType])
                valid_subtypes = ", ".join([s.value for s in WorldbuildingSubtype])
                return f"Error: Invalid type or subtype. Valid types are: {valid_types}. Valid subtypes (for worldbuilding only) are: {valid_subtypes}."

            # Check if this is a character with backstory
            if backstory and codex_type_enum != CodexItemType.CHARACTER:
                return f"Error: Backstory can only be provided for character items, not {type}."

            # Check voice profile fields
            has_voice_profile = any(
                [
                    vocabulary,
                    sentence_structure,
                    speech_patterns_tics,
                    tone,
                    habits_mannerisms,
                ]
            )
            if has_voice_profile and codex_type_enum != CodexItemType.CHARACTER:
                return f"Error: Voice profile information can only be provided for character items, not {type}."

            # Create the codex item in the database
            item_id = await db_instance.create_codex_item(
                name=name,
                description=description,
                type=type,
                subtype=subtype,
                user_id=user_id,
                project_id=project_id,
                backstory=backstory,
            )

            # Create voice profile if this is a character and voice profile data is provided
            if codex_type_enum == CodexItemType.CHARACTER and has_voice_profile:
                voice_profile_data = {
                    "vocabulary": vocabulary,
                    "sentence_structure": sentence_structure,
                    "speech_patterns_tics": speech_patterns_tics,
                    "tone": tone,
                    "habits_mannerisms": habits_mannerisms,
                }
                try:
                    await db_instance.get_or_create_character_voice_profile(
                        codex_item_id=item_id,
                        user_id=user_id,
                        project_id=project_id,
                        voice_profile_data=voice_profile_data,
                    )
                except Exception as vp_error:
                    self.logger.error(
                        f"Error creating voice profile for character {name}: {vp_error}",
                        exc_info=True,
                    )
                    # Continue even if voice profile creation fails

            # Add to knowledge base
            try:
                if not self.agent_manager:
                    return (
                        "Error: Agent manager not available for create_codex_item_tool"
                    )

                async with self.agent_manager.get_or_create_manager(
                    user_id, project_id
                ) as agent_manager_instance:
                    metadata = {
                        "id": item_id,
                        "name": name,
                        "type": type,
                        "subtype": subtype,
                    }

                    embedding_id = await agent_manager_instance.add_to_knowledge_base(
                        type, description, metadata
                    )

                    if embedding_id:
                        await db_instance.update_codex_item_embedding_id(
                            item_id, embedding_id
                        )
                        voice_profile_note = (
                            " (with voice profile)"
                            if has_voice_profile
                            and codex_type_enum == CodexItemType.CHARACTER
                            else ""
                        )
                        return f"Successfully created new {type}{' (' + subtype + ')' if subtype else ''} codex item: {name}{voice_profile_note}"
                    else:
                        return f"Created {type} codex item '{name}' but failed to index it in the knowledge base."
            except Exception as kb_e:
                self.logger.error(
                    f"Error adding codex item to knowledge base: {kb_e}", exc_info=True
                )
                return f"Created {type} codex item '{name}' but failed to index it in the knowledge base: {str(kb_e)}"

        except Exception as e:
            self.logger.error(f"Error in create_codex_item_tool: {e}", exc_info=True)
            return f"Error creating codex item: {str(e)}"

    async def update_codex_item_tool(
        self,
        item_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        type: Optional[str] = None,
        subtype: Optional[str] = None,
        backstory: Optional[str] = None,
        vocabulary: Optional[str] = None,
        sentence_structure: Optional[str] = None,
        speech_patterns_tics: Optional[str] = None,
        tone: Optional[str] = None,
        habits_mannerisms: Optional[str] = None,
    ) -> str:
        """Update a codex item in the project's knowledge base.

        Args:
            item_id: ID of the codex item to update
            name: Updated name of the codex item
            description: Updated description of the codex item
            type: Updated type of the codex item
            subtype: Updated subtype for worldbuilding items
            backstory: Updated backstory for character items
            vocabulary: Updated character's vocabulary style
            sentence_structure: Updated character's sentence structures
            speech_patterns_tics: Updated character's speech patterns
            tone: Updated character's tone
            habits_mannerisms: Updated character's habits and mannerisms

        Returns:
            String confirmation that the codex item was updated
        """
        try:
            # First get the current item to make sure it exists
            try:
                # Get the item using db_instance instead of self.agent_manager.database
                existing_item = await db_instance.get_codex_item_by_id(
                    item_id, self.user_id, self.project_id
                )
                if not existing_item:
                    return f"Error: Codex item with ID {item_id} not found"
            except Exception as e:
                return f"Error finding codex item: {str(e)}"

            # Create voice profile data if character voice fields are provided
            voice_profile_data = {}
            if (
                vocabulary
                or sentence_structure
                or speech_patterns_tics
                or tone
                or habits_mannerisms
            ):
                voice_profile_data = {
                    "vocabulary": vocabulary,
                    "sentence_structure": sentence_structure,
                    "speech_patterns_tics": speech_patterns_tics,
                    "tone": tone,
                    "habits_mannerisms": habits_mannerisms,
                }

            # Update the codex item in the database
            try:
                # Use db_instance instead of self.agent_manager.database
                await db_instance.update_codex_item(
                    item_id=item_id,
                    user_id=self.user_id,
                    project_id=self.project_id,
                    name=name,
                    description=description,
                    type=type,
                    subtype=subtype,
                    backstory=backstory,
                )

                # If this is a character and we have voice profile data, update the voice profile
                if (
                    type == "character" or existing_item["type"] == "character"
                ) and voice_profile_data:
                    try:
                        # Check if voice profile exists
                        existing_voice_profile = (
                            await db_instance.get_character_voice_profile_by_codex_id(
                                codex_item_id=item_id,
                                user_id=self.user_id,
                                project_id=self.project_id,
                            )
                        )

                        if existing_voice_profile:
                            # Update existing voice profile
                            await db_instance.update_character_voice_profile(
                                codex_item_id=item_id,
                                user_id=self.user_id,
                                project_id=self.project_id,
                                voice_profile_data=voice_profile_data,
                            )
                        else:
                            # Create new voice profile
                            await db_instance.create_character_voice_profile(
                                codex_item_id=item_id,
                                user_id=self.user_id,
                                project_id=self.project_id,
                                voice_profile_data=voice_profile_data,
                            )
                    except Exception as e:
                        return f"Successfully updated codex item {item_id}, but failed to update voice profile: {str(e)}"

                # Get the updated item from the database
                updated_item = await db_instance.get_codex_item_by_id(
                    item_id, self.user_id, self.project_id
                )

                # Update the item in the knowledge base
                if updated_item and updated_item.get("embedding_id"):
                    content = f"Name: {updated_item.get('name')}\nType: {updated_item.get('type')}\nDescription: {updated_item.get('description')}"
                    if updated_item.get("subtype"):
                        content += f"\nSubtype: {updated_item.get('subtype')}"
                    if backstory and (
                        type == "character" or existing_item["type"] == "character"
                    ):
                        content += f"\nBackstory: {backstory}"

                    metadata = {
                        "type": "codex_item",
                        "codex_item_id": item_id,
                        "codex_item_type": updated_item.get("type"),
                    }

                    # Use the agent_manager_instance to update the knowledge base
                    if not self.agent_manager:
                        return "Error: Agent manager not available for update_codex_item_tool"

                    async with self.agent_manager.get_or_create_manager(
                        self.user_id, self.project_id
                    ) as agent_manager_instance:
                        await agent_manager_instance.update_or_remove_from_knowledge_base(
                            identifier=updated_item.get("embedding_id"),
                            action="update",
                            new_content=content,
                            new_metadata=metadata,
                        )

                message = f"Successfully updated codex item: {updated_item.get('name')} (ID: {item_id})"
                if name or description:
                    message += f" with {'new name' if name else ''}{' and ' if name and description else ''}{'new description' if description else ''}"
                return message
            except Exception as e:
                return f"Error updating codex item: {str(e)}"
        except Exception as e:
            return f"Error updating codex item: {str(e)}"

    async def batch_create_codex_items_tool(self, items: List[Dict[str, Any]]) -> str:
        """Creates multiple codex items at once in the project knowledge base."""
        project_id = self.project_id
        user_id = self.user_id
        self.logger.info(
            f"[Architect Tool] batch_create_codex_items_tool called for project {project_id}: {len(items)} items"
        )

        if not items:
            return "Error: No items provided."

        created_items = []
        failed_items = []

        for i, item in enumerate(items):
            try:
                name = item.get("name")
                description = item.get("description")
                type_val = item.get("type")
                subtype = item.get("subtype")
                backstory = item.get("backstory")

                # Extract voice profile fields if present
                vocabulary = item.get("vocabulary")
                sentence_structure = item.get("sentence_structure")
                speech_patterns_tics = item.get("speech_patterns_tics")
                tone = item.get("tone")
                habits_mannerisms = item.get("habits_mannerisms")

                if not name or not description or not type_val:
                    failed_items.append(
                        f"Item #{i+1} - Missing required fields (name, description, type)"
                    )
                    continue

                # Validate the type and subtype
                try:
                    codex_type_enum = CodexItemType(type_val)
                    subtype_enum = None
                    if subtype:
                        if codex_type_enum != CodexItemType.WORLDBUILDING:
                            failed_items.append(
                                f"Item '{name}' - Subtype '{subtype}' can only be specified for worldbuilding items"
                            )
                            continue
                        subtype_enum = WorldbuildingSubtype(subtype)
                except ValueError:
                    failed_items.append(
                        f"Item '{name}' - Invalid type '{type_val}' or subtype '{subtype}'"
                    )
                    continue

                # Check if backstory is valid for this type
                if backstory and codex_type_enum != CodexItemType.CHARACTER:
                    failed_items.append(
                        f"Item '{name}' - Backstory can only be provided for character items"
                    )
                    continue

                # Check voice profile fields
                has_voice_profile = any(
                    [
                        vocabulary,
                        sentence_structure,
                        speech_patterns_tics,
                        tone,
                        habits_mannerisms,
                    ]
                )
                if has_voice_profile and codex_type_enum != CodexItemType.CHARACTER:
                    failed_items.append(
                        f"Item '{name}' - Voice profile information can only be provided for character items"
                    )
                    continue

                # Create the codex item in the database
                item_id = await db_instance.create_codex_item(
                    name=name,
                    description=description,
                    type=type_val,
                    subtype=subtype,
                    user_id=user_id,
                    project_id=project_id,
                    backstory=backstory,
                )

                # Create voice profile if this is a character and voice profile data is provided
                if codex_type_enum == CodexItemType.CHARACTER and has_voice_profile:
                    voice_profile_data = {
                        "vocabulary": vocabulary,
                        "sentence_structure": sentence_structure,
                        "speech_patterns_tics": speech_patterns_tics,
                        "tone": tone,
                        "habits_mannerisms": habits_mannerisms,
                    }
                    try:
                        await db_instance.get_or_create_character_voice_profile(
                            codex_item_id=item_id,
                            user_id=user_id,
                            project_id=project_id,
                            voice_profile_data=voice_profile_data,
                        )
                    except Exception as vp_error:
                        self.logger.error(
                            f"Error creating voice profile for character {name}: {vp_error}",
                            exc_info=True,
                        )
                        # Continue even if voice profile creation fails

                # Add to knowledge base
                if self.agent_manager:
                    async with self.agent_manager.get_or_create_manager(
                        user_id, project_id
                    ) as agent_manager_instance:
                        metadata = {
                            "id": item_id,
                            "name": name,
                            "type": type_val,
                            "subtype": subtype,
                        }

                        try:
                            embedding_id = (
                                await agent_manager_instance.add_to_knowledge_base(
                                    type_val, description, metadata
                                )
                            )

                            if embedding_id:
                                await db_instance.update_codex_item_embedding_id(
                                    item_id, embedding_id
                                )
                                voice_profile_note = (
                                    " (with voice profile)"
                                    if has_voice_profile
                                    and codex_type_enum == CodexItemType.CHARACTER
                                    else ""
                                )
                                created_items.append(
                                    f"{name} ({type_val}{voice_profile_note})"
                                )
                            else:
                                failed_items.append(
                                    f"Item '{name}' - Failed to index in knowledge base"
                                )
                        except Exception:
                            failed_items.append(
                                f"Item '{name}' - Failed to index in knowledge base"
                            )

            except Exception as e:
                failed_items.append(f"Item #{i+1} - {str(e)}")

        # Prepare response
        if created_items and not failed_items:
            return f"Successfully created {len(created_items)} codex items: {', '.join(created_items)}"
        elif created_items and failed_items:
            return f"Created {len(created_items)} items: {', '.join(created_items)}\nFailed to create {len(failed_items)} items: {', '.join(failed_items)}"
        else:
            return f"Failed to create any codex items: {', '.join(failed_items)}"

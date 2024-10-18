# backend/agent_manager.py
import os
from typing import Dict, Any, List, Tuple, Optional
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
import logging
import uuid
from database import db_instance
from pydantic import BaseModel, Field
import json
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
from langchain.docstore.document import Document
import asyncio


class CodexItem(BaseModel):
    name: str = Field(default="", description="Name of the codex item")
    description: str = Field(default="", description="Description of the codex item")
    type: str = Field(default="lore", description="Type of the codex item (e.g., lore, worldbuilding, item, character)")
    subtype: Optional[str] = Field(default=None, description="Subtype of the codex item (e.g., history, culture, geography)")

class CodexExtraction(BaseModel):
    new_items: List[CodexItem] = Field(default_factory=list, description="List of new codex items found in the chapter")

class AgentManager:
    def __init__(self, user_id: str):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.logger.info(f"Initializing AgentManager for user: {user_id}")
        self.user_id = user_id
        self.api_key = self._get_api_key()
        self.model_settings = self._get_model_settings()
        self.MAX_INPUT_TOKENS = 2097152 if 'pro' in self.model_settings['mainLLM'] else 1048576
        self.MAX_OUTPUT_TOKENS = 8192
        self.chat_history = db_instance.get_chat_history(user_id)
        self.logger.info(f"AgentManager initialized for user: {user_id}")

        self.setup_caching()
        self.setup_rate_limiter()
        self.llm = self._initialize_llm(self.model_settings['mainLLM'])
        self.check_llm = self._initialize_llm(self.model_settings['checkLLM'])
        self.vector_store = VectorStore(self.user_id, self.api_key, self.model_settings['embeddingsModel'])
        self.summarize_chain = load_summarize_chain(self.llm, chain_type="map_reduce")

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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _initialize_llm(self, model: str) -> ChatGoogleGenerativeAI:
        self.logger.debug(f"Initializing LLM with model: {model}")
        try:
            llm = ChatGoogleGenerativeAI(
                model=model,
                google_api_key=self.api_key,
                temperature=0.7,
                max_output_tokens=self.MAX_OUTPUT_TOKENS,
                max_input_tokens=self.MAX_INPUT_TOKENS,
                caching=True,
                rate_limiter=self.rate_limiter,
                streaming=True,
                callback_manager=CallbackManager([StreamingStdOutCallbackHandler()])
            )
            self.logger.debug("LLM initialized successfully")
            return llm
        except Exception as e:
            self.logger.error(f"Error initializing LLM: {str(e)}")
            raise

    async def generate_chapter_stream(self, chapter_number: int, plot: str, writing_style: str, 
                                      instructions: Dict[str, Any],
                                      previous_chapters: List[Dict[str, Any]],
                                      codex_items: List[Dict[str, Any]]):
        self.logger.info(f"Starting chapter generation for chapter {chapter_number}")
        try:
            codex_items_dict = {item['name']: item['description'] for item in codex_items}
            
            context = await asyncio.to_thread(self._construct_context, plot, writing_style, instructions, codex_items_dict, previous_chapters)
            
            prompt = await asyncio.to_thread(self._construct_prompt, instructions, context)

            chat_history = ChatMessageHistory()
            total_tokens = 0
            max_history_tokens = self.MAX_INPUT_TOKENS // 4
            for i, chapter in enumerate(reversed(previous_chapters), 1):
                chapter_content = f"Chapter {chapter.get('chapter_number', i)}: {chapter['content']}"
                chapter_tokens = await asyncio.to_thread(self.estimate_token_count, chapter_content)
                if total_tokens + chapter_tokens > max_history_tokens:
                    break
                chat_history.add_user_message(chapter_content)
                chat_history.add_ai_message("Understood.")
                total_tokens += chapter_tokens

            chain = RunnableWithMessageHistory(
                prompt | self.llm | StrOutputParser(),
                lambda session_id: chat_history,
                input_messages_key="context",
                history_messages_key="chat_history",
            )

            chapter_content = ""
            async for chunk in self._async_generator(chain.stream, {
                "chapter_number": chapter_number,
                "context": context,
                "instructions": instructions,
                "codex_items": codex_items_dict
            }, config={"configurable": {"session_id": f"chapter_{chapter_number}"}},
            ):
                chapter_content += chunk
                yield {"type": "chunk", "content": chunk}

            self.logger.info("Chapter generation completed")
            
            # Extract new codex items after the chapter is generated
            new_codex_items = self.check_and_extract_new_codex_items(chapter_content, codex_items)
            
            # Add new codex items to the knowledge base
            added_codex_items = []
            for item in new_codex_items:
                try:
                    embedding_id = self.add_to_knowledge_base("codex_item", item['description'], {
                        "name": item['name'],
                        "type": item['type'],
                        "subtype": item['subtype'] or "None"  # Use "None" as a string if subtype is None
                    })
                    self.logger.info(f"Added new codex item to knowledge base: {item['name']}")
                    added_codex_items.append(item)
                except Exception as e:
                    self.logger.error(f"Error adding codex item to knowledge base: {str(e)}")
            
            yield {"type": "complete", "content": chapter_content, "new_codex_items": added_codex_items}

        except Exception as e:
            self.logger.error(f"Error in generate_chapter_stream: {e}", exc_info=True)
            yield {"error": str(e)}

    async def _async_generator(self, sync_generator, *args, **kwargs):
        for item in sync_generator(*args, **kwargs):
            yield item

    def _construct_context(self, plot: str, writing_style: str, instructions: Dict[str, Any], 
                           codex_items: Dict[str, str], previous_chapters: List[Dict[str, Any]]) -> str:
        context = f"Plot: {plot}\n\n"
        context += f"Writing Style: {writing_style}\n\n"
        context += "Instructions:\n"
        for key, value in instructions.items():
            context += f"{key}: {value}\n"
        context += "\n"
        
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
        try:
            truncated_previous_chapters = self._truncate_previous_chapters(previous_chapters)
            check_prompt = ChatPromptTemplate.from_template("""
            Analyze the following chapter and provide feedback on its quality, consistency, and adherence to instructions:

            Chapter:
            {chapter}

            Instructions:
            {instructions}

            Previous Chapters:
            {truncated_previous_chapters}

            Provide your analysis in the following JSON format:
            ```json
            {{
              "is_valid": true/false,
              "feedback": "feedback",
              "review": "review",
              "style_guide_adherence": true/false,
              "style_guide_feedback": "feedback",
              "continuity": true/false,
              "continuity_feedback": "feedback",
              "test_results": "results"
            }}
            ```
            """)

            check_chain = check_prompt | self.check_llm | StrOutputParser()
            result = check_chain.invoke({
                "chapter": chapter,
                "instructions": instructions,
                "truncated_previous_chapters": truncated_previous_chapters
            })

            # Log the raw response
            #self.logger.debug(f"Raw validity check response: {result}")
            #self.logger.debug(f"Truncated previous chapters: {truncated_previous_chapters}")
            #self.logger.debug(f"previous_chapters: {previous_chapters}")

            # Strip leading and trailing backticks
            result = result.strip().strip('```json').strip('```')

            if not result.strip():
                self.logger.error("Empty response from validity check.")
                return {"is_valid": False, "feedback": "Empty response from validity check."}

            try:
                # Strip leading and trailing backticks and whitespace
                result = result.strip().strip('```json').strip('```').strip()
                if not result:
                    self.logger.error("Empty response from validity check.")
                    return {"is_valid": False, "feedback": "Empty response from validity check."}

                validity_dict = json.loads(result)
            except json.JSONDecodeError as e:
                self.logger.error(f"Could not parse validity result as JSON: {e}")
                validity_dict = {
                    "is_valid": False,
                    "feedback": "Invalid JSON output from validity check.",
                    "review": "N/A",
                    "style_guide_adherence": False,
                    "style_guide_feedback": "N/A",
                    "continuity": False,
                    "continuity_feedback": "N/A",
                    "test_results": "N/A"
                }

            return validity_dict
        except Exception as e:
            self.logger.error(f"An error occurred in check_chapter: {str(e)}", exc_info=True)
            return {"is_valid": False, "feedback": "An error occurred during validity check."}

    def _extract_section(self, text: str, section_name: str) -> str:
        start = text.find(section_name)
        if start == -1:
            return ""
        start += len(section_name)
        end = text.find("\n", start)
        return text[start:end].strip() if end != -1 else text[start:].strip()

    def extend_chapter(self, chapter: str, instructions: Dict[str, Any], context: str, min_word_count: int) -> str:
        while len(chapter.split()) < min_word_count:
            prompt = ChatPromptTemplate.from_template("""
            Current Chapter: {chapter}
            Instructions:
            {instructions}
            Context: {context}
            Avoid starting with phrases like: "Continuing from where we left off", "Picking up where we left off", "Resuming the story", etc.
            Start the extension seamlessly as if it were part of the original generation.
            Minimum Word Count: {min_word_count}

            The current chapter is below the minimum word count. Extend the chapter further, maintaining consistency with the existing content and instructions.
            """)
            
            chain = prompt | self.llm | StrOutputParser()
            extension = chain.invoke({
                "chapter": chapter,
                "instructions": instructions,
                "context": context,
                "min_word_count": min_word_count
            })
            chapter += " " + extension
        return chapter

    def save_chapter(self, chapter: str, chapter_number: int, chapter_title: str):
        chapter_id = db_instance.create_chapter(chapter_title, chapter, self.user_id)
        self.add_to_knowledge_base("chapter", chapter, {"type": "chapter", "user_id": self.user_id, "chapter_number": chapter_number})
        self.logger.info(f"Chapter {chapter_number} saved to the knowledge base with ID: {chapter_id}")
        return chapter_id

    def save_validity_feedback(self, result: str, chapter_number: int, chapter_id: str):
        chapter_title = f'Chapter {chapter_number}'
        db_instance.save_validity_check(chapter_id, chapter_title, result, self.user_id)
        self.logger.info(f"Validity feedback for Chapter {chapter_number} saved to the database with ID: {chapter_id}")

    def add_to_knowledge_base(self, content_type: str, content: str, metadata: Dict[str, Any]) -> str:
        #self.logger.info(f"Adding {content_type} to knowledge base")
        try:
            # Ensure metadata includes the content type
            metadata['type'] = content_type

            # Add the content to the vector store and get the embedding ID
            embedding_id = self.vector_store.add_to_knowledge_base(content, metadata=metadata)

            #self.logger.info(f"Successfully added {content_type} to knowledge base. Embedding ID: {embedding_id}")
            return embedding_id
        except Exception as e:
            #self.logger.error(f"Error adding {content_type} to knowledge base: {str(e)}")
            raise
    

    def update_or_remove_from_knowledge_base(self, identifier, action, new_content=None, new_metadata=None):
        self.logger.info(f"Performing {action} operation on knowledge base")
        try:
            if isinstance(identifier, str):
                embedding_id = identifier
            elif isinstance(identifier, dict) and 'item_id' in identifier and 'item_type' in identifier:
                embedding_id = self.vector_store.get_embedding_id(identifier['item_id'], identifier['item_type'])
            else:
                raise ValueError("Invalid identifier. Must be embedding_id or dict with item_id and item_type")

            if action == 'delete':
                self.vector_store.delete_from_knowledge_base(embedding_id)
            elif action == 'update':
                if new_content is None and new_metadata is None:
                    raise ValueError("Either new_content or new_metadata must be provided for update action")
                self.vector_store.update_in_knowledge_base(embedding_id, new_content, new_metadata)
            else:
                raise ValueError("Invalid action. Must be 'delete' or 'update'")
            
            self.logger.info(f"Successfully performed {action} operation on embedding ID {embedding_id}")
        except Exception as e:
            self.logger.error(f"Error in update_or_remove_from_knowledge_base: {str(e)}", exc_info=True)
            raise

    def query_knowledge_base(self, query: str, k: int = 5) -> List[Document]:
        return self.vector_store.similarity_search(query, k=k)

    async def generate_with_retrieval(self, query: str, chat_history: List[Dict[str, str]]) -> str:
        self.logger.debug(f"Generating response for query: {query}")
        qa_llm = self._initialize_llm(self.model_settings['knowledgeBaseQueryLLM'])
        retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})
        
        # Create a history-aware retriever
        condense_question_prompt = ChatPromptTemplate.from_messages([
            ("system", "Given a chat history and the latest user question which might reference context in the chat history, formulate a standalone question which can be understood without the chat history. Do NOT answer the question, just reformulate it if needed and otherwise return it as is."),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])
        history_aware_retriever = create_history_aware_retriever(qa_llm, retriever, condense_question_prompt)

        # Create the QA chain
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question. If you don't know the answer, say that you don't know. Use three sentences maximum and keep the answer concise."),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            ("human", "Context: {context}"),
        ])
        qa_chain = create_stuff_documents_chain(qa_llm, qa_prompt)

        # Create the retrieval chain
        retrieval_chain = create_retrieval_chain(history_aware_retriever, qa_chain)

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

        # Invoke the chain
        result = await retrieval_chain.ainvoke({
            "input": query,
            "chat_history": messages
        })

        answer = result['answer']
        source_documents = result.get('source_documents', [])

        self.logger.info(f"Generated response. Number of source documents: {len(source_documents)}")

        # Format the response with source information
        response = f"{answer}\n\nSources:\n"
        for i, doc in enumerate(source_documents, 1):
            response += f"{i}. {doc.metadata.get('source', 'Unknown source')}\n"

        return response

    def _construct_query_context(self, relevant_docs: List[Document]) -> str:
        context = "\n".join([doc.page_content for doc in relevant_docs])
        
        # Add codex items information
        codex_items = db_instance.get_all_codex_items(self.user_id)
        if codex_items:
            context += "\n\nCodex Items:\n"
            for codex_item in codex_items:
                context += f"{codex_item['name']}: {codex_item['description']}\n"
        
        # Add chapters information (you might want to limit this to avoid token limits)
        chapters = db_instance.get_all_chapters(self.user_id)
        if chapters:
            context += "\n\nChapters:\n"
            for chapter in chapters:
                context += f"Chapter {chapter['id']}: {chapter['title']}\n"
        
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

    def _construct_prompt(self, instructions: Dict[str, Any], context: str) -> ChatPromptTemplate:
        template = """
        You are a skilled author tasked with writing a chapter for a novel. Use the following context and instructions to generate the chapter:

        Context:
        {context}

        Instructions:
        {instructions}

        Write Chapter {chapter_number} of the novel. Be creative, engaging, and consistent with the provided context and previous chapters.
        Ensure that the chapter follows the plot points, incorporates the codex items and settings, 
        adheres to the specified writing style, and maintains continuity with previous chapters.
        Avoid starting with phrases like: "Continuing from where we left off", "Picking up where we left off", "Resuming the story", etc.
        Start the chapter seamlessly as if it were part of the original generation. Do not add the chapter title at all
        """
        return ChatPromptTemplate.from_template(template)


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
        self.logger.debug(f"Generating title for chapter {chapter_number}")
        try:
            title_llm = self._initialize_llm(self.model_settings['titleGenerationLLM'])
            prompt = ChatPromptTemplate.from_template("""
            Based on the following chapter content, generate a short, engaging title, but please only generate 1 title based on the chapter, 
            use this format Chapter {chapter_number}: <Title>, do not respond with anything else, nothing more nothing less.

            Chapter Content:
            {chapter}

            Title:
            """)
            
            chain = prompt | title_llm | StrOutputParser()
            title = await chain.ainvoke({"chapter": chapter_content[:1000], "chapter_number": chapter_number})
            self.logger.debug(f"Generated title: {title}")
            return title
        except Exception as e:
            self.logger.error(f"Error generating title: {str(e)}")
            return f"Chapter {chapter_number}"

    def get_knowledge_base_content(self):
        return self.vector_store.get_knowledge_base_content()

    def reset_memory(self):
        self.chat_history = []
        db_instance.delete_chat_history(self.user_id)
        self.logger.info("Chat history has been reset.")

    def check_and_extract_new_codex_items(self, chapter: str, codex_items: List[Dict[str, str]]) -> List[Dict[str, str]]:
        codex_item_names = [item['name'] for item in codex_items]
        
        parser = PydanticOutputParser(pydantic_object=CodexExtraction)
        fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=self._initialize_llm(self.model_settings['CodexExtractionLLM']))
        
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

        extraction_chain = prompt | self._initialize_llm(self.model_settings['CodexExtractionLLM']) | fixing_parser

        try:
            result = extraction_chain.invoke({
                "chapter": chapter,
                "codex_items": ", ".join(codex_item_names),
                "format_instructions": parser.get_format_instructions()
            })

            if result is None or not isinstance(result, CodexExtraction):
                self.logger.warning("Invalid result from extraction_chain.invoke. Returning an empty list.")
                return []

            self.logger.debug(f"check_and_extract_new_codex_items returned: {result}")

            new_codex_items = result.new_items
            
            if not new_codex_items:
                self.logger.warning("No new codex items were extracted. This might be correct, or there might be an issue with codex item extraction.")
            
            # Convert CodexItem objects to dictionaries
            new_codex_items_dicts = [{"name": item.name, "description": item.description, "type": item.type, "subtype": item.subtype} for item in new_codex_items]
            
            return new_codex_items_dicts

        except Exception as e:
            self.logger.error(f"Error in check_and_extract_new_codex_items: {str(e)}")
            return []
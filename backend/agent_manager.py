# backend/agent_manager.py
import os
from typing import Dict, Any, List, Tuple, Optional
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain.schema import StrOutputParser
from langchain.schema.runnable import Runnable
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.chains import LLMChain
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
import logging
import uuid
from database import db, db_instance
from pydantic import BaseModel  # Ensure you import directly from pydantic
import json
# Load environment variables
load_dotenv()
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from vector_store import VectorStore

class AgentManager:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.api_key = self._get_api_key()
        self.model_settings = self._get_model_settings()
        self.llm = self._initialize_llm(self.model_settings['mainLLM'])
        self.check_llm = self._initialize_llm(self.model_settings['checkLLM'])
        self.vector_store = VectorStore(self.user_id, self.api_key, self.model_settings['embeddingsModel'])
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.MAX_INPUT_TOKENS = 2097152 if 'pro' in self.model_settings['mainLLM'] else 1048576
        self.MAX_OUTPUT_TOKENS = 8192
        self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        self.chat_history = db_instance.get_chat_history(user_id)
        self.logger.info(f"AgentManager initialized for user: {user_id}")

    def _get_api_key(self) -> str:
        api_key = db_instance.get_api_key(self.user_id)
        if not api_key:
            raise ValueError("API key not set. Please set your API key in the settings.")
        return api_key

    def _get_model_settings(self) -> dict:
        return db_instance.get_model_settings(self.user_id)

    def _initialize_llm(self, model: str) -> ChatGoogleGenerativeAI:
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=self.api_key,
            temperature=0.7,
            streaming=True,
            callback_manager=CallbackManager([StreamingStdOutCallbackHandler()])
        )

    def generate_chapter(self, chapter_number: int, plot: str, writing_style: str, 
                         instructions: Dict[str, Any],
                         previous_chapters: List[Dict[str, Any]],
                         characters: List[Dict[str, Any]]) -> Tuple[str, str, Dict[str, Any]]:
        characters_dict = {char['name']: char['description'] for char in characters}
        context = self._construct_context(plot, writing_style, instructions, characters_dict, previous_chapters)
        prompt = self._construct_prompt(instructions, context)
    
        chat_history = ChatMessageHistory()
        total_tokens = 0
        max_history_tokens = self.MAX_INPUT_TOKENS // 4  # Reserve a quarter of the tokens for chat history
        for i, chapter in enumerate(reversed(previous_chapters), 1):
            chapter_content = f"Chapter {chapter.get('chapter_number', i)}: {chapter['content']}"
            chapter_tokens = self.estimate_token_count(chapter_content)
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

        chapter = chain.invoke(
            {"chapter_number": chapter_number, "context": context, "instructions": instructions, "characters": characters_dict},
            config={"configurable": {"session_id": f"chapter_{chapter_number}"}}
        )
    
        title = self._generate_title(chapter, chapter_number)
        new_characters = self.extract_new_characters(chapter, characters_dict)
    
        min_word_count = instructions.get('min_word_count', 0)
        if len(chapter.split()) < min_word_count:
            chapter = self.extend_chapter(chapter, instructions, context, min_word_count)
        
        chapter_title = instructions.get('chapter_title', f'Chapter {chapter_number}')
        validity = self.check_chapter(chapter, instructions, previous_chapters)
    
        new_characters = self.check_new_characters(chapter, characters_dict)

        return chapter, title, new_characters

    def _construct_context(self, plot: str, writing_style: str, instructions: Dict[str, Any], 
                           characters: Dict[str, str], previous_chapters: List[Dict[str, Any]]) -> str:
        context = f"Plot: {plot}\n\n"
        context += f"Writing Style: {writing_style}\n\n"
        context += "Instructions:\n"
        for key, value in instructions.items():
            context += f"{key}: {value}\n"
        context += "\n"
        
        context += "Characters:\n"
        for name, description in characters.items():
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
                break

            chapters_content = chapter_content + chapters_content
            total_tokens += chapter_tokens

        context += chapters_content

        return context

    def estimate_token_count(self, text: str) -> int:
        # Gemini models use about 4 characters per token
        return len(text) // 4

    def get_embedding(self, text: str) -> List[float]:
        return self.embeddings.embed_query(text)

    def check_chapter(self, chapter: str, instructions: Dict[str, Any], 
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
          #  self.logger.debug(f"Truncated previous chapters: {truncated_previous_chapters}")
           # self.logger.debug(f"previous_chapters: {previous_chapters}")

            # Strip leading and trailing backticks
            result = result.strip().strip('```json').strip('```')

            if not result.strip():
                self.logger.error("Empty response from validity check.")
                return {"is_valid": False, "feedback": "Empty response from validity check."}

            try:
                validity_dict = json.loads(result)
            except json.JSONDecodeError as e:
                self.logger.error(f"Could not parse validity result as JSON: {e}")
                validity_dict = {"is_valid": False, "feedback": "Invalid JSON output from validity check.",
                                 "review": "N/A", "style_guide_adherence": False, "style_guide_feedback": "N/A",
                                 "continuity": False, "continuity_feedback": "N/A", "test_results": "N/A"}

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
        chapter_id = db.create_chapter(chapter_title, chapter, self.user_id)
        self.logger.info(f"Chapter {chapter_number} saved to the database with ID: {chapter_id}")
        return chapter_id

    def save_validity_feedback(self, result: str, chapter_number: int, chapter_id: str):
        chapter_title = f'Chapter {chapter_number}'
        db.save_validity_check(chapter_id, chapter_title, result, self.user_id)
        self.logger.info(f"Validity feedback for Chapter {chapter_number} saved to the database with ID: {chapter_id}")

    def add_to_knowledge_base(self, documents: List[str]):
        for doc in documents:
            self.vector_store.add_to_knowledge_base(doc)
        self.logger.info(f"Added {len(documents)} documents to the knowledge base for user {self.user_id}")

    def query_knowledge_base(self, query: str, k: int = 5) -> List[Document]:
        return self.vector_store.similarity_search(query, k=k)

    def generate_with_retrieval(self, query: str) -> str:
        self.logger.debug(f"Generating response for query: {query}")
        qa_llm = self._initialize_llm(self.model_settings['knowledgeBaseQueryLLM'])
        retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})
        
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="answer"
        )
        
        qa_chain = ConversationalRetrievalChain.from_llm(
            llm=qa_llm,
            retriever=retriever,
            memory=memory,
            return_source_documents=True,
            combine_docs_chain_kwargs={"prompt": self._get_qa_prompt()},
            chain_type="stuff",
        )
        
        self.logger.debug("Invoking ConversationalRetrievalChain")
        result = qa_chain.invoke({"question": query})
        
        answer = result['answer']
        source_documents = result['source_documents']
        
        self.logger.info(f"Generated response. Number of source documents: {len(source_documents)}")
        
        # Format the response with source information
        response = f"{answer}\n\nSources:\n"
        for i, doc in enumerate(source_documents, 1):
            response += f"{i}. {doc.metadata.get('source', 'Unknown source')}\n"
        
        # Update chat history
        self.chat_history.append({"role": "user", "content": query})
        self.chat_history.append({"role": "assistant", "content": answer})
        db_instance.save_chat_history(self.user_id, self.chat_history)
        
        return response

    def _get_qa_prompt(self):
        template = """Use the following pieces of context to answer the human's question. 
        If you don't know the answer, just say that you don't know, don't try to make up an answer.
        
        Context:
        {context}
        
        Human: {question}
        AI: """
        return PromptTemplate(
            template=template, input_variables=["context", "question"]
        )

    def _construct_query_context(self, relevant_docs: List[Document]) -> str:
        context = "\n".join([doc.page_content for doc in relevant_docs])
        
        # Add characters information
        characters = db_instance.get_all_characters(self.user_id)
        if characters:
            context += "\n\nCharacters:\n"
            for character in characters:
                context += f"{character['name']}: {character['description']}\n"
        
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
        Ensure that the chapter follows the plot points, incorporates the characters and settings, 
        adheres to the specified writing style, and maintains continuity with previous chapters.
        Avoid starting with phrases like: "Continuing from where we left off", "Picking up where we left off", "Resuming the story", etc.
        Start the chapter seamlessly as if it were part of the original generation. Do not add the chapter title at all
        """
        return ChatPromptTemplate.from_template(template)

    def check_new_characters(self, chapter: str, characters: Dict[str, str]) -> Dict[str, str]:
        character_names = list(characters.keys())
        prompt = ChatPromptTemplate.from_template("""
        Analyze the following chapter and check for any new characters based on the provided list:
        
        Chapter:
        {chapter}
        
        Existing Characters:
        {characters}
        
        Are there any new characters introduced in this chapter? Respond with "Yes" or "No".
        """)

        check_chain = prompt | self.llm | StrOutputParser()
        result = check_chain.invoke({
            "chapter": chapter,
            "characters": ", ".join(character_names)
        })

        new_characters = {}
        if "Yes" in result:
            # Extract new character information (this part can be enhanced based on your needs)
            new_characters = self.extract_new_characters(chapter, characters)

        return new_characters

    def extract_new_characters(self, chapter: str, existing_characters: Dict[str, str]) -> Dict[str, str]:
        extraction_llm = self._initialize_llm(self.model_settings['characterExtractionLLM'])
        existing_names = set(existing_characters.keys())
        
        prompt = ChatPromptTemplate.from_template("""
        Analyze the following chapter and extract any new characters that are not in the provided list. 
        For each new character, provide their name and a brief description in the following JSON format:

        ```json
        {{
"character_name": "description",
"character_name": "description"
        }}
        ```

        Chapter:
        {chapter}

        Existing Characters:
        {existing_characters}

        New Characters:
        """)

        extraction_chain = prompt | extraction_llm | StrOutputParser()
        result = extraction_chain.invoke({
            "chapter": chapter,
            "existing_characters": ", ".join(existing_names)
        })
            # Log the raw response
        #self.logger.debug(f"Raw new characters response: {result}")

        # Strip leading and trailing backticks
        result = result.strip().strip('```json').strip('```')

        if not result.strip():
            self.logger.error("Empty response from new characters check.")
            return {}

        new_characters = {}
        try:
            new_characters = json.loads(result)
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding JSON: {e}")
            # Handle the error appropriately, e.g., log it or return an empty dictionary

        return new_characters

    def _truncate_previous_chapters(self, previous_chapters: List[Dict[str, Any]]) -> str:
        truncated = ""
        total_tokens = 0
        max_tokens = self.MAX_INPUT_TOKENS // 4  # Reserve a quarter of the tokens for previous chapters
        for i, chapter in enumerate(reversed(previous_chapters), 1):
            chapter_num = chapter.get('chapter_number', i)  # Use index as fallback
            chapter_content = f"Chapter {chapter_num}: {chapter['content']}\n"
            chapter_tokens = self.estimate_token_count(chapter_content)
            if total_tokens + chapter_tokens > max_tokens:
                break
            truncated = chapter_content + truncated
            total_tokens += chapter_tokens
        return truncated

    def _generate_title(self, chapter: str, chapter_number: int) -> str:
        title_llm = self._initialize_llm(self.model_settings['titleGenerationLLM'])
        prompt = ChatPromptTemplate.from_template("""
        Based on the following chapter content, generate a short, engaging title, but please only generate 1 title based on the chapter, 
        use this format Chapter {chapter_number}: <Title>, do not respond with anything else, nothing more nothing less.

        Chapter Content:
        {chapter}

        Title:
        """)
        
        chain = prompt | title_llm | StrOutputParser()
        return chain.invoke({"chapter": chapter[:1000], "chapter_number": chapter_number})  # Use first 1000 characters to generate title

    def add_character_to_knowledge_base(self, character: Dict[str, Any]):
        text = f"Character: {character['name']}\nDescription: {character['description']}"
        self.add_to_knowledge_base([text])

    def add_chapter_to_knowledge_base(self, chapter: Dict[str, Any]):
        text = f"Chapter {chapter['id']}: {chapter['title']}\n{chapter['content']}"
        self.logger.debug(f"Adding chapter to knowledge base for user {self.user_id}: {text[:100]}...")  # Log first 100 characters
        self.vector_store.add_to_knowledge_base(text, metadata={"type": "Chapter", "id": chapter['id']})
        self.logger.info(f"Added chapter {chapter['id']} to knowledge base for user {self.user_id}")
        # Verify the addition
        content = self.vector_store.get_knowledge_base_content()
        self.logger.info(f"Current knowledge base content after adding chapter for user {self.user_id}: {content}")

    def remove_from_knowledge_base(self, text: str):
        self.vector_store.delete_from_knowledge_base(text)

    def remove_character_from_knowledge_base(self, character: Dict[str, Any]):
        text = f"Character: {character['name']}"
        self.remove_from_knowledge_base(text)

    def remove_chapter_from_knowledge_base(self, chapter: Dict[str, Any]):
        text = f"Chapter {chapter['id']}: {chapter['title']}"
        self.remove_from_knowledge_base(text)

    def get_knowledge_base_content(self):
        return self.vector_store.get_knowledge_base_content()

    def reset_memory(self):
        self.chat_history = []
        db_instance.save_chat_history(self.user_id, self.chat_history)

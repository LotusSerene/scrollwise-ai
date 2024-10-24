import asyncio  # Add this import at the top
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.docstore.document import Document
from typing import List, Dict, Any
import os
import logging
from chromadb.config import Settings
import chromadb

def flatten_metadata(metadata):
    flattened = {}
    for key, value in metadata.items():
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                flattened[f"{key}_{subkey}"] = subvalue
        else:
            flattened[key] = value
    return flattened


class VectorStore:
    def __init__(self, user_id, project_id, api_key, embeddings_model):
        self.chroma_url = os.getenv("CHROMA_SERVER_URL", "http://localhost:8000")
        self.chroma_port = int(os.getenv("CHROMA_SERVER_PORT", "8000"))
        self.user_id = user_id
        self.project_id = project_id
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        
        #self.logger.debug(f"Initializing VectorStore for user: {user_id}")
        
        try:
            #self.logger.debug("Initializing GoogleGenerativeAIEmbeddings")
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model=embeddings_model, google_api_key=self.api_key
            )
            #self.logger.debug("GoogleGenerativeAIEmbeddings initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing GoogleGenerativeAIEmbeddings: {str(e)}")
            raise

        try:
            #self.logger.debug("Initializing Chroma client")
            chroma_client = chromadb.HttpClient(host=self.chroma_url, port=self.chroma_port, settings=Settings(anonymized_telemetry=False))
            #self.logger.debug("Chroma client initialized successfully")
            
            #self.logger.debug("Initializing Chroma vector store")
            collection_name = f"user_{user_id[:8]}_project_{project_id[:8]}"
            self.vector_store = Chroma(
                client=chroma_client,
                collection_name=collection_name,
                embedding_function=self.embeddings,
            )
            #self.logger.debug("Chroma vector store initialized successfully")
            #self.logger.info(f"Vector store initialized for user: {user_id} and project: {project_id}")
        except Exception as e:
            self.logger.error(f"Error initializing Chroma vector store: {str(e)}")
            raise

        #self.logger.info(
        #    f"VectorStore initialized for user: {user_id} with embeddings model: {embeddings_model}"
        #)

    async def add_to_knowledge_base(self, text: str, metadata: Dict[str, Any] = None) -> str:
        if metadata is None:
            metadata = {}
        metadata["user_id"] = self.user_id
        metadata["project_id"] = self.project_id
        
        try:
            loop = asyncio.get_running_loop()
            ids = await loop.run_in_executor(None, self.vector_store.add_texts, [text], [metadata])
            embedding_id = ids[0]
            return embedding_id
        except Exception as e:
            self.logger.error(f"Error adding content to knowledge base: {str(e)}", exc_info=True)
            raise

    async def delete_from_knowledge_base(self, embedding_id: str):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self.vector_store._collection.delete(ids=[embedding_id]))

    async def update_in_knowledge_base(self, embedding_id: str, new_content: str = None, new_metadata: Dict[str, Any] = None):
        try:
            if new_content or new_metadata:
                loop = asyncio.get_running_loop()
                
                # Fetch the current metadata
                current_metadata = await loop.run_in_executor(None, lambda: self.vector_store._collection.get(ids=[embedding_id]))
                current_metadata = current_metadata['metadatas'][0]
                
                if new_metadata is None:
                    new_metadata = {}
                new_metadata["user_id"] = self.user_id
                new_metadata["project_id"] = self.project_id

                # Update the current metadata with new values, removing keys if the new value is None
                for key, value in new_metadata.items():
                    if value is None:
                        current_metadata.pop(key, None)  # Remove the key if it exists
                    else:
                        current_metadata[key] = value

                # If new content is provided, compute new embeddings
                if new_content:
                    new_embeddings = await loop.run_in_executor(None, self.embeddings.embed_documents, [new_content])
                else:
                    new_embeddings = None

                # Update the existing embedding in Chroma
                await loop.run_in_executor(
                    None,
                    lambda: self.vector_store._collection.update(
                        ids=[embedding_id],
                        embeddings=new_embeddings[0] if new_embeddings else None,
                        documents=[new_content] if new_content else None,
                        metadatas=[current_metadata]
                    )
                )

                #self.logger.info(f"Updated content... Embedding ID: {embedding_id}")
            else:
                self.logger.warning(f"No new content or metadata provided for update. Embedding ID: {embedding_id}")
        except Exception as e:
            self.logger.error(f"Error updating embedding ID: {embedding_id}. Error: {str(e)}")
            raise

    async def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            self.vector_store.similarity_search,
            query,
            k,
            {"user_id": self.user_id, "project_id": self.project_id}
        )
        return results

    async def get_knowledge_base_content(self) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        collection = self.vector_store._collection
        if collection is None:
            self.logger.warning(f"No collection found for user {self.user_id}")
            return []

        try:
            all_docs = await loop.run_in_executor(
                None, 
                lambda: collection.get(where={"user_id": self.user_id})
            )
            content = []
            for i, doc_id in enumerate(all_docs["ids"]):
                metadata = all_docs["metadatas"][i] if all_docs["metadatas"] else {}
                page_content = all_docs["documents"][i] if all_docs["documents"] else ""
                content.append(
                    {
                        "id": doc_id,  # This is the embedding ID
                        "metadata": metadata,
                        "page_content": page_content,
                    }
                )

            return content if content else []
        except Exception as e:
            self.logger.error(f"Error in get_knowledge_base_content: {str(e)}")
            return []

    def _get_type(self, doc: Any) -> str:
        if isinstance(doc, Document):
            return doc.metadata.get("type", "Unknown")
        elif isinstance(doc, dict):
            return doc.get("metadata", {}).get("type", "Unknown")
        else:
            return "Unknown"

    def _get_content(self, doc: Any) -> str:
        if isinstance(doc, Document):
            return doc.page_content
        elif isinstance(doc, dict):
            return doc.get("page_content", str(doc))
        else:
            return str(doc)

    def _get_metadata(self, doc: Any) -> Dict[str, Any]:
        if isinstance(doc, Document):
            return doc.metadata
        elif isinstance(doc, dict):
            return doc.get("metadata", {})
        else:
            return {}

    def as_retriever(self, search_kwargs: Dict[str, Any] = None):
        if search_kwargs is None:
            search_kwargs = {"k": 5}
        return self.vector_store.as_retriever(search_kwargs=search_kwargs)

    async def update_document(
        self, doc_id: str, new_content: str, metadata: Dict[str, Any] = None
    ):
        loop = asyncio.get_running_loop()
        if metadata is None:
            metadata = {}
        await loop.run_in_executor(
            None,
            self.vector_store.update_document,
            doc_id,
            Document(page_content=new_content, metadata=metadata)
        )

    async def clear(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.vector_store.delete_collection)
        self.vector_store = Chroma(
            client=self.vector_store._client,
            collection_name=f"user_{self.user_id}_project_{self.project_id}",
            embedding_function=self.embeddings,
        )

    async def get_document_by_id(self, doc_id: str) -> Document:
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, self.vector_store.get, [doc_id])
        if results and results["documents"]:
            return Document(
                page_content=results["documents"][0], metadata=results["metadatas"][0]
            )
        return None

    async def add_texts(
        self, texts: List[str], metadatas: List[Dict[str, Any]] = None
    ) -> List[str]:
        if metadatas is None:
            metadatas = [{}] * len(texts)
        for metadata in metadatas:
            metadata["user_id"] = self.user_id
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.vector_store.add_texts, texts, metadatas)

    def close(self):
        # Perform any necessary cleanup
        if hasattr(self, '_client') and hasattr(self._client, 'close'):
            self._client.close()
        # Add any other cleanup steps here


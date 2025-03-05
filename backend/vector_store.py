import asyncio 
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.docstore.document import Document
from typing import List, Dict, Any, Optional
import logging
from chromadb.config import Settings
import chromadb
import json
from datetime import datetime
import os
from pathlib import Path

# Constants for Chroma configuration
CHROMA_HOST = "localhost"
CHROMA_PORT = 8000
CHROMA_URL = f"http://{CHROMA_HOST}:{CHROMA_PORT}"

class ChromaEmbeddingFunction:
    def __init__(self, embeddings_model):
        self.embeddings = embeddings_model

    def __call__(self, input: List[str]) -> List[List[float]]:
        """Generates embeddings for a list of texts."""
        # Handle single string input
        if isinstance(input, str):
            input = [input]
        return self.embeddings.embed_documents(input)

    # Add embed_documents method to maintain compatibility with LangChain
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a list of texts."""
        return self.embeddings.embed_documents(texts)
        
    # Add the missing embed_query method
    def embed_query(self, text: str) -> List[float]:
        """Generates an embedding for a single query text."""
        # Use embed_documents and take the first result
        result = self.embeddings.embed_documents([text])
        return result[0] if result else []

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
        self.chroma_url = CHROMA_URL
        self.host = CHROMA_HOST
        self.chroma_port = CHROMA_PORT
        self.user_id = user_id
        self.project_id = project_id
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.llm = None
        
        try:
            self.logger.debug("Initializing embeddings model...")
            base_embeddings = GoogleGenerativeAIEmbeddings(
                model=embeddings_model, google_api_key=self.api_key
            )
            self.embeddings = ChromaEmbeddingFunction(base_embeddings)
            self.logger.debug("Embeddings model initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing GoogleGenerativeAIEmbeddings: {str(e)}")
            raise

        try:
            self.logger.debug("Creating Chroma client...")
            chroma_client = chromadb.PersistentClient(
                path="./chroma_db",
                settings=Settings(
                    anonymized_telemetry=False,
                    is_persistent=True,
                    persist_directory="./chroma_db",
                    allow_reset=True
                )
            )
            self.logger.debug("Chroma client created successfully")
            
            collection_name = f"user_{user_id[:8]}_project_{project_id[:8]}"
            self.logger.debug(f"Setting up collection: {collection_name}")
            
            # Get or create collection
            try:
                self.logger.debug("Attempting to get existing collection...")
                collection = chroma_client.get_collection(
                    name=collection_name,
                    embedding_function=self.embeddings
                )
                self.logger.debug("Successfully retrieved existing collection")
            except Exception as collection_e:
                self.logger.debug(f"Collection not found, creating new one: {str(collection_e)}")
                try:
                    # Only delete if we can't get the collection AND it exists
                    try:
                        existing = chroma_client.get_collection(name=collection_name)
                        if not existing._embedding_function:
                            self.logger.debug("Found collection without embedding function, recreating...")
                            chroma_client.delete_collection(name=collection_name)
                            self.logger.debug(f"Deleted corrupted collection: {collection_name}")
                    except Exception:
                        self.logger.debug("No existing collection found")
                    
                    # Create new collection
                    collection = chroma_client.create_collection(
                        name=collection_name,
                        embedding_function=self.embeddings,
                        metadata={"user_id": user_id, "project_id": project_id}
                    )
                    self.logger.debug("New collection created successfully")
                except Exception as create_e:
                    self.logger.error(f"Error creating collection: {str(create_e)}")
                    raise

            self.logger.debug("Initializing Chroma vector store...")
            self.vector_store = Chroma(
                client=chroma_client,
                collection_name=collection_name,
                embedding_function=self.embeddings,
                persist_directory="./chroma_db"
            )
            
            # Verify collection initialization
            if not self.vector_store._collection:
                self.logger.error("Collection not properly initialized in vector store")
                raise ValueError("Failed to initialize Chroma collection in vector store")
            
            # Try to perform a simple operation to verify the collection is working
            self.logger.debug("Verifying collection functionality...")
            try:
                count = len(self.vector_store._collection.get()['ids'])
                self.logger.debug(f"Collection verification successful. Current document count: {count}")
                if count == 0:
                    self.logger.warning("Collection is empty - this might indicate data loss")
            except Exception as verify_e:
                self.logger.error(f"Collection verification failed: {str(verify_e)}")
                raise
                
            self.logger.info(f"Successfully initialized vector store with collection: {collection_name}")
            
        except Exception as e:
            self.logger.error(f"Error initializing Chroma vector store: {str(e)}", exc_info=True)
            # Try to clean up if initialization failed
            try:
                if hasattr(self, 'vector_store') and hasattr(self.vector_store, '_client'):
                    self.vector_store._client.persist()
                    self.vector_store._client.close()
            except:
                pass
            raise

        self.backup_dir = Path("./vector_store_backups")
        self.backup_dir.mkdir(exist_ok=True)
        self.backup_file = self.backup_dir / f"backup_{user_id[:8]}_{project_id[:8]}.json"

    async def _backup_item(self, content: str, metadata: Dict[str, Any], embedding_id: str):
        """Backup a single item to the backup file."""
        try:
            # Create backup entry
            backup_entry = {
                "content": content,
                "metadata": metadata,
                "embedding_id": embedding_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Load existing backups
            existing_backups = []
            if self.backup_file.exists():
                try:
                    with open(self.backup_file, 'r', encoding='utf-8') as f:
                        existing_backups = json.load(f)
                except json.JSONDecodeError:
                    self.logger.warning(f"Corrupted backup file found, creating new backup")
                    existing_backups = []

            # Add new entry
            existing_backups.append(backup_entry)
            
            # Save updated backups
            with open(self.backup_file, 'w', encoding='utf-8') as f:
                json.dump(existing_backups, f, ensure_ascii=False, indent=2)
                
            self.logger.debug(f"Backed up item with ID: {embedding_id}")
            
        except Exception as e:
            self.logger.error(f"Error backing up item: {str(e)}")
            # Don't raise the error as backup failure shouldn't stop the main operation

    async def add_to_knowledge_base(self, text: str, metadata: Dict[str, Any] = None) -> str:
        """Add single text to the vector store."""
        try:
            # Add to vector store
            ids = await self.add_texts([text], [metadata] if metadata is not None else None)
            embedding_id = ids[0]
            
            # Backup the item
            await self._backup_item(text, metadata, embedding_id)
            
            return embedding_id
        except Exception as e:
            self.logger.error(f"Error adding to knowledge base: {str(e)}")
            raise

    async def delete_from_knowledge_base(self, embedding_id: str):
        try:
            self.logger.info(f"Attempting to delete embedding ID: {embedding_id}")
            
            # First, try to get the document to verify it exists
            collection = self.vector_store._collection
            if collection is None:
                self.logger.error(f"No collection found when trying to delete embedding ID: {embedding_id}")
                return
            
            self.logger.debug(f"Got collection reference. Collection name: {collection.name}")
            
            # Check if the document exists before deletion
            self.logger.debug(f"Checking if document exists with ID: {embedding_id}")
            doc_check = None
            try:
                doc_check = await asyncio.get_running_loop().run_in_executor(
                    None, lambda: collection.get(ids=[embedding_id])
                )
                self.logger.debug(f"Document check result: {doc_check}")
            except Exception as inner_e:
                self.logger.error(f"Error checking document existence: {str(inner_e)}", exc_info=True)
                raise
            
            if not doc_check or not doc_check['ids']:
                self.logger.warning(f"Document with embedding ID {embedding_id} not found in collection")
                return
                
            self.logger.debug(f"Found document to delete. Metadata: {doc_check['metadatas'][0] if doc_check['metadatas'] else 'None'}")
            
            # Proceed with deletion
            self.logger.debug(f"Attempting to execute delete operation for ID: {embedding_id}")
            try:
                await asyncio.get_running_loop().run_in_executor(
                    None, lambda: collection.delete(ids=[embedding_id])
                )
                self.logger.debug(f"Delete operation executed successfully")
                
                # Persist changes after deletion
                if hasattr(self.vector_store, '_client') and hasattr(self.vector_store._client, 'persist'):
                    await asyncio.get_running_loop().run_in_executor(
                        None, self.vector_store._client.persist
                    )
                    self.logger.debug("Changes persisted to disk")
                
            except Exception as delete_e:
                self.logger.error(f"Error during delete operation: {str(delete_e)}", exc_info=True)
                self.logger.error(f"Delete error type: {type(delete_e).__name__}")
                self.logger.error(f"Delete error args: {delete_e.args}")
                raise
            
            self.logger.info(f"Successfully deleted embedding ID: {embedding_id}")
        except Exception as e:
            self.logger.error(f"Error deleting embedding ID {embedding_id}: {str(e)}", exc_info=True)
            self.logger.error(f"Error type: {type(e).__name__}")
            self.logger.error(f"Error args: {e.args}")
            return None

    async def update_in_knowledge_base(self, doc_id: str, new_content: str = None, new_metadata: Dict[str, Any] = None):
        """Single unified method for updating documents."""
        try:
            if not (new_content or new_metadata):
                self.logger.warning(f"No new content or metadata provided for update. Doc ID: {doc_id}")
                return

            loop = asyncio.get_running_loop()
            
            # Fetch current metadata
            current_metadata = await loop.run_in_executor(None, lambda: self.vector_store._collection.get(ids=[doc_id]))
            current_metadata = current_metadata['metadatas'][0]
            
            # Update metadata
            if new_metadata:
                new_metadata["user_id"] = self.user_id
                new_metadata["project_id"] = self.project_id
                for key, value in new_metadata.items():
                    if value is None:
                        current_metadata.pop(key, None)
                    else:
                        current_metadata[key] = value

            # Compute new embeddings if content changed
            new_embeddings = await loop.run_in_executor(None, self.embeddings.embed_documents, [new_content]) if new_content else None

            # Update document
            await loop.run_in_executor(
                None,
                lambda: self.vector_store._collection.update(
                    ids=[doc_id],
                    embeddings=new_embeddings[0] if new_embeddings else None,
                    documents=[new_content] if new_content else None,
                    metadatas=[current_metadata]
                )
            )
        except Exception as e:
            self.logger.error(f"Error updating doc ID: {doc_id}. Error: {str(e)}")
            raise

    async def similarity_search(self, query_text: str, k: int = 4, filter: Dict[str, Any] = None) -> List[Document]:
        try:
            loop = asyncio.get_running_loop()

            # Prepare the base filter with user and project
            combined_filter = {
                "$and": [
                    {"user_id": {"$eq": self.user_id}},
                    {"project_id": {"$eq": self.project_id}}
                ]
            }
            
            # Handle type filtering
            if filter and "type" in filter:
                if isinstance(filter["type"], dict):
                    # Handle $nin operator by converting to $neq if there's only one value
                    if "$nin" in filter["type"] and len(filter["type"]["$nin"]) == 1:
                        combined_filter["$and"].append(
                            {"type": {"$ne": filter["type"]["$nin"][0]}}
                        )
                    # For multiple values, we'll need to use $or with $ne
                    elif "$nin" in filter["type"]:
                        combined_filter["$and"].append({
                            "$or": [
                                {"type": {"$ne": val}} 
                                for val in filter["type"]["$nin"]
                            ]
                        })
                    else:
                        combined_filter["$and"].append({"type": filter["type"]})
                else:
                    combined_filter["$and"].append({"type": {"$eq": filter["type"]}})
            
            # Add any additional filter conditions
            if filter:
                for key, value in filter.items():
                    if key != "type":  # Skip 'type' as it's already handled
                        if isinstance(value, dict):
                            # Handle operators
                            combined_filter["$and"].append({key: value})
                        else:
                            combined_filter["$and"].append({key: {"$eq": value}})

            # Perform the similarity search with relevance scores
            results = await self._search_with_relevance(
                query_text,
                k=k,
                filter=combined_filter
            )

            return results

        except Exception as e:
            self.logger.error(f"Error in similarity_search: {str(e)}")
            raise

    async def _search_with_relevance(self, query: str, k: int, filter: Dict[str, Any]) -> List[Document]:
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            lambda: self.vector_store.similarity_search_with_relevance_scores(
                query,
                k=k,
                filter=filter
            )
        )
        
        # Add relevance scores to metadata
        for doc, score in results:
            doc.metadata['relevance_score'] = score
            
        return [doc for doc, _ in results]

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

    async def update_doc(self, doc_id: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Update a document in the vector store."""
        try:
            self.logger.debug(f"Updating document with ID: {doc_id}")
            
            # Get the existing document to verify it exists
            try:
                result = self.vector_store._collection.get(
                    ids=[doc_id],
                    include=['documents', 'metadatas']
                )
                if not result['ids']:
                    self.logger.warning(f"Document {doc_id} not found in collection")
                    raise ValueError(f"Document {doc_id} not found in collection")
            except Exception as e:
                self.logger.error(f"Error getting existing document: {str(e)}")
                raise

            # Delete the existing document
            try:
                self.vector_store._collection.delete(
                    ids=[doc_id]
                )
                self.logger.debug(f"Deleted existing document: {doc_id}")
            except Exception as e:
                self.logger.error(f"Error deleting existing document: {str(e)}")
                raise

            # Add the updated document with the same ID
            try:
                self.vector_store._collection.add(
                    documents=[content],
                    metadatas=[metadata] if metadata else None,
                    ids=[doc_id]
                )
                self.logger.debug(f"Added updated document with ID: {doc_id}")
                return doc_id
            except Exception as e:
                self.logger.error(f"Error adding updated document: {str(e)}")
                raise

        except Exception as e:
            self.logger.error(f"Error updating doc ID: {doc_id}. Error: {str(e)}")
            raise

    async def update_or_remove_from_knowledge_base(self, doc_id: str, content: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Update or remove a document from the knowledge base."""
        try:
            if content is None:
                # Remove the document
                self.logger.debug(f"Removing document with ID: {doc_id}")
                await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self.vector_store._collection.delete(ids=[doc_id])
                )
                return None
            else:
                # Update the document
                self.logger.debug(f"Updating document with ID: {doc_id}")
                return await self.update_doc(doc_id, content, metadata)
        except Exception as e:
            self.logger.error(f"Error updating/removing doc ID: {doc_id}. Error: {str(e)}")
            raise

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

    async def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]] = None) -> List[str]:
        """Add multiple texts to the vector store."""
        if metadatas is None:
            metadatas = [{}] * len(texts)
        for metadata in metadatas:
            metadata["user_id"] = self.user_id
            metadata["project_id"] = self.project_id
        
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.vector_store.add_texts, texts, metadatas)

    def close(self):
        """Properly close the vector store connections"""
        try:
            if hasattr(self.vector_store, '_client'):
                if hasattr(self.vector_store._client, 'persist'):
                    self.vector_store._client.persist()
                if hasattr(self.vector_store._client, 'close'):
                    self.vector_store._client.close()
        except Exception as e:
            self.logger.error(f"Error closing vector store: {str(e)}")

    async def get_embedding_id(self, item_id: str, item_type: str) -> Optional[str]:
        """
        Get the embedding ID for a given item from the vector store.
        
        Args:
            item_id: The ID of the item
            item_type: The type of the item (e.g., 'event', 'location')
            
        Returns:
            The embedding ID if found, None otherwise
        """
        try:
            # Create filter for the search
            search_filter = {
                "$and": [
                    {"user_id": {"$eq": self.user_id}},
                    {"project_id": {"$eq": self.project_id}},
                    {"id": {"$eq": item_id}},
                    {"type": {"$eq": item_type}}
                ]
            }

            # Get all matching documents
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.vector_store._collection.get(
                    where=search_filter
                )
            )

            # Return the ID of the first matching document if found
            if results and results['ids'] and len(results['ids']) > 0:
                return results['ids'][0]

            return None

        except Exception as e:
            self.logger.error(f"Error getting embedding ID: {str(e)}")
            return None

    def set_llm(self, llm):
        """Set the LLM instance for this vector store."""
        self.llm = llm

    async def reset_knowledge_base(self):
        """Delete and recreate the collection."""
        try:
            collection_name = f"user_{self.user_id[:8]}_project_{self.project_id[:8]}"
            self.logger.info(f"Resetting knowledge base for collection: {collection_name}")
            
            # Load backups before deleting collection
            backups = []
            if self.backup_file.exists():
                try:
                    with open(self.backup_file, 'r', encoding='utf-8') as f:
                        backups = json.load(f)
                except json.JSONDecodeError:
                    self.logger.warning("Corrupted backup file found, proceeding without backups")
                    backups = []
            
            # Delete the collection
            try:
                await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self.vector_store._client.delete_collection(collection_name)
                )
                self.logger.debug("Existing collection deleted successfully")
            except Exception as e:
                self.logger.debug(f"No existing collection to delete or error: {str(e)}")
            
            # Create new collection
            collection = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self.vector_store._client.create_collection(
                    name=collection_name,
                    embedding_function=self.embeddings,
                    metadata={"user_id": self.user_id, "project_id": self.project_id}
                )
            )
            self.logger.debug("New collection created successfully")
            
            # Reinitialize the vector store with the new collection
            self.vector_store = Chroma(
                client=self.vector_store._client,
                collection_name=collection_name,
                embedding_function=self.embeddings,
                persist_directory="./chroma_db"
            )
            self.logger.debug("Vector store reinitialized with new collection")
            
            # Track restored items to prevent duplicates
            restored_items = set()
            
            # Restore from backups
            for backup in backups:
                item_key = self._get_item_key(backup['metadata'])
                if item_key not in restored_items:
                    try:
                        await self.add_texts(
                            [backup['content']], 
                            [backup['metadata']]
                        )
                        restored_items.add(item_key)
                        self.logger.debug(f"Restored item from backup: {item_key}")
                    except Exception as e:
                        self.logger.error(f"Error restoring backup item: {str(e)}")
            
            return restored_items
            
        except Exception as e:
            self.logger.error(f"Error resetting knowledge base: {str(e)}")
            raise

    def _get_item_key(self, metadata: Dict[str, Any]) -> str:
        """Generate a unique key for an item based on its metadata."""
        if metadata.get('id'):
            return f"{metadata.get('type', 'unknown')}_{metadata['id']}"
        elif metadata.get('item_id'):
            return f"{metadata.get('type', 'unknown')}_{metadata['item_id']}"
        else:
            return f"{metadata.get('type', 'unknown')}_{metadata.get('name', 'unnamed')}"





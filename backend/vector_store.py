import asyncio 
from langchain_qdrant import Qdrant
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.docstore.document import Document
from typing import List, Dict, Any, Optional
import logging
import json
from datetime import datetime
import os
from pathlib import Path
import psutil
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from qdrant_client.http.models import Distance, VectorParams, PointStruct, FieldCondition, Filter, MatchValue
import uuid

# Constants for Qdrant configuration - saving locally
QDRANT_PATH = "./qdrant_db"

class QdrantEmbeddingFunction:
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
            self.embeddings = QdrantEmbeddingFunction(base_embeddings)
            self.embedding_size = 768  # Default for Google's text embeddings
            self.logger.debug("Embeddings model initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing GoogleGenerativeAIEmbeddings: {str(e)}")
            raise

        try:
            self.logger.debug("Creating Qdrant client...")
            # Initialize Qdrant with local persistence and telemetry off
            self.collection_name = f"user_{user_id[:8]}_project_{project_id[:8]}"
            self.logger.debug(f"Setting up collection: {self.collection_name}")
            
            # Create local Qdrant client with telemetry disabled
            self.qdrant_client = QdrantClient(
                path=QDRANT_PATH,
                prefer_grpc=False,
                timeout=10.0,
            )
            
            # Check if collection exists or create it
            try:
                collections = self.qdrant_client.get_collections()
                collection_exists = any(c.name == self.collection_name for c in collections.collections)
                
                if not collection_exists:
                    self.logger.debug(f"Collection not found, creating new one: {self.collection_name}")
                    # Create the collection
                    self.qdrant_client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=VectorParams(
                            size=self.embedding_size,
                            distance=Distance.COSINE
                        )
                    )
                else:
                    self.logger.debug(f"Collection already exists: {self.collection_name}")
            except Exception as e:
                self.logger.error(f"Error checking or creating collection: {str(e)}")
                raise
            
            # Initialize Qdrant vector store with LangChain
            self.vector_store = Qdrant(
                client=self.qdrant_client,
                collection_name=self.collection_name,
                embeddings=base_embeddings
            )
            
            # Verify collection initialization by getting count
            try:
                count = self.qdrant_client.count(
                    collection_name=self.collection_name,
                    exact=True
                ).count
                self.logger.debug(f"Collection verification successful. Current document count: {count}")
                if count == 0:
                    self.logger.warning("Collection is empty - this might indicate data loss")
            except Exception as verify_e:
                self.logger.error(f"Collection verification failed: {str(verify_e)}")
                raise
            
            self.logger.info(f"Successfully initialized vector store with collection: {self.collection_name}")
            
        except Exception as e:
            self.logger.error(f"Error initializing Qdrant vector store: {str(e)}", exc_info=True)
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
            
            # Check if point exists before deletion
            try:
                point_exists = await asyncio.get_running_loop().run_in_executor(
                    None, 
                    lambda: self.qdrant_client.retrieve(
                        collection_name=self.collection_name,
                        ids=[embedding_id],
                        with_payload=True
                    )
                )
                if not point_exists:
                    self.logger.warning(f"Document with embedding ID {embedding_id} not found in collection")
                    return
            except Exception as inner_e:
                self.logger.error(f"Error checking document existence: {str(inner_e)}", exc_info=True)
                raise
            
            # Proceed with deletion
            self.logger.debug(f"Attempting to execute delete operation for ID: {embedding_id}")
            try:
                await asyncio.get_running_loop().run_in_executor(
                    None, 
                    lambda: self.qdrant_client.delete(
                        collection_name=self.collection_name,
                        points_selector=[embedding_id]
                    )
                )
                self.logger.debug(f"Delete operation executed successfully")
            except Exception as delete_e:
                self.logger.error(f"Error during delete operation: {str(delete_e)}", exc_info=True)
                raise
            
            self.logger.info(f"Successfully deleted embedding ID: {embedding_id}")
        except Exception as e:
            self.logger.error(f"Error deleting embedding ID {embedding_id}: {str(e)}", exc_info=True)
            return None

    async def update_in_knowledge_base(self, doc_id: str, new_content: str = None, new_metadata: Dict[str, Any] = None):
        """Single unified method for updating documents."""
        try:
            if not (new_content or new_metadata):
                self.logger.warning(f"No new content or metadata provided for update. Doc ID: {doc_id}")
                return

            loop = asyncio.get_running_loop()
            
            # Fetch current payload/metadata
            current_point = await loop.run_in_executor(
                None, 
                lambda: self.qdrant_client.retrieve(
                    collection_name=self.collection_name,
                    ids=[doc_id],
                    with_payload=True
                )
            )
            
            if not current_point:
                self.logger.error(f"Document with ID {doc_id} not found for update")
                return
                
            current_metadata = current_point[0].payload
            
            # Update metadata
            if new_metadata:
                new_metadata["user_id"] = self.user_id
                new_metadata["project_id"] = self.project_id
                for key, value in new_metadata.items():
                    if value is None and key in current_metadata:
                        current_metadata.pop(key, None)
                    else:
                        current_metadata[key] = value

            # Prepare data for update
            update_data = {}
            
            # Add new embedding if content changed
            if new_content:
                # Compute new embeddings
                new_vector = await loop.run_in_executor(
                    None, 
                    lambda: self.embeddings.embed_documents([new_content])[0]
                )
                
                update_data["vectors"] = new_vector
                current_metadata["page_content"] = new_content
            
            # Always update metadata
            update_data["payload"] = current_metadata
            
            # Update point
            await loop.run_in_executor(
                None,
                lambda: self.qdrant_client.update(
                    collection_name=self.collection_name,
                    points=[rest.PointStruct(
                        id=doc_id,
                        **update_data
                    )]
                )
            )
            
        except Exception as e:
            self.logger.error(f"Error updating doc ID: {doc_id}. Error: {str(e)}")
            raise

    async def similarity_search(self, query_text: str, k: int = 4, filter: Dict[str, Any] = None) -> List[Document]:
        try:
            # Add a memory check before performing expensive operations
            mem = psutil.virtual_memory()
            if mem.percent > 90:  # If memory usage is above 90%
                self.logger.warning(f"High memory usage detected: {mem.percent}%. This might cause instability.")
            
            loop = asyncio.get_running_loop()

            # Build Qdrant filter for search
            qdrant_filter = self._build_qdrant_filter(filter)
            
            # Perform the similarity search with relevance scores
            results = await self._search_with_relevance(
                query_text,
                k=k,
                filter=qdrant_filter
            )

            return results

        except Exception as e:
            self.logger.error(f"Error in similarity_search: {str(e)}")
            raise
    
    def _build_qdrant_filter(self, filter_dict: Dict[str, Any] = None) -> Optional[Filter]:
        """Convert API filter dict to Qdrant Filter object"""
        if not filter_dict:
            # Base filter for user and project
            return Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=self.user_id)
                    ),
                    FieldCondition(
                        key="project_id",
                        match=MatchValue(value=self.project_id)
                    )
                ]
            )
        
        # Start with user and project filter conditions
        must_conditions = [
            FieldCondition(key="user_id", match=MatchValue(value=self.user_id)),
            FieldCondition(key="project_id", match=MatchValue(value=self.project_id))
        ]
        
        # Handle special case for type filtering
        if "type" in filter_dict:
            if isinstance(filter_dict["type"], dict):
                # Handle $nin operator by converting to $neq for each value
                if "$nin" in filter_dict["type"]:
                    for val in filter_dict["type"]["$nin"]:
                        must_not_condition = FieldCondition(
                            key="type",
                            match=MatchValue(value=val)
                        )
                        # Add a must_not condition to filter
                        return Filter(
                            must=must_conditions,
                            must_not=[must_not_condition]
                        )
                # Other operators can be handled similarly
            else:
                # Simple equality match
                must_conditions.append(
                    FieldCondition(key="type", match=MatchValue(value=filter_dict["type"]))
                )
        
        # Add any other filter conditions (simplified implementation)
        for key, value in filter_dict.items():
            if key != "type":  # Skip 'type' as it's already handled
                if isinstance(value, dict):
                    # Operators not fully implemented in this basic version
                    pass
                else:
                    must_conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )
        
        return Filter(must=must_conditions)

    async def _search_with_relevance(self, query: str, k: int, filter: Filter) -> List[Document]:
        loop = asyncio.get_running_loop()
        
        # Get embedding for query
        query_vector = await loop.run_in_executor(None, self.embeddings.embed_query, query)
        
        # Search with Qdrant native client for more control
        search_results = await loop.run_in_executor(
            None,
            lambda: self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=k,
                with_payload=True,
                filter=filter
            )
        )
        
        # Convert to Document objects
        documents = []
        for result in search_results:
            # Extract payload/metadata
            payload = result.payload
            page_content = payload.pop("page_content", "")
            
            # Add score to metadata
            payload["relevance_score"] = result.score
            
            # Create Document
            doc = Document(
                page_content=page_content,
                metadata=payload
            )
            documents.append(doc)
            
        return documents

    async def get_knowledge_base_content(self) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        
        try:
            # Get all points in batches (Qdrant typically limits to 100 points per call)
            points = []
            offset = 0
            limit = 100
            
            while True:
                # Use scroll without filter parameter
                batch = await loop.run_in_executor(
                    None,
                    lambda: self.qdrant_client.scroll(
                        collection_name=self.collection_name,
                        limit=limit,
                        offset=offset,
                        with_payload=True
                    )
                )
                
                # Unpack the tuple (points, next_page_offset)
                batch_points, next_offset = batch
                
                if not batch_points:
                    break
                
                points.extend(batch_points)
                
                if next_offset is None:
                    break
                    
                offset = next_offset

            # Filter points manually for user and project
            filtered_points = [
                p for p in points 
                if p.payload.get("user_id") == self.user_id and p.payload.get("project_id") == self.project_id
            ]

            # Convert to required format
            content = []
            for point in filtered_points:
                payload = point.payload
                page_content = payload.pop("page_content", "")
                content.append({
                    "id": point.id,
                    "metadata": payload,
                    "page_content": page_content
                })

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
            
            # Verify document exists
            try:
                point = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self.qdrant_client.retrieve(
                        collection_name=self.collection_name,
                        ids=[doc_id],
                        with_payload=True
                    )
                )
                if not point:
                    self.logger.warning(f"Document {doc_id} not found in collection")
                    raise ValueError(f"Document {doc_id} not found in collection")
            except Exception as e:
                self.logger.error(f"Error getting existing document: {str(e)}")
                raise

            # Generate embeddings for new content
            new_vector = await asyncio.get_running_loop().run_in_executor(
                None, 
                lambda: self.embeddings.embed_documents([content])[0]
            )
            
            # Prepare metadata payload
            if metadata is None:
                metadata = {}
            
            # Make sure page_content is in the payload
            metadata["page_content"] = content
            metadata["user_id"] = self.user_id
            metadata["project_id"] = self.project_id
                
            # Update the point
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=[
                        PointStruct(
                            id=doc_id,
                            vector=new_vector,
                            payload=metadata
                        )
                    ]
                )
            )
            
            self.logger.debug(f"Updated document with ID: {doc_id}")
            return doc_id

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
                    lambda: self.qdrant_client.delete(
                        collection_name=self.collection_name,
                        points_selector=[doc_id]
                    )
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
        """LangChain-compatible update method"""
        if metadata is None:
            metadata = {}
            
        # Store content in metadata for Qdrant
        metadata["page_content"] = new_content
        metadata["user_id"] = self.user_id
        metadata["project_id"] = self.project_id
        
        # Generate new embedding
        new_vector = await asyncio.get_running_loop().run_in_executor(
            None, 
            lambda: self.embeddings.embed_documents([new_content])[0]
        )
        
        # Update the document
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=doc_id,
                        vector=new_vector,
                        payload=metadata
                    )
                ]
            )
        )

    async def clear(self):
        """Clear the collection"""
        loop = asyncio.get_running_loop()
        # Delete and recreate collection
        try:
            await loop.run_in_executor(
                None, 
                lambda: self.qdrant_client.delete_collection(
                    collection_name=self.collection_name
                )
            )
        except Exception as e:
            self.logger.warning(f"Error deleting collection: {str(e)}")
            
        # Recreate collection    
        await loop.run_in_executor(
            None,
            lambda: self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_size,
                    distance=Distance.COSINE
                )
            )
        )

    async def get_document_by_id(self, doc_id: str) -> Document:
        """Get a document by ID"""
        loop = asyncio.get_running_loop()
        
        # Retrieve the point by ID
        points = await loop.run_in_executor(
            None,
            lambda: self.qdrant_client.retrieve(
                collection_name=self.collection_name,
                ids=[doc_id],
                with_payload=True
            )
        )
        
        if not points:
            return None
            
        # Convert to Document
        point = points[0]
        payload = point.payload
        page_content = payload.pop("page_content", "")
        
        return Document(
            page_content=page_content,
            metadata=payload
        )

    async def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]] = None) -> List[str]:
        """Add multiple texts to the vector store."""
        if metadatas is None:
            metadatas = [{}] * len(texts)
        
        # Ensure user_id and project_id in metadata
        for metadata in metadatas:
            metadata["user_id"] = self.user_id
            metadata["project_id"] = self.project_id
        
        # Add batching to prevent memory issues with large numbers of documents
        batch_size = 10  # Process 10 documents at a time
        all_ids = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            batch_metadatas = metadatas[i:i+batch_size]
            
            # Generate UUIDs for this batch instead of custom strings
            batch_ids = [str(uuid.uuid4()) for _ in range(len(batch_texts))]
            
            # Create embeddings
            loop = asyncio.get_running_loop()
            vectors = await loop.run_in_executor(
                None, self.embeddings.embed_documents, batch_texts
            )
            
            # Prepare points for batch upsert
            points = []
            for j, (text, metadata, vector, point_id) in enumerate(
                zip(batch_texts, batch_metadatas, vectors, batch_ids)
            ):
                # Store the text in metadata for Qdrant
                metadata["page_content"] = text
                
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=metadata
                    )
                )
            
            # Upsert the batch
            await loop.run_in_executor(
                None,
                lambda: self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
            )
            
            all_ids.extend(batch_ids)
            
            # Give the event loop a chance to process other tasks
            await asyncio.sleep(0.1)
            
        return all_ids

    def close(self):
        """Properly close the vector store connections"""
        try:
            # Close Qdrant client connection if possible
            if hasattr(self, 'qdrant_client'):
                if hasattr(self.qdrant_client, 'close'):
                    self.qdrant_client.close()
                    
            # Also clean up the embedding model if possible
            if hasattr(self, 'embeddings') and hasattr(self.embeddings, 'embeddings'):
                if hasattr(self.embeddings.embeddings, 'close'):
                    self.embeddings.embeddings.close()
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
            search_filter = Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=self.user_id)),
                    FieldCondition(key="project_id", match=MatchValue(value=self.project_id)),
                    FieldCondition(key="id", match=MatchValue(value=item_id)),
                    FieldCondition(key="type", match=MatchValue(value=item_type))
                ]
            )

            # Get matching points
            loop = asyncio.get_running_loop()
            points = await loop.run_in_executor(
                None,
                lambda: self.qdrant_client.scroll(
                    collection_name=self.collection_name,
                    filter=search_filter,
                    limit=1,
                    with_payload=False
                )
            )
            
            # Unpack the tuple (points, next_page_offset)
            matching_points, _ = points

            # Return the ID of the first matching document if found
            if matching_points and len(matching_points) > 0:
                return str(matching_points[0].id)

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
            self.logger.info(f"Resetting knowledge base for collection: {self.collection_name}")
            
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
                    lambda: self.qdrant_client.delete_collection(collection_name=self.collection_name)
                )
                self.logger.debug("Existing collection deleted successfully")
            except Exception as e:
                self.logger.debug(f"No existing collection to delete or error: {str(e)}")
            
            # Create new collection
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_size,
                        distance=Distance.COSINE
                    )
                )
            )
            self.logger.debug("New collection created successfully")
            
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





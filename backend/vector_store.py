import asyncio

# from langchain_qdrant import Qdrant # Deprecated
from langchain_qdrant import QdrantVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
from typing import List, Dict, Any, Optional
import logging
import json
import os

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    SparseVectorParams,  # Added
    PointStruct,
    FieldCondition,
    Filter,
    MatchValue,
    MatchAny,
    PointIdsList,
)
import uuid
from fastembed import SparseTextEmbedding  # Added


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
        self.embeddings_model = embeddings_model # Store for later use
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.llm = None

        # Initialize Sparse Embedding Model (Qdrant/bm25 is standard/lightweight)
        try:
            self.logger.debug("Initializing SparseTextEmbedding model...")
            self.sparse_embedding_model = SparseTextEmbedding(model_name="Qdrant/bm25")
            self.logger.debug("SparseTextEmbedding model initialized.")
        except Exception as e:
            self.logger.error(f"Error initializing SparseTextEmbedding: {e}")
            raise

        try:
            self.logger.debug("Initializing embeddings model...")
            base_embeddings = GoogleGenerativeAIEmbeddings(
                model=embeddings_model, google_api_key=self.api_key
            )
            self.embeddings = QdrantEmbeddingFunction(base_embeddings)
            self.embedding_size = 3072  # Current Google embedding model dimension
            self.logger.debug(f"Embeddings model initialized successfully with dimension: {self.embedding_size}")
        except Exception as e:
            self.logger.error(
                f"Error initializing GoogleGenerativeAIEmbeddings: {str(e)}"
            )
            raise

        try:
            self.logger.debug("Initializing local Qdrant client...")
            # Use local path for persistent storage
            qdrant_path = "./local_qdrant_storage"
            
            self.collection_name = f"user_{user_id[:8]}_project_{project_id[:8]}"
            self.logger.debug(f"Setting up collection: {self.collection_name}")

            self.qdrant_client = QdrantClient(
                path=qdrant_path
            )
            self.logger.info(f"Local Qdrant client initialized at: {qdrant_path}")
        except Exception as e:
            self.logger.error(f"Error initializing local Qdrant client: {str(e)}")
            raise

            # Check if collection exists or create it
            try:
                collections = self.qdrant_client.get_collections()
                collection_exists = any(
                    c.name == self.collection_name for c in collections.collections
                )

                # Check dimension mismatch AND vector configuration
                if collection_exists:
                    collection_info = self.qdrant_client.get_collection(
                        collection_name=self.collection_name
                    )
                    
                    # Check if it's using named vectors (hybrid config)
                    config_vectors = collection_info.config.params.vectors
                    is_hybrid_config = isinstance(config_vectors, dict) and "dense" in config_vectors
                    
                    # Note: We don't strictly check for "sparse" in vectors_config because it might be in sparse_vectors_config
                    # But for our specific migration from "dense-only" to "hybrid", checking for dict is enough.
                    
                    if not is_hybrid_config:
                         self.logger.warning(
                            f"Collection '{self.collection_name}' exists but is not configured for Hybrid Search. "
                            "Migration required."
                        )
                         self.needs_migration = True
                         # Do NOT delete here. Let AgentManager handle it.

                    elif config_vectors["dense"].size != self.embedding_size:
                        error_msg = (
                            f"Dimension mismatch: Collection '{self.collection_name}' dense vector has {config_vectors['dense'].size} dimensions "
                            f"but current embeddings model produces {self.embedding_size} dimensions.\n"
                            f"Migration required."
                        )
                        self.logger.warning(error_msg)
                        self.needs_migration = True
                    else:
                        self.needs_migration = False
                else:
                    self.needs_migration = False # New collection will be created correctly below

                if not collection_exists:
                    # ... creation logic ...
                    self.logger.debug(
                        f"Collection not found (or deleted), creating new one: {self.collection_name}"
                    )
                    # Create the collection with HYBRID config
                    # Create the collection with HYBRID config
                    self.qdrant_client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config={
                            "dense": VectorParams(
                                size=self.embedding_size, 
                                distance=Distance.COSINE
                            )
                        },
                        sparse_vectors_config={
                            "sparse": SparseVectorParams(
                                index=rest.SparseIndexParams(
                                    on_disk=False,
                                )
                            )
                        }
                    )
                    self.logger.info(f"Collection {self.collection_name} created with Hybrid Search config.")

                    # Create payload index for the 'type' field immediately after collection creation
                    try:
                        self.qdrant_client.create_payload_index(
                            collection_name=self.collection_name,
                            field_name="type",
                            field_schema=rest.PayloadSchemaType.KEYWORD,  # Use KEYWORD for exact matching/filtering
                            wait=True,  # Wait for index creation to complete
                        )
                        self.logger.info(
                            f"Created keyword index for 'type' field in collection {self.collection_name}."
                        )
                        # Create payload index for 'user_id'
                        self.qdrant_client.create_payload_index(
                            collection_name=self.collection_name,
                            field_name="user_id",
                            field_schema=rest.PayloadSchemaType.KEYWORD,
                            wait=True,
                        )
                        self.logger.info(
                            f"Created keyword index for 'user_id' field in collection {self.collection_name}."
                        )
                        # Create payload index for 'project_id'
                        self.qdrant_client.create_payload_index(
                            collection_name=self.collection_name,
                            field_name="project_id",
                            field_schema=rest.PayloadSchemaType.KEYWORD,
                            wait=True,
                        )
                        self.logger.info(
                            f"Created keyword index for 'project_id' field in collection {self.collection_name}."
                        )
                        # Create payload index for 'id' (original item ID)
                        self.qdrant_client.create_payload_index(
                            collection_name=self.collection_name,
                            field_name="id",  # Field to store original DB item ID
                            field_schema=rest.PayloadSchemaType.KEYWORD,
                            wait=True,
                        )
                        self.logger.info(
                            f"Created keyword index for 'id' field in collection {self.collection_name}."
                        )
                    except Exception as index_e:
                        self.logger.error(
                            f"Failed to create payload index for 'type' field: {index_e}",
                            exc_info=True,
                        )
                        # Decide if we should raise here or just log the error
                        raise  # Re-raise for now, as filtering might fail without it

                else:
                    self.logger.debug(
                        f"Collection already exists: {self.collection_name}"
                    )
                    # Dimension check already done above, just verify indexes
                    try:
                        collection_info = self.qdrant_client.get_collection(
                            collection_name=self.collection_name
                        )
                        if "type" not in collection_info.payload_schema:
                            self.logger.warning(
                                f"Index 'type' not found in existing collection {self.collection_name}. Creating it now."
                            )
                            self.qdrant_client.create_payload_index(
                                collection_name=self.collection_name,
                                field_name="type",
                                field_schema=rest.PayloadSchemaType.KEYWORD,
                                wait=True,
                            )
                            self.logger.info(
                                f"Created missing keyword index for 'type' field."
                            )
                        if "user_id" not in collection_info.payload_schema:
                            self.logger.warning(
                                f"Index 'user_id' not found in existing collection {self.collection_name}. Creating it now."
                            )
                            self.qdrant_client.create_payload_index(
                                collection_name=self.collection_name,
                                field_name="user_id",
                                field_schema=rest.PayloadSchemaType.KEYWORD,
                                wait=True,
                            )
                            self.logger.info(
                                f"Created missing keyword index for 'user_id' field."
                            )
                        if "project_id" not in collection_info.payload_schema:
                            self.logger.warning(
                                f"Index 'project_id' not found in existing collection {self.collection_name}. Creating it now."
                            )
                            self.qdrant_client.create_payload_index(
                                collection_name=self.collection_name,
                                field_name="project_id",
                                field_schema=rest.PayloadSchemaType.KEYWORD,
                                wait=True,
                            )
                            self.logger.info(
                                f"Created missing keyword index for 'project_id' field."
                            )
                        if (
                            "id" not in collection_info.payload_schema
                        ):  # Check for "id" index
                            self.logger.warning(
                                f"Index 'id' not found in existing collection {self.collection_name}. Creating it now."
                            )
                            self.qdrant_client.create_payload_index(
                                collection_name=self.collection_name,
                                field_name="id",
                                field_schema=rest.PayloadSchemaType.KEYWORD,
                                wait=True,
                            )
                            self.logger.info(
                                f"Created missing keyword index for 'id' field."
                            )
                    except Exception as check_index_e:
                        self.logger.error(
                            f"Error checking/creating index for existing collection: {check_index_e}",
                            exc_info=True,
                        )
                        # Handle error appropriately, maybe log and continue

            except Exception as e:
                self.logger.error(f"Error checking or creating collection: {str(e)}")
                raise

            # Initialize Qdrant vector store with LangChain
            # self.vector_store = Qdrant( # Deprecated usage
            # Initialize Qdrant vector store with LangChain
            if not getattr(self, "needs_migration", False):
                self.vector_store = QdrantVectorStore(  # Correct usage
                    client=self.qdrant_client,
                    collection_name=self.collection_name,
                    embedding=base_embeddings,  # Correct argument name is 'embedding'
                    vector_name="dense", # Specify the named vector
                )
            else:
                self.logger.info("Skipping QdrantVectorStore initialization due to pending migration.")
                self.vector_store = None

            # Verify collection initialization by getting count
            try:
                count = self.qdrant_client.count(
                    collection_name=self.collection_name, exact=True
                ).count
                self.logger.debug(
                    f"Collection verification successful. Current document count: {count}"
                )
                if count == 0:
                    self.logger.warning(
                        "Collection is empty - this might indicate data loss"
                    )
            except Exception as verify_e:
                self.logger.error(f"Collection verification failed: {str(verify_e)}")
                raise

            self.logger.info(
                f"Successfully initialized vector store with collection: {self.collection_name}"
            )

        except Exception as e:
            self.logger.error(
                f"Error initializing Qdrant vector store: {str(e)}", exc_info=True
            )
            raise

        # Removed backup_dir and backup_file initialization

    # Removed _backup_item method

    async def get_count(self) -> int:
        """Returns the current number of documents in the collection."""
        try:
             # Use run_in_executor for async context
             count = await asyncio.get_running_loop().run_in_executor(
                 None,
                 lambda: self.qdrant_client.count(
                    collection_name=self.collection_name, exact=True
                ).count
             )
             return count
        except:
            return 0

    async def add_to_knowledge_base(
        self, text: str, metadata: Dict[str, Any] = None
    ) -> str:
        """Add single text to the vector store."""
        try:
            # Add to vector store
            ids = await self.add_texts(
                [text], [metadata] if metadata is not None else None
            )
            embedding_id = ids[0]

            # Removed backup call

            return embedding_id
        except Exception as e:
            self.logger.error(f"Error adding to knowledge base: {str(e)}")
            raise

    async def delete_from_knowledge_base(self, embedding_id: str):
        try:
            self.logger.info(f"Attempting to delete embedding ID: {embedding_id}")

            # Check if point exists before deletion
            try:
                points = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self.qdrant_client.retrieve(
                        collection_name=self.collection_name,
                        ids=[embedding_id],
                        with_payload=True,
                    ),
                )
                if not points or len(points) == 0:
                    self.logger.warning(
                        f"Document with embedding ID {embedding_id} not found in collection"
                    )
                    return False  # Return false to indicate deletion was not performed
            except Exception as inner_e:
                self.logger.error(
                    f"Error checking document existence: {str(inner_e)}", exc_info=True
                )
                raise

            # Proceed with deletion
            self.logger.debug(
                f"Attempting to execute delete operation for ID: {embedding_id}"
            )
            try:
                await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self.qdrant_client.delete(
                        collection_name=self.collection_name,
                        points_selector=PointIdsList(points=[embedding_id]),
                        wait=True,  # Ensure deletion completes before returning
                    ),
                )
                self.logger.info(f"Successfully deleted embedding ID: {embedding_id}")
                return True  # Return true to indicate successful deletion
            except Exception as delete_e:
                self.logger.error(
                    f"Error during delete operation: {str(delete_e)}", exc_info=True
                )
                raise

        except Exception as e:
            self.logger.error(
                f"Error deleting embedding ID {embedding_id}: {str(e)}", exc_info=True
            )
            raise  # Re-raise to let caller handle the error

    async def update_in_knowledge_base(
        self, doc_id: str, new_content: str = None, new_metadata: Dict[str, Any] = None
    ):
        """Single unified method for updating documents."""
        try:
            if not (new_content or new_metadata):
                self.logger.warning(
                    f"No new content or metadata provided for update. Doc ID: {doc_id}"
                )
                return

            loop = asyncio.get_running_loop()

            # Prepare update data
            update_data = {}
            current_metadata = {}
            current_vector = None

            # Try to get existing point data
            try:
                points = await loop.run_in_executor(
                    None,
                    lambda: self.qdrant_client.retrieve(
                        collection_name=self.collection_name,
                        ids=[doc_id],
                        with_payload=True,
                        with_vectors=True,  # Also get the existing vector
                    ),
                )
                if points and len(points) > 0:
                    current_metadata = points[0].payload
                    current_vector = points[0].vector
            except Exception as e:
                self.logger.debug(
                    f"Could not retrieve existing point (this is OK for new points): {e}"
                )

            # Update metadata
            if new_metadata:
                new_metadata["user_id"] = self.user_id
                new_metadata["project_id"] = self.project_id
                for key, value in new_metadata.items():
                    if value is None and key in current_metadata:
                        current_metadata.pop(key, None)
                    else:
                        current_metadata[key] = value

            # Get vector - either from new content or use existing
            vector_struct = None
            
            if new_content:
                # Compute new embeddings (DENSE)
                dense_vector = await loop.run_in_executor(
                    None, lambda: self.embeddings.embed_documents([new_content])[0]
                )
                # Compute new embeddings (SPARSE)
                # fastembed returns generator of SparseEmbedding, we need list
                sparse_embedding_gen = await loop.run_in_executor(
                    None, lambda: list(self.sparse_embedding_model.embed([new_content]))
                )
                sparse_vector_data = sparse_embedding_gen[0]
                
                # Construct Hybrid Vector
                vector_struct = {
                    "dense": dense_vector,
                    "sparse": rest.SparseVector(
                        indices=sparse_vector_data.indices.tolist(),
                        values=sparse_vector_data.values.tolist()
                    )
                }
                current_metadata["page_content"] = new_content
                
            elif current_vector is not None:
                # Use existing vector if no new content
                # Warning: If existing vector was old (dense-only), this keeps it old.
                # Ideally we should re-embed if it's not a dict, but for now preserve existing.
                vector_struct = current_vector
                
            else:
                # Fallback: metadata as content
                fallback_text = json.dumps(current_metadata)
                
                dense_vector = await loop.run_in_executor(
                    None, lambda: self.embeddings.embed_documents([fallback_text])[0]
                )
                sparse_embedding_gen = await loop.run_in_executor(
                    None, lambda: list(self.sparse_embedding_model.embed([fallback_text]))
                )
                sparse_vector_data = sparse_embedding_gen[0]
                
                vector_struct = {
                    "dense": dense_vector,
                    "sparse": rest.SparseVector(
                        indices=sparse_vector_data.indices.tolist(),
                        values=sparse_vector_data.values.tolist()
                    )
                }
                self.logger.warning(
                    f"Generated fallback Hybrid vector for doc {doc_id} using metadata as content"
                )

            # Create point with required vector
            point_to_upsert = rest.PointStruct(
                id=doc_id, vector=vector_struct, payload=current_metadata
            )

            # Perform upsert
            await loop.run_in_executor(
                None,
                lambda: self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=[point_to_upsert],
                    wait=True,  # Ensure the operation completes before returning
                ),
            )

            self.logger.info(f"Successfully updated document with ID: {doc_id}")
            return True  # Return success indicator

        except Exception as e:
            self.logger.error(f"Error updating doc ID: {doc_id}. Error: {str(e)}")
            raise

    async def similarity_search(
        self, query_text: str, k: int = 4, filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """Search for similar documents."""
        try:
            # Convert the filter dict to Qdrant's filter format
            qdrant_filter = None
            if filter:
                must_conditions = []
                must_not_conditions = []

                for key, value in filter.items():
                    if isinstance(value, dict):
                        # Handle special operators
                        for op, val in value.items():
                            if op == "$eq":
                                must_conditions.append(
                                    FieldCondition(key=key, match=MatchValue(value=val))
                                )
                            elif op == "$ne":
                                must_not_conditions.append(
                                    FieldCondition(key=key, match=MatchValue(value=val))
                                )
                            elif op == "$in":
                                must_conditions.append(
                                    FieldCondition(key=key, match=MatchAny(any=val))
                                )
                            elif op == "$nin":
                                must_not_conditions.append(
                                    FieldCondition(key=key, match=MatchAny(any=val))
                                )
                    else:
                        # Simple equality match
                        must_conditions.append(
                            FieldCondition(key=key, match=MatchValue(value=value))
                        )

                if must_conditions or must_not_conditions:
                    qdrant_filter = Filter(
                        must=must_conditions if must_conditions else None,
                        must_not=must_not_conditions if must_not_conditions else None,
                    )

            # Get embeddings for the query
            query_embedding = await asyncio.get_running_loop().run_in_executor(
                None, self.embeddings.embed_query, query_text
            )

            # Search in Qdrant
            search_result = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self.qdrant_client.search(
                    collection_name=self.collection_name,
                    query_vector=query_embedding,
                    limit=k,
                    query_filter=qdrant_filter,  # Use query_filter instead of filter
                ),
            )

            # Convert results to Documents
            documents = []
            for scored_point in search_result:
                if hasattr(scored_point, "payload") and scored_point.payload:
                    # Extract page_content and metadata from payload
                    page_content = scored_point.payload.pop("page_content", "")
                    metadata = scored_point.payload

                    documents.append(
                        Document(page_content=page_content, metadata=metadata)
                    )

            return documents

        except Exception as e:
            self.logger.error(f"Error in similarity_search: {str(e)}")
            raise

    def _build_qdrant_filter(
        self, filter_dict: Dict[str, Any] = None
    ) -> Optional[Filter]:
        """Convert API filter dict to Qdrant Filter object"""
        if not filter_dict:
            # Base filter for user and project
            return Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=self.user_id)),
                    FieldCondition(
                        key="project_id", match=MatchValue(value=self.project_id)
                    ),
                ]
            )

        # Start with user and project filter conditions
        must_conditions = [
            FieldCondition(key="user_id", match=MatchValue(value=self.user_id)),
            FieldCondition(key="project_id", match=MatchValue(value=self.project_id)),
        ]

        # Handle special case for type filtering
        if "type" in filter_dict:
            if isinstance(filter_dict["type"], dict):
                # Handle $nin operator by converting to $neq for each value
                if "$nin" in filter_dict["type"]:
                    for val in filter_dict["type"]["$nin"]:
                        must_not_condition = FieldCondition(
                            key="type", match=MatchValue(value=val)
                        )
                        # Add a must_not condition to filter
                        return Filter(
                            must=must_conditions, must_not=[must_not_condition]
                        )
                # Other operators can be handled similarly
            else:
                # Simple equality match
                must_conditions.append(
                    FieldCondition(
                        key="type", match=MatchValue(value=filter_dict["type"])
                    )
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

    async def _search_with_relevance(
        self, query: str, k: int, filter: Optional[Filter] = None
    ) -> List[Document]:
        loop = asyncio.get_running_loop()

        # Get embedding for query
        query_vector = await loop.run_in_executor(
            None, self.embeddings.embed_query, query
        )

        # Prepare search parameters
        search_params = {
            "collection_name": self.collection_name,
            "query_vector": query_vector,
            "limit": k,
            "with_payload": True,
        }

        # Only add filter if it's not None
        if filter is not None:
            search_params["filter"] = filter

        # Search with Qdrant native client for more control
        search_results = await loop.run_in_executor(
            None, lambda: self.qdrant_client.search(**search_params)
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
            doc = Document(page_content=page_content, metadata=payload)
            documents.append(doc)

        return documents

    async def get_knowledge_base_content(self) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()

        try:
            # Define the server-side filter
            qdrant_filter = Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=self.user_id)),
                    FieldCondition(
                        key="project_id", match=MatchValue(value=self.project_id)
                    ),
                ]
            )

            # Get points using the filter
            points = []
            offset = None  # Start with None for the first scroll call
            limit = 100  # Qdrant default scroll limit

            while True:
                # Use scroll WITH filter parameter
                batch = await loop.run_in_executor(
                    None,
                    lambda: self.qdrant_client.scroll(
                        collection_name=self.collection_name,
                        scroll_filter=qdrant_filter,  # <-- APPLY SERVER-SIDE FILTER
                        limit=limit,
                        offset=offset,  # Pass the offset for subsequent pages
                        with_payload=True,
                    ),
                )

                # Unpack the tuple (points, next_page_offset)
                batch_points, next_offset = batch

                if not batch_points:
                    break  # No more points matching the filter

                points.extend(batch_points)

                if next_offset is None:
                    break  # Reached the end of filtered results

                offset = next_offset  # Set offset for the next iteration

            # Convert to required format (directly from points retrieved)
            content = []
            for point in points:  # Process points directly from Qdrant response
                payload = point.payload
                # page_content might be missing if only metadata was stored for some items
                page_content = payload.pop("page_content", "")
                content.append(
                    {"id": point.id, "metadata": payload, "page_content": page_content}
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

    async def update_doc(
        self, doc_id: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
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
                        with_payload=True,
                    ),
                )
                if not point:
                    self.logger.warning(f"Document {doc_id} not found in collection")
                    raise ValueError(f"Document {doc_id} not found in collection")
            except Exception as e:
                self.logger.error(f"Error getting existing document: {str(e)}")
                raise

            # Generate embeddings for new content
            new_vector = await asyncio.get_running_loop().run_in_executor(
                None, lambda: self.embeddings.embed_documents([content])[0]
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
                        PointStruct(id=doc_id, vector=new_vector, payload=metadata)
                    ],
                ),
            )

            self.logger.debug(f"Updated document with ID: {doc_id}")
            return doc_id

        except Exception as e:
            self.logger.error(f"Error updating doc ID: {doc_id}. Error: {str(e)}")
            raise

    async def update_or_remove_from_knowledge_base(
        self,
        doc_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Update or remove a document from the knowledge base."""
        try:
            if content is None:
                # Remove the document
                self.logger.debug(f"Removing document with ID: {doc_id}")
                await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self.qdrant_client.delete(
                        collection_name=self.collection_name, points_selector=[doc_id]
                    ),
                )
                return None
            else:
                # Update the document
                self.logger.debug(f"Updating document with ID: {doc_id}")
                return await self.update_doc(doc_id, content, metadata)
        except Exception as e:
            self.logger.error(
                f"Error updating/removing doc ID: {doc_id}. Error: {str(e)}"
            )
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
            None, lambda: self.embeddings.embed_documents([new_content])[0]
        )

        # Update the document
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[PointStruct(id=doc_id, vector=new_vector, payload=metadata)],
            ),
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
                ),
            )
        except Exception as e:
            self.logger.warning(f"Error deleting collection: {str(e)}")

        # Recreate collection
        await loop.run_in_executor(
            None,
            lambda: self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_size, distance=Distance.COSINE
                ),
            ),
        )

    def recreate_collection(self):
        """
        Deletes and recreates the collection with the correct Hybrid configuration.
        This is used during the migration process.
        """
        try:
            self.logger.info(f"Recreating collection {self.collection_name} for migration...")
            self.qdrant_client.delete_collection(self.collection_name)
            
            # Create the collection with HYBRID config
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": VectorParams(
                        size=self.embedding_size, 
                        distance=Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(
                        index=rest.SparseIndexParams(
                            on_disk=False,
                        )
                    )
                }
            )
            self.logger.info(f"Collection {self.collection_name} recreated successfully.")
            
            # Re-create indices
            self.qdrant_client.create_payload_index(
                collection_name=self.collection_name,
                field_name="type",
                field_schema=rest.PayloadSchemaType.KEYWORD,
                wait=True,
            )
            self.qdrant_client.create_payload_index(
                collection_name=self.collection_name,
                field_name="user_id",
                field_schema=rest.PayloadSchemaType.KEYWORD,
                wait=True,
            )
            self.qdrant_client.create_payload_index(
                collection_name=self.collection_name,
                field_name="project_id",
                field_schema=rest.PayloadSchemaType.KEYWORD,
                wait=True,
            )
            
            self.needs_migration = False

            # Re-initialize the LangChain wrapper now that the collection is correct
            base_embeddings = GoogleGenerativeAIEmbeddings(
                model=self.embeddings_model,
                google_api_key=self.api_key,
                task_type="retrieval_document",
            )
            self.vector_store = QdrantVectorStore(
                client=self.qdrant_client,
                collection_name=self.collection_name,
                embedding=base_embeddings,
                vector_name="dense",
            )
            self.logger.info("QdrantVectorStore wrapper initialized after recreation.")
            
        except Exception as e:
            self.logger.error(f"Error recreating collection: {e}")
            raise

    async def get_document_by_id(self, doc_id: str) -> Document:
        """Get a document by ID"""
        loop = asyncio.get_running_loop()

        # Retrieve the point by ID
        points = await loop.run_in_executor(
            None,
            lambda: self.qdrant_client.retrieve(
                collection_name=self.collection_name, ids=[doc_id], with_payload=True
            ),
        )

        if not points:
            return None

        # Convert to Document
        point = points[0]
        payload = point.payload
        page_content = payload.pop("page_content", "")

        return Document(page_content=page_content, metadata=payload)

    async def add_texts(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Add multiple texts to the vector store, optionally using provided IDs."""
        if metadatas is None:
            metadatas = [{}] * len(texts)
        if len(texts) != len(metadatas):
            raise ValueError("Number of texts and metadatas must match")
        if ids is not None and len(texts) != len(ids):
            raise ValueError("Number of texts and provided IDs must match")

        # Ensure user_id and project_id in metadata
        for metadata in metadatas:
            metadata["user_id"] = self.user_id
            metadata["project_id"] = self.project_id

        # Add batching to prevent memory issues with large numbers of documents
        batch_size = 10  # Process 10 documents at a time
        all_ids_returned = (
            []
        )  # Use a different name to avoid confusion with input 'ids'

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_metadatas = metadatas[i : i + batch_size]
            batch_ids_input = ids[i : i + batch_size] if ids else None

            # Generate UUIDs only if specific IDs are not provided for the batch
            batch_point_ids = (
                batch_ids_input
                if batch_ids_input
                else [str(uuid.uuid4()) for _ in range(len(batch_texts))]
            )

            # Create DENSE embeddings
            loop = asyncio.get_running_loop()
            dense_vectors = await loop.run_in_executor(
                None, self.embeddings.embed_documents, batch_texts
            )
            
            # Create SPARSE embeddings
            # fastembed returns a generator, so we convert to list
            sparse_vectors = await loop.run_in_executor(
                None, lambda: list(self.sparse_embedding_model.embed(batch_texts))
            )

            # Prepare points for batch upsert
            points = []
            for j, (text, metadata, dense_vec, sparse_vec, point_id) in enumerate(
                zip(
                    batch_texts, batch_metadatas, dense_vectors, sparse_vectors, batch_point_ids
                )
            ):
                # Store the text in metadata for Qdrant
                metadata["page_content"] = text

                # Use named vectors for Hybrid Search
                points.append(PointStruct(
                    id=point_id, 
                    vector={
                        "dense": dense_vec,
                        "sparse": rest.SparseVector(
                            indices=sparse_vec.indices.tolist(),
                            values=sparse_vec.values.tolist()
                        )
                    }, 
                    payload=metadata
                ))

            # Upsert the batch
            await loop.run_in_executor(
                None,
                lambda: self.qdrant_client.upsert(
                    collection_name=self.collection_name, points=points
                ),
            )

            all_ids_returned.extend(batch_point_ids)

            # Give the event loop a chance to process other tasks
            await asyncio.sleep(0.1)

        return all_ids_returned

    async def update_doc(
        self, doc_id: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
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
                        with_payload=True,
                    ),
                )
                if not point:
                    self.logger.warning(f"Document {doc_id} not found in collection")
                    raise ValueError(f"Document {doc_id} not found in collection")
            except Exception as e:
                self.logger.error(f"Error getting existing document: {str(e)}")
                raise

            loop = asyncio.get_running_loop()

            # Generate DENSE embeddings for new content
            new_dense_vector = await loop.run_in_executor(
                None, lambda: self.embeddings.embed_documents([content])[0]
            )
            
            # Generate SPARSE embeddings for new content
            new_sparse_vector_gen = await loop.run_in_executor(
                None, lambda: list(self.sparse_embedding_model.embed([content]))
            )
            new_sparse_vector = new_sparse_vector_gen[0]

            # Prepare metadata payload
            if metadata is None:
                metadata = {}

            # Make sure page_content is in the payload
            metadata["page_content"] = content
            metadata["user_id"] = self.user_id
            metadata["project_id"] = self.project_id

            # Update the point with named vectors
            await loop.run_in_executor(
                None,
                lambda: self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=[
                        PointStruct(
                            id=doc_id, 
                            vector={
                                "dense": new_dense_vector,
                                "sparse": rest.SparseVector(
                                    indices=new_sparse_vector.indices.tolist(),
                                    values=new_sparse_vector.values.tolist()
                                )
                            }, 
                            payload=metadata
                        )
                    ],
                ),
            )

            self.logger.debug(f"Updated document with ID: {doc_id}")
            return doc_id

        except Exception as e:
            self.logger.error(f"Error updating doc ID: {doc_id}. Error: {str(e)}")
            raise

    async def similarity_search(
        self, query_text: str, k: int = 4, filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """Search for similar documents using Hybrid Search (Dense + Sparse)."""
        try:
            # Convert the filter dict to Qdrant's filter format
            qdrant_filter = self._build_qdrant_filter(filter)

            loop = asyncio.get_running_loop()

            # Get DENSE embedding for query
            query_dense_vector = await loop.run_in_executor(
                None, self.embeddings.embed_query, query_text
            )
            
            # Get SPARSE embedding for query
            query_sparse_vector_gen = await loop.run_in_executor(
                None, lambda: list(self.sparse_embedding_model.embed([query_text]))
            )
            query_sparse_vector = query_sparse_vector_gen[0]

            # Perform Hybrid Search using Prefetch (for RRF or simple fusion)
            # We will use a simple fusion approach: search both and combine results
            # Qdrant 1.10+ supports `query_points` with `fusion`
            
            # Since we are using `qdrant-client`, let's try the modern `query_points` API if available, 
            # otherwise fallback to `search` on dense (as a safe default if hybrid fails, but we want hybrid).
            
            # Actually, the most robust way across versions for Hybrid is using `prefetch`
            # But let's try the standard `search` on DENSE for now if we can't easily do fusion without newer client features.
            # WAIT: The user wants Hybrid Search. I must implement it.
            
            # Implementation using `prefetch` (supported in recent versions):
            # 1. Prefetch Dense
            # 2. Prefetch Sparse
            # 3. Fuse
            
            try:
                search_result = await loop.run_in_executor(
                    None,
                    lambda: self.qdrant_client.query_points(
                        collection_name=self.collection_name,
                        prefetch=[
                            rest.Prefetch(
                                query=query_dense_vector,
                                using="dense",
                                limit=k,
                                filter=qdrant_filter,
                            ),
                            rest.Prefetch(
                                query=rest.SparseVector(
                                    indices=query_sparse_vector.indices.tolist(),
                                    values=query_sparse_vector.values.tolist(),
                                ),
                                using="sparse",
                                limit=k,
                                filter=qdrant_filter,
                            ),
                        ],
                        query=rest.FusionQuery(fusion=rest.Fusion.RRF), # Reciprocal Rank Fusion
                        limit=k,
                    ).points
                )
            except AttributeError:
                # Fallback for older clients that might not have query_points or Fusion
                self.logger.warning("Qdrant client might be outdated. Falling back to Dense-only search.")
                search_result = await loop.run_in_executor(
                    None,
                    lambda: self.qdrant_client.search(
                        collection_name=self.collection_name,
                        query_vector=rest.NamedVector(
                            name="dense",
                            vector=query_dense_vector
                        ),
                        limit=k,
                        query_filter=qdrant_filter,
                    ),
                )

            # Convert results to Documents
            documents = []
            for scored_point in search_result:
                if hasattr(scored_point, "payload") and scored_point.payload:
                    # Extract page_content and metadata from payload
                    payload = scored_point.payload
                    page_content = payload.pop("page_content", "")
                    metadata = payload

                    documents.append(
                        Document(page_content=page_content, metadata=metadata)
                    )

            return documents

        except Exception as e:
            self.logger.error(f"Error in similarity_search: {str(e)}")
            raise

    # ... (rest of the file remains unchanged, including _build_qdrant_filter and others)

    async def update_in_knowledge_base(
        self, doc_id: str, new_content: str = None, new_metadata: Dict[str, Any] = None
    ):
        """Single unified method for updating documents."""
        try:
            if not (new_content or new_metadata):
                self.logger.warning(
                    f"No new content or metadata provided for update. Doc ID: {doc_id}"
                )
                return

            loop = asyncio.get_running_loop()

            # Prepare update data
            current_metadata = {}
            current_dense_vector = None
            current_sparse_vector = None

            # Try to get existing point data
            try:
                points = await loop.run_in_executor(
                    None,
                    lambda: self.qdrant_client.retrieve(
                        collection_name=self.collection_name,
                        ids=[doc_id],
                        with_payload=True,
                        with_vectors=True,  # Also get the existing vector
                    ),
                )
                if points and len(points) > 0:
                    current_metadata = points[0].payload
                    # Handle named vectors in retrieval
                    vectors = points[0].vector
                    if isinstance(vectors, dict):
                        current_dense_vector = vectors.get("dense")
                        current_sparse_vector = vectors.get("sparse")
                    else:
                        current_dense_vector = vectors # Fallback if not named yet
            except Exception as e:
                self.logger.debug(
                    f"Could not retrieve existing point (this is OK for new points): {e}"
                )

            # Update metadata
            if new_metadata:
                new_metadata["user_id"] = self.user_id
                new_metadata["project_id"] = self.project_id
                for key, value in new_metadata.items():
                    if value is None and key in current_metadata:
                        current_metadata.pop(key, None)
                    else:
                        current_metadata[key] = value

            # Get vectors - either from new content or use existing
            dense_vector_to_use = None
            sparse_vector_to_use = None
            
            if new_content:
                # Compute new embeddings
                dense_vector_to_use = await loop.run_in_executor(
                    None, lambda: self.embeddings.embed_documents([new_content])[0]
                )
                sparse_gen = await loop.run_in_executor(
                    None, lambda: list(self.sparse_embedding_model.embed([new_content]))
                )
                sparse_vector_to_use = sparse_gen[0]
                
                current_metadata["page_content"] = new_content
            elif current_dense_vector is not None:
                # Use existing vectors if no new content
                dense_vector_to_use = current_dense_vector
                sparse_vector_to_use = current_sparse_vector
            else:
                # Fallback: generate from metadata
                fallback_text = json.dumps(current_metadata)
                dense_vector_to_use = await loop.run_in_executor(
                    None, lambda: self.embeddings.embed_documents([fallback_text])[0]
                )
                sparse_gen = await loop.run_in_executor(
                    None, lambda: list(self.sparse_embedding_model.embed([fallback_text]))
                )
                sparse_vector_to_use = sparse_gen[0]
                
                self.logger.warning(
                    f"Generated fallback vector for doc {doc_id} using metadata as content"
                )

            # Prepare SparseVector object if we have one
            final_sparse_vector = None
            if sparse_vector_to_use:
                # Check if it's already a SparseVector object or raw data
                if isinstance(sparse_vector_to_use, rest.SparseVector):
                    final_sparse_vector = sparse_vector_to_use
                elif hasattr(sparse_vector_to_use, "indices") and hasattr(sparse_vector_to_use, "values"):
                     final_sparse_vector = rest.SparseVector(
                        indices=sparse_vector_to_use.indices.tolist(),
                        values=sparse_vector_to_use.values.tolist()
                    )

            # Create point with named vectors
            point_to_upsert = rest.PointStruct(
                id=doc_id, 
                vector={
                    "dense": dense_vector_to_use,
                    "sparse": final_sparse_vector
                }, 
                payload=current_metadata
            )

            # Perform upsert
            await loop.run_in_executor(
                None,
                lambda: self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=[point_to_upsert],
                    wait=True,  # Ensure the operation completes before returning
                ),
            )

            self.logger.info(f"Successfully updated document with ID: {doc_id}")
            return True  # Return success indicator

        except Exception as e:
            self.logger.error(f"Error updating doc ID: {doc_id}. Error: {str(e)}")
            raise


    def close(self):
        """Properly close the vector store connections"""
        try:
            # Close Qdrant client connection if possible
            if hasattr(self, "qdrant_client"):
                if hasattr(self.qdrant_client, "close"):
                    self.qdrant_client.close()

            # Also clean up the embedding model if possible
            if hasattr(self, "embeddings") and hasattr(self.embeddings, "embeddings"):
                if hasattr(self.embeddings.embeddings, "close"):
                    self.embeddings.embeddings.close()
        except Exception as e:
            self.logger.error(f"Error closing vector store: {str(e)}")

        self.logger.info(
            f"VectorStore closed for user: {self.user_id}, project: {self.project_id}"
        )

    async def delete_collection(self):
        """Deletes the entire Qdrant collection associated with this user/project."""
        try:
            self.logger.warning(
                f"Attempting to delete entire Qdrant collection: {self.collection_name}"
            )
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self.qdrant_client.delete_collection(
                    collection_name=self.collection_name, timeout=60  # Add timeout
                ),
            )
            self.logger.info(
                f"Successfully deleted Qdrant collection: {self.collection_name}"
            )
            return True
        except Exception as e:
            # Log error but don't necessarily raise, depending on desired behavior
            self.logger.error(
                f"Error deleting Qdrant collection {self.collection_name}: {str(e)}",
                exc_info=True,
            )
            return False

    async def get_embedding_id(self, item_id: str, item_type: str) -> Optional[str]:
        """Retrieves the embedding_id for a given item_id and item_type from Qdrant."""
        try:
            # Create filter for the search
            search_filter = Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=self.user_id)),
                    FieldCondition(
                        key="project_id", match=MatchValue(value=self.project_id)
                    ),
                    FieldCondition(key="id", match=MatchValue(value=item_id)),
                    FieldCondition(key="type", match=MatchValue(value=item_type)),
                ]
            )

            # Get matching points
            loop = asyncio.get_running_loop()
            points = await loop.run_in_executor(
                None,
                lambda: self.qdrant_client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=search_filter,
                    limit=1,
                    with_payload=False,
                ),
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
            self.logger.info(
                f"Resetting knowledge base for collection: {self.collection_name}"
            )

            # Removed backup loading logic

            # Delete the collection
            try:
                await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self.qdrant_client.delete_collection(
                        collection_name=self.collection_name
                    ),
                )
                self.logger.debug("Existing collection deleted successfully")
            except Exception as e:
                self.logger.debug(
                    f"No existing collection to delete or error: {str(e)}"
                )

            # Create new collection
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_size, distance=Distance.COSINE
                    ),
                ),
            )
            self.logger.debug("New collection created successfully")

            # Removed backup restoration logic
            restored_items = set()  # Return empty set as no items are restored

            return restored_items

        except Exception as e:
            self.logger.error(f"Error resetting knowledge base: {str(e)}")
            raise

    # Removed _get_item_key method

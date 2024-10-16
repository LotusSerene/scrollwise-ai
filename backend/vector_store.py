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
    def __init__(self, user_id, api_key, embeddings_model):
        self.chroma_url = os.getenv("CHROMA_SERVER_URL", "http://localhost:8000")
        self.chroma_port = int(os.getenv("CHROMA_SERVER_PORT", "8000"))
        self.user_id = user_id
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        
        self.logger.debug(f"Initializing VectorStore for user: {user_id}")
        
        try:
            self.logger.debug("Initializing GoogleGenerativeAIEmbeddings")
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model=embeddings_model, google_api_key=self.api_key
            )
            self.logger.debug("GoogleGenerativeAIEmbeddings initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing GoogleGenerativeAIEmbeddings: {str(e)}")
            raise

        try:
            self.logger.debug("Initializing Chroma client")
            chroma_client = chromadb.HttpClient(host=self.chroma_url, port=self.chroma_port)
            self.logger.debug("Chroma client initialized successfully")
            
            self.logger.debug("Initializing Chroma vector store")
            self.vector_store = Chroma(
                client=chroma_client,
                collection_name=f"user_{user_id}",
                embedding_function=self.embeddings,
            )
            self.logger.debug("Chroma vector store initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing Chroma vector store: {str(e)}")
            raise

        self.logger.info(
            f"VectorStore initialized for user: {user_id} with embeddings model: {embeddings_model}"
        )

    def add_to_knowledge_base(self, text: str, metadata: Dict[str, Any] = None) -> str:
        self.logger.debug(f"Adding to knowledge base for user {self.user_id}")
        if metadata is None:
            metadata = {}
        metadata["user_id"] = self.user_id
        flattened_metadata = flatten_metadata(metadata)
        try:
            # Add the text and get the IDs
            ids = self.vector_store.add_texts([text], metadatas=[flattened_metadata])
            
            # The add_texts method returns a list of IDs, but we're only adding one document,
            # so we can safely take the first (and only) ID
            embedding_id = ids[0]
            
            self.logger.info(f"Added content to knowledge base for user {self.user_id}. Embedding ID: {embedding_id}")
            return embedding_id
        except Exception as e:
            self.logger.error(
                f"Error adding to knowledge base for user {self.user_id}. Error: {str(e)}"
            )
            raise

    def delete_from_knowledge_base(self, embedding_id: str):
        self.logger.debug(f"Deleting from knowledge base..., embedding ID: {embedding_id}")
        try:
            self.vector_store._collection.delete(ids=[embedding_id])
            self.logger.info(f"Deleted content... Embedding ID: {embedding_id}")
        except Exception as e:
            self.logger.error(f"Error deleting embedding ID: {embedding_id}. Error: {str(e)}")
            raise

    def update_in_knowledge_base(self, embedding_id: str, new_content: str = None, new_metadata: Dict[str, Any] = None):
        self.logger.debug(f"Updating in knowledge base..., embedding ID: {embedding_id}")
        try:
            if new_content or new_metadata:
                if new_metadata is None:
                    new_metadata = {}
                new_metadata["user_id"] = self.user_id

                # If new content is provided, we need to compute new embeddings
                if new_content:
                    new_embeddings = self.embeddings.embed_documents([new_content])
                else:
                    new_embeddings = None

                # Update the existing embedding in Chroma:
                self.vector_store._collection.update(
                    ids=[embedding_id],
                    embeddings=new_embeddings[0] if new_embeddings else None,
                    documents=[new_content] if new_content else None,
                    metadatas=[new_metadata] if new_metadata else None
                )

                self.logger.info(f"Updated content... Embedding ID: {embedding_id}")
            else:
                self.logger.warning(f"No new content or metadata provided for update. Embedding ID: {embedding_id}")
        except Exception as e:
            self.logger.error(f"Error updating embedding ID: {embedding_id}. Error: {str(e)}")
            raise

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        self.logger.info(f"Starting similarity search for query: {query}")
        results = self.vector_store.similarity_search(
            query, k=k, filter={"user_id": self.user_id}
        )
        self.logger.info(f"Similarity search completed, found {len(results)} results")
        return results

    def get_knowledge_base_content(self) -> List[Dict[str, Any]]:
        self.logger.debug(
            f"Retrieving all knowledge base content for user {self.user_id}"
        )
        collection = self.vector_store._collection
        if collection is None:
            self.logger.warning(f"No collection found for user {self.user_id}")
            return []

        all_docs = collection.get(where={"user_id": self.user_id})
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

        self.logger.info(
            f"Retrieved {len(content)} items from knowledge base for user {self.user_id}"
        )
        return content

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

    def update_document(
        self, doc_id: str, new_content: str, metadata: Dict[str, Any] = None
    ):
        if metadata is None:
            metadata = {}
        self.vector_store.update_document(
            doc_id, Document(page_content=new_content, metadata=metadata)
        )

    def clear(self):
        self.vector_store.delete_collection()
        self.vector_store = Chroma(
            client=self.vector_store._client,
            collection_name=f"user_{self.user_id}",
            embedding_function=self.embeddings,
        )

    def get_document_by_id(self, doc_id: str) -> Document:
        results = self.vector_store.get([doc_id])
        if results and results["documents"]:
            return Document(
                page_content=results["documents"][0], metadata=results["metadatas"][0]
            )
        return None

    def add_texts(
        self, texts: List[str], metadatas: List[Dict[str, Any]] = None
    ) -> List[str]:
        if metadatas is None:
            metadatas = [{}] * len(texts)
        for metadata in metadatas:
            metadata["user_id"] = self.user_id
        return self.vector_store.add_texts(texts, metadatas)

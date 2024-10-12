from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.docstore.document import Document
from typing import List, Dict, Any
import os
import logging


class VectorStore:
    def __init__(self, user_id, api_key, embeddings_model):
        self.user_id = user_id
        self.api_key = api_key
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=embeddings_model, google_api_key=self.api_key
        )
        self.vector_store = Chroma(
            persist_directory=f"./chroma_db/{user_id}",
            embedding_function=self.embeddings,
        )
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.logger.info(
            f"VectorStore initialized for user: {user_id} with embeddings model: {embeddings_model}"
        )


    def add_to_knowledge_base(self, text: str, metadata: Dict[str, Any] = None):
        self.logger.debug(f"Adding to knowledge base for user {self.user_id}")
        if metadata is None:
            metadata = {}
        metadata["user_id"] = self.user_id
        flattened_metadata = flatten_metadata(metadata)
        try:
            self.vector_store.add_texts([text], metadatas=[flattened_metadata])
            self.logger.info(f"Added content to knowledge base for user {self.user_id}")
        except Exception as e:
            self.logger.error(
                f"Error adding to knowledge base for user {self.user_id}. Error: {str(e)}"
            )
    
    def delete_from_knowledge_base(self, embedding_id: str):
        self.logger.debug(
            f"Attempting to delete from knowledge base for user {self.user_id}, embedding ID: {embedding_id}"
        )
        try:
            self.vector_store.delete([embedding_id])
            self.logger.info(
                f"Deleted content from knowledge base for user {self.user_id}. Embedding ID: {embedding_id}"
            )
        except Exception as e:
            self.logger.error(
                f"Error deleting embedding ID: {embedding_id} for user {self.user_id}. Error: {str(e)}"
            )

    def update_in_knowledge_base(
        self,
        embedding_id: str,
        new_content: str = None,
        new_metadata: Dict[str, Any] = None,
    ):
        self.logger.debug(
            f"Updating in knowledge base for user {self.user_id}, embedding ID: {embedding_id}"
        )
        try:
            # Delete the old embedding
            self.delete_from_knowledge_base(embedding_id)

            # Add the new content with the same ID
            if new_content:
                if new_metadata is None:
                    new_metadata = {}
                new_metadata["user_id"] = self.user_id
                self.vector_store.add_texts(
                    [new_content], metadatas=[new_metadata], ids=[embedding_id]
                )
                self.logger.info(
                    f"Updated content in knowledge base for user {self.user_id}. Embedding ID: {embedding_id}"
                )
            elif new_metadata:
                self.logger.warning(
                    f"Attempted to update only metadata for embedding ID: {embedding_id}. This operation is not supported."
                )
        except Exception as e:
            self.logger.error(
                f"Error updating embedding ID: {embedding_id} for user {self.user_id}. Error: {str(e)}"
            )

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        self.logger.debug(
            f"Performing similarity search for user {self.user_id} and query: {query}"
        )
        results = self.vector_store.similarity_search(
            query, k=k, filter={"user_id": self.user_id}
        )
        self.logger.info(
            f"Similarity search returned {len(results)} results for user {self.user_id}"
        )
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
            persist_directory=f"./chroma_db/{self.user_id}",
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

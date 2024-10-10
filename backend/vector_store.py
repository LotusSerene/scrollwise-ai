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
        self.embeddings = GoogleGenerativeAIEmbeddings(model=embeddings_model, google_api_key=self.api_key)
        self.vector_store = Chroma(persist_directory=f"./chroma_db/{user_id}", embedding_function=self.embeddings)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.logger.info(f"VectorStore initialized for user: {user_id} with embeddings model: {embeddings_model}")

    def add_to_knowledge_base(self, text: str, metadata: Dict[str, Any] = None):
        if metadata is None:
            metadata = {}
        self.logger.debug(f"Adding to knowledge base for user {self.user_id}: {text[:100]}...")
        self.vector_store.add_texts([text], metadatas=[metadata])
        self.vector_store.persist()  # Ensure data is persisted
        self.logger.info(f"Added text to knowledge base for user {self.user_id}. Metadata: {metadata}")

    def delete_from_knowledge_base(self, text: str):
        self.logger.debug(f"Attempting to delete from knowledge base for user {self.user_id}: {text[:100]}...")
        documents = self.vector_store.similarity_search(text, k=1)
        if documents:
            self.delete([documents[0].metadata.get('id')])
            self.logger.info(f"Deleted document from knowledge base for user {self.user_id}. ID: {documents[0].metadata.get('id')}")
        else:
            self.logger.warning(f"No matching document found for deletion for user {self.user_id}: {text[:100]}...")

    def delete(self, ids: List[str]):
        for id in ids:
            if id:
                self.vector_store.delete(id)

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        self.logger.debug(f"Performing similarity search for user {self.user_id} and query: {query}")
        results = self.vector_store.similarity_search(query, k=k)
        self.logger.info(f"Similarity search returned {len(results)} results for user {self.user_id}")
        return results

    def get_knowledge_base_content(self) -> List[Dict[str, Any]]:
        self.logger.debug(f"Retrieving all knowledge base content for user {self.user_id}")
        docs = self.vector_store.get()
        self.logger.info(f"Retrieved {len(docs)} documents from knowledge base for user {self.user_id}")
        return [
            {
                "type": self._get_type(doc),
                "content": self._get_content(doc)[:100],  # Return first 100 characters of content
                "metadata": self._get_metadata(doc)
            } for doc in docs
        ]

    def _get_type(self, doc: Any) -> str:
        if isinstance(doc, Document):
            return doc.metadata.get('type', 'Unknown')
        elif isinstance(doc, dict):
            return doc.get('metadata', {}).get('type', 'Unknown')
        else:
            return 'Unknown'

    def _get_content(self, doc: Any) -> str:
        if isinstance(doc, Document):
            return doc.page_content
        elif isinstance(doc, dict):
            return doc.get('page_content', str(doc))
        else:
            return str(doc)

    def _get_metadata(self, doc: Any) -> Dict[str, Any]:
        if isinstance(doc, Document):
            return doc.metadata
        elif isinstance(doc, dict):
            return doc.get('metadata', {})
        else:
            return {}

    def as_retriever(self, search_kwargs: Dict[str, Any] = None):
        if search_kwargs is None:
            search_kwargs = {"k": 5}
        return self.vector_store.as_retriever(search_kwargs=search_kwargs)

    def update_document(self, doc_id: str, new_content: str, new_metadata: Dict[str, Any] = None):
        if new_metadata is None:
            new_metadata = {}
        self.vector_store.update_document(doc_id, Document(page_content=new_content, metadata=new_metadata))

    def clear(self):
        self.vector_store.delete_collection()
        self.vector_store = Chroma(persist_directory=f"./chroma_db/{self.user_id}", embedding_function=self.embeddings)

    def get_document_by_id(self, doc_id: str) -> Document:
        return self.vector_store.get([doc_id])[0]

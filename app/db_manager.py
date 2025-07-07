import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any

import chromadb
from langchain_community.vectorstores import PGVector
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_core.documents import Document

class VectorDB(ABC):
    @abstractmethod
    def add_documents(self, documents: List[Document], file_path: str):
        pass

    @abstractmethod
    def get_all_documents(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def delete_documents(self, file_path: str):
        pass

    @abstractmethod
    def document_exists(self, file_path: str) -> bool:
        pass

    @abstractmethod
    def query_documents(self, query_text: str, n_results: int = 2) -> Dict[str, Any]:
        pass

class ChromaDBManager(VectorDB):
    def __init__(self):
        self.client = chromadb.HttpClient(host=os.getenv("CHROMA_HOST", "localhost"), port=int(os.getenv("CHROMA_PORT", 8000)))
        self.collection = self.client.get_or_create_collection("my_documents")

    def add_documents(self, documents: List[Document], file_path: str):
        for i, doc in enumerate(documents):
            self.collection.add(
                documents=[doc.page_content],
                metadatas=[{"source": file_path}],
                ids=[f"{file_path}-{i}"]
            )

    def get_all_documents(self) -> Dict[str, Any]:
        return self.collection.get(include=['metadatas', 'documents'])

    def delete_documents(self, file_path: str):
        self.collection.delete(where={"source": file_path})

    def document_exists(self, file_path: str) -> bool:
        existing_records = self.collection.get(where={"source": file_path})
        return bool(existing_records['ids'])

    def query_documents(self, query_text: str, n_results: int = 2) -> Dict[str, Any]:
        return self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            include=['documents', 'metadatas']
        )

class PGVectorManager(VectorDB):
    def __init__(self):
        self.connection_string = os.getenv("PG_CONNECTION_STRING")
        if not self.connection_string:
            raise ValueError("PG_CONNECTION_STRING environment variable not set for PGVector.")
        self.embedding_function = self._get_embedding_function()
        self.collection_name = "my_documents"
        self.vectorstore = self._get_vectorstore()

    def _get_embedding_function(self):
        # Prioritize OpenAIEmbeddings if API key is available
        if os.getenv("OPENAI_API_KEY"):
            return OpenAIEmbeddings()
        else:
            # Fallback to SentenceTransformerEmbeddings if no OpenAI key
            return SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

    def _get_vectorstore(self):
        return PGVector(
            connection_string=self.connection_string,
            embedding_function=self.embedding_function,
            collection_name=self.collection_name,
            pre_delete_collection=False, # Set to True if you want to drop the collection on init
        )

    def add_documents(self, documents: List[Document], file_path: str):
        # PGVector's add_documents handles metadata and IDs automatically if present in Document objects
        # Ensure 'source' metadata is set for filtering
        for doc in documents:
            if 'source' not in doc.metadata:
                doc.metadata['source'] = file_path
        self.vectorstore.add_documents(documents)

    def get_all_documents(self) -> Dict[str, Any]:
        # PGVector does not have a direct 'get all' method like ChromaDB.
        # This is a workaround to fetch all documents.
        # In a real application, you might paginate or fetch based on specific criteria.
        # This will fetch a large number of documents, adjust limit as needed.
        # This is not efficient for very large databases.
        all_docs = self.vectorstore.similarity_search(" ", k=10000) # Query with a space to get all, limit to 10k
        ids = [f"{doc.metadata.get('source', 'unknown')}-{i}" for i, doc in enumerate(all_docs)]
        metadatas = [doc.metadata for doc in all_docs]
        documents = [doc.page_content for doc in all_docs]
        return {"ids": ids, "metadatas": metadatas, "documents": documents}

    def delete_documents(self, file_path: str):
        # PGVector's delete method requires IDs. We need to query for IDs first.
        # This is a limitation compared to ChromaDB's metadata-based delete.
        docs_to_delete = self.vectorstore.similarity_search(query="", k=10000, filter={"source": file_path})
        ids_to_delete = [doc.metadata.get('id') for doc in docs_to_delete if doc.metadata.get('id')]
        if ids_to_delete:
            self.vectorstore.delete(ids=ids_to_delete)
        else:
            # If no specific IDs are available in metadata, we can't delete by ID.
            # A more robust solution would involve storing unique IDs in metadata during add.
            # For now, we'll just inform if no IDs were found for deletion.
            print(f"No specific IDs found for {file_path} to delete in PGVector.")


    def document_exists(self, file_path: str) -> bool:
        # Check if any document with the given source exists
        docs = self.vectorstore.similarity_search(query="", k=1, filter={"source": file_path})
        return bool(docs)

    def query_documents(self, query_text: str, n_results: int = 2) -> Dict[str, Any]:
        docs = self.vectorstore.similarity_search(query_text, k=n_results)
        ids = [f"{doc.metadata.get('source', 'unknown')}-{i}" for i, doc in enumerate(docs)]
        metadatas = [doc.metadata for doc in docs]
        documents = [doc.page_content for doc in docs]
        return {"ids": ids, "metadatas": metadatas, "documents": documents}

class DatabaseManager:
    def __init__(self):
        self.db_backend = os.getenv("DB_BACKEND", "chroma").lower()
        if self.db_backend == "chroma":
            self.vector_db: VectorDB = ChromaDBManager()
        elif self.db_backend == "pgvector":
            self.vector_db: VectorDB = PGVectorManager()
        else:
            raise ValueError(f"Unsupported DB_BACKEND: {self.db_backend}. Choose 'chroma' or 'pgvector'.")

    def add_documents(self, documents: List[Document], file_path: str):
        self.vector_db.add_documents(documents, file_path)

    def get_all_documents(self) -> Dict[str, Any]:
        return self.vector_db.get_all_documents()

    def delete_documents(self, file_path: str):
        self.vector_db.delete_documents(file_path)

    def document_exists(self, file_path: str) -> bool:
        return self.vector_db.document_exists(file_path)

    def query_documents(self, query_text: str, n_results: int = 2) -> Dict[str, Any]:
        return self.vector_db.query_documents(query_text, n_results)

# Initialize the DatabaseManager
db_manager = DatabaseManager()

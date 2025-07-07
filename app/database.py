# app/database.py
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
import os
from tqdm import tqdm
from app.db_manager import db_manager

def add_file_to_db(file_path: str):
    """Loads a PDF, splits it into chunks, and adds it to ChromaDB."""
    if not os.path.exists(file_path):
        return "Error: File not found."

    # Check if the file already exists in the database
    if db_manager.document_exists(file_path):
        return f"Warning: {file_path} is already in the database. Skipping upload."

    try:
        # Load the PDF
        loader = PyPDFLoader(file_path)
        documents = loader.load()

        # Split the document into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_documents(documents)

        # Add chunks to ChromaDB with a progress bar
        for i, chunk in tqdm(enumerate(chunks), total=len(chunks), desc="Adding chunks to DB"):
            # ChromaDB expects page_content, PGVector expects Document objects
            # We'll pass Document objects to db_manager.add_documents
            chunk.metadata['source'] = file_path # Ensure source is in metadata for PGVector
        db_manager.add_documents(chunks, file_path)
        return f"Successfully added {file_path} to the database."
    except Exception as e:
        return f"An error occurred: {e}"

def query_db(query_text: str, n_results: int = 2):
    """Queries the ChromaDB for relevant document chunks."""
    return db_manager.query_documents(query_text, n_results)


def get_all_records():
    """Retrieves all records from the ChromaDB collection."""
    return db_manager.get_all_documents()

def remove_file_from_db(file_path: str):
    """Removes a file and its chunks from ChromaDB."""
    db_manager.delete_documents(file_path)
    return f"Successfully removed {file_path} from the database."

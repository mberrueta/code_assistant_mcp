# Gemini Blueprint: RAG-MCP Elixir Server


Markdown

Create the following project structure and file content for a Python application that uses ChromaDB, FastAPI, and Docker with `uv`.

**Project Structure:**

chroma_project/
├── app/
│   ├── init.py
│   ├── cli.py
│   ├── server.py
│   └── database.py
├── Dockerfile
└── requirements.txt


**File Content:**

**1. `chroma_project/requirements.txt`:**

```txt
chromadb
fastapi
uvicorn[standard]
python-multipart
langchain
pypdf
2. chroma_project/app/__init__.py:

Python

# This file can be empty.
3. chroma_project/app/database.py:

Python

import chromadb
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import PyPDFLoader
import os

# Initialize ChromaDB client. This will create a persistent database in the './chroma_db' directory.
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("my_documents")

def add_file_to_db(file_path: str):
    """Loads a PDF, splits it into chunks, and adds it to ChromaDB."""
    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}"

    try:
        # Load the PDF
        loader = PyPDFLoader(file_path)
        documents = loader.load()

        # Split the document into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_documents(documents)

        # Add chunks to ChromaDB
        ids = [f"{os.path.basename(file_path)}-{i}" for i, _ in enumerate(chunks)]
        contents = [chunk.page_content for chunk in chunks]
        metadatas = [{"source": os.path.basename(file_path)} for _ in chunks]

        collection.add(
            documents=contents,
            metadatas=metadatas,
            ids=ids
        )
        return f"Successfully added {os.path.basename(file_path)} to the database."
    except Exception as e:
        return f"An error occurred: {e}"

def query_db(query_text: str, n_results: int = 2):
    """Queries the ChromaDB for relevant document chunks."""
    results = collection.query(
        query_texts=[query_text],
        n_results=n_results
    )
    return results
4. chroma_project/app/cli.py:

Python

import argparse
from app.database import add_file_to_db
import os

def main():
    parser = argparse.ArgumentParser(description="Add a file to the ChromaDB.")
    parser.add_argument("file_path", type=str, help="The path to the file to add.")
    args = parser.parse_args()

    # In a container, the path might be relative to the app directory
    file_path = os.path.join(os.getcwd(), args.file_path)

    result = add_file_to_db(args.file_path)
    print(result)

if __name__ == "__main__":
    main()
5. chroma_project/app/server.py:

Python

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.database import query_db

app = FastAPI(
    title="MCP Server API",
    description="An API to query documents stored in ChromaDB."
)

class Query(BaseModel):
    text: str
    n_results: int = 2

@app.post("/query/")
def ask_question(query: Query):
    """
    Receives a question and returns relevant document excerpts from the database.
    """
    try:
        results = query_db(query.text, n_results=query.n_results)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"message": "MCP Server is running. Post your queries to the /query/ endpoint."}
6. chroma_project/Dockerfile:

Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install uv for fast package management
RUN pip install uv

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies using uv
RUN uv pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY ./app /app/app

# The ChromaDB database will be stored in this directory
VOLUME /app/chroma_db

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run uvicorn server when the container launches
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]


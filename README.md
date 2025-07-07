# RAG-MCP Python Server. 

## About The Project

This project aims to build a Retrieval-Augmented Generation (RAG) system in Python. The system will have two primary functions:

- Ingestion Service: A client interface to feed documents (PDFs, text files) and web URLs into a knowledge base. These sources are processed, converted into vector embeddings, and stored in a specialized vector database.
- MCP Server: A Model-Controlled Proxy (MCP) server that exposes an API endpoint. An external Large Language Model (LLM), like one hosted via Ollama, can query this endpoint. The server finds relevant information from the knowledge base and provides it as context to the LLM, enabling more accurate and context-aware responses.

The entire application will be built using Python and the OTP framework to create a robust, concurrent, and fault-tolerant system.

## Architecture Overview

The system is split into two distinct, asynchronous parts:

Ingestion Pipeline: A multi-stage Broadway pipeline handles the processing of new sources.
Query Server: A lightweight Plug web server handles real-time queries.


```
+------------------+      +-------------------------+      +--------------------+
|   Source (File,  |----->|   Ingestion Pipeline    |----->|   Vector Database  |
|      URL)        |      |      (        )         |      |      (Qdrant)      |
+------------------+      +-------------------------+      +--------------------+
                              |        |        |
                              v        v        v
                         +--------+ +-------+ +-----------+
                         | Extract| | Chunk | | Embed     |
                         +--------+ +-------+ +-----------+
                                                ^
                                                |
                               +----------------+
                               |
+------------------+      +-------------------------+      +--------------------+
|   LLM / User     |----->|       MCP Server        |<---->|   Vector Database  |
|      Query       |      |         (Plug)          |      | (for search)       |
+------------------+      +-------------------------+      +--------------------+
                              |
                              v
                         +-----------+
                         | Embed     |
                         +-----------+
```

## Tech Stack

- Language & Framework: Python 
- AI/ML & Numerics:
    - xxx for numerical computing.
    - xxx for running transformer models to generate embeddings.
- Data Ingestion: Broadway for the concurrent processing pipeline.
- Vector Database: chromadb (running as a Docker container).
- Web Server: .
- Supporting Services (from docker-compose.yml):

## Getting Started

### Prerequisites

- Python 
- uv
- Docker and Docker Compose

### Installation & Setup

Clone the repository:

``` sh
git clone git@github.com:mberrueta/rag_mcp.git
cd rag_mcp
docker-compose up -d
```

## Usage

### CLI Usage

To build the command-line executable (escript):

```bash
uv run python -m app.cli -h
uv run python -m app.cli add ./data/PhoenixEcto_BestPractices.pdf
uv run python -m app.cli remove ./data/PhoenixEcto_BestPractices.pdf
```

``` bash
export DB_BACKEND=pgvector
export PG_CONNECTION_STRING="postgresql://user:password@host:port/database"
export OPENAI_API_KEY="your_openai_api_key" # Required for OpenAIEmbeddings
uv run python -m app.cli add <file_path>
```

This will generate an executable named `rag_mcp` in the current directory.

To use the CLI:

*   **Add a document:**
    ```bash
    ./rag_mcp --add <file_path>
    # or
    ./rag_mcp -a <file_path>
    ```
    Replace `<file_path>` with the absolute or relative path to your document (e.g., `./data/samples/PhoenixBestPractices.pdf`).

*   **Show help message:**
    ```bash
    ./rag_mcp --help
    # or
    ./rag_mcp -h
    ```

### Ingesting Data (from iex)

The application will expose a function to start the ingestion process. 
This can be triggered from an iex session, a script, or a future API endpoint.

Example (from iex)

``` python
sources = ["/path/to/my_document.pdf", "https://python-lang.org/getting-started/introduction.html"]
iex> RagMcp.add_sources(sources)
{:ok, :processing_started}

```

### Querying the MCP Server

The MCP server will listen for POST requests on the /query endpoint.

Example using curl:

``` sh
curl -X POST \
  http://localhost:4000/query \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "How do you define a GenServer in Python?"
  }'
Expected Response:{
  "prompt": "How do you define a GenServer in Python?",
  "context": "A GenServer is a process... [retrieved text chunks from the vector database] ...and it is a core part of OTP."
}
```

## Upgrade libs

``` sh
uv lock --upgrade
```

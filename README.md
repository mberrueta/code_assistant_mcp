# Database MCP Server

A dual-mode server that provides database inspection via both FastAPI REST endpoints and MCP protocol for seamless integration with AI assistants like Gemini CLI.

## Features

- **Dual Mode Operation**: Run as HTTP REST API or MCP stdio server
- **Database Agnostic**: Supports PostgreSQL, MySQL, SQLite via SQLAlchemy
- **Schema Inspection**: Get table structures, columns, and relationships
- **Sample Data**: Safely query sample rows with built-in limits
- **MCP Integration**: Direct integration with AI assistants for database exploration

## Database Connection

Set your database URL as an environment variable:

```bash
# PostgreSQL (use 127.0.0.1 or localhost to force TCP connections)
export DATABASE_URL="postgresql://postgres:password@127.0.0.1:5432/database_name"

# MySQL
export DATABASE_URL="mysql://user:password@localhost:3306/database_name"

# SQLite
export DATABASE_URL="sqlite:///./database.db"
```

**Important**: For PostgreSQL, always specify `127.0.0.1` or `localhost` in the host to avoid Unix socket connection issues.

## Usage Modes

### 1. FastAPI Mode (HTTP REST API)
```bash
uv run db_tools.py
# or with explicit DATABASE_URL
export DATABASE_URL="postgresql://user:password@127.0.0.1:5432/database" 
uv run db_tools.py
```

Access at: http://127.0.0.1:8000

### 2. MCP Mode (stdio for AI integration)
```bash
uv run db_tools.py --mcp
```

## MCP Client Configuration

### For Gemini CLI, Claude
Add to your Gemini CLI configuration file:

```json
{
  "mcpServers": {
    "dbHelper": {
      "command": "uv",
      "args": ["run", "db_tools.py", "--mcp"],
      "cwd": "/path/to/your/project",
      "timeout": 15000
    }
  }
}
```

### Alternative: Using Python directly
```json
{
  "mcpServers": {
    "database-inspector": {
      "command": "python",
      "args": ["/path/to/your/db_tools.py", "--mcp"],
      "env": {
        "DATABASE_URL": "postgresql://user:password@127.0.0.1:5432/database"
      }
    }
  }
}
```

## Available Tools (MCP Mode)

### 1. `list_tables`
- **Description**: Get a list of all tables in the database
- **Parameters**: None
- **Returns**: Plain text list of table names (one per line)

### 2. `describe_table`
- **Description**: Get detailed schema information for a specific table
- **Parameters**: 
  - `table_name` (string): Name of the table to inspect
- **Returns**: JSON object with columns, types, nullable status, defaults, and primary keys

### 3. `table_relationships`
- **Description**: Get foreign key relationships for a specific table
- **Parameters**:
  - `table_name` (string): Name of the table
- **Returns**: JSON object with foreign key relationships and constraints

### 4. `query_sample`
- **Description**: Get sample data from a table (max 10 rows for safety)
- **Parameters**:
  - `table_name` (string): Name of the table to sample
  - `limit` (integer, optional): Number of rows (default: 5, max: 10)
- **Returns**: JSON array of sample data rows

## REST API Endpoints (FastAPI Mode)

- `GET /tables` - List all tables
- `GET /tables/{table_name}` - Get detailed table schema
- `GET /tables/{table_name}/relationships` - Get table foreign key relationships

## Using with Gemini CLI

Once configured, you can use these commands in Gemini CLI:

```bash
# List all MCP servers
/mcp list

# See available tools
/mcp desc dbHelper

# Use the tools in conversation
"Can you list all the tables in my database?"
"Show me the schema for the users table"
"Get some sample data from the appointments table"
```

## Troubleshooting

### Connection Issues
- **PostgreSQL socket errors**: Use `127.0.0.1` instead of `localhost` in DATABASE_URL
- **Permission denied**: Check database credentials and user permissions
- **Connection refused**: Verify database server is running and accessible

### MCP Connection Issues
- **Connection closed errors**: Usually caused by logging interference - this is fixed in the current version
- **Tool not found**: Check MCP server configuration and restart Gemini CLI
- **Timeout errors**: Increase timeout in MCP configuration

### Architecture
- **FastAPI**: Provides HTTP REST endpoints for direct database access
- **MCP Protocol**: Enables AI assistant integration via stdin/stdout communication
- **SQLAlchemy**: Database abstraction layer supporting multiple database types
- **Dual Mode**: Single script can run in either HTTP or MCP mode

## RAG Builder

`rag_builder.py` is a utility to fetch, process, and store Elixir library documentation from hexdocs.pm for use in a Retrieval-Augmented Generation (RAG) system. It fetches the main documentation page and any linked pages from the sidebar (excluding API references and changelogs).

### Database Backends

The script supports three backends for storing the documentation embeddings:

*   `faiss`: (Default) Stores a FAISS index and JSON files on the local filesystem.
*   `chromadb`: Stores data in a ChromaDB vector database.
*   `pgvector`: Stores data in a PostgreSQL database with the pgvector extension.

To select a backend, set the `RAG_DB_BACKEND` environment variable. If not set, it will default to `faiss`.

**Docker Services:**

The `docker-compose.yml` file includes services for `chromadb` and `pgvector-db`. To use them, start them with:

```bash
docker-compose up -d
```

### First-Time Setup for pgvector

Before using the `pgvector` backend for the first time, you need to create the `rag_db` database. Make sure your `RAG_DB_*` variables are set in your environment (e.g., by sourcing `.envrc`), then run the following command:

```bash
PGPASSWORD=$RAG_DB_PASSWORD psql -h $RAG_DB_HOSTNAME -p $RAG_DB_PORT -U $RAG_DB_USERNAME -d postgres -c "CREATE DATABASE $RAG_DB_NAME;"
```

### Checking ChromaDB

To inspect the contents of your ChromaDB database, you can use the `check_chroma` command. This is a convenient way to verify that your data has been indexed correctly.

**List all collections:**

```bash
uv run python rag_builder.py check_chroma
```

**Inspect a specific collection:**

```bash
uv run python rag_builder.py check_chroma <collection_name>
```

This will show you the number of items in the collection and a sample of the first 5 documents.

### Usage

To fetch documentation for a specific Elixir library and version (version is optional; if omitted, the latest stable version will be fetched):

**FAISS (Default):**

```bash
uv run python rag_builder.py build jason 1.4.3
```

**ChromaDB:**

```bash
 RAG_DB_BACKEND=chromadb uv run python rag_builder.py build jason 1.4.3
```

**pgvector:**

```bash
 RAG_DB_BACKEND=pgvector RAG_DATABASE_URL="postgresql://user:pass@host:port/db" uv run python rag_builder.py build jason 1.4.3
```

This will save the raw HTML (`.html`), extracted text (`.txt`), and a FAISS index (`.faiss`) along with a JSON file (`.json`) containing the document chunks and metadata to `rag_store/<library_name>/<version>/`.

## Elixir Dependency Scraper

The `mix_dependency_scraper.py` script is a utility to parse an Elixir project's `mix.exs` and `mix.lock` files to generate a shell script. This generated script contains the commands to build the RAG data for each dependency using `rag_builder.py`.

### Usage

1.  **Run the scraper**: Point the script to your Elixir project's `mix.exs` file.
2.  **Redirect the output**: Save the generated commands to a shell script.
3.  **Execute the script**: Run the generated script to build the RAG data for all dependencies.

**Example:**

```bash
# Generate the build script
python mix_dependency_scraper.py /path/to/your/elixir_project/mix.exs > build_rag_data.sh

# Review the generated script
cat build_rag_data.sh

# Execute the script
bash build_rag_data.sh
```

This will execute the `uv run python rag_builder.py build <dependency> <version>` command for each dependency found in your `mix.exs` and `mix.lock` files.

## Library Documentation Tool

`library_doc_tool.py` is an MCP tool that allows you to fetch documentation for Python libraries from PyPI. It can handle both HTML and PDF documentation.

### Usage

To use the tool, you need to have the `library_docs` service running. You can start it with Docker Compose:

```bash
docker-compose up -d library_docs
```

Once the service is running, you can interact with it using an MCP client. For example, with the Gemini CLI, you can add the following to your configuration:

```json
{
  "mcpServers": {
    "library_doc_helper": {
      "command": "uv",
      "args": ["run", "library_doc_tool.py", "--mcp"],
      "cwd": "/path/to/your/project",
      "timeout": 15000
    }
  }
}
```

Then, you can use the tool in a conversation:

```bash
"Can you get me the documentation for the requests library?"
```
# Database MCP Server

A dual-mode server that provides database inspection via both FastAPI REST endpoints and MCP protocol for seamless integration with AI assistants like Gemini CLI.

## Features

- **Dual Mode Operation**: Run as HTTP REST API or MCP stdio server
- **Database Agnostic**: Supports PostgreSQL, MySQL, SQLite via SQLAlchemy
- **Schema Inspection**: Get table structures, columns, and relationships
- **Sample Data**: Safely query sample rows with built-in limits
- **MCP Integration**: Direct integration with AI assistants for database exploration

## Installation

### Using uv
```bash
# Initialize a new project (if not already done)
uv init

# Add dependencies
uv add mcp fastapi uvicorn sqlalchemy psycopg2-binary

# For MySQL instead of PostgreSQL:
# uv add mcp fastapi uvicorn sqlalchemy pymysql

# SQLite is included with Python by default
```

### Alternative: Using pip
```bash
pip install mcp fastapi uvicorn sqlalchemy psycopg2-binary
# For MySQL: pip install pymysql
```

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
DATABASE_URL="postgresql://user:password@127.0.0.1:5432/database" uv run db_tools.py
```

Access at: http://127.0.0.1:8000

### 2. MCP Mode (stdio for AI integration)
```bash
uv run db_tools.py --mcp
```

## MCP Client Configuration

### For Gemini CLI
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

### For Claude Desktop or other MCP clients
```json
{
  "mcpServers": {
    "database-inspector": {
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

### Testing Your Setup

Test database connection:
```bash
uv run python -c "
from sqlalchemy import create_engine, inspect
import os
engine = create_engine(os.getenv('DATABASE_URL'))
print('Connected! Tables:', inspect(engine).get_table_names())
"
```

Test MCP server:
```bash
uv run db_tools.py --mcp
# Should start and wait for input (Ctrl+C to exit)
```

Test FastAPI mode:
```bash
uv run db_tools.py &
curl http://127.0.0.1:8000/tables
```

## Key Implementation Details

### Critical Fixes Applied
1. **Logging Disabled in MCP Mode**: Prevents stdin/stdout interference with MCP protocol
2. **Proper Error Handling**: Errors returned as TextContent instead of raising exceptions
3. **Safe Query Limits**: Sample queries capped at 10 rows maximum
4. **TCP Connection Forcing**: Database URLs use explicit hosts to avoid socket issues
5. **Async/Await Support**: Proper async implementation for MCP protocol

### Architecture
- **FastAPI**: Provides HTTP REST endpoints for direct database access
- **MCP Protocol**: Enables AI assistant integration via stdin/stdout communication
- **SQLAlchemy**: Database abstraction layer supporting multiple database types
- **Dual Mode**: Single script can run in either HTTP or MCP mode

## RAG Builder

`rag_builder.py` is a utility to fetch, process, and store Elixir library documentation from hexdocs.pm for use in a Retrieval-Augmented Generation (RAG) system. It fetches the main documentation page and any linked pages from the sidebar (excluding API references and changelogs).

Currently, it saves the raw HTML, extracted clean text, and generated embeddings to local files. Future iterations will integrate with a vector database.

### Usage

To fetch documentation for a specific Elixir library and version (version is optional; if omitted, the latest stable version will be fetched):

```bash
uv run python rag_builder.py <library_name> [version]
```

**Examples:**

```bash
uv run python rag_builder.py jason 1.4.3
uv run python rag_builder.py req # Fetches the latest version of Req
```

This will save the raw HTML (`.html`), extracted text (`.txt`), and a FAISS index (`.faiss`) along with a JSON file (`.json`) containing the document chunks and metadata to `rag_store/<library_name>/<version>/`.

## License

MIT License - feel free to use and modify as needed.

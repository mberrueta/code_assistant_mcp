###############################################################################
# db_tools.py  – FastAPI REST + MCP for database introspection (FIXED)
# Works with mcp==1.12.1
###############################################################################
import os
import logging
import asyncio
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, inspect
from pydantic import BaseModel
import uvicorn

###############################################################################
# MCP 1.12.1 imports (corrected)
###############################################################################
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

###############################################################################
# Logging & DB setup
###############################################################################
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
engine = create_engine(DATABASE_URL)

###############################################################################
# Pydantic DTOs
###############################################################################
class TableName(BaseModel):
    name: str

class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    default: Any
    primary_key: bool

class TableInfo(BaseModel):
    name: str
    columns: List[ColumnInfo]

class RelationshipInfo(BaseModel):
    local_column: str
    remote_table: str
    remote_column: str
    on_delete: str | None = None

class TableRelationships(BaseModel):
    name: str
    relationships: List[RelationshipInfo]

###############################################################################
# Helper
###############################################################################
def get_db_inspector():
    if not engine:
        raise HTTPException(status_code=500, detail="Database unavailable.")
    return inspect(engine)

###############################################################################
# FastAPI REST endpoints (for direct HTTP access)
###############################################################################
app = FastAPI(title="DB MCP", version="1.0.0")

@app.get("/tables", response_model=List[TableName])
def list_tables():
    insp = get_db_inspector()
    return [{"name": t} for t in insp.get_table_names()]

@app.get("/tables/{table_name}", response_model=TableInfo)
def describe_table(table_name: str):
    insp = get_db_inspector()
    if not insp.has_table(table_name):
        raise HTTPException(404, "Table not found")
    cols = [
        ColumnInfo(
            name=c["name"],
            type=str(c["type"]),
            nullable=c["nullable"],
            default=c.get("default"),
            primary_key=c.get("primary_key", False),
        )
        for c in insp.get_columns(table_name)
    ]
    return TableInfo(name=table_name, columns=cols)

@app.get("/tables/{table_name}/relationships", response_model=TableRelationships)
def table_relationships(table_name: str):
    insp = get_db_inspector()
    if not insp.has_table(table_name):
        raise HTTPException(404, "Table not found")
    fks = insp.get_foreign_keys(table_name)
    rels = [
        RelationshipInfo(
            local_column=fk["constrained_columns"][0],
            remote_table=fk["referred_table"],
            remote_column=fk["referred_columns"][0],
            on_delete=fk.get("options", {}).get("ondelete"),
        )
        for fk in fks
    ]
    return TableRelationships(name=table_name, relationships=rels)

###############################################################################
# MCP server definition (FIXED)
###############################################################################
mcp_server = Server("dbExplorer")

@mcp_server.list_tools()
async def list_mcp_tools() -> List[Tool]:
    """List available MCP tools"""
    return [
        Tool(
            name="list_tables",
            description="List every table in the database",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="describe_table",
            description="Get column details for a specific table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Name of the table"}
                },
                "required": ["table_name"],
            },
        ),
        Tool(
            name="table_relationships",
            description="Get foreign-key relationships for a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Name of the table"}
                },
                "required": ["table_name"],
            },
        ),
        Tool(
            name="query_sample",
            description="Get sample data from a table (max 10 rows)",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Name of the table"},
                    "limit": {"type": "integer", "description": "Number of rows (max 10)", "default": 5, "maximum": 10}
                },
                "required": ["table_name"],
            },
        ),
    ]

@mcp_server.call_tool()
async def call_mcp_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle MCP tool calls"""
    try:
        if name == "list_tables":
            insp = get_db_inspector()
            tables = insp.get_table_names()
            return [TextContent(type="text", text="\n".join(tables))]

        elif name == "describe_table":
            table = arguments["table_name"]
            info = describe_table(table)
            return [TextContent(type="text", text=info.model_dump_json(indent=2))]

        elif name == "table_relationships":
            table = arguments["table_name"]
            rels = table_relationships(table)
            return [TextContent(type="text", text=rels.model_dump_json(indent=2))]

        elif name == "query_sample":
            table_name = arguments["table_name"]
            limit = min(arguments.get("limit", 5), 10)  # Cap at 10

            insp = get_db_inspector()
            if not insp.has_table(table_name):
                return [TextContent(type="text", text=f"Table '{table_name}' not found")]

            # Execute sample query
            with engine.connect() as conn:
                # Use SQLAlchemy's text() for raw SQL
                from sqlalchemy import text
                result = conn.execute(text(f'SELECT * FROM "{table_name}" LIMIT :limit'), {"limit": limit})
                rows = result.fetchall()
                columns = result.keys()

                if not rows:
                    return [TextContent(type="text", text=f"Table '{table_name}' is empty")]

                # Convert to list of dicts
                data = [dict(zip(columns, row)) for row in rows]
                import json
                return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        # In MCP mode, we can't use logger, so we return the error as text
        return [TextContent(type="text", text=f"Error: {str(e)}")]

###############################################################################
# Main execution modes
###############################################################################
async def run_mcp_stdio():
    """Run MCP server via stdio (for LLM integration)"""
    # Don't use logging in MCP mode - it interferes with stdin/stdout protocol
    try:
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options()
            )
    except Exception as e:
        # Can't use logger here, but we can write to stderr
        import sys
        print(f"MCP server error: {e}", file=sys.stderr)
        raise

def run_fastapi():
    """Run FastAPI server (for direct HTTP access)"""
    uvicorn.run(app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    import sys

    # Check if we should run in MCP stdio mode or FastAPI mode
    if len(sys.argv) > 1 and sys.argv[1] == "--mcp":
        # CRITICAL: Disable ALL logging in MCP mode to avoid stdin/stdout interference
        logging.getLogger().setLevel(logging.CRITICAL)

        # Run as MCP stdio server
        asyncio.run(run_mcp_stdio())
    else:
        # Run as FastAPI server
        logger.info("Starting FastAPI server on http://127.0.0.1:8000")
        logger.info("For MCP stdio mode, run with: python db_tools.py --mcp")
        run_fastapi()

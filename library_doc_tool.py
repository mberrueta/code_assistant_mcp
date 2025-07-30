"""A tool for fetching library documentation."""
import httpx
from bs4 import BeautifulSoup
from langchain_community.document_loaders import PyPDFLoader
import tempfile
import os
import asyncio
import sys
import logging
from typing import List, Dict, Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


def get_library_documentation(library_name: str) -> str:
    """Fetches the documentation for a given library.

    Args:
        library_name: The name of the library.

    Returns:
        The documentation as a string, or an error message if the documentation could not be fetched.
    """
    try:
        # For this example, we'll fetch documentation from pypi.org.
        # This could be adapted to other documentation sources.
        url = f"https://pypi.org/project/{library_name}/"
        response = httpx.get(url)
        response.raise_for_status()

        if "application/pdf" in response.headers.get("Content-Type", ""):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                temp_pdf.write(response.content)
                temp_pdf_path = temp_pdf.name
            
            loader = PyPDFLoader(temp_pdf_path)
            documents = loader.load()
            os.remove(temp_pdf_path)
            return "\n".join([doc.page_content for doc in documents])

        soup = BeautifulSoup(response.text, "html.parser")

        # Find the project description, which usually contains the README content.
        project_description = soup.find("div", id="description")

        if project_description:
            return project_description.get_text()
        else:
            return f"Could not find documentation for {library_name} on PyPI."

    except httpx.HTTPStatusError as e:
        return f"Could not fetch documentation for {library_name}. Status code: {e.response.status_code}"
    except Exception as e:
        return f"An error occurred: {e}"

mcp_server = Server("library_doc")

@mcp_server.list_tools()
async def list_mcp_tools() -> List[Tool]:
    """List available MCP tools"""
    return [
        Tool(
            name="get_library_documentation",
            description="Fetches the documentation for a given library.",
            inputSchema={
                "type": "object",
                "properties": {
                    "library_name": {"type": "string", "description": "The name of the library to get documentation for."}
                },
                "required": ["library_name"],
            },
        )
    ]

@mcp_server.call_tool()
async def call_mcp_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle MCP tool calls"""
    try:
        if name == "get_library_documentation":
            result = get_library_documentation(arguments["library_name"])
            return [TextContent(type="text", text=result)]
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def run_mcp_stdio():
    """Run MCP server via stdio (for LLM integration)"""
    try:
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options()
            )
    except Exception as e:
        print(f"MCP server error: {e}", file=sys.stderr)
        raise

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--mcp":
        logging.getLogger().setLevel(logging.CRITICAL)
        asyncio.run(run_mcp_stdio())
    else:
        print("This tool is meant to be run with the --mcp flag.")
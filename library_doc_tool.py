"""A tool for fetching library documentation."""
import httpx
from bs4 import BeautifulSoup
from langchain_community.document_loaders import PyPDFLoader
import tempfile
import os
from mcp import Tool, main
from pydantic import Field


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

class LibraryDocTool(Tool):
    """A tool for fetching library documentation."""

    name = "library_doc"

    def get_library_documentation(self, library_name: str = Field(..., description="The name of the library to get documentation for.")):
        """Fetches the documentation for a given library."""
        return get_library_documentation(library_name)

if __name__ == "__main__":
    main(LibraryDocTool)

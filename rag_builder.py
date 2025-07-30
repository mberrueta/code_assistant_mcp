import argparse
import os
import sys
import httpx
import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer



def fetch_page(url: str) -> str:
    """Fetches the content of a single page."""
    try:
        response = httpx.get(url)
        response.raise_for_status()
        return response.text
    except httpx.HTTPStatusError as e:
        print(f"HTTP error occurred: {e}", file=sys.stderr)
        return ""
    except httpx.RequestError as e:
        print(f"An error occurred while requesting {url}: {e}", file=sys.stderr)
        return ""

def save_documentation(pages: dict[str, str], library_name: str, version: str, output_dir: str = "rag_store"):
    """Saves the documentation pages to local files."""
    if not pages:
        print("No content to save.", file=sys.stderr)
        return

    store_path = os.path.join(output_dir, library_name, version)
    os.makedirs(store_path, exist_ok=True)

    for page_name, content in pages.items():
        try:
            # Sanitize page_name to be a valid filename
            sanitized_page_name = page_name.replace('/', '_') + ".html"
            file_path = os.path.join(store_path, sanitized_page_name)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Documentation saved to {file_path}")
        except IOError as e:
            print(f"Error writing to file {file_path}: {e}", file=sys.stderr)

def extract_text_from_html(html_content: str) -> str:
    """Extracts clean text from HTML content, focusing on the main content area."""
    soup = BeautifulSoup(html_content, 'lxml')
    # Target the main content div based on inspection of hexdocs.pm HTML
    main_content_div = soup.find('div', id='content', class_='content-inner')
    if main_content_div:
        # Remove script and style elements to clean up text
        for script_or_style in main_content_div(['script', 'style']):
            script_or_style.extract()
        return main_content_div.get_text(separator=' ', strip=True)
    return ""

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Splits text into chunks with optional overlap."""
    chunks = []
    words = text.split()
    if not words: return []

    current_chunk = []
    for word in words:
        current_chunk.append(word)
        if len(current_chunk) >= chunk_size:
            chunks.append(" ".join(current_chunk))
            current_chunk = current_chunk[chunk_size - overlap:]
    if current_chunk: # Add any remaining words as the last chunk
        chunks.append(" ".join(current_chunk))
    return chunks

def process_and_store_docs(library_name: str, version: str, output_dir: str = "rag_store"):
    """Processes saved HTML files, extracts text, chunks it, and stores in FAISS."""
    model = SentenceTransformer('all-MiniLM-L6-v2')

    docs_path = os.path.join(output_dir, library_name, version)
    if not os.path.exists(docs_path):
        print(f"Documentation directory not found: {docs_path}", file=sys.stderr)
        return

    all_chunks = []
    all_metadatas = []

    for filename in os.listdir(docs_path):
        if filename.endswith(".html"):
            file_path = os.path.join(docs_path, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            clean_text = extract_text_from_html(html_content)
            if not clean_text: continue

            chunks = chunk_text(clean_text)
            if not chunks: continue

            for chunk in chunks:
                all_chunks.append(chunk)
                all_metadatas.append({
                    "source": filename,
                    "library": library_name,
                    "version": version
                })

    if not all_chunks:
        print("No chunks to process.", file=sys.stderr)
        return

    print(f"Generating embeddings for {len(all_chunks)} chunks...")
    embeddings = model.encode(all_chunks)
    embeddings = np.array(embeddings).astype('float32')

    # Create FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)  # L2 distance for similarity search
    index.add(embeddings)

    # Save FAISS index and documents
    faiss_index_path = os.path.join(docs_path, "index.faiss")
    faiss.write_index(index, faiss_index_path)
    print(f"FAISS index saved to {faiss_index_path}")

    documents_path = os.path.join(docs_path, "documents.json")
    with open(documents_path, "w", encoding="utf-8") as f:
        json.dump({"chunks": all_chunks, "metadatas": all_metadatas}, f, indent=2)
    print(f"Documents saved to {documents_path}")

def get_latest_version(library_name: str) -> str:
    """Fetches the latest version of the library from hexdocs.pm."""
    url = f"https://hexdocs.pm/{library_name}/readme.html"
    content = fetch_page(url)
    if not content:
        raise ValueError(f"Failed to fetch main page for {library_name} to determine latest version.")

    soup = BeautifulSoup(content, 'lxml')

    # Try to find version from dropdown (for older ExDoc versions)
    version_select = soup.find('select', class_='sidebar-projectVersionsDropdown')
    if version_select:
        selected_option = version_select.find('option', selected=True)
        if selected_option and selected_option.has_attr('value'):
            version_url = selected_option['value']
            match = re.search(r'/([0-9]+\.[0-9]+\.[0-9a-zA-Z\-.]+)/readme.html', version_url)
            if match:
                return match.group(1)

    # Try to find version from direct div (for newer ExDoc versions)
    version_div = soup.find('div', class_='sidebar-projectVersion')
    if version_div:
        version_text = version_div.get_text(strip=True)
        # Remove 'v' prefix if present
        if version_text.startswith('v'):
            return version_text[1:]
        return version_text

    raise ValueError(f"Could not determine latest version for {library_name}.")

def main():
    """
    Main function to fetch and save Elixir library documentation, including linked pages.
    """
    parser = argparse.ArgumentParser(description="Fetch and save Elixir library documentation.")
    parser.add_argument("library", help="The name of the Elixir library (e.g., 'jason').")
    parser.add_argument("version", nargs='?', help="The version of the library (e.g., '1.4.3'). Optional, will fetch latest if not provided.")
    parser.add_argument("--output-dir", default="rag_store", help="The directory to store the documentation in.")
    args = parser.parse_args()

    library_name = args.library
    version = args.version

    if version is None:
        print(f"Version not provided. Attempting to find latest version for {library_name}...")
        try:
            version = get_latest_version(library_name)
            print(f"Detected latest version: {version}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    base_url = f"https://hexdocs.pm/{library_name}/{version}/"
    readme_url = urljoin(base_url, "readme.html")

    fetched_pages = {}

    readme_content = fetch_page(readme_url)
    if not readme_content:
        print(f"Failed to fetch the main readme page from {readme_url}", file=sys.stderr)
        sys.exit(1)

    fetched_pages["readme"] = readme_content
    print(f"Fetched readme.html")

    soup = BeautifulSoup(readme_content, 'lxml')
    sidebar_script = soup.find('script', src=re.compile(r"sidebar_items-.*\.js"))

    if not sidebar_script:
        print("Could not find sidebar_items.js script in the page.", file=sys.stderr)
        sys.exit(1)

    sidebar_url = urljoin(base_url, sidebar_script['src'])

    sidebar_content = fetch_page(sidebar_url)
    if not sidebar_content:
        print(f"Failed to fetch sidebar content from {sidebar_url}", file=sys.stderr)
        sys.exit(1)

    try:
        # The file is a JS file, but it contains a single JSON object.
        # We need to strip the `sidebarNodes=` part at the beginning.
        json_content = sidebar_content.split("=", 1)[1]
        sidebar_data = json.loads(json_content)
        links_to_fetch = {}
        for section_key in ["extras", "modules"]:
            for item in sidebar_data.get(section_key, []):
                page_id = item['id']
                # Hexdocs uses .html for pages, but the ID might not include it
                page_name = page_id + ".html" if not page_id.endswith(".html") else page_id

                # Exclude API Reference and Changelog as requested
                if 'api-reference' not in page_name and 'changelog' not in page_name:
                    full_url = urljoin(base_url, page_name)
                    links_to_fetch[page_id] = full_url # Use page_id as key for consistency

        for page_name, url in links_to_fetch.items():
            content = fetch_page(url)
            if content:
                fetched_pages[page_name] = content
                print(f"Fetched {page_name}.html")

    except (json.JSONDecodeError, IndexError):
        print("Failed to decode JSON from sidebar script.", file=sys.stderr)
        sys.exit(1)

    if fetched_pages:
        save_documentation(fetched_pages, library_name, version, args.output_dir)

    # Process and store the documentation
    process_and_store_docs(library_name, version, args.output_dir)

if __name__ == "__main__":
    main()

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
import chromadb
import psycopg2
from psycopg2.extras import execute_values
from pgvector.psycopg2 import register_vector

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
    main_content_div = soup.find('div', id='content', class_='content-inner')
    if main_content_div:
        for script_or_style in main_content_div(['script', 'style']):
            script_or_style.extract()
        return main_content_div.get_text(separator=' ', strip=True)
    return ""

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Splits text into chunks with optional overlap."""
    words = text.split()
    if not words:
        return []
    chunks = []
    current_pos = 0
    while current_pos < len(words):
        end_pos = current_pos + chunk_size
        chunk = words[current_pos:end_pos]
        chunks.append(" ".join(chunk))
        current_pos += chunk_size - overlap
    return chunks

def get_db_backend():
    """Returns the database backend specified by the DB_BACKEND environment variable."""
    return os.environ.get("RAG_DB_BACKEND", "faiss")

def process_and_store_docs(library_name: str, version: str, output_dir: str = "rag_store"):
    """Processes saved HTML files, extracts text, chunks it, and stores in the selected backend."""
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
            if not clean_text:
                continue
            chunks = chunk_text(clean_text)
            if not chunks:
                continue
            for chunk in chunks:
                all_chunks.append(chunk)
                all_metadatas.append({"source": filename, "library": library_name, "version": version})

    if not all_chunks:
        print("No chunks to process.", file=sys.stderr)
        return

    print(f"Generating embeddings for {len(all_chunks)} chunks...")
    embeddings = model.encode(all_chunks)
    db_backend = get_db_backend()
    print(f"Using backend: {db_backend}")

    if db_backend == "faiss":
        store_faiss(embeddings, all_chunks, all_metadatas, docs_path)
    elif db_backend == "chromadb":
        store_chromadb(embeddings, all_chunks, all_metadatas, library_name, version)
    elif db_backend == "pgvector":
        store_pgvector(embeddings, all_chunks, all_metadatas, library_name, version)
    else:
        print(f"Unknown backend: {db_backend}", file=sys.stderr)

def store_faiss(embeddings, chunks, metadatas, docs_path):
    """Stores embeddings, chunks, and metadatas in FAISS."""
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings).astype('float32'))
    faiss_index_path = os.path.join(docs_path, "index.faiss")
    faiss.write_index(index, faiss_index_path)
    print(f"FAISS index saved to {faiss_index_path}")
    documents_path = os.path.join(docs_path, "documents.json")
    with open(documents_path, "w", encoding="utf-8") as f:
        json.dump({"chunks": chunks, "metadatas": metadatas}, f, indent=2)
    print(f"Documents saved to {documents_path}")

def store_chromadb(embeddings, chunks, metadatas, library_name, version):
    """Stores embeddings, chunks, and metadatas in ChromaDB."""
    client = chromadb.HttpClient(host='localhost', port=8000)
    collection_name = f"{library_name}_{version}".replace('.', '_')
    collection = client.get_or_create_collection(name=collection_name)
    ids = [f"doc_{i}" for i in range(len(chunks))]
    collection.add(embeddings=embeddings.tolist(), documents=chunks, metadatas=metadatas, ids=ids)
    print(f"Data stored in ChromaDB collection: {collection_name}")

def store_pgvector(embeddings, chunks, metadatas, library_name, version):
    """Stores embeddings, chunks, and metadatas in pgvector."""
    conn = psycopg2.connect(os.environ.get("RAG_DATABASE_URL", "dbname=postgres user=postgres password=postgres host=localhost port=5433"))
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()

        register_vector(conn)

        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    library_name VARCHAR(255),
                    version VARCHAR(255),
                    source VARCHAR(255),
                    content TEXT,
                    embedding vector(384)
                );
            """)
            table_data = []
            for i, chunk in enumerate(chunks):
                table_data.append((library_name, version, metadatas[i]['source'], chunk, embeddings[i]))
            execute_values(cur, "INSERT INTO documents (library_name, version, source, content, embedding) VALUES %s", table_data)
        conn.commit()
        print("Data stored in pgvector.")
    finally:
        conn.close()

def get_latest_version(library_name: str) -> str:
    """Fetches the latest version of the library from hexdocs.pm."""
    url = f"https://hexdocs.pm/{library_name}"
    content = fetch_page(url)
    if not content:
        raise ValueError(f"Failed to fetch main page for {library_name} to determine latest version.")
    soup = BeautifulSoup(content, 'lxml')
    version_select = soup.find('select', class_='sidebar-projectVersionsDropdown')
    if version_select:
        selected_option = version_select.find('option', selected=True)
        if selected_option and selected_option.has_attr('value'):
            version_url = selected_option['value']
            match = re.search(r'/([0-9]+\.[0-9]+\.[0-9a-zA-Z\-.]+)', version_url)
            if match:
                return match.group(1)
    version_div = soup.find('div', class_='sidebar-projectVersion')
    if version_div:
        version_text = version_div.get_text(strip=True)
        if version_text.startswith('v'):
            return version_text[1:]
        return version_text
    raise ValueError(f"Could not determine latest version for {library_name}.")

def query_docs(library_name: str, version: str, query: str, output_dir: str = "rag_store", k: int = 5):
    """Queries the selected backend for a given library and version."""
    model = SentenceTransformer('all-MiniLM-L6-v2')
    query_embedding = model.encode([query])
    db_backend = get_db_backend()

    if db_backend == "faiss":
        query_faiss(library_name, version, query_embedding, output_dir, k)
    elif db_backend == "chromadb":
        query_chromadb(library_name, version, query_embedding, k)
    elif db_backend == "pgvector":
        query_pgvector(library_name, version, query_embedding, k)
    else:
        print(f"Unknown backend: {db_backend}", file=sys.stderr)

def query_faiss(library_name, version, query_embedding, output_dir, k):
    """Queries FAISS for the given query embedding."""
    docs_path = os.path.join(output_dir, library_name, version)
    if not os.path.exists(docs_path):
        print(f"Documentation directory not found: {docs_path}", file=sys.stderr)
        sys.exit(1)
    faiss_index_path = os.path.join(docs_path, "index.faiss")
    documents_path = os.path.join(docs_path, "documents.json")
    if not os.path.exists(faiss_index_path) or not os.path.exists(documents_path):
        print(f"FAISS index or documents not found in {docs_path}", file=sys.stderr)
        sys.exit(1)
    index = faiss.read_index(faiss_index_path)
    with open(documents_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        chunks = data["chunks"]
        metadatas = data["metadatas"]
    distances, indices = index.search(np.array(query_embedding).astype('float32'), k)
    print_results(distances[0], indices[0], chunks, metadatas)

def query_chromadb(library_name, version, query_embedding, k):
    """Queries ChromaDB for the given query embedding."""
    client = chromadb.HttpClient(host='localhost', port=8000)
    collection_name = f"{library_name}_{version}".replace('.', '_')
    collection = client.get_collection(name=collection_name)
    results = collection.query(query_embeddings=query_embedding.tolist(), n_results=k)
    print_chromadb_results(results)

def query_pgvector(library_name, version, query_embedding, k):
    """Queries pgvector for the given query embedding."""
    conn = psycopg2.connect(os.environ.get("RAG_DATABASE_URL", "dbname=postgres user=postgres password=postgres host=localhost port=5433"))
    cur = conn.cursor()
    cur.execute(
        "SELECT source, content, embedding <-> %s AS distance FROM documents WHERE library_name = %s AND version = %s ORDER BY distance LIMIT %s",
        (query_embedding[0].tolist(), library_name, version, k)
    )
    results = cur.fetchall()
    cur.close()
    conn.close()
    print_pgvector_results(results)

def print_results(distances, indices, chunks, metadatas):
    """Prints the results from a FAISS search."""
    print("\n" + "="*20)
    print(f"Top {len(indices)} results")
    print("="*20)
    for i, idx in enumerate(indices):
        if idx < 0:
            continue
        print("-" * 20)
        print(f"Result {i+1} (distance: {distances[i]:.4f}):")
        print(f"Source: {metadatas[idx]['source']}")
        print("\nContent:")
        print(chunks[idx])
    print("-" * 20)

def print_chromadb_results(results):
    """Prints the results from a ChromaDB search."""
    print("\n" + "="*20)
    print(f"Top {len(results['ids'][0])} results")
    print("="*20)
    for i, doc_id in enumerate(results['ids'][0]):
        print("-" * 20)
        print(f"Result {i+1} (distance: {results['distances'][0][i]:.4f}):")
        print(f"Source: {results['metadatas'][0][i]['source']}")
        print("\nContent:")
        print(results['documents'][0][i])
    print("-" * 20)

def print_pgvector_results(results):
    """Prints the results from a pgvector search."""
    print("\n" + "="*20)
    print(f"Top {len(results)} results")
    print("="*20)
    for i, row in enumerate(results):
        print("-" * 20)
        print(f"Result {i+1} (distance: {row[2]:.4f}):")
        print(f"Source: {row[0]}")
        print("\nContent:")
        print(row[1])
    print("-" * 20)

def handle_check_chroma(args):
    """Handles the check_chroma command."""
    client = chromadb.HttpClient(host='localhost', port=8000)
    if args.collection_name:
        try:
            collection = client.get_collection(name=args.collection_name)
            count = collection.count()
            print(f"Collection '{args.collection_name}' has {count} items.")
            items = collection.get(limit=5, include=["metadatas", "documents"])
            print("\nFirst 5 items:")
            print(items)
        except ValueError:
            print(f"Collection '{args.collection_name}' not found.", file=sys.stderr)
    else:
        collections = client.list_collections()
        print("Available collections:")
        for collection in collections:
            print(f"- {collection.name}")

def main():
    """
    Main function to fetch, save, and query Elixir library documentation.
    """
    parser = argparse.ArgumentParser(description="Fetch, process, and query Elixir library documentation for RAG.")
    parser.set_defaults(func=lambda args: parser.print_help())
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    parser_build = subparsers.add_parser("build", help="Fetch and build the documentation index.")
    parser_build.add_argument("library", help="The name of the Elixir library (e.g., 'jason').")
    parser_build.add_argument("version", nargs='?', help="The version of the library. Fetches latest if not provided.")
    parser_build.add_argument("--output-dir", default="rag_store", help="The directory to store the documentation in.")
    parser_build.set_defaults(func=handle_build)

    parser_query = subparsers.add_parser("query", help="Query the documentation index.")
    parser_query.add_argument("library", help="The name of the library to query.")
    parser_query.add_argument("query_string", help="The search query.")
    parser_query.add_argument("--version", help="The version of the library. Uses latest found locally if not provided.")
    parser_query.add_argument("--output-dir", default="rag_store", help="The directory where documentation is stored.")
    parser_query.add_argument("-k", "--top-k", type=int, default=5, help="Number of results to return.")
    parser_query.set_defaults(func=handle_query)

    parser_check_chroma = subparsers.add_parser("check_chroma", help="Check the status of the ChromaDB database.")
    parser_check_chroma.add_argument("collection_name", nargs='?', help="The name of the collection to inspect.")
    parser_check_chroma.set_defaults(func=handle_check_chroma)

    args = parser.parse_args()
    args.func(args)

def handle_build(args):
    library_name = args.library
    version = args.version
    output_dir = args.output_dir

    if version is None:
        print(f"Version not provided. Attempting to find latest version for {library_name}...")
        try:
            version = get_latest_version(library_name)
            print(f"Detected latest version: {version}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    docs_path = os.path.join(output_dir, library_name, version)
    if not os.path.exists(docs_path):
        base_url = f"https://hexdocs.pm/{library_name}/{version}/"
        fetched_pages = {}
        
        # Initial fetch, which might be a redirect page
        initial_content = fetch_page(base_url)
        if not initial_content:
            print(f"Failed to fetch the main page from {base_url}", file=sys.stderr)
            sys.exit(1)

        soup = BeautifulSoup(initial_content, 'lxml')
        
        # Handle meta refresh redirect
        meta_refresh = soup.find("meta", attrs={"http-equiv": "refresh"})
        if meta_refresh:
            redirect_url_part = meta_refresh['content'].split('url=')[1]
            redirect_url = urljoin(base_url, redirect_url_part)
            print(f"Redirecting to {redirect_url}")
            readme_content = fetch_page(redirect_url)
            if not readme_content:
                print(f"Failed to fetch the redirected page from {redirect_url}", file=sys.stderr)
                sys.exit(1)
            # Update base_url to the redirected path if the redirect is relative
            if not redirect_url.endswith('/'):
                base_url = os.path.dirname(redirect_url) + '/'

        else:
            readme_content = initial_content

        fetched_pages["readme"] = readme_content
        print(f"Fetched initial page.")

        soup = BeautifulSoup(readme_content, 'lxml')
        
        # Try to find sidebar.js first
        sidebar_script = soup.find('script', src=re.compile(r"sidebar_items-.*\.js"))
        if sidebar_script:
            sidebar_url = urljoin(base_url, sidebar_script['src'])
            sidebar_content = fetch_page(sidebar_url)
            if sidebar_content:
                try:
                    json_content = sidebar_content.split("=", 1)[1]
                    sidebar_data = json.loads(json_content)
                    links_to_fetch = {}
                    for section_key in ["extras", "modules"]:
                        for item in sidebar_data.get(section_key, []):
                            page_id = item['id']
                            page_name = page_id + ".html" if not page_id.endswith(".html") else page_id
                            if 'api-reference' not in page_name and 'changelog' not in page_name:
                                full_url = urljoin(base_url, page_name)
                                links_to_fetch[page_id] = full_url
                    for page_id, url in links_to_fetch.items():
                        content = fetch_page(url)
                        if content:
                            fetched_pages[page_id] = content
                            print(f"Fetched {page_id}.html")
                except (json.JSONDecodeError, IndexError):
                    print("Failed to decode JSON from sidebar script, proceeding with readme only.", file=sys.stderr)
            else:
                print(f"Failed to fetch sidebar content from {sidebar_url}, proceeding with readme only.", file=sys.stderr)
        else:
            # Fallback to tab-based navigation
            print("Could not find sidebar_items.js, falling back to tab-based navigation.")
            nav_list = soup.find('ul', id='sidebar-list-nav')
            if nav_list:
                links_to_fetch = {}
                tab_buttons = nav_list.find_all('button')
                for button in tab_buttons:
                    panel_id = button.get('aria-controls')
                    if panel_id:
                        panel = soup.find(id=panel_id)
                        if panel:
                            for link in panel.find_all('a', href=True):
                                href = link['href']
                                link_text = link.get_text(strip=True).lower()
                                if 'changelog' not in link_text and 'api-reference' not in href:
                                    page_id = href.replace('.html', '')
                                    full_url = urljoin(base_url, href)
                                    links_to_fetch[page_id] = full_url
                
                for page_id, url in links_to_fetch.items():
                    if page_id not in fetched_pages:
                        content = fetch_page(url)
                        if content:
                            fetched_pages[page_id] = content
                            print(f"Fetched {page_id}.html")
            else:
                print("Could not find sidebar navigation tabs.", file=sys.stderr)

        if fetched_pages:
            save_documentation(fetched_pages, library_name, version, output_dir)
    else:
        print(f"Documentation for {library_name} {version} already exists. Skipping download.")

    process_and_store_docs(library_name, version, output_dir)

def handle_query(args):
    library_name = args.library
    version = args.version
    output_dir = args.output_dir
    db_backend = get_db_backend()

    if version is None and db_backend == "faiss":
        library_path = os.path.join(output_dir, library_name)
        if not os.path.exists(library_path) or not os.path.isdir(library_path):
            print(f"No documentation found for library '{library_name}' in {output_dir}", file=sys.stderr)
            sys.exit(1)
        available_versions = [d for d in os.listdir(library_path) if os.path.isdir(os.path.join(library_path, d))]
        if not available_versions:
            print(f"No built versions found for library '{library_name}' in {library_path}", file=sys.stderr)
            sys.exit(1)
        available_versions.sort(key=lambda v: list(map(int, re.findall(r'\d+', v))), reverse=True)
        version = available_versions[0]
        print(f"No version specified, using latest found locally: {version}")
    elif version is None:
        print("Version must be specified for chromadb and pgvector backends.", file=sys.stderr)
        sys.exit(1)

    query_docs(library_name, version, args.query_string, output_dir, args.top_k)

if __name__ == "__main__":
    main()
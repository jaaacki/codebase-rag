# github_utils.py with Qdrant support and fixed dimensions
import os
import streamlit as st
import tempfile
import time
import gc  # For garbage collection
import psutil  # To monitor memory usage
from git import Repo
from langchain.schema import Document
from langchain_community.embeddings import HuggingFaceEmbeddings, OpenAIEmbeddings
from langchain.vectorstores import Qdrant

# Qdrant URL from environment or Docker service name
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")

from embedding_utils import get_embeddings
from chunk_utils import smart_code_chunking

# Default supported file extensions and ignored directories
DEFAULT_SUPPORTED_EXTENSIONS = {'.py', '.js', '.tsx', '.jsx', '.ipynb', '.java',
                                '.cpp', '.ts', '.go', '.rs', '.vue', '.swift', '.c', '.h'}
DEFAULT_IGNORED_DIRS = {'node_modules', 'venv', 'env', 'dist', 'build', '.git',
                        '__pycache__', '.next', '.vscode', 'vendor'}

def get_file_content(file_path, repo_path):
    """Extract content from a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        rel_path = os.path.relpath(file_path, repo_path)
        return {"name": rel_path, "content": content}
    except Exception as e:
        st.error(f"Error processing file {file_path}: {e}")
        return None


def scan_repository_files(repo_path, supported_extensions=None, ignored_dirs=None):
    """Scan repository and return list of files matching criteria"""
    if supported_extensions is None:
        supported_extensions = DEFAULT_SUPPORTED_EXTENSIONS
    if ignored_dirs is None:
        ignored_dirs = DEFAULT_IGNORED_DIRS

    file_list = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith('.')]
        for file in files:
            if os.path.splitext(file)[1] in supported_extensions:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_path)
                try:
                    size_kb = os.path.getsize(full_path) / 1024
                except:
                    size_kb = 0
                file_list.append({
                    "path": rel_path,
                    "size_kb": round(size_kb, 2),
                    "ext": os.path.splitext(file)[1]
                })
    return file_list


def get_selected_files_content(repo_path, selected_files):
    """Extract content from selected files"""
    contents = []
    for path in selected_files:
        full = os.path.join(repo_path, path)
        item = get_file_content(full, repo_path)
        if item:
            contents.append(item)
    return contents


def clone_repository(repo_url, temp_dir):
    """Clone a GitHub repository into a temp directory"""
    try:
        repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
        target = os.path.join(temp_dir, repo_name)
        Repo.clone_from(repo_url, target)
        return target
    except Exception as e:
        st.error(f"Error cloning repository: {e}")
        return None


def get_langchain_embeddings():
    """Select embedding model from Streamlit secrets"""
    provider = st.secrets.get("EMBEDDING_PROVIDER", "openai").lower()
    model = st.secrets.get("EMBEDDING_MODEL", "text-embedding-3-large")
    if provider == "openai":
        return OpenAIEmbeddings(model=model, openai_api_key=st.secrets["OPENAI_API_KEY"])
    elif provider == "huggingface":
        hf_model = "all-mpnet-base-v2" if model == "text-embedding-3-large" else model
        return HuggingFaceEmbeddings(model_name=hf_model)
    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")


def get_embedding_dimensions(embed):
    """Get the dimensions of the embedding model"""
    if isinstance(embed, OpenAIEmbeddings):
        # Get model name
        model_name = embed.model if hasattr(embed, 'model') else st.secrets.get("EMBEDDING_MODEL", "text-embedding-3-large")
        
        # Determine dimensions based on the model name
        if "text-embedding-3-large" in model_name:
            return 3072
        elif "text-embedding-3-small" in model_name:
            return 1536
        elif "text-embedding-ada-002" in model_name:
            return 1536
        else:
            # Default fallback dimension for older OpenAI models
            return 1536
    elif isinstance(embed, HuggingFaceEmbeddings):
        # For HuggingFace, we can try to get dimensions from the model
        if hasattr(embed, 'client') and hasattr(embed.client, 'get_sentence_embedding_dimension'):
            return embed.client.get_sentence_embedding_dimension()
        
        # Default values for common HuggingFace models
        model_name = embed.model_name if hasattr(embed, 'model_name') else ""
        if "all-mpnet-base-v2" in model_name:
            return 768
        else:
            # Default fallback dimension for HuggingFace models
            return 768
    else:
        # Default fallback dimension
        return 1536


def chunk_text(text, max_chars=30000):
    """Fallback simpler chunking by char length"""
    if len(text) <= max_chars:
        return [text]
    lines = text.split('\n')
    chunks = []
    current = []
    count = 0
    for line in lines:
        l = len(line) + 1
        if count + l > max_chars and current:
            chunks.append('\n'.join(current))
            current, count = [], 0
        current.append(line)
        count += l
    if current:
        chunks.append('\n'.join(current))
    return chunks


def index_github_repo(repo_url, namespace, qdrant_client=None, pinecone_index=None, index_name="codebase-rag", batch_size=5, max_files=None, selected_files=None):
    """
    Index a GitHub repo into Qdrant via LangChain
    Now accepts qdrant_client parameter (first priority) or pinecone_index (backwards compatibility)
    """
    try:
        if "repository_added" not in st.session_state:
            st.session_state.repository_added = False

        # If no qdrant_client is provided but we have a pinecone_index that's actually a Qdrant client
        if qdrant_client is None and isinstance(pinecone_index, object) and hasattr(pinecone_index, 'get_collections'):
            qdrant_client = pinecone_index
            
        # Make sure we have a Qdrant client
        if qdrant_client is None:
            from qdrant_client import QdrantClient
            qdrant_client = QdrantClient(url=QDRANT_URL)

        col1, _ = st.columns([1, 0.01])
        with col1:
            progress_text = st.empty()
            progress_bar = st.progress(0.0)
            mem_text = st.empty()

            def log_mem():
                mb = psutil.Process(os.getpid()).memory_info().rss / 1024**2
                mem_text.text(f"Memory: {mb:.1f} MB")
                return mb

            with tempfile.TemporaryDirectory() as tmp:
                # Step 1: Clone
                progress_text.text("Step 1/5: Cloning...")
                progress_bar.progress(0.1)
                log_mem()
                repo_path = clone_repository(repo_url, tmp)
                progress_bar.progress(0.2)
                if not repo_path:
                    st.session_state.repository_added = False
                    return False, "Clone failed"

                # Step 2: Scan
                progress_text.text("Step 2/5: Scanning files...")
                progress_bar.progress(0.3)
                log_mem()
                if not selected_files:
                    flist = scan_repository_files(repo_path)
                    if max_files and len(flist) > max_files:
                        flist.sort(key=lambda x: x["size_kb"])
                        flist = flist[:max_files]
                    selected_files = [f["path"] for f in flist]

                # Step 3: Chunk
                progress_text.text(f"Step 3/5: Chunking {len(selected_files)} files...")
                progress_bar.progress(0.4)
                docs = []
                for i in range(0, len(selected_files), batch_size):
                    batch = selected_files[i:i+batch_size]
                    log_mem()
                    for item in get_selected_files_content(repo_path, batch):
                        for idx, ch in enumerate(smart_code_chunking(item["content"], max_tokens=250_000)):
                            meta = {"filepath": item["name"], "chunk_index": idx+1}
                            docs.append(Document(page_content=ch, metadata=meta))
                log_mem()

                # Step 4: Embed
                progress_text.text(f"Step 4/5: Embedding {len(docs)} chunks...")
                progress_bar.progress(0.7)
                log_mem()
                embed = get_langchain_embeddings()
                
                # Get the embedding dimensions based on the model
                embed_dimensions = get_embedding_dimensions(embed)
                st.info(f"Using embedding dimensions: {embed_dimensions}")

                # Step 5: Upload to Qdrant
                progress_text.text("Step 5/5: Uploading to Qdrant...")
                progress_bar.progress(0.8)
                log_mem()
                try:
                    # Try to create the collection first - silently ignore if it exists
                    try:
                        from qdrant_client.models import VectorParams, Distance
                        qdrant_client.create_collection(
                            collection_name=namespace,
                            vectors_config=VectorParams(size=embed_dimensions, distance=Distance.COSINE)
                        )
                    except Exception as e:
                        # Ignore errors if collection already exists
                        if "already exists" not in str(e):
                            st.warning(f"Note: {str(e)}")
                    
                    Qdrant.from_documents(
                        documents=docs,
                        embedding=embed,
                        url=QDRANT_URL,
                        prefer_grpc=False,
                        collection_name=namespace
                    )
                except Exception as e:
                    st.error(f"Error uploading to Qdrant: {str(e)}")
                    return False, f"Error indexing: {str(e)}"
                    
                progress_bar.progress(1.0)
                log_mem()

                # Done
                st.session_state.repository_added = True
                st.session_state.refresh_required = True
                st.session_state.refresh_message = f"Indexed {len(docs)} vectors to '{namespace}'"
                progress_text.empty()
                progress_bar.empty()
                mem_text.empty()
                gc.collect()

                return True, f"Indexed {len(docs)} vectors to '{namespace}'"

    except Exception as e:
        st.session_state.repository_added = False
        return False, f"Error indexing repository: {e}"
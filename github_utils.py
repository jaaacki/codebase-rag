# github_utils.py with file selection and improved memory management
import os
import streamlit as st
import tempfile
import time
import gc  # For garbage collection
import psutil  # To monitor memory usage
from git import Repo
from langchain.schema import Document
from langchain_community.embeddings import HuggingFaceEmbeddings, OpenAIEmbeddings
from langchain.vectorstores import Pinecone as LangchainPinecone
from embedding_utils import get_embeddings

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
        # Get relative path from repo root
        rel_path = os.path.relpath(file_path, repo_path)
        return {
            "name": rel_path,
            "content": content
        }
    except Exception as e:
        st.error(f"Error processing file {file_path}: {str(e)}")
        return None

def scan_repository_files(repo_path, supported_extensions=None, ignored_dirs=None):
    """Scan repository and return a list of files that match criteria"""
    if supported_extensions is None:
        supported_extensions = DEFAULT_SUPPORTED_EXTENSIONS
    if ignored_dirs is None:
        ignored_dirs = DEFAULT_IGNORED_DIRS
        
    file_list = []
    
    for root, dirs, files in os.walk(repo_path):
        # Skip ignored directories
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith('.')]
        
        # Process each file in current directory
        for file in files:
            if os.path.splitext(file)[1] in supported_extensions:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_path)
                
                # Get file size
                try:
                    size_kb = os.path.getsize(file_path) / 1024
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
    files_content = []
    for file_path in selected_files:
        full_path = os.path.join(repo_path, file_path)
        file_content = get_file_content(full_path, repo_path)
        if file_content:
            files_content.append(file_content)
    return files_content

def clone_repository(repo_url, temp_dir):
    """Clone a GitHub repository to a temporary directory"""
    try:
        # Extract repository name from URL
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        repo_path = os.path.join(temp_dir, repo_name)
        
        # Clone the repository
        Repo.clone_from(repo_url, repo_path)
        return repo_path
    except Exception as e:
        st.error(f"Error cloning repository: {str(e)}")
        return None

def get_langchain_embeddings():
    """Get the appropriate embedding model based on configuration"""
    provider = st.secrets.get("EMBEDDING_PROVIDER", "openai")
    model = st.secrets.get("EMBEDDING_MODEL", "text-embedding-3-large")
    
    if provider.lower() == "openai":
        return OpenAIEmbeddings(
            model=model,
            openai_api_key=st.secrets["OPENAI_API_KEY"]
        )
    elif provider.lower() == "huggingface":
        if model == "text-embedding-3-large":
            model = "all-mpnet-base-v2"  # Default fallback
        return HuggingFaceEmbeddings(model_name=model)
    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")

def chunk_text(text, max_chars=30000):
    """Split text into chunks of maximum size"""
    # If text is small enough, return as is
    if len(text) <= max_chars:
        return [text]
    
    # Split by newlines first to maintain code structure
    lines = text.split('\n')
    chunks = []
    current_chunk = ""
    
    for line in lines:
        # If adding this line would exceed max_chars, start a new chunk
        if len(current_chunk) + len(line) + 1 > max_chars:
            chunks.append(current_chunk)
            current_chunk = line + '\n'
        else:
            current_chunk += line + '\n'
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

def index_github_repo(repo_url, namespace, pinecone_client, pinecone_index, index_name="codebase-rag", batch_size=5, max_files=None, selected_files=None):
    """
    Index a GitHub repository in Pinecone
    
    Args:
        repo_url: URL of the GitHub repository
        namespace: Namespace to store vectors in Pinecone
        pinecone_client: Pinecone client
        pinecone_index: Pinecone index
        index_name: Pinecone index name
        batch_size: Number of files to process in each batch
        max_files: Maximum number of files to index (None for all)
        selected_files: List of specific files to index (None for automatic selection)
    """
    try:
        # Initialize session state variable if it doesn't exist
        if "repository_added" not in st.session_state:
            st.session_state.repository_added = False
            
        # Set up the progress container with consistent spacing
        col1, _ = st.columns([1, 0.01])  # Create a column for the progress UI
        with col1:
            # Create progress elements
            progress_text = st.empty()
            progress_bar = st.progress(0.0)
            memory_usage = st.empty()
            
            # Memory monitoring function
            def log_memory_usage():
                process = psutil.Process(os.getpid())
                memory_mb = process.memory_info().rss / 1024 / 1024
                memory_usage.text(f"Memory usage: {memory_mb:.2f} MB")
                return memory_mb
            
            # Create a temporary directory for cloning
            with tempfile.TemporaryDirectory() as temp_dir:
                # Step 1: Cloning repository
                progress_text.text("Step 1/5: Cloning repository...")
                progress_bar.progress(0.1)
                log_memory_usage()
                
                repo_path = clone_repository(repo_url, temp_dir)
                progress_bar.progress(0.2)
                
                if not repo_path:
                    st.session_state.repository_added = False
                    return False, "Failed to clone repository"
                
                # Step 2: Scanning repository files
                progress_text.text("Step 2/5: Scanning repository files...")
                progress_bar.progress(0.3)
                log_memory_usage()
                
                # If specific files weren't provided, scan and select files
                if not selected_files:
                    file_list = scan_repository_files(repo_path)
                    
                    # Limit files if max_files is set
                    if max_files and len(file_list) > max_files:
                        # Sort by size (smallest first) to prioritize smaller files
                        file_list.sort(key=lambda x: x["size_kb"])
                        file_list = file_list[:max_files]
                    
                    # Extract just the paths
                    selected_files = [f["path"] for f in file_list]
                
                progress_text.text(f"Step 3/5: Processing {len(selected_files)} files...")
                progress_bar.progress(0.4)
                
                # Process files in batches to manage memory
                all_documents = []
                total_batches = (len(selected_files) + batch_size - 1) // batch_size
                
                for batch_num, i in enumerate(range(0, len(selected_files), batch_size)):
                    batch_files = selected_files[i:i+batch_size]
                    progress_text.text(f"Processing batch {batch_num+1}/{total_batches} ({len(batch_files)} files)...")
                    progress_bar.progress(0.4 + 0.3 * (batch_num / total_batches))
                    
                    # Get content for this batch
                    batch_content = get_selected_files_content(repo_path, batch_files)
                    
                    # Convert to documents
                    batch_documents = []
                    for file in batch_content:
                        content = file['content']
                        content_chunks = chunk_text(content)
                        
                        for j, chunk in enumerate(content_chunks):
                            metadata = {
                                "filepath": file['name'],
                                "type": "file",
                                "name": file['name'],
                                "line_number": 1,
                                "chunk_number": j+1,
                                "total_chunks": len(content_chunks),
                                # Include shortened text in metadata
                                "text": chunk[:30000]
                            }
                            
                            doc = Document(
                                page_content=chunk,
                                metadata=metadata
                            )
                            batch_documents.append(doc)
                    
                    # Add this batch to the overall document list
                    all_documents.extend(batch_documents)
                    
                    # Log memory usage after batch
                    memory_mb = log_memory_usage()
                    
                    # Force garbage collection after each batch to free memory
                    batch_content = None
                    batch_documents = None
                    gc.collect()
                
                # Step 4: Creating embeddings
                progress_text.text(f"Step 4/5: Creating embeddings for {len(all_documents)} chunks...")
                progress_bar.progress(0.7)
                log_memory_usage()
                
                # Get the appropriate embedding model
                embedding_model = get_langchain_embeddings()
                
                # Step 5: Uploading to Pinecone
                progress_text.text(f"Step 5/5: Uploading vectors to Pinecone...")
                progress_bar.progress(0.8)
                
                # Create and store vectors
                vectorstore = LangchainPinecone.from_documents(
                    documents=all_documents,
                    embedding=embedding_model,
                    index_name=index_name,
                    namespace=namespace
                )
                
                progress_bar.progress(1.0)
                log_memory_usage()
                
                # Wait a moment to ensure the operation is reflected in Pinecone
                time.sleep(2)
                
                # Get index stats to confirm upload
                stats = pinecone_index.describe_index_stats()
                namespace_count = stats['namespaces'].get(namespace, {}).get('vector_count', 0)
                
                # Set success in session state
                st.session_state.repository_added = True
                
                # Set refresh flags in session state
                st.session_state.refresh_required = True
                st.session_state.refresh_message = f"Repository '{namespace}' has been successfully added with {namespace_count} vectors."
                
                # Clear progress UI at the end
                progress_text.empty()
                progress_bar.empty()
                memory_usage.empty()
                
                # Force garbage collection again
                all_documents = None
                vectorstore = None
                gc.collect()
                
                return True, f"Successfully indexed repository. {namespace_count} vectors added to namespace '{namespace}'."
                
    except Exception as e:
        st.session_state.repository_added = False
        return False, f"Error indexing repository: {str(e)}"

def show_repository_file_selection(repo_url, max_files=200):
    """
    THIS FUNCTION IS DEPRECATED - Use the version in repository_management.py instead
    
    This function has critical issues because it uses a temporary directory that gets
    deleted before the UI can interact with it. In a Streamlit app, the temp directory
    is deleted after the function returns, but before the user interacts with the UI.
    
    The proper approach is to split the clone and UI steps with session state in between.
    See the implementation in repository_management.py for the corrected version.
    """
    try:
        # Clone the repository first to scan its files
        with st.spinner("Cloning repository to scan files..."):
            with tempfile.TemporaryDirectory() as temp_dir:
                repo_path = clone_repository(repo_url, temp_dir)
                
                if not repo_path:
                    return None
                
                # Scan for files
                file_list = scan_repository_files(repo_path)
                
                # Store file list in session state for persistence
                st.session_state.repo_file_list = file_list
                
                # Return file list - but note this won't be useful for UI interaction
                # because the temp directory will be gone
                return [file["path"] for file in file_list]
        
    except Exception as e:
        st.error(f"Error scanning repository: {str(e)}")
        return None
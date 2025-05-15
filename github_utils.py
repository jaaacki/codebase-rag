# github_utils.py
import os
import streamlit as st
import tempfile
from git import Repo
from langchain.schema import Document
from langchain_community.embeddings import HuggingFaceEmbeddings, OpenAIEmbeddings
from langchain.vectorstores import Pinecone as LangchainPinecone
from embedding_utils import get_embeddings

# Supported file extensions and ignored directories
SUPPORTED_EXTENSIONS = {'.py', '.js', '.tsx', '.jsx', '.ipynb', '.java',
                       '.cpp', '.ts', '.go', '.rs', '.vue', '.swift', '.c', '.h'}

IGNORED_DIRS = {'node_modules', 'venv', 'env', 'dist', 'build', '.git',
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

def get_main_files_content(repo_path):
    """Extract content from all supported files in repository"""
    files_content = []
    try:
        for root, _, files in os.walk(repo_path):
            # Skip if current directory is in ignored directories
            if any(ignored_dir in root for ignored_dir in IGNORED_DIRS):
                continue
            # Process each file in current directory
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.splitext(file)[1] in SUPPORTED_EXTENSIONS:
                    file_content = get_file_content(file_path, repo_path)
                    if file_content:
                        files_content.append(file_content)
    except Exception as e:
        st.error(f"Error reading repository: {str(e)}")
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

def index_github_repo(repo_url, namespace, pinecone_client, pinecone_index, index_name="codebase-rag"):
    """Index a GitHub repository in Pinecone"""
    try:
        # Create a temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            # Show progress steps
            progress = st.progress(0)
            st.text("Step 1/4: Cloning repository...")
            
            repo_path = clone_repository(repo_url, temp_dir)
            progress.progress(25)
            
            if not repo_path:
                return False, "Failed to clone repository"
            
            st.text("Step 2/4: Extracting code files...")
            file_content = get_main_files_content(repo_path)
            progress.progress(50)
            
            if not file_content:
                return False, "No files found in repository"
            
            st.text(f"Step 3/4: Processing {len(file_content)} files...")
            documents = []
            
            # Process files and create documents
            for i, file in enumerate(file_content):
                # Check file size and potentially split into chunks
                content = file['content']
                content_chunks = chunk_text(content)
                
                for j, chunk in enumerate(content_chunks):
                    # Create a truncated metadata copy for Pinecone
                    metadata = {
                        "filepath": file['name'],
                        "type": "file",
                        "name": file['name'],
                        "line_number": 1,
                        "chunk_number": j+1,
                        "total_chunks": len(content_chunks),
                        # Include shortened text in metadata, full text in content
                        "text": chunk[:30000]  # Limit to 30KB to leave room for other metadata
                    }
                    
                    doc = Document(
                        page_content=chunk,
                        metadata=metadata
                    )
                    documents.append(doc)
            
            progress.progress(75)
            st.text(f"Step 4/4: Creating embeddings and uploading to Pinecone...")
            
            # Get the appropriate embedding model
            embedding_model = get_langchain_embeddings()
            
            # Create and store vectors
            vectorstore = LangchainPinecone.from_documents(
                documents=documents,
                embedding=embedding_model,
                index_name=index_name,
                namespace=namespace
            )
            
            progress.progress(100)
            
            # Get index stats to confirm upload
            stats = pinecone_index.describe_index_stats()
            namespace_count = stats['namespaces'].get(namespace, {}).get('vector_count', 0)
            
            return True, f"Successfully indexed repository. {namespace_count} vectors added to namespace '{namespace}'."
            
    except Exception as e:
        return False, f"Error indexing repository: {str(e)}"
import os
import tempfile
import streamlit as st
from pathlib import Path
from github import Github
from git import Repo
import shutil
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone
from langchain.schema import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore

# List of supported file extensions to index
SUPPORTED_EXTENSIONS = {'.py', '.js', '.tsx', '.jsx', '.ipynb', '.java',
                         '.cpp', '.ts', '.go', '.rs', '.vue', '.swift', '.c', '.h'}

# Directories to ignore during indexing
IGNORED_DIRS = {'node_modules', 'venv', 'env', 'dist', 'build', '.git',
                '__pycache__', '.next', '.vscode', 'vendor'}

def get_file_content(file_path, repo_path):
    """
    Get content of a single file.
    Args:
        file_path (str): Path to the file
        repo_path (str): Path to the repository root
    Returns:
        Optional[Dict[str, str]]: Dictionary with file name and content
    """
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
    """
    Get content of supported code files from the local repository.
    Args:
        repo_path: Path to the local repository
    Returns:
        List of dictionaries containing file names and contents
    """
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
    """Clones a GitHub repository to a temporary directory.
    Args:
        repo_url: The URL of the GitHub repository.
        temp_dir: Temporary directory to clone into
    Returns:
        The path to the cloned repository.
    """
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

def get_huggingface_embeddings(text, model_name="sentence-transformers/all-mpnet-base-v2"):
    """
    Get embeddings for text using HuggingFace model
    Args:
        text: Text to embed
        model_name: Name of the model to use
    Returns:
        Embeddings vector
    """
    model = SentenceTransformer(model_name)
    return model.encode(text)

def index_github_repo(repo_url, namespace, pinecone_api_key, pinecone_index_name="codebase-rag"):
    """
    Index a GitHub repository in Pinecone
    Args:
        repo_url: URL of the GitHub repository
        namespace: Namespace to use in Pinecone
        pinecone_api_key: API Key for Pinecone
        pinecone_index_name: Name of the Pinecone index
    Returns:
        Success status and message
    """
    try:
        # Initialize Pinecone
        pc = Pinecone(api_key=pinecone_api_key)
        
        # Check if index exists
        indices = pc.list_indexes()
        if pinecone_index_name not in indices:
            st.warning(f"Index '{pinecone_index_name}' does not exist. Creating it now...")
            pc.create_index(
                name=pinecone_index_name,
                dimension=768,  # For sentence-transformers/all-mpnet-base-v2
                metric="cosine"
            )
            st.success(f"Created index '{pinecone_index_name}'")
        
        # Connect to index
        pinecone_index = pc.Index(pinecone_index_name)
        
        # Create a temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            st.info(f"Cloning repository {repo_url}...")
            repo_path = clone_repository(repo_url, temp_dir)
            
            if not repo_path:
                return False, "Failed to clone repository"
            
            st.info("Getting files content...")
            file_content = get_main_files_content(repo_path)
            
            if not file_content:
                return False, "No files found in repository"
            
            st.info(f"Processing {len(file_content)} files...")
            documents = []
            
            # Create progress bar
            progress_bar = st.progress(0)
            
            # Process files and create documents
            for i, file in enumerate(file_content):
                # Update progress bar
                progress = (i + 1) / len(file_content)
                progress_bar.progress(progress)
                
                doc = Document(
                    page_content=file['content'],
                    metadata={
                        "filepath": file['name'],
                        "text": file['content'],
                        "type": "file",
                        "name": file['name'],
                        "line_number": 1
                    }
                )
                documents.append(doc)
            
            st.info(f"Creating embeddings and uploading to Pinecone namespace '{namespace}'...")
            
            # Create and store vectors
            vectorstore = PineconeVectorStore.from_documents(
                documents=documents,
                embedding=HuggingFaceEmbeddings(),
                index_name=pinecone_index_name,
                namespace=namespace
            )
            
            # Get index stats to confirm upload
            stats = pinecone_index.describe_index_stats()
            namespace_count = stats['namespaces'].get(namespace, {}).get('vector_count', 0)
            
            return True, f"Successfully indexed repository. {namespace_count} vectors added to namespace '{namespace}'."
            
    except Exception as e:
        return False, f"Error indexing repository: {str(e)}"

def github_indexer_app():
    """
    Streamlit app for indexing GitHub repositories in Pinecone
    """
    st.title("GitHub Repository Indexer")
    st.write("Add a GitHub repository to your Pinecone index for RAG")
    
    # Repository URL input
    repo_url = st.text_input("GitHub Repository URL", placeholder="https://github.com/username/repository")
    
    # Namespace input
    namespace = st.text_input("Namespace", placeholder="my-repo", 
                             help="A unique identifier for this repository in your Pinecone index")
    
    # Get Pinecone API key from secrets
    pinecone_api_key = st.secrets.get("PINECONE_API_KEY", "")
    pinecone_index_name = st.secrets.get("PINECONE_INDEX_NAME", "codebase-rag")
    
    # Button to start indexing
    if st.button("Index Repository"):
        if not repo_url:
            st.error("Please enter a GitHub repository URL")
        elif not namespace:
            st.error("Please enter a namespace")
        elif not pinecone_api_key:
            st.error("Pinecone API key not found in secrets")
        else:
            with st.spinner("Indexing repository... This may take a while."):
                success, message = index_github_repo(
                    repo_url=repo_url, 
                    namespace=namespace, 
                    pinecone_api_key=pinecone_api_key,
                    pinecone_index_name=pinecone_index_name
                )
                
                if success:
                    st.success(message)
                    st.info("You can now chat with this codebase using the main chat interface.")
                else:
                    st.error(message)

if __name__ == "__main__":
    github_indexer_app()
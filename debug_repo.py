# Create this as debug_repo.py in your root directory
import streamlit as st
import os
import tempfile
from git import Repo
from pinecone_utils import initialize_pinecone
from github_utils import index_github_repo
from repository_storage import RepositoryStorage

st.title("Repository Debug Tool")

# Initialize basic components
pc_api_key = st.secrets["PINECONE_API_KEY"]
pc, index = initialize_pinecone(pc_api_key)
repo_storage = RepositoryStorage()

# Very simple form with no complex state management
st.write("### Simple Repository Test")
repo_url = st.text_input("Repository URL", "https://github.com/streamlit/streamlit")
namespace = st.text_input("Namespace", "debug-repo")

if st.button("Test Clone Only"):
    with st.spinner("Cloning repository..."):
        try:
            temp_dir = tempfile.mkdtemp()
            st.write(f"Created temp dir: {temp_dir}")
            repo_name = repo_url.split("/")[-1].replace(".git", "")
            repo_path = os.path.join(temp_dir, repo_name)
            Repo.clone_from(repo_url, repo_path)
            st.success(f"Successfully cloned repo to {repo_path}")
            st.write("Files in repo:")
            for root, dirs, files in os.walk(repo_path, topdown=True):
                files = [f for f in files if not f.startswith('.')]
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for file in files[:10]:  # Show only first 10 files
                    st.write(os.path.join(root, file))
        except Exception as e:
            st.error(f"Error: {str(e)}")

if st.button("Test Full Index"):
    with st.spinner("Indexing repository..."):
        try:
            success, message = index_github_repo(
                repo_url=repo_url,
                namespace=namespace,
                pinecone_client=pc,
                pinecone_index=index,
                batch_size=5
            )
            if success:
                st.success(message)
                # Store the URL
                repo_storage.store_repository(namespace, repo_url)
            else:
                st.error(message)
        except Exception as e:
            st.error(f"Error: {str(e)}")
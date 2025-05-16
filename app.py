# app.py
import streamlit as st
import time
import os
import gc  # For garbage collection
from openai import OpenAI
from pinecone_utils import initialize_pinecone, get_namespaces, delete_namespace
from github_utils import index_github_repo, show_repository_file_selection
from embedding_utils import perform_rag, create_llm_client, get_llm_model, get_available_models
from export_utils import export_chat_message
from repository_storage import RepositoryStorage
from app_components.app_state import initialize_session_state
from app_components.chat_interface import chat_interface, show_export_modal
from app_components.ui_components import setup_sidebar, show_repository_management
from memory_utils import log_memory_usage, force_garbage_collection, add_memory_monitor_settings, monitor_memory_usage

def main():
    """Main application function"""
    st.title("Codebase RAG")
    
    # Initialize all session state variables
    initialize_session_state()
    
    # Monitor memory usage
    memory_metrics = st.sidebar.empty()
    monitor_memory_usage()
    
    # Initialize repository storage with data directory
    repo_storage = RepositoryStorage("data/repo_data.json")
    
    # Load repository URLs from persistent storage to session state
    repo_storage.export_to_session_state()
    
    # Check if we need to display a refresh notification
    if st.session_state.refresh_required:
        st.success(st.session_state.refresh_message)
        # Reset the refresh flags
        st.session_state.refresh_required = False
        st.session_state.repository_added = False
        st.session_state.repository_deleted = False
    
    # Initialize Pinecone with silent mode after first initialization
    pinecone_api_key = st.secrets["PINECONE_API_KEY"]
    pinecone_index_name = st.secrets.get("PINECONE_INDEX_NAME", "codebase-rag")
    silent_mode = st.session_state.index_initialization_complete
    
    # Add memory monitoring settings to sidebar
    add_memory_monitor_settings()
    
    # Initialize Pinecone
    pc, pinecone_index = initialize_pinecone(pinecone_api_key, pinecone_index_name)
    
    # Mark as initialized to prevent messages on subsequent reruns
    st.session_state.index_initialization_complete = True
    
    # Get namespaces - no caching to ensure it's always fresh
    namespace_list = get_namespaces(pinecone_index)
    
    # Import repository URLs from session state to persistent storage
    # This ensures we capture any URLs added during the session
    repo_storage.import_from_session_state()
    
    # Check if namespace list is empty
    if not namespace_list:
        st.warning("No namespaces found in your Pinecone index. You need to add data to the index first.")
        
        # Add GitHub repository indexing form directly on this page
        st.subheader("Add a GitHub Repository")
        st.markdown("Index a public GitHub repository to start using the RAG system.")
        
        # Show repository form with file selection
        from app_components.repository_management import show_repository_form
        show_repository_form(pc, pinecone_index, pinecone_index_name, repo_storage)
        
        # Display memory usage 
        log_memory_usage(memory_metrics)
        
        st.stop()  # Stop execution here if no namespaces exist
    
    # Setup sidebar and get the navigation selection
    navigation = setup_sidebar(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list)
    
    # Get the selected namespace from session state
    selected_namespace = st.session_state.get("selected_namespace", namespace_list[0])
    
    # Handle reindex modal if it needs to be shown
    # This is a MAIN AREA modal, not a sidebar modal
    if st.session_state.show_reindex_modal:
        show_reindex_modal(selected_namespace, pc, pinecone_index, pinecone_index_name, repo_storage)
    
    # Handle export modal if it needs to be shown
    if st.session_state.show_export_modal and st.session_state.export_message_id is not None:
        show_export_modal(st.session_state.export_message_id)
    
    # Display appropriate content based on navigation
    if navigation == "Manage Repositories":
        show_repository_management(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list)
    else:  # Chat with Codebase
        st.caption(f"Currently browsing: {selected_namespace} | Using: {st.session_state.llm_provider.upper()} ({st.session_state.selected_model})")
        chat_interface(pinecone_index, selected_namespace)
    
    # Display memory usage at the end
    log_memory_usage(memory_metrics)

def show_reindex_modal(selected_namespace, pc, pinecone_index, pinecone_index_name, repo_storage):
    """Show modal for reindexing a repository with file selection"""
    from app_components.repository_management import reindex_repository
    
    with st.container():
        st.subheader("Reindex Repository")
        st.warning("⚠️ This will delete and reindex the selected repository namespace.")
        
        # Get URL from storage first, then from session state as fallback
        default_url = repo_storage.get_repository_url(selected_namespace) or st.session_state.repository_urls.get(selected_namespace, "")
        
        repo_url = st.text_input(
            "GitHub Repository URL", 
            value=default_url,
            placeholder="https://github.com/username/repository",
            key="reindex_repo_url",
            help="Enter the GitHub URL of the repository to reindex with latest code"
        )
        
        # Add batch size selection
        batch_size = st.slider(
            "Batch size (files per batch)", 
            min_value=1, 
            max_value=20,
            value=st.session_state.batch_size,
            help="Lower values help avoid memory issues for large repos."
        )
        
        confirm = st.checkbox("I understand this will replace the existing data", key="confirm_reindex_checkbox")
        
        # Use columns in the main area (where it's allowed)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Confirm", key="confirm_reindex_btn", type="primary") and confirm and repo_url:
                # Call the reindex function
                reindex_repository(
                    selected_namespace, repo_url, pc, pinecone_index, pinecone_index_name, repo_storage, batch_size
                )
        with col2:
            if st.button("Cancel", key="cancel_reindex_btn"):
                # Reset the modal state
                st.session_state.show_reindex_modal = False
                st.rerun()

if __name__ == "__main__":
    main()
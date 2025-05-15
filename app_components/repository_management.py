# app_components/repository_management.py
import streamlit as st
import time
from token_utils import reset_token_tracking, get_token_usage
from pinecone_utils import delete_namespace
from github_utils import index_github_repo

def add_repository(repo_url, namespace, pc, pinecone_index, pinecone_index_name, repo_storage, batch_size=5):
    """Handle repository addition process"""
    # Reset token tracking for this operation
    reset_token_tracking("indexing")
    
    # Set operation in progress flag
    st.session_state.operation_in_progress = True
    
    progress_container = st.container()
    
    with progress_container:
        with st.spinner("Indexing repository... This may take a while."):
            # First store the URL in repository storage
            repo_storage.store_repository(namespace, repo_url)
            
            # Also update session state
            if "repository_urls" not in st.session_state:
                st.session_state.repository_urls = {}
            st.session_state.repository_urls[namespace] = repo_url
            
            # Now perform the indexing
            success, message = index_github_repo(
                repo_url=repo_url, 
                namespace=namespace, 
                pinecone_client=pc,
                pinecone_index=pinecone_index,
                index_name=pinecone_index_name,
                batch_size=batch_size
            )
            
            # Reset operation flag
            st.session_state.operation_in_progress = False
            
            if success:
                st.success(message)
                # Set flag in session state to trigger refresh on next run
                st.session_state.repository_added = True
                st.session_state.refresh_required = True
                st.session_state.refresh_message = f"Repository '{namespace}' has been successfully added. Token usage: {get_token_usage('indexing'):,}"
                # Add a small delay to ensure UI updates before refresh
                time.sleep(1)
                st.rerun()
            else:
                st.error(message)
    
    return success, message

def delete_repository(namespace_to_delete, pinecone_index, repo_storage):
    """Handle repository deletion process"""
    # Set operation in progress flag
    st.session_state.operation_in_progress = True
    
    with st.spinner(f"Deleting namespace '{namespace_to_delete}'..."):
        success, message = delete_namespace(pinecone_index, namespace_to_delete)
        
        # Reset operation flag
        st.session_state.operation_in_progress = False
        
        if success:
            st.success(message)
            # Remove from repository storage
            repo_storage.delete_repository(namespace_to_delete)
            
            # Set flag in session state to trigger refresh on next run
            st.session_state.repository_deleted = True
            st.session_state.refresh_required = True
            st.session_state.refresh_message = f"Repository '{namespace_to_delete}' has been successfully deleted."
            # Clear session state if the deleted namespace was selected
            if "selected_namespace" in st.session_state and st.session_state.selected_namespace == namespace_to_delete:
                del st.session_state.selected_namespace
            # Remove the URL from repository_urls if it exists
            if "repository_urls" in st.session_state and namespace_to_delete in st.session_state.repository_urls:
                del st.session_state.repository_urls[namespace_to_delete]
            # Add a small delay to ensure UI updates before refresh
            time.sleep(1)
            st.rerun()
        else:
            st.error(message)
    
    return success, message

def reindex_repository(namespace, repo_url, pc, pinecone_index, pinecone_index_name, repo_storage, batch_size=10):
    """Function to handle repository reindexing"""
    try:
        # Reset token tracking for this operation
        reset_token_tracking("indexing")
        
        # Set operation in progress flag
        st.session_state.operation_in_progress = True
        
        # Store the URL in repository storage
        repo_storage.store_repository(namespace, repo_url)
        
        # Also update session state
        if "repository_urls" not in st.session_state:
            st.session_state.repository_urls = {}
        st.session_state.repository_urls[namespace] = repo_url
        
        # First delete the existing namespace
        with st.spinner(f"Deleting existing data for '{namespace}'..."):
            success, delete_message = delete_namespace(pinecone_index, namespace)
            
            if not success:
                # Reset operation flag
                st.session_state.operation_in_progress = False
                st.error(f"Error deleting namespace: {delete_message}")
                return False, delete_message
            
            # Small delay to ensure deletion completes
            time.sleep(2)
        
        # Prepare progress display
        progress_placeholder = st.empty()
        progress_container = progress_placeholder.container()
        
        # Then add the repository with the same namespace
        with progress_container:
            with st.spinner(f"Reindexing repository '{namespace}'... This may take a while."):
                success, add_message = index_github_repo(
                    repo_url=repo_url, 
                    namespace=namespace, 
                    pinecone_client=pc,
                    pinecone_index=pinecone_index,
                    index_name=pinecone_index_name,
                    batch_size=batch_size
                )
                
                # Reset operation flag
                st.session_state.operation_in_progress = False
                
                if success:
                    st.success(f"Successfully reindexed repository '{namespace}'. Token usage: {get_token_usage('indexing'):,}")
                    # Store the repository URL in storage
                    repo_storage.store_repository(namespace, repo_url)
                    
                    # Set flag in session state to trigger refresh on next run
                    st.session_state.repository_added = True
                    st.session_state.refresh_required = True
                    st.session_state.refresh_message = f"Repository '{namespace}' has been successfully reindexed. Token usage: {get_token_usage('indexing'):,}"
                    
                    # Reset reindex modal
                    st.session_state.show_reindex_modal = False
                    
                    # Add a small delay to ensure UI updates before refresh
                    time.sleep(1)
                    st.rerun()
                    return True, add_message
                else:
                    st.error(f"Error reindexing repository: {add_message}")
                    return False, add_message
    except Exception as e:
        # Reset operation flag
        st.session_state.operation_in_progress = False
        error_msg = f"Error during reindexing: {str(e)}"
        st.error(error_msg)
        return False, error_msg

def show_repository_form(pc, pinecone_index, pinecone_index_name, repo_storage):
    """Display repository addition form with persistent values"""
    with st.form("repository_form"):
        repo_url = st.text_input(
            "GitHub Repository URL", 
            value=st.session_state.repo_url,
            placeholder="https://github.com/username/repository",
            help="The URL of the public GitHub repository you want to index."
        )
        
        namespace = st.text_input(
            "Namespace", 
            value=st.session_state.namespace,
            placeholder="my-repo",
            help="A unique identifier for this repository in your Pinecone index."
        )
        
        # Add an advanced options expander
        with st.expander("Advanced Options"):
            st.caption("These options control how the repository is processed.")
            # Add a checkbox to use batched processing
            use_batched = st.checkbox(
                "Use batched processing", 
                value=True,
                help="Process files in smaller batches to avoid token limit errors."
            )
            
            # Add a slider for batch size
            if use_batched:
                batch_size = st.slider(
                    "Batch size (files per batch)", 
                    min_value=1, 
                    max_value=50,
                    value=st.session_state.batch_size,
                    help="Number of files to process in each batch. Lower values help avoid token limit errors."
                )
                # Store batch size in session state
                st.session_state.batch_size = batch_size
            else:
                batch_size = 1
                st.session_state.batch_size = 1
            
            # Add a checkbox for token tracking
            track_tokens = st.checkbox(
                "Track token usage", 
                value=True,
                help="Track and display token usage during processing."
            )
        
        submit_button = st.form_submit_button("Index Repository")
    
    # Always update session state when form values change
    st.session_state.repo_url = repo_url
    st.session_state.namespace = namespace
    
    # Handle form submission
    if submit_button:
        if not repo_url:
            st.error("Please enter a GitHub repository URL")
        elif not namespace:
            st.error("Please enter a namespace")
        else:
            add_repository(repo_url, namespace, pc, pinecone_index, pinecone_index_name, repo_storage, batch_size)
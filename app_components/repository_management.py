# app_components/repository_management.py - Completely Rewritten

import streamlit as st
import os
import tempfile
import time
import traceback
import shutil
import gc
from git import Repo
from token_utils import reset_token_tracking, get_token_usage
from pinecone_utils import delete_namespace

# Standalone utility functions that don't depend on other modules

def clone_repository_simple(repo_url, temp_dir):
    """Simplified clone repository function that doesn't rely on github_utils"""
    try:
        # Extract repository name from URL for the subfolder
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        repo_path = os.path.join(temp_dir, repo_name)
        
        # Clone the repository
        Repo.clone_from(repo_url, repo_path)
        return repo_path, None
    except Exception as e:
        error_msg = f"Error cloning repository: {str(e)}"
        return None, error_msg

def scan_files_simple(repo_path):
    """Simplified file scanner that doesn't rely on github_utils"""
    try:
        supported_extensions = {'.py', '.js', '.tsx', '.jsx', '.ipynb', '.java',
                       '.cpp', '.ts', '.go', '.rs', '.vue', '.swift', '.c', '.h'}
        
        ignored_dirs = {'node_modules', 'venv', 'env', 'dist', 'build', '.git',
                       '__pycache__', '.next', '.vscode', 'vendor'}
        
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
        
        return file_list, None
    except Exception as e:
        error_msg = f"Error scanning files: {str(e)}"
        return None, error_msg

def add_repository_simple(repo_url, namespace, pc, pinecone_index, pinecone_index_name, repo_storage, batch_size=5, selected_files=None):
    """Simplified repository addition function that directly calls index_github_repo"""
    from github_utils import index_github_repo
    
    # Reset token tracking for this operation
    reset_token_tracking("indexing")
    
    # Store the URL in repository storage
    repo_storage.store_repository(namespace, repo_url)
    
    # Update session state
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
        batch_size=batch_size,
        selected_files=selected_files
    )
    
    if success:
        # Set flag in session state to trigger refresh on next run
        st.session_state.repository_added = True
        st.session_state.refresh_required = True
        st.session_state.refresh_message = f"Repository '{namespace}' has been successfully added. Token usage: {get_token_usage('indexing'):,}"
    
    return success, message

def delete_repository(namespace_to_delete, pinecone_index, repo_storage):
    """Handle repository deletion process"""
    try:
        success, message = delete_namespace(pinecone_index, namespace_to_delete)
        
        if success:
            # Remove from repository storage
            repo_storage.delete_repository(namespace_to_delete)
            
            # Update session state
            st.session_state.repository_deleted = True
            st.session_state.refresh_required = True
            st.session_state.refresh_message = f"Repository '{namespace_to_delete}' has been successfully deleted."
            
            # Clear session state if the deleted namespace was selected
            if "selected_namespace" in st.session_state and st.session_state.selected_namespace == namespace_to_delete:
                del st.session_state.selected_namespace
            
            # Remove the URL from repository_urls if it exists
            if "repository_urls" in st.session_state and namespace_to_delete in st.session_state.repository_urls:
                del st.session_state.repository_urls[namespace_to_delete]
        
        return success, message
    except Exception as e:
        return False, f"Error deleting repository: {str(e)}"

def reindex_repository(namespace, repo_url, pc, pinecone_index, pinecone_index_name, repo_storage, batch_size=10):
    """Simplified reindex function"""
    try:
        # Reset token tracking
        reset_token_tracking("indexing")
        
        # First delete the existing namespace
        success, delete_message = delete_namespace(pinecone_index, namespace)
        
        if not success:
            return False, f"Error deleting namespace: {delete_message}"
        
        # Small delay to ensure deletion completes
        time.sleep(2)
        
        # Now add the repository
        success, add_message = add_repository_simple(
            repo_url=repo_url,
            namespace=namespace,
            pc=pc,
            pinecone_index=pinecone_index,
            pinecone_index_name=pinecone_index_name,
            repo_storage=repo_storage,
            batch_size=batch_size
        )
        
        if success:
            st.session_state.show_reindex_modal = False
            return True, f"Successfully reindexed repository '{namespace}'"
        else:
            return False, add_message
            
    except Exception as e:
        return False, f"Error during reindexing: {str(e)}"

# Completely rewritten repository form with single-page approach
def show_repository_form(pc, pinecone_index, pinecone_index_name, repo_storage):
    """
    Simplified repository addition form that uses a single-page approach instead of 
    a multi-step workflow. This avoids issues with state management across reruns.
    """
    st.subheader("Add GitHub Repository")
    
    # Generate a unique ID for this form instance
    form_id = int(time.time())
    
    # Create a simple 2-column layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Repository details form
        with st.form(key=f"add_repo_form_{form_id}"):
            repo_url = st.text_input(
                "GitHub Repository URL", 
                value=st.session_state.get("repo_url", ""),
                placeholder="https://github.com/username/repository",
                help="The URL of the public GitHub repository you want to index."
            )
            
            namespace = st.text_input(
                "Namespace", 
                value=st.session_state.get("namespace", ""),
                placeholder="my-repo",
                help="A unique identifier for this repository in your Pinecone index."
            )
            
            # Get batch size from session state or default
            batch_size = st.slider(
                "Batch size (files per batch)",
                min_value=1,
                max_value=50,
                value=st.session_state.get("batch_size", 10),
                help="Number of files to process in each batch. Lower values help avoid memory issues."
            )
            
            submit_button = st.form_submit_button("Add Repository", type="primary")
            
            # Also add a scan button that doesn't require full form submission
            scan_button = st.form_submit_button("Scan Repository Files", type="secondary")
    
    with col2:
        # Status and help information
        st.info("""
        **Adding a Repository**
        
        1. Enter the GitHub repository URL
        2. Provide a unique namespace
        3. Click "Add Repository" to index without scanning
        4. Or click "Scan Repository Files" to select specific files
        """)
    
    # Processing logic
    if submit_button and repo_url and namespace:
        # Store in session state
        st.session_state.repo_url = repo_url
        st.session_state.namespace = namespace
        st.session_state.batch_size = batch_size
        
        # Clear any previous scan results
        if "repo_scan_complete" in st.session_state:
            del st.session_state.repo_scan_complete
        if "repo_file_list" in st.session_state:
            del st.session_state.repo_file_list
        
        # Process repository addition directly (no scanning)
        with st.spinner("Adding repository... This may take a while."):
            try:
                success, message = add_repository_simple(
                    repo_url=repo_url,
                    namespace=namespace,
                    pc=pc,
                    pinecone_index=pinecone_index,
                    pinecone_index_name=pinecone_index_name,
                    repo_storage=repo_storage,
                    batch_size=batch_size
                )
                
                if success:
                    st.success(message)
                    # No rerun - let the user see the success message
                else:
                    st.error(message)
            except Exception as e:
                st.error(f"Error adding repository: {str(e)}")
                st.write(f"Exception details: {traceback.format_exc()}")
    
    # Scan repository logic
    elif scan_button and repo_url:
        # Store in session state
        st.session_state.repo_url = repo_url
        st.session_state.namespace = namespace
        st.session_state.batch_size = batch_size
        
        # Start the scan process
        with st.spinner("Scanning repository files..."):
            try:
                # Create a temporary directory
                temp_dir = tempfile.mkdtemp()
                
                # Clone the repository
                repo_path, error = clone_repository_simple(repo_url, temp_dir)
                
                if error:
                    st.error(error)
                    # Clean up
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    return
                
                # Scan for files
                file_list, error = scan_files_simple(repo_path)
                
                if error:
                    st.error(error)
                    # Clean up
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    return
                
                # Store results in session state for display
                st.session_state.repo_scan_complete = True
                st.session_state.repo_file_list = file_list
                st.session_state.repo_temp_dir = temp_dir
                st.session_state.repo_path = repo_path
            
            except Exception as e:
                st.error(f"Error scanning repository: {str(e)}")
                st.write(f"Exception details: {traceback.format_exc()}")
                
                # Clean up
                try:
                    if 'temp_dir' in locals() and temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                except:
                    pass
    
    # If scan is complete, show file selection UI
    if st.session_state.get("repo_scan_complete", False) and st.session_state.get("repo_file_list"):
        show_file_selection_ui(
            st.session_state.repo_file_list,
            st.session_state.get("repo_url", ""),
            st.session_state.get("namespace", ""),
            st.session_state.get("batch_size", 10),
            pc,
            pinecone_index,
            pinecone_index_name,
            repo_storage,
            st.session_state.get("repo_temp_dir"),
            st.session_state.get("repo_path")
        )

def show_file_selection_ui(file_list, repo_url, namespace, batch_size, pc, pinecone_index, pinecone_index_name, repo_storage, temp_dir, repo_path):
    """Simplified file selection UI that's shown on the same page"""
    try:
        st.subheader("Select Files to Index")
        
        # Group files by extension for better organization
        files_by_ext = {}
        for file in file_list:
            ext = file["ext"]
            if ext not in files_by_ext:
                files_by_ext[ext] = []
            files_by_ext[ext].append(file)
        
        # File selection methods
        selection_method = st.radio(
            "File Selection Method",
            options=["Select by extension", "Limit by file size", "Select all files"],
            horizontal=True
        )
        
        selected_files = []
        
        if selection_method == "Select by extension":
            extensions = list(files_by_ext.keys())
            extension_counts = {ext: len(files_by_ext[ext]) for ext in extensions}
            extension_options = [f"{ext} ({extension_counts[ext]} files)" for ext in extensions]
            
            selected_extensions = st.multiselect(
                "Select file extensions to include",
                options=extension_options,
                default=extension_options
            )
            
            # Convert back to actual extensions
            selected_exts = [ext.split()[0] for ext in selected_extensions]
            
            # Collect files with selected extensions
            for ext in selected_exts:
                if ext in files_by_ext:
                    selected_files.extend([file["path"] for file in files_by_ext[ext]])
        
        elif selection_method == "Limit by file size":
            max_size_kb = st.slider(
                "Maximum file size (KB)",
                min_value=1,
                max_value=1000,
                value=100
            )
            
            # Select files under the size limit
            for ext in files_by_ext:
                for file in files_by_ext[ext]:
                    if file["size_kb"] <= max_size_kb:
                        selected_files.append(file["path"])
        
        else:  # Select all files
            for ext in files_by_ext:
                selected_files.extend([file["path"] for file in files_by_ext[ext]])
        
        st.write(f"**Selected {len(selected_files)} files for indexing**")
        
        # Preview selected files
        with st.expander("Preview selected files", expanded=False):
            for i, path in enumerate(selected_files[:20]):
                st.write(f"- {path}")
            if len(selected_files) > 20:
                st.write(f"... and {len(selected_files) - 20} more")
        
        # Process the selected files
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Index Selected Files", type="primary"):
                with st.spinner("Indexing selected files... This may take a while."):
                    try:
                        success, message = add_repository_simple(
                            repo_url=repo_url,
                            namespace=namespace,
                            pc=pc,
                            pinecone_index=pinecone_index,
                            pinecone_index_name=pinecone_index_name,
                            repo_storage=repo_storage,
                            batch_size=batch_size,
                            selected_files=selected_files
                        )
                        
                        # Clean up temp directory
                        if temp_dir and os.path.exists(temp_dir):
                            shutil.rmtree(temp_dir, ignore_errors=True)
                        
                        # Reset scan state
                        st.session_state.repo_scan_complete = False
                        st.session_state.repo_file_list = None
                        st.session_state.repo_temp_dir = None
                        st.session_state.repo_path = None
                        
                        # Force garbage collection
                        gc.collect()
                        
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                    
                    except Exception as e:
                        st.error(f"Error indexing files: {str(e)}")
                        st.write(f"Exception details: {traceback.format_exc()}")
                        
                        # Clean up
                        if temp_dir and os.path.exists(temp_dir):
                            try:
                                shutil.rmtree(temp_dir, ignore_errors=True)
                            except:
                                pass
        
        with col2:
            if st.button("Cancel"):
                # Clean up temp directory
                if temp_dir and os.path.exists(temp_dir):
                    try:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    except:
                        pass
                
                # Reset scan state
                st.session_state.repo_scan_complete = False
                st.session_state.repo_file_list = None
                st.session_state.repo_temp_dir = None
                st.session_state.repo_path = None
                
                # Force garbage collection
                gc.collect()
                
                st.info("Operation cancelled. Repository was not indexed.")
    
    except Exception as e:
        st.error(f"Error showing file selection UI: {str(e)}")
        st.write(f"Exception details: {traceback.format_exc()}")
        
        # Clean up
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
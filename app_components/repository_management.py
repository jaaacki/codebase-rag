# app_components/repository_management.py - Fixed Version

import streamlit as st
import time
import os
import tempfile
from token_utils import reset_token_tracking, get_token_usage
from pinecone_utils import delete_namespace
from github_utils import index_github_repo, clone_repository, scan_repository_files

def add_repository(repo_url, namespace, pc, pinecone_index, pinecone_index_name, repo_storage, batch_size=5, max_files=None, selected_files=None):
    """Handle repository addition process with file selection"""
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
                batch_size=batch_size,
                max_files=max_files,
                selected_files=selected_files
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
        
        # First select files to include
        st.subheader("Select Files to Include")
        st.info("Please select which files to include in the reindex operation. This helps avoid memory issues.")
        
        # Use our improved repository scanning function
        if "repo_file_list" not in st.session_state:
            st.session_state.repo_file_list = None
            
        # First phase - clone and scan repository
        if st.session_state.repo_file_list is None:
            with st.spinner("Cloning repository to scan files..."):
                # Create a more persistent temporary directory
                temp_dir = tempfile.mkdtemp()
                try:
                    repo_path = clone_repository(repo_url, temp_dir)
                    if repo_path:
                        file_list = scan_repository_files(repo_path)
                        # Store in session state
                        st.session_state.repo_file_list = file_list
                        st.session_state.repo_path = repo_path
                        st.session_state.temp_dir = temp_dir
                        st.rerun()  # Force a rerun to show the file selection UI
                    else:
                        st.error("Failed to clone repository.")
                        st.session_state.operation_in_progress = False
                        return False, "Failed to clone repository"
                except Exception as e:
                    st.error(f"Error scanning repository: {str(e)}")
                    st.session_state.operation_in_progress = False
                    try:
                        import shutil
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    except:
                        pass
                    return False, f"Error scanning repository: {str(e)}"
        
        # Second phase - display file selection UI
        if st.session_state.repo_file_list:
            selected_files = select_repository_files(st.session_state.repo_file_list, st.session_state.repo_path)
            
            if not selected_files:
                st.warning("No files selected for indexing.")
                st.session_state.operation_in_progress = False
                return False, "No files selected for indexing."
            
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
                        batch_size=batch_size,
                        selected_files=selected_files
                    )
                    
                    # Reset operation flag
                    st.session_state.operation_in_progress = False
                    
                    # Clean up temporary directory
                    try:
                        import shutil
                        if "temp_dir" in st.session_state and st.session_state.temp_dir:
                            shutil.rmtree(st.session_state.temp_dir, ignore_errors=True)
                            st.session_state.temp_dir = None
                    except:
                        pass
                    
                    # Reset repository scan data
                    st.session_state.repo_file_list = None
                    st.session_state.repo_path = None
                    
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
        
        # Cleanup
        try:
            import shutil
            if "temp_dir" in st.session_state and st.session_state.temp_dir:
                shutil.rmtree(st.session_state.temp_dir, ignore_errors=True)
                st.session_state.temp_dir = None
        except:
            pass
            
        return False, error_msg


def select_repository_files(file_list, repo_path):
    """
    Show UI for selecting files from a previously scanned repository
    
    Args:
        file_list: List of files found in repository
        repo_path: Path to the cloned repository
    
    Returns:
        list: List of selected files
    """
    if not file_list:
        st.warning("No files found in repository.")
        return []
        
    # Group files by extension for better organization
    files_by_ext = {}
    for file in file_list:
        ext = file["ext"]
        if ext not in files_by_ext:
            files_by_ext[ext] = []
        files_by_ext[ext].append(file)
    
    # Display file selection UI
    st.subheader("Select Files to Index")
    
    # Options for file selection method
    selection_method = st.radio(
        "File Selection Method",
        options=["Select by extension", "Select individual files", "Limit by file size", "Select all files"],
        index=0,
        help="Choose how you want to select files for indexing"
    )
    
    selected_files = []
    
    if selection_method == "Select by extension":
        # Show extension options with counts
        extensions = list(files_by_ext.keys())
        extension_counts = {ext: len(files_by_ext[ext]) for ext in extensions}
        extension_options = [f"{ext} ({extension_counts[ext]} files)" for ext in extensions]
        
        selected_extensions = st.multiselect(
            "Select file extensions to include",
            options=extension_options,
            default=extension_options,
            help="Only files with these extensions will be indexed"
        )
        
        # Convert back to actual extensions
        selected_exts = [ext.split()[0] for ext in selected_extensions]
        
        # Collect files with selected extensions
        for ext in selected_exts:
            selected_files.extend([file["path"] for file in files_by_ext[ext]])
        
    elif selection_method == "Select individual files":
        # Show a list of files with checkboxes, grouped by extension
        st.write("Select individual files to include:")
        
        # Add a filter for easier searching
        file_filter = st.text_input("Filter files by name", "")
        
        for ext in sorted(files_by_ext.keys()):
            with st.expander(f"{ext} files ({len(files_by_ext[ext])})"):
                # Filter files based on user input
                filtered_files = [f for f in files_by_ext[ext] if file_filter.lower() in f["path"].lower()]
                
                # Display warning if too many files
                if len(filtered_files) > 100:
                    st.warning(f"Showing only the first 100 of {len(filtered_files)} files. Use the filter to narrow down.")
                    filtered_files = filtered_files[:100]
                
                for file in filtered_files:
                    if st.checkbox(f"{file['path']} ({file['size_kb']} KB)", key=f"file_{file['path']}"):
                        selected_files.append(file["path"])
        
    elif selection_method == "Limit by file size":
        # Show a slider for size limit
        max_size_kb = st.slider(
            "Maximum file size (KB)",
            min_value=1,
            max_value=1000,
            value=100,
            help="Only files smaller than this size will be indexed"
        )
        
        # Select files under the size limit
        for ext in files_by_ext:
            for file in files_by_ext[ext]:
                if file["size_kb"] <= max_size_kb:
                    selected_files.append(file["path"])
        
    else:  # Select all files
        for ext in files_by_ext:
            selected_files.extend([file["path"] for file in files_by_ext[ext]])
        
        # Warn if there are too many files
        if len(selected_files) > 200:
            st.warning(f"Selected {len(selected_files)} files. Processing too many files may cause memory issues.")
    
    # Show summary
    st.write(f"Selected {len(selected_files)} files for indexing")
    
    # Show a sample of selected files
    if selected_files:
        with st.expander("Preview selected files"):
            for i, path in enumerate(selected_files[:20]):
                st.write(f"- {path}")
            if len(selected_files) > 20:
                st.write(f"... and {len(selected_files) - 20} more")
    
    # Button to confirm selection
    if st.button("Confirm File Selection", type="primary"):
        return selected_files
    
    return []

def show_repository_form(pc, pinecone_index, pinecone_index_name, repo_storage):
    """Display repository addition form with file selection"""
    # Import only the batch size slider
    from app_components.ui_components import get_batch_size_slider
    
    # Initialize session state variables
    if "repo_scan_step" not in st.session_state:
        st.session_state.repo_scan_step = "initial"  # ['initial', 'scanning', 'selection', 'indexing']
    
    if "repo_temp_dir" not in st.session_state:
        st.session_state.repo_temp_dir = None
        
    if "repo_file_list" not in st.session_state:
        st.session_state.repo_file_list = None
        
    if "selected_files" not in st.session_state:
        st.session_state.selected_files = None
    
    # Debug information to help troubleshoot
    with st.expander("Debug Information", expanded=False):
        st.write(f"Current step: {st.session_state.repo_scan_step}")
        st.write(f"Temporary directory: {st.session_state.repo_temp_dir}")
        st.write(f"Files found: {len(st.session_state.repo_file_list) if st.session_state.repo_file_list else 0}")
        st.write(f"Files selected: {len(st.session_state.selected_files) if st.session_state.selected_files else 0}")
    
    # Step 1: Initial form to enter repository details
    if st.session_state.repo_scan_step == "initial":
        # Use a form to capture Enter key presses
        with st.form(key="add_repository_form"):
            repo_url = st.text_input(
                "GitHub Repository URL", 
                value=st.session_state.get("repo_url", ""),
                placeholder="https://github.com/username/repository",
                help="The URL of the public GitHub repository you want to index."
            )
            
            # Always update session state when form values change
            st.session_state.repo_url = repo_url
            
            namespace = st.text_input(
                "Namespace", 
                value=st.session_state.get("namespace", ""),
                placeholder="my-repo",
                help="A unique identifier for this repository in your Pinecone index."
            )
            
            # Always update session state when form values change
            st.session_state.namespace = namespace
            
            # Add an advanced options expander
            with st.expander("Advanced Options"):
                st.caption("These options control how the repository is processed.")
                
                # Use the centralized batch size slider with a unique key
                batch_size = get_batch_size_slider(key="add_repo_batch_size")
                
                # Add a checkbox for token tracking
                track_tokens = st.checkbox(
                    "Track token usage", 
                    value=True,
                    help="Track and display token usage during processing.",
                    key="track_tokens_checkbox"
                )
            
            # Add form submission buttons
            col1, col2 = st.columns([1, 1])
            with col1:
                scan_button = st.form_submit_button("Scan Repository Files", type="secondary")
            with col2:
                submit_button = st.form_submit_button("Add Repository", type="primary")
        
        # Process scan button
        if scan_button and repo_url:
            st.session_state.repo_scan_step = "scanning"
            st.rerun()
            
        # Process submit button (direct add without scanning)
        if submit_button and repo_url and namespace:
            # Store repository information 
            st.session_state.repo_url = repo_url
            st.session_state.namespace = namespace
            st.session_state.batch_size = batch_size
            
            # Set state to indexing
            st.session_state.repo_scan_step = "indexing"
            st.rerun()
    
    # Step 2: Scanning repository
    elif st.session_state.repo_scan_step == "scanning":
        st.info(f"Scanning repository: {st.session_state.repo_url}")
        
        with st.spinner("Cloning repository to scan files..."):
            try:
                # Create a more persistent temporary directory
                temp_dir = tempfile.mkdtemp()
                st.session_state.repo_temp_dir = temp_dir
                
                # Clone the repository
                repo_path = clone_repository(st.session_state.repo_url, temp_dir)
                if not repo_path:
                    st.error("Failed to clone repository.")
                    st.session_state.repo_scan_step = "initial"  # Go back to initial step
                    st.rerun()
                
                # Scan for files
                file_list = scan_repository_files(repo_path)
                
                # Store results in session state
                st.session_state.repo_file_list = file_list
                st.session_state.repo_path = repo_path
                
                # Move to selection step
                st.session_state.repo_scan_step = "selection"
                st.rerun()
                
            except Exception as e:
                st.error(f"Error scanning repository: {str(e)}")
                # Clean up temp directory
                try:
                    import shutil
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                except:
                    pass
                # Go back to initial step
                st.session_state.repo_scan_step = "initial"
                st.rerun()
    
    # Step 3: File selection UI
    elif st.session_state.repo_scan_step == "selection":
        st.subheader("Select Files to Include")
        
        if not st.session_state.repo_file_list:
            st.warning("No files found in repository.")
            st.session_state.repo_scan_step = "initial"
            st.rerun()
        
        # Display file selection UI
        file_list = st.session_state.repo_file_list
        repo_path = st.session_state.repo_path
        
        # Group files by extension for better organization
        files_by_ext = {}
        for file in file_list:
            ext = file["ext"]
            if ext not in files_by_ext:
                files_by_ext[ext] = []
            files_by_ext[ext].append(file)
        
        # Options for file selection method
        selection_method = st.radio(
            "File Selection Method",
            options=["Select by extension", "Select individual files", "Limit by file size", "Select all files"],
            index=0,
            help="Choose how you want to select files for indexing",
            key="selection_method"
        )
        
        selected_files = []
        
        if selection_method == "Select by extension":
            # Show extension options with counts
            extensions = list(files_by_ext.keys())
            extension_counts = {ext: len(files_by_ext[ext]) for ext in extensions}
            extension_options = [f"{ext} ({extension_counts[ext]} files)" for ext in extensions]
            
            selected_extensions = st.multiselect(
                "Select file extensions to include",
                options=extension_options,
                default=extension_options,
                help="Only files with these extensions will be indexed",
                key="extension_multiselect"
            )
            
            # Convert back to actual extensions
            selected_exts = [ext.split()[0] for ext in selected_extensions]
            
            # Collect files with selected extensions
            for ext in selected_exts:
                selected_files.extend([file["path"] for file in files_by_ext[ext]])
            
        elif selection_method == "Select individual files":
            # Show a list of files with checkboxes, grouped by extension
            st.write("Select individual files to include:")
            
            # Add a filter for easier searching
            file_filter = st.text_input("Filter files by name", "", key="file_filter")
            
            for ext in sorted(files_by_ext.keys()):
                with st.expander(f"{ext} files ({len(files_by_ext[ext])})", expanded=False):
                    # Filter files based on user input
                    filtered_files = [f for f in files_by_ext[ext] if file_filter.lower() in f["path"].lower()]
                    
                    # Display warning if too many files
                    if len(filtered_files) > 100:
                        st.warning(f"Showing only the first 100 of {len(filtered_files)} files. Use the filter to narrow down.")
                        filtered_files = filtered_files[:100]
                    
                    for file in filtered_files:
                        if st.checkbox(f"{file['path']} ({file['size_kb']} KB)", key=f"file_{file['path']}"):
                            selected_files.append(file["path"])
            
        elif selection_method == "Limit by file size":
            # Show a slider for size limit
            max_size_kb = st.slider(
                "Maximum file size (KB)",
                min_value=1,
                max_value=1000,
                value=100,
                help="Only files smaller than this size will be indexed",
                key="max_size_slider"
            )
            
            # Select files under the size limit
            for ext in files_by_ext:
                for file in files_by_ext[ext]:
                    if file["size_kb"] <= max_size_kb:
                        selected_files.append(file["path"])
            
        else:  # Select all files
            for ext in files_by_ext:
                selected_files.extend([file["path"] for file in files_by_ext[ext]])
            
            # Warn if there are too many files
            if len(selected_files) > 200:
                st.warning(f"Selected {len(selected_files)} files. Processing too many files may cause memory issues.")
        
        # Show summary
        st.write(f"Selected {len(selected_files)} files for indexing")
        
        # Show a sample of selected files
        if selected_files:
            with st.expander("Preview selected files"):
                for i, path in enumerate(selected_files[:20]):
                    st.write(f"- {path}")
                if len(selected_files) > 20:
                    st.write(f"... and {len(selected_files) - 20} more")
        
        # Buttons for navigation
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("« Back", key="back_button"):
                # Go back to initial step
                st.session_state.repo_scan_step = "initial"
                # Clean up
                try:
                    import shutil
                    if st.session_state.repo_temp_dir:
                        shutil.rmtree(st.session_state.repo_temp_dir, ignore_errors=True)
                        st.session_state.repo_temp_dir = None
                except:
                    pass
                st.rerun()
        
        with col3:
            if st.button("Index Selected Files »", type="primary", key="continue_button"):
                if selected_files:
                    # Store selected files in session state
                    st.session_state.selected_files = selected_files
                    # Move to final step
                    st.session_state.repo_scan_step = "indexing"
                    st.rerun()
                else:
                    st.warning("Please select at least one file to index.")
    
    # Step 4: Indexing repository
    elif st.session_state.repo_scan_step == "indexing":
        # Check if we have repository details and files
        repo_url = st.session_state.get("repo_url", "")
        namespace = st.session_state.get("namespace", "")
        batch_size = st.session_state.get("batch_size", 10)
        selected_files = st.session_state.get("selected_files", None)
        
        if not repo_url or not namespace:
            st.error("Missing repository URL or namespace.")
            st.session_state.repo_scan_step = "initial"
            st.rerun()
        
        # Show confirmation
        st.subheader(f"Indexing Repository: {repo_url}")
        st.write(f"Namespace: {namespace}")
        
        if selected_files:
            st.write(f"Indexing {len(selected_files)} selected files")
        else:
            st.write("No specific files selected. All files will be indexed.")
        
        # Start indexing
        with st.spinner("Adding repository to Pinecone..."):
            success, message = add_repository(
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
            try:
                import shutil
                if st.session_state.repo_temp_dir and os.path.exists(st.session_state.repo_temp_dir):
                    shutil.rmtree(st.session_state.repo_temp_dir, ignore_errors=True)
                    st.session_state.repo_temp_dir = None
            except:
                pass
            
            # Reset state variables
            st.session_state.repo_scan_step = "initial"
            st.session_state.repo_file_list = None
            st.session_state.selected_files = None
            
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)
                st.rerun()
# flat_file_selector.py
import streamlit as st
import os
import tempfile
import shutil
from git import Repo

st.title("Hierarchical File Selector")

# Initialize session state
if "temp_dir" not in st.session_state:
    st.session_state.temp_dir = None
if "repo_path" not in st.session_state:
    st.session_state.repo_path = None
if "file_list" not in st.session_state:
    st.session_state.file_list = []
if "folder_list" not in st.session_state:
    st.session_state.folder_list = []
if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

# Function to scan repository
def scan_repository(repo_path):
    """Scan repository for files and folders"""
    file_list = []
    folder_list = []
    # Only ignore these specific directories
    ignored_dirs = {'.git', 'node_modules', '__pycache__', 'venv', '.vscode'}
    
    for root, dirs, files in os.walk(repo_path):
        # Don't filter out .devcontainer
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        
        # Add folder to list
        rel_path = os.path.relpath(root, repo_path)
        if rel_path != '.':
            folder_list.append(rel_path)
        
        # Process files
        for file in files:
            file_path = os.path.join(root, file)
            rel_file_path = os.path.relpath(file_path, repo_path)
            
            try:
                size_kb = os.path.getsize(file_path) / 1024
                ext = os.path.splitext(file)[1]
                
                file_list.append({
                    "path": rel_file_path,
                    "size_kb": round(size_kb, 2),
                    "ext": ext,
                    "folder": rel_path if rel_path != '.' else ''
                })
            except:
                pass
    
    return file_list, folder_list

# Clone repository step
if not st.session_state.repo_path:
    with st.form("repo_form"):
        repo_url = st.text_input("Repository URL", "https://github.com/streamlit/streamlit-example")
        clone_button = st.form_submit_button("Clone Repository")
        
    if clone_button:
        with st.spinner("Cloning repository..."):
            try:
                # Create temp directory
                temp_dir = tempfile.mkdtemp()
                st.session_state.temp_dir = temp_dir
                
                # Clone repository
                repo_name = repo_url.split("/")[-1].replace(".git", "")
                repo_path = os.path.join(temp_dir, repo_name)
                Repo.clone_from(repo_url, repo_path)
                st.session_state.repo_path = repo_path
                
                # Scan repository for files
                file_list, folder_list = scan_repository(repo_path)
                st.session_state.file_list = file_list
                st.session_state.folder_list = folder_list
                
                st.success(f"Repository cloned successfully. Found {len(file_list)} files in {len(folder_list)} folders.")
                st.rerun()
            except Exception as e:
                st.error(f"Error cloning repository: {str(e)}")

# Show file selection UI if repository is cloned
if st.session_state.repo_path and st.session_state.file_list:
    st.write(f"## Select Files from Repository")
    st.write(f"Found {len(st.session_state.file_list)} files. Select files and folders below:")
    
    # Group files by folder
    files_by_folder = {}
    for file in st.session_state.file_list:
        folder = file["folder"] or "Root"
        if folder not in files_by_folder:
            files_by_folder[folder] = []
        files_by_folder[folder].append(file)
    
    # Create select all checkbox
    all_selected = len(st.session_state.selected_files) == len(st.session_state.file_list)
    if st.checkbox("Select All Files", value=all_selected):
        st.session_state.selected_files = [file["path"] for file in st.session_state.file_list]
    else:
        if all_selected:
            st.session_state.selected_files = []
    
    # Show folders and files
    for folder, files in sorted(files_by_folder.items()):
        # Calculate if folder is fully selected
        folder_files = [file["path"] for file in files]
        folder_selected = all(path in st.session_state.selected_files for path in folder_files)
        
        # Folder checkbox
        if folder != "Root":
            if st.checkbox(f"📁 {folder} ({len(files)} files)", value=folder_selected, key=f"folder_{folder}"):
                # Select all files in this folder
                for file_path in folder_files:
                    if file_path not in st.session_state.selected_files:
                        st.session_state.selected_files.append(file_path)
            elif folder_selected:
                # Unselect all files in this folder
                for file_path in folder_files:
                    if file_path in st.session_state.selected_files:
                        st.session_state.selected_files.remove(file_path)
        
        # Display files
        for file in sorted(files, key=lambda x: x["path"]):
            file_selected = file["path"] in st.session_state.selected_files
            prefix = "    " if folder != "Root" else ""
            
            if st.checkbox(f"{prefix}📄 {os.path.basename(file['path'])} ({file['size_kb']:.2f} KB)", 
                          value=file_selected, 
                          key=f"file_{file['path']}"):
                if file["path"] not in st.session_state.selected_files:
                    st.session_state.selected_files.append(file["path"])
            else:
                if file["path"] in st.session_state.selected_files:
                    st.session_state.selected_files.remove(file["path"])
    
    # Show selection summary and confirmation
    st.write(f"### Selected {len(st.session_state.selected_files)} files")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirm Selection", type="primary"):
            st.success(f"Selection confirmed: {len(st.session_state.selected_files)} files")
            # Here you would typically proceed to the next step like indexing
    
    with col2:
        if st.button("Reset Selection"):
            st.session_state.selected_files = []
            st.rerun()

# Reset button (outside of sidebar)
if st.button("Reset Everything"):
    # Clean up temp directory
    if st.session_state.temp_dir and os.path.exists(st.session_state.temp_dir):
        try:
            shutil.rmtree(st.session_state.temp_dir)
        except Exception as e:
            st.error(f"Error cleaning up: {str(e)}")
    
    # Clear session state
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    st.rerun()
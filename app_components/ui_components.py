# import streamlit as st
# import time
# from embedding_utils import get_available_models, get_llm_model
# from app_components.app_state import show_token_usage_panel
# from app_components.repository_management import show_repository_management as rm_manage, delete_repository as rm_delete
# from pinecone_utils import get_namespaces

# def get_batch_size_slider(min_value=1, max_value=60, key=None):
#     slider_key = key or "batch_size_slider"
#     batch_size = st.slider(
#         "Batch size (files per batch)",
#         min_value=min_value,
#         max_value=max_value,
#         value=st.session_state.get("batch_size", 20),
#         help="Number of files to process in each batch. Lower values help avoid memory issues.",
#         key=slider_key
#     )
#     st.session_state.batch_size = batch_size
#     return batch_size


# def setup_memory_management():
#     with st.expander("Memory Management", expanded=False):
#         monitor = st.checkbox(
#             "Enable memory monitoring",
#             value=st.session_state.get("memory_monitoring", False),
#             key="memory_monitoring_checkbox"
#         )
#         st.session_state.memory_monitoring = monitor
#         if st.button("Force Memory Cleanup", key="force_memory_cleanup_btn"):
#             with st.spinner("Cleaning up memory..."):
#                 import gc
#                 gc.collect()
#                 st.success("Memory cleanup complete.")


# def setup_sidebar(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list):
#     st.sidebar.title("Options")
#     st.sidebar.subheader("LLM Provider")
#     providers = ["groq", "openai"]
#     if "ANTHROPIC_API_KEY" in st.secrets:
#         providers.append("anthropic")
#     provider = st.sidebar.selectbox(
#         "Select LLM Provider", providers,
#         index=providers.index(st.session_state.llm_provider),
#         key="provider_selector"
#     )
#     if provider != st.session_state.llm_provider:
#         st.session_state.llm_provider = provider
#         st.session_state.selected_model = None
#     models = get_available_models(st.session_state.llm_provider)
#     if st.session_state.llm_provider == "groq":
#         preferred = [m for m in ["llama-3.3-70b-versatile", "llama3-70b-8192"] if m in models]
#         default_model = preferred[0] if preferred else models[0]
#     else:
#         default_model = get_llm_model(st.session_state.llm_provider)
#     selected_index = models.index(st.session_state.get("selected_model", default_model))
#     selected_model = st.sidebar.selectbox(
#         "Select Model", models, index=selected_index, key="model_selector"
#     )
#     st.session_state.selected_model = selected_model

#     token_toggle = st.sidebar.checkbox(
#         "Show Token Usage",
#         value=st.session_state.get("show_token_usage", False),
#         key="show_token_usage_checkbox"
#     )
#     st.session_state.show_token_usage = token_toggle
#     if st.session_state.show_token_usage:
#         show_token_usage_panel()

#     if namespace_list:
#         setup_repository_selector(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list)

#     navigation = st.sidebar.radio(
#         "Navigation",
#         ["Chat with Codebase", "Manage Repositories"],
#         key="navigation_radio"
#     )
#     return navigation


# def setup_repository_selector(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list):
#     from app_components.repository_management import reindex_repository
#     st.sidebar.subheader("Repository")
#     st.sidebar.selectbox(
#         "Select Namespace", namespace_list,
#         key="selected_namespace"
#     )
#     col1, col2 = st.sidebar.columns(2)
#     with col1:
#         if st.button("➕  Manage Repositories", key="add_repo_sidebar_btn"):
#             st.session_state.navigation_radio = "Manage Repositories"
#     with col2:
#         if st.button("🔄 Reindex", key="reindex_repo_btn"):
#             st.session_state.show_reindex_modal = True


# def show_repository_management(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list):
#     """Display scan, add, and delete tabs with hierarchical file selector and scrollable UI"""
#     # Initialize session state keys if missing
#     for key, default in {
#         'temp_dir': None,
#         'repo_path': None,
#         'file_list': [],
#         'folder_list': [],
#         'selected_files': [],
#         'repo_url': '',
#         'namespace': ''
#     }.items():
#         if key not in st.session_state:
#             st.session_state[key] = default
#     import os
#     import tempfile
#     from git import Repo
#     from app_components.repository_management import add_repository_simple, delete_repository, scan_repository
#     tabs = st.tabs(["Scan Repository", "Add Repository", "Delete Repository"])

#     # --- Scan Tab ---
#     with tabs[0]:
#         st.markdown("### Clone & Scan Repository")
#         if not st.session_state.repo_path:
#             with st.form("scan_form"):  # unique key
#                 url = st.text_input("Repository URL", key="scan_url")
#                 clone = st.form_submit_button("Clone & Scan")
#             if clone:
#                 if not url:
#                     st.error("Enter a valid repository URL.")
#                 else:
#                     with st.spinner("Cloning repository..."):
#                         temp = tempfile.mkdtemp()
#                         st.session_state.temp_dir = temp
#                         name = url.rstrip("/").split("/")[-1].replace(".git", "")
#                         path = os.path.join(temp, name)
#                         Repo.clone_from(url, path)
#                         st.session_state.repo_path = path
#                     with st.spinner("Scanning files..."):
#                         files, folders = scan_repository(st.session_state.repo_path)
#                         st.session_state.file_list = files
#                         st.session_state.folder_list = folders
#                     st.success(f"Scanned {len(files)} files across {len(folders)} folders.")
#         else:
#             st.markdown(f"### Select Files from {os.path.basename(st.session_state.repo_path)}")
#             files = st.session_state.file_list
#             folders = st.session_state.folder_list
#             selected = st.session_state.selected_files

#             # Scrollable container for file tree
#             st.markdown("<div style='height:400px; overflow:auto; border:1px solid #ccc; padding:10px;'>", unsafe_allow_html=True)
#             # Select All
#             if st.checkbox("Select All Files", value=len(selected)==len(files), key="select_all_files"):
#                 st.session_state.selected_files = [f["path"] for f in files]
#             # Folder and file checkboxes
#             for folder in ['Root'] + folders:
#                 group = [f for f in files if (f['folder']==folder or (folder=='Root' and f['folder']=='') )]
#                 label = f"📁 {folder}" if folder!='Root' else '📁 Root'
#                 folder_sel = all(p['path'] in selected for p in group)
#                 if st.checkbox(f"{label} ({len(group)} files)", value=folder_sel, key=f"fold_{folder}"):
#                     for p in group:
#                         if p['path'] not in st.session_state.selected_files:
#                             st.session_state.selected_files.append(p['path'])
#                 elif folder_sel:
#                     for p in group:
#                         if p['path'] in st.session_state.selected_files:
#                             st.session_state.selected_files.remove(p['path'])
#                 for p in group:
#                     file_sel = p['path'] in selected
#                     if st.checkbox(f"&nbsp;&nbsp;📄 {os.path.basename(p['path'])} ({p['size_kb']} KB)", value=file_sel, key=f"file_{p['path']}"):
#                         if p['path'] not in st.session_state.selected_files:
#                             st.session_state.selected_files.append(p['path'])
#                     elif file_sel:
#                         st.session_state.selected_files.remove(p['path'])
#             st.markdown("</div>", unsafe_allow_html=True)

#             # Confirm selection
#             if st.button("Confirm File Selection", key="confirm_selection"):
#                 if not st.session_state.selected_files:
#                     st.error("No files selected. Please select at least one file.")
#                 else:
#                     st.success(f"{len(st.session_state.selected_files)} files selected. Please switch to 'Add Repository' tab to index.")

#     # --- Add Tab ---
#     with tabs[1]:
#         st.markdown("### Index Selected Files")
#         url = st.text_input("Repository URL", value=st.session_state.get('repo_url',''), key='add_url')
#         ns = st.text_input("Namespace", value=st.session_state.get('namespace',''), key='add_ns')
#         bs = st.slider("Batch Size", 1, 50, st.session_state.get('batch_size',10), key='add_bs')
#         files = st.session_state.selected_files or None
#         if st.button("Add Repository", key="add_repo_btn"):
#             succ, msg = add_repository_simple(url, ns, pc, pinecone_index, pinecone_index_name, repo_storage, bs, files)
#             if succ:
#                 st.success(msg)
#             else:
#                 st.error(msg)

#     # --- Delete Tab ---
#     with tabs[2]:
#         st.markdown("### Delete Repository Namespace")
#         if namespace_list:
#             nsd = st.selectbox('Select Namespace to Delete', namespace_list, key='del_ns')
#             if st.button('Delete Repository', key='del_repo_btn'):
#                 ok, msg = delete_repository(nsd, pinecone_index, repo_storage)
#                 if ok:
#                     st.success(msg)
#                 else:
#                     st.error(msg)

#     # Existing repos
#     st.subheader("Existing Repositories")
#     for ns in get_namespaces(pinecone_index):
#         url = repo_storage.get_repository_url(ns) or st.session_state.repository_urls.get(ns,"")
#         st.write(f"- {ns}: {url}")
import streamlit as st
import time
from embedding_utils import get_available_models, get_llm_model
from app_components.app_state import show_token_usage_panel
from app_components.repository_management import show_repository_management as rm_manage, delete_repository as rm_delete
from pinecone_utils import get_namespaces

def get_batch_size_slider(min_value=1, max_value=60, key=None):
    slider_key = key or "batch_size_slider"
    batch_size = st.slider(
        "Batch size (files per batch)",
        min_value=min_value,
        max_value=max_value,
        value=st.session_state.get("batch_size", 20),
        help="Number of files to process in each batch. Lower values help avoid memory issues.",
        key=slider_key
    )
    st.session_state.batch_size = batch_size
    return batch_size


def setup_memory_management():
    with st.expander("Memory Management", expanded=False):
        monitor = st.checkbox(
            "Enable memory monitoring",
            value=st.session_state.get("memory_monitoring", False),
            key="memory_monitoring_checkbox"
        )
        st.session_state.memory_monitoring = monitor
        if st.button("Force Memory Cleanup", key="force_memory_cleanup_btn"):
            with st.spinner("Cleaning up memory..."):
                import gc
                gc.collect()
                st.success("Memory cleanup complete.")


def setup_sidebar(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list):
    st.sidebar.title("Options")
    st.sidebar.subheader("LLM Provider")
    providers = ["groq", "openai"]
    if "ANTHROPIC_API_KEY" in st.secrets:
        providers.append("anthropic")
    provider = st.sidebar.selectbox(
        "Select LLM Provider", providers,
        index=providers.index(st.session_state.llm_provider),
        key="provider_selector"
    )
    if provider != st.session_state.llm_provider:
        st.session_state.llm_provider = provider
        st.session_state.selected_model = None
    models = get_available_models(st.session_state.llm_provider)
    if st.session_state.llm_provider == "groq":
        preferred = [m for m in ["llama-3.3-70b-versatile", "llama3-70b-8192"] if m in models]
        default_model = preferred[0] if preferred else models[0]
    else:
        default_model = get_llm_model(st.session_state.llm_provider)
    selected_index = models.index(st.session_state.get("selected_model", default_model))
    selected_model = st.sidebar.selectbox(
        "Select Model", models, index=selected_index, key="model_selector"
    )
    st.session_state.selected_model = selected_model

    token_toggle = st.sidebar.checkbox(
        "Show Token Usage",
        value=st.session_state.get("show_token_usage", False),
        key="show_token_usage_checkbox"
    )
    st.session_state.show_token_usage = token_toggle
    if st.session_state.show_token_usage:
        show_token_usage_panel()

    if namespace_list:
        setup_repository_selector(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list)

    navigation = st.sidebar.radio(
        "Navigation",
        ["Chat with Codebase", "Manage Repositories"],
        key="navigation_radio"
    )
    return navigation


def setup_repository_selector(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list):
    from app_components.repository_management import reindex_repository
    st.sidebar.subheader("Repository")
    st.sidebar.selectbox(
        "Select Namespace", namespace_list,
        key="selected_namespace"
    )
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("➕  Manage Repositories", key="add_repo_sidebar_btn"):
            st.session_state.navigation_radio = "Manage Repositories"
    with col2:
        if st.button("🔄 Reindex", key="reindex_repo_btn"):
            st.session_state.show_reindex_modal = True


def show_repository_management(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list):
    """Delegate repository management display to the core implementation."""
    # Always refresh the namespace list
    namespace_list = get_namespaces(pinecone_index)
    # Call the primary repository management UI
    rm_manage(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list)

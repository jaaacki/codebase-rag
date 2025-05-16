# app.py with Add Repository button
import streamlit as st
import time
import traceback
import os
import gc
from openai import OpenAI
from pinecone_utils import initialize_pinecone, get_namespaces, delete_namespace
from github_utils import index_github_repo
from embedding_utils import perform_rag, create_llm_client, get_llm_model, get_available_models
from export_utils import export_chat_message
from repository_storage import RepositoryStorage
from app_components.app_state import initialize_session_state
from app_components.chat_interface import chat_interface, show_export_modal
from app_components.ui_components import setup_sidebar, show_repository_management, get_batch_size_slider
from memory_utils import log_memory_usage, force_garbage_collection, add_memory_monitor_settings, monitor_memory_usage

def main():
    st.title("Codebase RAG")
    initialize_session_state()
    if "navigate_to_add_repository" not in st.session_state:
        st.session_state.navigate_to_add_repository = False

    memory_metrics = st.sidebar.empty()
    monitor_memory_usage()

    repo_storage = RepositoryStorage("data/repo_data.json")
    repo_storage.export_to_session_state()

    if st.session_state.refresh_required:
        st.success(st.session_state.refresh_message)
        st.session_state.refresh_required = False
        st.session_state.repository_added = False
        st.session_state.repository_deleted = False

    pinecone_api_key = st.secrets["PINECONE_API_KEY"]
    pinecone_index_name = st.secrets.get("PINECONE_INDEX_NAME", "codebase-rag")
    add_memory_monitor_settings()
    pc, pinecone_index = initialize_pinecone(pinecone_api_key, pinecone_index_name)
    st.session_state.index_initialization_complete = True

    namespace_list = get_namespaces(pinecone_index)
    repo_storage.import_from_session_state()

    if not namespace_list:
        st.warning("No namespaces found in your Pinecone index. You need to add data to the index first.")
        st.subheader("Add a GitHub Repository")
        st.markdown("Index a public GitHub repository to start using the RAG system.")
        show_repository_management(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list)
        log_memory_usage(memory_metrics)
        st.stop()

    navigation = setup_sidebar(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list)

    if st.session_state.get("navigate_to_add_repository", False):
        navigation = "Manage Repositories"
        st.session_state.navigate_to_add_repository = False

    selected_namespace = st.session_state.get("selected_namespace", namespace_list[0])

    if st.session_state.show_reindex_modal:
        show_reindex_modal(selected_namespace, pc, pinecone_index, pinecone_index_name, repo_storage)

    if st.session_state.show_export_modal and st.session_state.export_message_id is not None:
        show_export_modal(st.session_state.export_message_id)

    if navigation == "Manage Repositories":
        show_repository_management(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list)
        st.stop()

    st.caption(f"Currently browsing: {selected_namespace} | Using: {st.session_state.llm_provider.upper()} ({st.session_state.selected_model})")
    chat_interface(pinecone_index, selected_namespace)
    log_memory_usage(memory_metrics)

def show_reindex_modal(selected_namespace, pc, pinecone_index, pinecone_index_name, repo_storage):
    from app_components.repository_management import reindex_repository
    with st.container():
        st.subheader("Reindex Repository")
        st.warning("⚠️ This will delete and reindex the selected repository namespace.")
        default_url = repo_storage.get_repository_url(selected_namespace) or st.session_state.repository_urls.get(selected_namespace, "")
        repo_url = st.text_input("GitHub Repository URL", value=default_url, placeholder="https://github.com/username/repository", key="reindex_repo_url", help="Enter the GitHub URL of the repository to reindex with latest code")
        batch_size = get_batch_size_slider(key="reindex_batch_size")
        confirm = st.checkbox("I understand this will replace the existing data", key="confirm_reindex_checkbox")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Confirm", key="confirm_reindex_btn", type="primary") and confirm and repo_url:
                reindex_repository(selected_namespace, repo_url, pc, pinecone_index, pinecone_index_name, repo_storage, batch_size)
        with col2:
            if st.button("Cancel", key="cancel_reindex_btn"):
                st.session_state.show_reindex_modal = False
                st.rerun()

if __name__ == "__main__":
    main()

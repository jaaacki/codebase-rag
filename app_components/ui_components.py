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
    
    # Provider changed - need to reset selected model
    if provider != st.session_state.llm_provider:
        st.session_state.llm_provider = provider
        st.session_state.selected_model = None
    
    # Get available models with error handling
    try:
        models = get_available_models(st.session_state.llm_provider)
        if not models:
            st.sidebar.warning(f"No models available for {st.session_state.llm_provider}. Using default models.")
            # Provide default models based on provider
            if provider.lower() == "groq":
                models = ["llama-3.3-70b-versatile", "llama3-70b-8192", "llama-3.1-8b-instant"]
            elif provider.lower() == "openai":
                models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]
            elif provider.lower() == "anthropic":
                models = ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
            else:
                models = ["unknown"]
    except Exception as e:
        st.sidebar.warning(f"Error fetching models: {str(e)}. Using default models.")
        # Provide default models based on provider as fallback
        if provider.lower() == "groq":
            models = ["llama-3.3-70b-versatile", "llama3-70b-8192", "llama-3.1-8b-instant"]
        elif provider.lower() == "openai":
            models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]
        elif provider.lower() == "anthropic":
            models = ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
        else:
            models = ["unknown"]
    
    # Determine the default model for the current provider
    if st.session_state.llm_provider == "groq":
        preferred = [m for m in ["llama-3.3-70b-versatile", "llama3-70b-8192"] if m in models]
        default_model = preferred[0] if preferred else models[0] if models else "llama-3.3-70b-versatile"
    else:
        default_model = get_llm_model(st.session_state.llm_provider)
    
    # Get currently selected model or use default
    model_to_select = st.session_state.get("selected_model", default_model)
    
    # Make sure the model exists in the available models list
    if model_to_select not in models:
        st.sidebar.info(f"Previously selected model '{model_to_select}' is not available. Using default model.")
        model_to_select = default_model if default_model in models else models[0] if models else "unknown"
        st.session_state.selected_model = model_to_select
    
    # Get the index safely
    try:
        selected_index = models.index(model_to_select)
    except (ValueError, IndexError):
        # Fallback to the first model if index not found
        selected_index = 0
        # Update session state to match
        st.session_state.selected_model = models[0] if models else "unknown"
    
    # Show model selection dropdown
    if models:
        selected_model = st.sidebar.selectbox(
            "Select Model", models, index=selected_index, key="model_selector"
        )
        st.session_state.selected_model = selected_model
    else:
        st.sidebar.warning("No models available.")
        st.session_state.selected_model = "unknown"

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
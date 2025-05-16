# app_components/ui_components.py with Add Repository button
import streamlit as st
from embedding_utils import get_available_models, get_llm_model
from app_components.app_state import show_token_usage_panel

def get_batch_size_slider(min_value=1, max_value=60, key=None):
    """
    Centralized function to create a consistent batch size slider.
    
    Args:
        min_value: Minimum batch size
        max_value: Maximum batch size
        key: Optional unique key for the slider
        
    Returns:
        int: Selected batch size
    """
    # If key is not provided, create a default one
    slider_key = key or "batch_size_slider"
    
    # Create and return the slider
    batch_size = st.slider(
        "Batch size (files per batch)", 
        min_value=min_value, 
        max_value=max_value,
        value=st.session_state.get("batch_size", 20),
        help="Number of files to process in each batch. Lower values help avoid memory issues.",
        key=slider_key
    )
    
    # Always update session state when the value changes
    st.session_state.batch_size = batch_size
    
    return batch_size

def setup_memory_management():
    """Setup memory management UI in an expander"""
    with st.expander("Memory Management", expanded=False):
        # Add toggle for memory monitoring with a unique key
        memory_monitoring = st.checkbox(
            "Enable memory monitoring", 
            value=st.session_state.get("memory_monitoring", False),
            help="Show current memory usage statistics",
            key="memory_monitoring_checkbox"  # Added unique key
        )
        
        # Update session state if changed
        if memory_monitoring != st.session_state.get("memory_monitoring", False):
            st.session_state.memory_monitoring = memory_monitoring
            st.rerun()
        
        # Add memory cleanup button with unique key
        if st.button("Force Memory Cleanup", key="force_memory_cleanup_btn"):
            with st.spinner("Cleaning up memory..."):
                import gc
                gc.collect()
                st.success("Memory cleanup complete.")

def setup_sidebar(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list):
    """Setup the sidebar UI with LLM settings and token usage panel"""
    st.sidebar.title("Options")
    
    # Add LLM provider selection in sidebar
    st.sidebar.subheader("LLM Provider")
    llm_provider_options = ["groq", "openai"]
    
    # Check if keys exist and add providers
    if "ANTHROPIC_API_KEY" in st.secrets:
        llm_provider_options.append("anthropic")
        
    selected_provider = st.sidebar.selectbox(
        "Select LLM Provider", 
        options=llm_provider_options,
        index=llm_provider_options.index(st.session_state.llm_provider),
        key="provider_selector"
    )
    
    # Update session state when provider changes
    if selected_provider != st.session_state.llm_provider:
        st.session_state.llm_provider = selected_provider
        # Reset selected model when provider changes
        if "selected_model" in st.session_state:
            st.session_state.selected_model = None
        st.rerun()  # Rerun to update available models
    
    # Fetch available models for the selected provider
    available_models = get_available_models(st.session_state.llm_provider)
    
    # Set default model based on provider
    if st.session_state.llm_provider == "groq":
        # For GROQ, prefer a more powerful model
        preferred_groq_models = ["llama-3.3-70b-versatile", "llama3-70b-8192"]
        default_model = next((m for m in preferred_groq_models if m in available_models), available_models[0])
    else:
        default_model = get_llm_model(st.session_state.llm_provider)
    
    # Find the index of the default model in available models
    default_index = 0
    if default_model in available_models:
        default_index = available_models.index(default_model)
    
    # If there's already a selected model in session state, use it
    if "selected_model" in st.session_state and st.session_state.selected_model in available_models:
        default_index = available_models.index(st.session_state.selected_model)
    
    # Display the model selection dropdown
    selected_model = st.sidebar.selectbox(
        "Select Model",
        options=available_models,
        index=default_index,
        key="model_selector"  # Added unique key
    )
    
    # Always update the session state with the selected model
    st.session_state.selected_model = selected_model
    
    # Add token usage toggle in sidebar
    show_tokens = st.sidebar.checkbox(
        "Show Token Usage", 
        value=st.session_state.show_token_usage,
        key="show_token_usage_checkbox"  # Added unique key
    )
    if show_tokens != st.session_state.show_token_usage:
        st.session_state.show_token_usage = show_tokens
        st.rerun()
    
    # Show token usage panel if enabled
    if st.session_state.show_token_usage:
        # Create the token usage section directly in the sidebar, not in an expander
        show_token_usage_panel()
    
    # Repository section (only if we have namespaces)
    if namespace_list:
        setup_repository_selector(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list)
    
    # Navigation section
    navigation = st.sidebar.radio(
        "Navigation", 
        ["Chat with Codebase", "Manage Repositories"],
        key="navigation_radio"  # Added unique key
    )
    
    return navigation

def setup_repository_selector(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list):
    """Setup the repository selector in the sidebar"""
    # Import reindex_repository here to avoid circular imports
    from app_components.repository_management import reindex_repository
    
    st.sidebar.subheader("Repository")
    
    # Simple selectbox for repository namespace - NO COLUMNS in sidebar
    selected_namespace = st.sidebar.selectbox(
        "Select Repository Namespace",
        options=namespace_list,
        key="selected_namespace"
    )
    
    # Create a columns layout for the two buttons to appear side by side
    col1, col2 = st.sidebar.columns(2)
    
    # Add Repository button in first column
    with col1:
        add_repo_button = st.button(
            "➕  Manage Repositories", 
            help="Manage repositories",
            key="add_repo_sidebar_btn"
        )
        if add_repo_button:
            # Set flag to navigate to repository management page
            st.session_state.navigate_to_add_repository = True
            st.rerun()
    
    # Reindex button in second column
    with col2:
        reindex_button = st.button(
            "🔄 Reindex", 
            help="Reindex this repository with the latest code",
            key="reindex_repo_btn"
        )
        if reindex_button:
            st.session_state.show_reindex_modal = True
    
    # Show reindex modal if button was clicked
    if st.session_state.show_reindex_modal:
        # Create reindex UI in a separate container in the MAIN AREA instead of sidebar
        # We'll show this only if the modal state is active
        st.session_state.show_sidebar_modal = True
    
    return selected_namespace

def show_repository_management(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list):
    """Show the repository management UI"""
    # Local import to avoid circular dependencies
    from app_components.repository_management import show_repository_form, delete_repository
    
    st.subheader("Manage GitHub Repositories")
    
    # Create tabs for different repository management actions
    repo_tabs = st.tabs(["Add Repository", "Delete Repository"])
    
    # Add Repository Tab
    with repo_tabs[0]:
        st.markdown("Index a public GitHub repository to enhance your RAG system.")
        show_repository_form(pc, pinecone_index, pinecone_index_name, repo_storage)
    
    # Delete Repository Tab
    with repo_tabs[1]:
        st.markdown("Delete a repository namespace from your Pinecone index.")
        
        if namespace_list:
            st.warning("⚠️ Warning: This action cannot be undone. All vectors in the selected namespace will be permanently deleted.")
            
            with st.form("delete_repository_form"):
                namespace_to_delete = st.selectbox(
                    "Select Repository to Delete",
                    options=namespace_list,
                    key="namespace_to_delete"
                )
                
                confirm_delete = st.checkbox(
                    "I understand that this action is irreversible and all data in this namespace will be permanently deleted.",
                    key="confirm_delete_checkbox"  # Added unique key
                )
                
                submit_button = st.form_submit_button("Delete Repository")
            
            if submit_button:
                if not confirm_delete:
                    st.error("Please confirm the deletion by checking the confirmation box.")
                else:
                    # Call the separate function to handle repository deletion
                    delete_repository(namespace_to_delete, pinecone_index, repo_storage)
        else:
            st.info("No repositories to delete.")
    
    # Show existing namespaces
    st.subheader("Existing Repositories")
    if namespace_list:
        # Create a container for repositories with a refresh button
        repo_container = st.container()
        col1, col2 = st.columns([0.85, 0.15])
        
        with col2:
            if st.button("🔄 Refresh", key="refresh_repo_list_btn"):  # Added unique key
                st.rerun()
        
        with repo_container:
            for ns in namespace_list:
                # Get URL from storage first, then from session state as fallback
                url = repo_storage.get_repository_url(ns) or st.session_state.repository_urls.get(ns, "Unknown URL")
                st.write(f"- {ns}: {url}")
    else:
        st.write("No repositories indexed yet.")
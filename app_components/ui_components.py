# app_components/ui_components.py
import streamlit as st
from embedding_utils import get_available_models, get_llm_model
from app_components.app_state import show_token_usage_panel

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
        index=default_index
    )
    
    # Always update the session state with the selected model
    st.session_state.selected_model = selected_model
    
    # Add token usage toggle in sidebar
    show_tokens = st.sidebar.checkbox("Show Token Usage", value=st.session_state.show_token_usage)
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
    navigation = st.sidebar.radio("Navigation", ["Chat with Codebase", "Manage Repositories"])
    
    return navigation

def setup_repository_selector(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list):
    """Setup the repository selector in the sidebar"""
    # Import reindex_repository here to avoid circular imports
    from app_components.repository_management import reindex_repository
    
    st.sidebar.subheader("Repository")
    cols = st.sidebar.columns([0.85, 0.15])  # Adjust for better alignment
    
    with cols[0]:
        selected_namespace = st.selectbox(
            "Select Repository Namespace",
            options=namespace_list,
            key="selected_namespace",
            label_visibility="collapsed"  # Hide duplicate label
        )
    
    with cols[1]:
        reindex_button = st.button("🔄", help="Reindex this repository with the latest code")
        if reindex_button:
            st.session_state.show_reindex_modal = True
    
    # Show reindex modal if button was clicked
    if st.session_state.show_reindex_modal:
        with st.sidebar.expander("Reindex Repository", expanded=True):
            st.warning("⚠️ This will delete and reindex the selected repository namespace.")
            
            # Get URL from storage first, then from session state as fallback
            default_url = repo_storage.get_repository_url(selected_namespace) or st.session_state.repository_urls.get(selected_namespace, "")
            
            repo_url = st.text_input(
                "GitHub Repository URL", 
                value=default_url,
                placeholder="https://github.com/username/repository",
                help="Enter the GitHub URL of the repository to reindex with latest code"
            )
            
            # Add batch size selection
            batch_size = st.slider(
                "Batch size (files per batch)", 
                min_value=1, 
                max_value=20,
                value=st.session_state.batch_size,
                help="Lower values help avoid token limit errors for large repos."
            )
            
            confirm = st.checkbox("I understand this will replace the existing data")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Confirm") and confirm and repo_url:
                    # Call the reindex function
                    success, message = reindex_repository(
                        selected_namespace, repo_url, pc, pinecone_index, pinecone_index_name, repo_storage, batch_size
                    )
                    if success:
                        # Reset the modal state
                        st.session_state.show_reindex_modal = False
            with col2:
                if st.button("Cancel"):
                    # Reset the modal state
                    st.session_state.show_reindex_modal = False
                    st.rerun()
    
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
                    "I understand that this action is irreversible and all data in this namespace will be permanently deleted."
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
            if st.button("🔄 Refresh"):
                st.rerun()
        
        with repo_container:
            for ns in namespace_list:
                # Get URL from storage first, then from session state as fallback
                url = repo_storage.get_repository_url(ns) or st.session_state.repository_urls.get(ns, "Unknown URL")
                st.write(f"- {ns}: {url}")
    else:
        st.write("No repositories indexed yet.")
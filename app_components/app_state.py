# app_components/app_state.py
import streamlit as st
from token_utils import get_token_usage, reset_token_tracking

def initialize_session_state():
    """Initialize all session state variables"""
    # Form persistence
    if "repo_url" not in st.session_state:
        st.session_state.repo_url = ""
    if "namespace" not in st.session_state:
        st.session_state.namespace = ""
    
    # Repository URLs storage with persistence
    if "repository_urls" not in st.session_state:
        st.session_state.repository_urls = {}
    
    # Tracking refreshes and operations
    if "refresh_required" not in st.session_state:
        st.session_state.refresh_required = False
    if "refresh_message" not in st.session_state:
        st.session_state.refresh_message = ""
    if "repository_added" not in st.session_state:
        st.session_state.repository_added = False
    if "repository_deleted" not in st.session_state:
        st.session_state.repository_deleted = False
    
    # Reindex modal state
    if "show_reindex_modal" not in st.session_state:
        st.session_state.show_reindex_modal = False
    
    # Operation in progress tracking
    if "operation_in_progress" not in st.session_state:
        st.session_state.operation_in_progress = False
    
    # LLM provider selection
    if "llm_provider" not in st.session_state:
        st.session_state.llm_provider = st.secrets.get("LLM_PROVIDER", "groq")
    
    # Index initialization tracking
    if "index_initialization_complete" not in st.session_state:
        st.session_state.index_initialization_complete = False
    
    # Chat messages
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Export message state
    if "export_message_id" not in st.session_state:
        st.session_state.export_message_id = None
    if "show_export_modal" not in st.session_state:
        st.session_state.show_export_modal = False
    
    # Token tracking initialization
    if "token_usage" not in st.session_state:
        st.session_state.token_usage = {
            "indexing": 0,
            "chat_input": 0,
            "chat_output": 0,
            "system_prompt": 0,
            "rag_context": 0,
            "embedding": 0,
            "total": 0
        }
    
    # Show token usage panel
    if "show_token_usage" not in st.session_state:
        st.session_state.show_token_usage = False
        
    # Batch size for repository processing
    if "batch_size" not in st.session_state:
        st.session_state.batch_size = 10

def show_token_usage_panel():
    """Display a summary of token usage"""
    token_usage = get_token_usage()
    
    # Create a clean display
    st.subheader("Token Usage Statistics")
    
    # Create a two-column layout for the stats
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Total Tokens", f"{token_usage.get('total', 0):,}")
        st.metric("Indexing Tokens", f"{token_usage.get('indexing', 0):,}")
        st.metric("Embedding Tokens", f"{token_usage.get('embedding', 0):,}")
    
    with col2:
        st.metric("Chat Input Tokens", f"{token_usage.get('chat_input', 0):,}")
        st.metric("Chat Output Tokens", f"{token_usage.get('chat_output', 0):,}")
        st.metric("RAG Context Tokens", f"{token_usage.get('rag_context', 0):,}")
    
    # Add a button to reset token tracking
    if st.button("Reset Token Counters"):
        reset_token_tracking()
        st.success("Token counters have been reset.")
        st.rerun()
    
    # Add some information about token usage (not in an expander)
    st.markdown("### About Token Usage")
    
    st.markdown("""
    **What are tokens?**
    
    Tokens are pieces of text that language models process. Generally, one token is about 4 characters or 3/4 of a word in English.
    
    **Token Categories**
    
    - **Indexing**: Tokens used when processing repository files for vectorization
    - **Embedding**: Tokens used for creating embeddings
    - **Chat Input**: Tokens in your queries
    - **Chat Output**: Tokens in AI responses
    - **RAG Context**: Tokens used in the context provided to the LLM for answering
    
    **Managing Token Usage**
    
    To reduce token usage:
    - Use smaller repositories
    - Process repositories in batches
    - Ask more specific questions
    - Limit the number of files processed
    """)
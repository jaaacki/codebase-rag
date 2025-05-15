# streamlit_app.py
import streamlit as st
import time
from openai import OpenAI
from pinecone_utils import initialize_pinecone, get_namespaces, delete_namespace
from github_utils import index_github_repo
from embedding_utils import perform_rag, create_llm_client, get_llm_model, get_available_models

def add_repository(repo_url, namespace, pc, pinecone_index, pinecone_index_name):
    """Separate function to handle repository addition"""
    with st.spinner("Indexing repository... This may take a while."):
        success, message = index_github_repo(
            repo_url=repo_url, 
            namespace=namespace, 
            pinecone_client=pc,
            pinecone_index=pinecone_index,
            index_name=pinecone_index_name
        )
        
        if success:
            st.success(message)
            # Store the repository URL in session state
            if "repository_urls" not in st.session_state:
                st.session_state.repository_urls = {}
            st.session_state.repository_urls[namespace] = repo_url
            # Set flag in session state to trigger refresh on next run
            st.session_state.repository_added = True
            st.session_state.refresh_required = True
            st.session_state.refresh_message = f"Repository '{namespace}' has been successfully added."
            # Add a small delay to ensure UI updates before refresh
            time.sleep(1)
            st.rerun()
        else:
            st.error(message)
    
    return success, message

def delete_repository(namespace_to_delete, pinecone_index):
    """Separate function to handle repository deletion"""
    with st.spinner(f"Deleting namespace '{namespace_to_delete}'..."):
        success, message = delete_namespace(pinecone_index, namespace_to_delete)
        
        if success:
            st.success(message)
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

def reindex_repository(namespace, repo_url, pc, pinecone_index, pinecone_index_name):
    """Function to handle repository reindexing"""
    try:
        # First delete the existing namespace
        with st.spinner(f"Deleting existing data for '{namespace}'..."):
            success, delete_message = delete_namespace(pinecone_index, namespace)
            
            if not success:
                st.error(f"Error deleting namespace: {delete_message}")
                return False, delete_message
            
            # Small delay to ensure deletion completes
            time.sleep(2)
        
        # Then add the repository with the same namespace
        with st.spinner(f"Reindexing repository '{namespace}'... This may take a while."):
            success, add_message = index_github_repo(
                repo_url=repo_url, 
                namespace=namespace, 
                pinecone_client=pc,
                pinecone_index=pinecone_index,
                index_name=pinecone_index_name
            )
            
            if success:
                st.success(f"Successfully reindexed repository '{namespace}'")
                # Store the repository URL in session state
                if "repository_urls" not in st.session_state:
                    st.session_state.repository_urls = {}
                st.session_state.repository_urls[namespace] = repo_url
                # Set flag in session state to trigger refresh on next run
                st.session_state.repository_added = True
                st.session_state.refresh_required = True
                st.session_state.refresh_message = f"Repository '{namespace}' has been successfully reindexed."
                # Add a small delay to ensure UI updates before refresh
                time.sleep(1)
                st.rerun()
                return True, add_message
            else:
                st.error(f"Error reindexing repository: {add_message}")
                return False, add_message
    except Exception as e:
        error_msg = f"Error during reindexing: {str(e)}"
        st.error(error_msg)
        return False, error_msg

def main():
    st.title("Codebase RAG")
    
    # Initialize session state variables for tracking refresh
    if "refresh_required" not in st.session_state:
        st.session_state.refresh_required = False
    
    if "refresh_message" not in st.session_state:
        st.session_state.refresh_message = ""
    
    if "repository_added" not in st.session_state:
        st.session_state.repository_added = False
    
    if "repository_deleted" not in st.session_state:
        st.session_state.repository_deleted = False
    
    # Initialize session state for reindex modal
    if "show_reindex_modal" not in st.session_state:
        st.session_state.show_reindex_modal = False
        
    # Initialize session state for repository URLs
    if "repository_urls" not in st.session_state:
        st.session_state.repository_urls = {}
    
    # Check if we need to display a refresh notification
    if st.session_state.refresh_required:
        st.success(st.session_state.refresh_message)
        # Reset the refresh flags
        st.session_state.refresh_required = False
        st.session_state.repository_added = False
        st.session_state.repository_deleted = False
    
    # Initialize session state for LLM provider if it doesn't exist
    if "llm_provider" not in st.session_state:
        st.session_state.llm_provider = st.secrets.get("LLM_PROVIDER", "groq")
    
    # Initialize Pinecone and get list of namespaces
    pinecone_api_key = st.secrets["PINECONE_API_KEY"]
    pinecone_index_name = st.secrets.get("PINECONE_INDEX_NAME", "codebase-rag")
    pc, pinecone_index = initialize_pinecone(pinecone_api_key, pinecone_index_name)
    
    # Get namespaces - no caching to ensure it's always fresh
    namespace_list = get_namespaces(pinecone_index)
    
    # Check if namespace list is empty
    if not namespace_list:
        st.warning("No namespaces found in your Pinecone index. You need to add data to the index first.")
        
        # Add GitHub repository indexing form directly on this page
        st.subheader("Add a GitHub Repository")
        st.markdown("Index a public GitHub repository to start using the RAG system.")
        
        # Form to collect repository information
        with st.form("repository_form"):
            repo_url = st.text_input(
                "GitHub Repository URL", 
                placeholder="https://github.com/username/repository",
                help="The URL of the public GitHub repository you want to index."
            )
            
            namespace = st.text_input(
                "Namespace", 
                placeholder="my-repo",
                help="A unique identifier for this repository in your Pinecone index."
            )
            
            submit_button = st.form_submit_button("Index Repository")
        
        if submit_button:
            if not repo_url:
                st.error("Please enter a GitHub repository URL")
            elif not namespace:
                st.error("Please enter a namespace")
            else:
                # Call the separate function to handle repository addition
                add_repository(repo_url, namespace, pc, pinecone_index, pinecone_index_name)
        
        st.stop()  # Stop execution here if no namespaces exist
    
    # Initialize session state for namespace if it doesn't exist
    if "selected_namespace" not in st.session_state:
        st.session_state.selected_namespace = namespace_list[0]
    elif st.session_state.selected_namespace not in namespace_list and namespace_list:
        # If the selected namespace was deleted, select the first available one
        st.session_state.selected_namespace = namespace_list[0]
    
    # Sidebar for app navigation
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
        st.session_state.selected_model = None
        st.rerun()  # Rerun to update available models
    
    # Fetch available models for the selected provider
    available_models = get_available_models(st.session_state.llm_provider)
    
    # Model selection dropdown
    # Set default model and index
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
    
    # Navigation options
    app_page = st.sidebar.radio("Navigation", ["Chat with Codebase", "Manage Repositories"])
    
    if app_page == "Manage Repositories":
        st.subheader("Manage GitHub Repositories")
        
        # Create tabs for different repository management actions
        repo_tabs = st.tabs(["Add Repository", "Delete Repository"])
        
        # Add Repository Tab
        with repo_tabs[0]:
            st.markdown("Index a public GitHub repository to enhance your RAG system.")
            
            # Form to collect repository information
            with st.form("repository_form"):
                repo_url = st.text_input(
                    "GitHub Repository URL", 
                    placeholder="https://github.com/username/repository",
                    help="The URL of the public GitHub repository you want to index."
                )
                
                namespace = st.text_input(
                    "Namespace", 
                    placeholder="my-repo",
                    help="A unique identifier for this repository in your Pinecone index."
                )
                
                submit_button = st.form_submit_button("Index Repository")
            
            if submit_button:
                if not repo_url:
                    st.error("Please enter a GitHub repository URL")
                elif not namespace:
                    st.error("Please enter a namespace")
                else:
                    # Call the separate function to handle repository addition
                    add_repository(repo_url, namespace, pc, pinecone_index, pinecone_index_name)
        
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
                        delete_repository(namespace_to_delete, pinecone_index)
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
                    st.write(f"- {ns}")
        else:
            st.write("No repositories indexed yet.")
            
        return
    
    # Repository selector with aligned reindex button
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
            
            # Get stored URL if available
            default_url = st.session_state.repository_urls.get(selected_namespace, "")
            
            repo_url = st.text_input(
                "GitHub Repository URL", 
                value=default_url,
                placeholder="https://github.com/username/repository",
                help="Enter the GitHub URL of the repository to reindex with latest code"
            )
            
            confirm = st.checkbox("I understand this will replace the existing data")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Confirm") and confirm and repo_url:
                    # Call the reindex function
                    success, message = reindex_repository(
                        selected_namespace, repo_url, pc, pinecone_index, pinecone_index_name
                    )
                    if success:
                        # Reset the modal state
                        st.session_state.show_reindex_modal = False
            with col2:
                if st.button("Cancel"):
                    # Reset the modal state
                    st.session_state.show_reindex_modal = False
                    st.rerun()
    
    st.caption(f"Currently browsing: {selected_namespace} | Using: {st.session_state.llm_provider.upper()} ({st.session_state.selected_model})")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # React to user input
    if prompt := st.chat_input("Ask a question about your codebase..."):
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Get AI response using RAG
        with st.chat_message("assistant"):
            with st.spinner(f"Generating response using {st.session_state.llm_provider.upper()} ({st.session_state.selected_model})..."):
                # Create a client for the selected provider
                try:
                    response = perform_rag(
                        prompt, 
                        None,  # We'll create the client inside perform_rag
                        pinecone_index, 
                        selected_namespace,
                        llm_provider=st.session_state.llm_provider,
                        selected_model=st.session_state.selected_model
                    )
                    st.markdown(response)
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    response = error_msg
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()
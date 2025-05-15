# streamlit_app.py
import streamlit as st
from openai import OpenAI
from pinecone_utils import initialize_pinecone, get_namespaces
from github_utils import index_github_repo
from embedding_utils import perform_rag, create_llm_client, get_llm_model, get_available_models

def main():
    st.title("Codebase RAG")
    
    # Initialize session state for LLM provider if it doesn't exist
    if "llm_provider" not in st.session_state:
        st.session_state.llm_provider = st.secrets.get("LLM_PROVIDER", "groq")
    
    # Initialize session state for selected model
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = None
    
    # Initialize Pinecone and get list of namespaces
    pinecone_api_key = st.secrets["PINECONE_API_KEY"]
    pinecone_index_name = st.secrets.get("PINECONE_INDEX_NAME", "codebase-rag")
    pc, pinecone_index = initialize_pinecone(pinecone_api_key, pinecone_index_name)
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
                        st.info("Refreshing the page to show the newly indexed repository...")
                        st.rerun()
                    else:
                        st.error(message)
        
        st.stop()  # Stop execution here if no namespaces exist
    
    # Initialize session state for namespace if it doesn't exist
    if "selected_namespace" not in st.session_state:
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
        st.session_state.selected_model = None  # Reset selected model when provider changes
        st.rerun()  # Rerun to update available models
    
    # Fetch available models for the selected provider
    st.sidebar.text("Loading models...")
    available_models = get_available_models(st.session_state.llm_provider)
    
    # Model selection dropdown
    default_model = get_llm_model(st.session_state.llm_provider)
    default_index = 0
    if default_model in available_models:
        default_index = available_models.index(default_model)
    
    selected_model = st.sidebar.selectbox(
        "Select Model",
        options=available_models,
        index=default_index,
        key="model_selector"
    )
    
    # Update session state when model changes
    if selected_model != st.session_state.selected_model:
        st.session_state.selected_model = selected_model
    
    # Navigation options
    app_page = st.sidebar.radio("Navigation", ["Chat with Codebase", "Add Repository"])
    
    if app_page == "Add Repository":
        st.subheader("Add a GitHub Repository")
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
                        st.info("Refreshing the page to update the namespace list...")
                        st.rerun()
                    else:
                        st.error(message)
        
        # Show existing namespaces
        st.subheader("Existing Repositories")
        if namespace_list:
            for ns in namespace_list:
                st.write(f"- {ns}")
        else:
            st.write("No repositories indexed yet.")
            
        return
    
    # Update sidebar selection to use session state
    selected_namespace = st.sidebar.selectbox(
        "Select Repository Namespace",
        options=namespace_list,
        key="selected_namespace"
    )
    
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
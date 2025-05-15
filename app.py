import streamlit as st
import importlib
import streamlit_app
import github_indexer

# Set up page config
st.set_page_config(
    page_title="Codebase RAG",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Create a sidebar for navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Chat with Codebase", "Add GitHub Repository"])

# Load the selected page
if page == "Chat with Codebase":
    streamlit_app.main()
elif page == "Add GitHub Repository":
    github_indexer.github_indexer_app()
# pinecone_utils.py - Compatibility version for Qdrant
import streamlit as st
import time

# This wrapper provides Pinecone-like methods but uses Qdrant
def initialize_pinecone(api_key, index_name="codebase-rag"):
    """Compatibility function that now initializes Qdrant instead of Pinecone"""
    import os
    from qdrant_client import QdrantClient
    from github_utils import QDRANT_URL
    
    st.warning("Using Qdrant instead of Pinecone. This compatibility layer will be removed in the future.")
    
    try:
        qdrant_url = os.environ.get("QDRANT_URL", QDRANT_URL)
        qdrant_client = QdrantClient(url=qdrant_url)
        # Return dummy Pinecone client and the real Qdrant client as the "index"
        return None, qdrant_client
    except Exception as e:
        st.error(f"Error connecting to Qdrant: {str(e)}")
        return None, None

def get_namespaces(qdrant_client):
    """Get list of collections from Qdrant (replacing Pinecone namespaces)"""
    try:
        if qdrant_client is None:
            return []
        collections = qdrant_client.get_collections().collections
        return [collection.name for collection in collections]
    except Exception as e:
        st.error(f"Error getting collections from Qdrant: {str(e)}")
        return []

def delete_namespace(qdrant_client, collection_name):
    """Delete a collection from Qdrant (replacing Pinecone namespace)"""
    try:
        qdrant_client.delete_collection(collection_name=collection_name)
        return True, f"Successfully deleted collection '{collection_name}'."
    except Exception as e:
        return False, f"Error deleting collection: {str(e)}"
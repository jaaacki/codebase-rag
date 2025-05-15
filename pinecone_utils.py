# pinecone_utils.py
import streamlit as st
import time
from pinecone import Pinecone as PineconeClient, ServerlessSpec

def initialize_pinecone(api_key, index_name="codebase-rag"):
    """Initialize Pinecone client and ensure index exists with correct dimensions"""
    pc = PineconeClient(api_key=api_key)
    
    # Get dimension from secrets based on model
    embedding_model = st.secrets.get("EMBEDDING_MODEL", "text-embedding-3-large")
    if embedding_model == "text-embedding-3-large":
        dimension = 3072
    else:
        dimension = 768  # Default for most HuggingFace models like all-mpnet-base-v2
    
    # Override with explicit dimension if provided
    dimension = int(st.secrets.get("EMBEDDING_DIMENSION", dimension))
    
    try:
        # Check if index exists
        indices = pc.list_indexes()
        
        # Check if index exists with wrong dimension
        if index_name in indices:
            try:
                # Get index description to check dimensions
                index_description = pc.describe_index(index_name)
                current_dimension = index_description.dimension
                
                if current_dimension != dimension:
                    st.warning(f"Index '{index_name}' exists with dimension {current_dimension}, but your configuration requires {dimension} dimensions.")
                    st.warning(f"Please update your EMBEDDING_MODEL and EMBEDDING_DIMENSION settings to match the index, or create a new index with the correct dimensions.")
                    st.info(f"Current settings: EMBEDDING_MODEL={embedding_model}, EMBEDDING_DIMENSION={dimension}")
            except Exception as e:
                st.error(f"Error checking index dimensions: {str(e)}")
        else:
            # Index doesn't exist, create it
            st.warning(f"Index '{index_name}' does not exist. Creating it now...")
            try:
                pc.create_index(
                    name=index_name,
                    dimension=dimension,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    )
                )
                st.success(f"Created index '{index_name}' with dimension {dimension}")
                time.sleep(5)  # Wait for index to be ready
            except Exception as e:
                if "ALREADY_EXISTS" in str(e):
                    st.info(f"Index '{index_name}' already exists.")
                else:
                    st.error(f"Error creating index: {str(e)}")
    except Exception as e:
        st.error(f"Error checking indexes: {str(e)}")
    
    # Connect to index
    index = pc.Index(index_name)
    return pc, index

def get_namespaces(index):
    """Get list of namespaces from Pinecone index"""
    try:
        stats = index.describe_index_stats()
        namespace_list = sorted(list(stats['namespaces'].keys()))
        return namespace_list
    except Exception as e:
        st.error(f"Error getting namespaces: {str(e)}")
        return []
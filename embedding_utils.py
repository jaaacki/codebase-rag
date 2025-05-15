# embedding_utils.py
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import streamlit as st

def get_embeddings(text, client=None, model=None, provider=None):
    """Generate embeddings using the specified model and provider"""
    
    # Get embedding configuration from secrets
    provider = provider or st.secrets.get("EMBEDDING_PROVIDER", "openai")
    model = model or st.secrets.get("EMBEDDING_MODEL", "text-embedding-3-large")
    
    # Generate embeddings based on provider
    if provider.lower() == "openai":
        if client is None:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        
        response = client.embeddings.create(
            input=text,
            model=model
        )
        return response.data[0].embedding
    
    elif provider.lower() == "huggingface":
        # Default to a common model if not specified
        if model == "text-embedding-3-large":
            model = "all-mpnet-base-v2"  # Default fallback
        
        sentence_transformer = SentenceTransformer(model)
        return sentence_transformer.encode(text).tolist()
    
    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")

def perform_rag(query, client, pinecone_index, selected_namespace):
    """Perform RAG query and get response from LLM"""
    # Get embeddings dynamically based on configuration
    raw_query_embedding = get_embeddings(query, client)

    # Query Pinecone for relevant code
    top_matches = pinecone_index.query(
        vector=raw_query_embedding, 
        top_k=10,
        include_metadata=True,
        namespace=selected_namespace
    )

    # Enhanced context building with metadata
    contexts = []
    for item in top_matches['matches']:
        metadata = item['metadata']
        context_header = f"File: {metadata.get('filepath', 'Unknown')}"
        if 'type' in metadata:
            context_header += f"\n{metadata['type']}: {metadata['name']} (Line {metadata['line_number']})"
        
        contexts.append(f"{context_header}\n```\n{metadata['text']}\n```")

    augmented_query = (
        "<CODE_CONTEXT>\n" + 
        "\n\n---\n\n".join(contexts) + 
        "\n</CODE_CONTEXT>\n\n" +
        "QUESTION:\n" + query
    )

    system_prompt = """You are a Senior Software Engineer specializing in code analysis.
    
    Analyze the provided code context carefully, considering:
    1. The structure and relationships between code components
    2. The specific implementation details and patterns
    3. The filepath and location of each code segment
    4. The type of code segment (e.g., function, class, etc.)
    5. The name of the code segment
    
    When answering questions:
    - Reference specific parts of the code and their locations
    - Explain the reasoning behind the implementation
    - Suggest improvements if relevant to the question
    - Consider the broader context of the codebase
    - Always use the code context to answer the question
    - Take a step by step approach in your problem-solving
    """

    llm_response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": augmented_query}
        ]
    )

    return llm_response.choices[0].message.content
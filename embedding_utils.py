# embedding_utils.py
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import streamlit as st

def get_embeddings(text, client=None, model=None, provider=None):
    """Generate embeddings using the specified model and provider"""
    
    # Get embedding configuration from secrets
    provider = provider or st.secrets.get("EMBEDDING_PROVIDER", "openai")
    model = model or st.secrets.get("EMBEDDING_MODEL", "text-embedding-ada-002")
    
    # Generate embeddings based on provider
    if provider.lower() == "openai":
        try:
            # Create a dedicated OpenAI client (not using the passed GROQ client)
            openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            
            response = openai_client.embeddings.create(
                input=text,
                model=model
            )
            return response.data[0].embedding
        except Exception as e:
            st.warning(f"Error using OpenAI embeddings: {str(e)}. Falling back to HuggingFace.")
            # Fall back to HuggingFace if OpenAI fails
            provider = "huggingface"
            model = "all-mpnet-base-v2"
    
    if provider.lower() == "huggingface":
        # Use a reliable HuggingFace model
        if model in ["text-embedding-ada-002", "text-embedding-3-small", "text-embedding-3-large"]:
            model = "all-mpnet-base-v2"  # Default fallback for OpenAI models
        
        sentence_transformer = SentenceTransformer(model)
        return sentence_transformer.encode(text).tolist()
    
    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")

def create_llm_client(provider="groq"):
    """Create LLM client based on provider"""
    if provider.lower() == "groq":
        return OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=st.secrets["GROQ_API_KEY"]
        )
    elif provider.lower() == "openai":
        return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    elif provider.lower() == "anthropic":
        # If you want to add Anthropic Claude support
        from anthropic import Anthropic
        return Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

def get_llm_model(provider="groq"):
    """Get appropriate model name based on provider"""
    if provider.lower() == "groq":
        return st.secrets.get("GROQ_MODEL", "llama-3.1-8b-instant")
    elif provider.lower() == "openai":
        return st.secrets.get("OPENAI_MODEL", "gpt-3.5-turbo")
    elif provider.lower() == "anthropic":
        return st.secrets.get("ANTHROPIC_MODEL", "claude-3-opus-20240229")
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

def summarize_context(contexts, max_tokens=30000):
    """Summarize the context to reduce the token count"""
    total_chars = sum(len(ctx) for ctx in contexts)
    if total_chars <= max_tokens:
        return contexts
    
    # Simple approach: Keep the most relevant contexts (first few matches)
    # and truncate others if needed
    result = []
    current_chars = 0
    for ctx in contexts:
        # Always include at least first line of each context (the header)
        header = ctx.split('\n')[0]
        if current_chars + len(ctx) <= max_tokens:
            result.append(ctx)
            current_chars += len(ctx)
        else:
            # Only include the header for this one
            result.append(header + "\n[Context truncated to reduce token count]")
            current_chars += len(header) + 40  # Approximate length of truncation message
        
        # Stop if we're approaching the limit
        if current_chars >= max_tokens * 0.9:
            break
    
    return result

def perform_rag(query, client, pinecone_index, selected_namespace, llm_provider=None):
    """Perform RAG query and get response from LLM"""
    try:
        # Get LLM provider from session state or secrets
        llm_provider = llm_provider or st.session_state.get("llm_provider", st.secrets.get("LLM_PROVIDER", "groq"))
        
        # Get embeddings dynamically based on configuration
        raw_query_embedding = get_embeddings(query)

        # Query Pinecone for relevant code
        top_matches = pinecone_index.query(
            vector=raw_query_embedding, 
            top_k=5,  # Reduced from 10 to 5 to help with token limits
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
            
            # Limit the size of each code snippet to reduce tokens
            code_text = metadata['text']
            if len(code_text) > 5000:  # Arbitrary limit per snippet
                code_text = code_text[:5000] + "... [truncated]"
                
            contexts.append(f"{context_header}\n```\n{code_text}\n```")
        
        # Summarize context if it's too large
        contexts = summarize_context(contexts)

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

        # Create the appropriate client and get model
        client = create_llm_client(llm_provider)
        model = get_llm_model(llm_provider)
        
        # Handle different provider APIs
        if llm_provider.lower() in ["groq", "openai"]:
            llm_response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": augmented_query}
                ]
            )
            return llm_response.choices[0].message.content
            
        elif llm_provider.lower() == "anthropic":
            message = client.messages.create(
                model=model,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": augmented_query}
                ]
            )
            return message.content[0].text
        
        else:
            return f"Unsupported LLM provider: {llm_provider}"

    except Exception as e:
        return f"Error performing RAG: {str(e)}"
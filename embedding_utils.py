# Updated embedding_utils.py with token tracking
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import streamlit as st
from token_utils import track_token_usage, count_tokens

def get_embeddings(text, client=None, model=None, provider=None):
    """Generate embeddings using the specified model and provider"""
    
    # Get embedding configuration from secrets
    provider = provider or st.secrets.get("EMBEDDING_PROVIDER", "openai")
    model = model or st.secrets.get("EMBEDDING_MODEL", "text-embedding-ada-002")
    
    # Track token usage for embedding
    track_token_usage(text, model=model, purpose="embedding", precise=True)
    
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

def get_available_models(provider="groq"):
    """Get list of available models for the selected provider"""
    try:
        client = create_llm_client(provider)
        
        if provider.lower() == "groq":
            # GROQ models - try to get actual models from API
            try:
                response = client.models.list()
                models = [model.id for model in response.data]
                
                # Filter models to keep only the real LLM models (not TTS, etc.)
                llm_models = [
                    model for model in models 
                    if "whisper" not in model.lower() and 
                       "tts" not in model.lower() and
                       model.startswith(("llama", "meta-llama", "mistral", "gemma", "qwen"))
                ]
                
                # If we don't find any LLM models, use all models
                if not llm_models:
                    llm_models = models
                
                # Sort models: larger models first, then by name
                sorted_models = sorted(llm_models, key=lambda x: (
                    # Put the larger models (70b) first
                    0 if "70b" in x.lower() else 1,
                    # Then by name
                    x
                ))
                
                return sorted_models
                
            except Exception as e:
                st.warning(f"Error getting GROQ models: {str(e)}")
                # Fallback GROQ models - updated based on actual API response
                return ["llama-3.3-70b-versatile", "llama3-70b-8192", "llama-3.1-8b-instant"]
        elif provider.lower() == "openai":
            # OpenAI models
            response = client.models.list()
            # Filter to only include chat completion models
            chat_models = [
                model.id for model in response.data 
                if model.id.startswith(("gpt-3.5", "gpt-4")) and "vision" not in model.id
            ]
            # Sort models in a sensible order
            sorted_models = sorted(chat_models, key=lambda x: (
                # Put GPT-4 models first
                0 if x.startswith("gpt-4") else 1,
                # Then sort by version
                x
            ))
            return sorted_models
        elif provider.lower() == "anthropic":
            # Anthropic doesn't have a models.list() endpoint in the same way
            # Return hardcoded list of common models
            return [
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307"
            ]
    except Exception as e:
        st.warning(f"Error fetching models for {provider}: {str(e)}")
        # Return default models if we can't fetch
        if provider.lower() == "groq":
            return ["llama-3.3-70b-versatile", "llama3-70b-8192", "llama-3.1-8b-instant"]
        elif provider.lower() == "openai":
            return ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]
        elif provider.lower() == "anthropic":
            return ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
        return ["unknown"]

def get_llm_model(provider="groq", selected_model=None):
    """Get appropriate model name based on provider"""
    # For GROQ, use a model that actually exists in the API
    if provider.lower() == "groq":
        # If a selected model is provided and valid, use that
        if selected_model and selected_model.strip():
            return selected_model
        else:
            # Use a more powerful model by default (based on actual API response)
            return "llama-3.3-70b-versatile"
    elif provider.lower() == "openai":
        return selected_model or st.secrets.get("OPENAI_MODEL", "gpt-3.5-turbo")
    elif provider.lower() == "anthropic":
        return selected_model or st.secrets.get("ANTHROPIC_MODEL", "claude-3-opus-20240229")
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

def summarize_context(contexts, max_tokens=30000):
    """Summarize the context to reduce the token count"""
    total_chars = sum(len(ctx) for ctx in contexts)
    if total_chars <= max_tokens:
        return contexts
    
    # Count tokens instead of characters for better estimation
    total_token_count = 0
    for ctx in contexts:
        total_token_count += count_tokens(ctx)
    
    if total_token_count <= max_tokens:
        return contexts
    
    # Simple approach: Keep the most relevant contexts (first few matches)
    # and truncate others if needed
    result = []
    current_tokens = 0
    for ctx in contexts:
        # Always include at least first line of each context (the header)
        header = ctx.split('\n')[0]
        header_tokens = count_tokens(header)
        
        # Calculate tokens for this context
        ctx_tokens = count_tokens(ctx)
        
        if current_tokens + ctx_tokens <= max_tokens:
            result.append(ctx)
            current_tokens += ctx_tokens
        else:
            # Only include the header for this one
            truncation_message = "\n[Context truncated to reduce token count]"
            truncated_ctx = header + truncation_message
            truncated_tokens = count_tokens(truncated_ctx)
            result.append(truncated_ctx)
            current_tokens += truncated_tokens
        
        # Stop if we're approaching the limit
        if current_tokens >= max_tokens * 0.9:
            break
    
    return result

def perform_rag(query, client, pinecone_index, selected_namespace, llm_provider=None, selected_model=None):
    """Perform RAG query and get response from LLM with token tracking"""
    try:
        # Get LLM provider from session state or secrets
        llm_provider = llm_provider or st.session_state.get("llm_provider", st.secrets.get("LLM_PROVIDER", "groq"))
        
        # Track token usage for query
        track_token_usage(query, purpose="chat_input", precise=True)
        
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

        # Track token usage for the augmented query
        augmented_query_tokens = track_token_usage(augmented_query, purpose="rag_context", precise=True)
        
        # Show token usage information
        st.sidebar.info(f"RAG context: {augmented_query_tokens:,} tokens")

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

        # Track system prompt tokens
        system_prompt_tokens = track_token_usage(system_prompt, purpose="system_prompt", precise=True)

        # Create the appropriate client
        client = create_llm_client(llm_provider)
        
        # CRITICAL FIX: For GROQ, use a model that's actually in the API
        if llm_provider.lower() == "groq":
            # Check if selected model is valid
            if selected_model and selected_model.strip():
                model = selected_model
            else:
                # Use a more powerful model by default (based on actual API response)
                model = "llama-3.3-70b-versatile"
        else:
            model = selected_model or get_llm_model(llm_provider)
        
        # Track token usage information in UI
        token_usage = st.session_state.token_usage
        st.sidebar.info(
            f"Token usage:\n"
            f"- Query: {token_usage.get('chat_input', 0):,}\n"
            f"- System: {token_usage.get('system_prompt', 0):,}\n"
            f"- Context: {token_usage.get('rag_context', 0):,}"
        )
        
        # Handle different provider APIs
        if llm_provider.lower() in ["groq", "openai"]:
            llm_response = client.chat.completions.create(
                model=model,  # Use the model we just determined
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": augmented_query}
                ]
            )
            
            response_text = llm_response.choices[0].message.content
            
            # Track token usage for the response
            response_tokens = track_token_usage(response_text, purpose="chat_output", precise=True)
            
            # If we have usage information from the API, use that
            completion_tokens = getattr(llm_response.usage, "completion_tokens", None)
            prompt_tokens = getattr(llm_response.usage, "prompt_tokens", None)
            
            if completion_tokens and prompt_tokens:
                # Update with more accurate token counts
                st.sidebar.info(
                    f"API reported usage:\n"
                    f"- Prompt: {prompt_tokens:,} tokens\n"
                    f"- Completion: {completion_tokens:,} tokens\n"
                    f"- Total: {prompt_tokens + completion_tokens:,} tokens"
                )
            
            return response_text
            
        elif llm_provider.lower() == "anthropic":
            message = client.messages.create(
                model=model,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": augmented_query}
                ]
            )
            response_text = message.content[0].text
            
            # Track token usage for the response
            response_tokens = track_token_usage(response_text, purpose="chat_output", precise=True)
            
            # If we have usage information from the API, use that
            input_tokens = getattr(message, "usage", {}).get("input_tokens", None)
            output_tokens = getattr(message, "usage", {}).get("output_tokens", None)
            
            if input_tokens and output_tokens:
                # Update with more accurate token counts
                st.sidebar.info(
                    f"API reported usage:\n"
                    f"- Input: {input_tokens:,} tokens\n"
                    f"- Output: {output_tokens:,} tokens\n"
                    f"- Total: {input_tokens + output_tokens:,} tokens"
                )
            
            return response_text
        
        else:
            return f"Unsupported LLM provider: {llm_provider}"

    except Exception as e:
        return f"Error performing RAG: {str(e)}"
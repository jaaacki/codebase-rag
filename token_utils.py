# token_utils.py
import tiktoken
import streamlit as st
from typing import Dict, List, Union, Optional

def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """
    Count the number of tokens in the given text using the appropriate tokenizer.
    
    Args:
        text: The text to tokenize
        model: The model name to use for tokenization
    
    Returns:
        int: Number of tokens
    """
    try:
        # Get the appropriate encoding for the model
        if "gpt-4" in model:
            encoding = tiktoken.encoding_for_model("gpt-4")
        elif "gpt-3.5" in model:
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        elif "llama" in model or "Llama" in model:
            # Use cl100k_base for LLaMA models as a reasonable approximation
            encoding = tiktoken.get_encoding("cl100k_base")
        elif "claude" in model:
            # Use cl100k_base for Claude models as a reasonable approximation
            encoding = tiktoken.get_encoding("cl100k_base")
        else:
            # Default to cl100k_base for other models
            encoding = tiktoken.get_encoding("cl100k_base")
        
        # Count tokens
        tokens = encoding.encode(text)
        return len(tokens)
    except Exception as e:
        # If there's an error, use a simple approximation (4 chars per token)
        return len(text) // 4

def estimate_tokens_in_file(content: str) -> int:
    """
    Estimate the number of tokens in a file using a simple approximation.
    This is faster than precise counting but less accurate.
    
    Args:
        content: The file content
    
    Returns:
        int: Estimated number of tokens
    """
    # Simple approximation: 4 characters per token on average
    return len(content) // 4

def track_token_usage(text: str, model: str = None, purpose: str = None, precise: bool = False) -> int:
    """
    Track token usage for the given text and add to session state tracking.
    
    Args:
        text: The text to count tokens for
        model: The model name
        purpose: What the tokens are being used for (indexing, chat, etc.)
        precise: Whether to use precise counting (slower) or estimation (faster)
    
    Returns:
        int: Number of tokens counted
    """
    # Initialize token tracking in session state if not present
    if "token_usage" not in st.session_state:
        st.session_state.token_usage = {
            "indexing": 0,
            "chat_input": 0,
            "chat_output": 0,
            "total": 0
        }
    
    # Count tokens
    if precise:
        token_count = count_tokens(text, model)
    else:
        token_count = estimate_tokens_in_file(text)
    
    # Update tracking based on purpose
    if purpose:
        if purpose not in st.session_state.token_usage:
            st.session_state.token_usage[purpose] = 0
        st.session_state.token_usage[purpose] += token_count
    
    # Always update total
    st.session_state.token_usage["total"] += token_count
    
    return token_count

def reset_token_tracking(purpose: Optional[str] = None) -> None:
    """
    Reset token tracking counters.
    
    Args:
        purpose: Specific counter to reset, or None to reset all counters
    """
    if "token_usage" not in st.session_state:
        st.session_state.token_usage = {
            "indexing": 0,
            "chat_input": 0,
            "chat_output": 0,
            "total": 0
        }
    
    if purpose:
        if purpose in st.session_state.token_usage:
            st.session_state.token_usage[purpose] = 0
    else:
        for key in st.session_state.token_usage:
            st.session_state.token_usage[key] = 0

def get_token_usage(purpose: Optional[str] = None) -> Union[int, Dict[str, int]]:
    """
    Get current token usage statistics.
    
    Args:
        purpose: Specific counter to get, or None to get all counters
    
    Returns:
        Union[int, Dict[str, int]]: Token usage for specified purpose or all purposes
    """
    if "token_usage" not in st.session_state:
        st.session_state.token_usage = {
            "indexing": 0,
            "chat_input": 0,
            "chat_output": 0,
            "total": 0
        }
    
    if purpose:
        return st.session_state.token_usage.get(purpose, 0)
    else:
        return st.session_state.token_usage

def tokenize_and_chunk(text: str, max_tokens: int = 8000, overlap_tokens: int = 200) -> List[str]:
    """
    Tokenize text and split into chunks with a maximum token count.
    
    Args:
        text: Text to split
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Number of tokens to overlap between chunks
    
    Returns:
        List[str]: List of text chunks
    """
    # If text is small enough, return as is
    if count_tokens(text) <= max_tokens:
        return [text]
    
    # Initialize tokenizer
    encoding = tiktoken.get_encoding("cl100k_base")
    
    # Tokenize the entire text
    tokens = encoding.encode(text)
    total_tokens = len(tokens)
    
    # Split into chunks
    chunks = []
    start_idx = 0
    
    while start_idx < total_tokens:
        # Calculate end index for this chunk
        end_idx = min(start_idx + max_tokens, total_tokens)
        
        # Decode tokens for this chunk back to text
        chunk_tokens = tokens[start_idx:end_idx]
        chunk_text = encoding.decode(chunk_tokens)
        
        # Add chunk to results
        chunks.append(chunk_text)
        
        # Move start_idx for next chunk, with overlap
        start_idx = end_idx - overlap_tokens
        
        # Ensure we're making progress
        if start_idx >= total_tokens:
            break
    
    return chunks
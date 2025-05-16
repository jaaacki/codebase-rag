# chunk_utils.py
import streamlit as st
import re
from token_utils import count_tokens, track_token_usage

def split_code_by_function(code_text, language=None):
    """
    Split code into chunks based on function/class definitions.
    Tries to keep related code together.
    
    Args:
        code_text: The code to split
        language: Optional language identifier to use specific patterns
    
    Returns:
        list: List of code chunks
    """
    # Default patterns that work for most languages
    function_patterns = [
        r'(?:public\s+|private\s+|protected\s+|static\s+|async\s+)*\s*(?:function|def|class|interface|void|int|string|bool|var|let|const)\s+\w+\s*\([^)]*\)\s*(?:\{|:)', # General function pattern
        r'(?:export\s+)?(?:default\s+)?(?:class|interface)\s+\w+(?:\s+extends\s+\w+)?(?:\s+implements\s+\w+)?\s*\{', # Class pattern
        r'(?:const|let|var)\s+\w+\s*=\s*(?:function|\([^)]*\)\s*=>)', # JavaScript function assignment
    ]
    
    # Language-specific patterns
    if language == 'python':
        function_patterns = [
            r'def\s+\w+\s*\([^)]*\)\s*:', # Python function
            r'class\s+\w+(?:\([^)]*\))?\s*:', # Python class
            r'@\w+(?:\([^)]*\))?\s*\ndef\s+\w+\s*\([^)]*\)\s*:', # Python decorated function
        ]
    elif language == 'javascript' or language == 'typescript':
        function_patterns = [
            r'(?:export\s+)?(?:async\s+)?function\s*\w*\s*\([^)]*\)\s*\{', # JS/TS function
            r'(?:export\s+)?(?:class|interface)\s+\w+(?:\s+extends\s+\w+)?(?:\s+implements\s+\w+)?\s*\{', # JS/TS class
            r'(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:function|\([^)]*\)\s*=>)', # JS/TS arrow function
            r'(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*\{', # JS/TS object literal
        ]
    
    # Create a combined pattern with named capture groups for each pattern type
    combined_pattern = '|'.join(f'({pattern})' for pattern in function_patterns)
    
    # Find all matches for function/class starts
    matches = list(re.finditer(combined_pattern, code_text))
    
    # If no matches or just one match, return the whole text as one chunk
    if len(matches) <= 1:
        return [code_text]
    
    # Create chunks based on match positions
    chunks = []
    for i in range(len(matches)):
        start_pos = matches[i].start()
        
        # End position is either the start of the next match or the end of the text
        end_pos = matches[i+1].start() if i < len(matches) - 1 else len(code_text)
        
        # Extract chunk
        chunk = code_text[start_pos:end_pos]
        chunks.append(chunk)
    
    # Add any code before the first match as a separate chunk
    if matches[0].start() > 0:
        first_chunk = code_text[:matches[0].start()]
        chunks.insert(0, first_chunk)
    
    return chunks

def split_text_by_lines(text, max_tokens=4000, overlap=200):
    """
    Split text into chunks by line boundaries, respecting token limits.
    
    Args:
        text: Text to split
        max_tokens: Maximum tokens per chunk
        overlap: Number of lines to overlap between chunks
    
    Returns:
        list: List of text chunks
    """
    lines = text.split('\n')
    chunks = []
    current_chunk = []
    current_token_count = 0
    
    for line in lines:
        line_token_count = count_tokens(line + '\n')
        
        # If a single line exceeds max_tokens, split it further
        if line_token_count > max_tokens:
            # If we have accumulated lines, add them as a chunk
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
                # Keep overlap lines for context
                current_chunk = current_chunk[-overlap:] if overlap > 0 else []
                current_token_count = count_tokens('\n'.join(current_chunk))
            
            # Split the long line into smaller chunks
            words = line.split(' ')
            temp_chunk = []
            temp_token_count = 0
            
            for word in words:
                word_token_count = count_tokens(word + ' ')
                if temp_token_count + word_token_count <= max_tokens:
                    temp_chunk.append(word)
                    temp_token_count += word_token_count
                else:
                    # Add the temp chunk and reset
                    if temp_chunk:
                        chunks.append(' '.join(temp_chunk))
                    temp_chunk = [word]
                    temp_token_count = word_token_count
            
            # Add any remaining words
            if temp_chunk:
                chunks.append(' '.join(temp_chunk))
            
            # Reset the main chunk accumulator to start fresh
            current_chunk = []
            current_token_count = 0
        
        # Normal case: add the line if it fits
        elif current_token_count + line_token_count <= max_tokens:
            current_chunk.append(line)
            current_token_count += line_token_count
        else:
            # Line doesn't fit, add current chunk and start a new one
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
                # Keep overlap lines for context
                current_chunk = current_chunk[-overlap:] if overlap > 0 else []
                current_token_count = count_tokens('\n'.join(current_chunk))
                
                # Now add the current line
                current_chunk.append(line)
                current_token_count += line_token_count
    
    # Add the last chunk if not empty
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    return chunks

def smart_code_chunking(code_text, max_tokens=4000, language=None):
    """
    Intelligently chunk code based on language-specific structures.
    Tries to keep logical units together and handles token limits.
    
    Args:
        code_text: Code text to chunk
        max_tokens: Maximum tokens per chunk
        language: Programming language of the code
    
    Returns:
        list: List of code chunks
    """
    # First attempt to split by functions/classes
    chunks = split_code_by_function(code_text, language)
    
    # Check if any chunk exceeds token limit
    final_chunks = []
    for chunk in chunks:
        chunk_tokens = count_tokens(chunk)
        if chunk_tokens <= max_tokens:
            final_chunks.append(chunk)
        else:
            # If a chunk is too big, split it by lines
            line_chunks = split_text_by_lines(chunk, max_tokens)
            final_chunks.extend(line_chunks)
    
    # Track token usage of all chunks
    total_tokens = 0
    for chunk in final_chunks:
        chunk_tokens = count_tokens(chunk)
        total_tokens += chunk_tokens
    
    # Track total tokens for statistics
    track_token_usage(code_text, purpose="chunking", precise=False)
    
    return final_chunks
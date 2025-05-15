# export_utils.py
import os
import datetime
import streamlit as st
from openai import OpenAI

def ensure_export_dir():
    """Ensure the export directory exists"""
    export_dir = os.path.join(os.getcwd(), "export")
    os.makedirs(export_dir, exist_ok=True)
    return export_dir

# Update the generate_filename function to support custom filenames
def generate_filename(extension="txt", custom_name=None):
    """Generate a filename based on current timestamp or custom name"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Use custom name if provided, otherwise use default format
    if custom_name and custom_name.strip():
        # Clean the custom name to ensure it's a valid filename
        # Remove special characters that aren't allowed in filenames
        import re
        clean_name = re.sub(r'[<>:"/\\|?*]', '', custom_name.strip())
        
        # If cleaning left an empty string, fall back to default
        if clean_name:
            return f"{clean_name}.{extension}"
    
    # Default timestamp-based filename
    return f"chat_export_{timestamp}.{extension}"

# Update the export_chat_message function to accept custom filename
def export_chat_message(message, export_type="text", custom_filename=None):
    """Export a single chat message to a file"""
    try:
        # Ensure export directory exists
        export_dir = ensure_export_dir()
        
        # Get content to export
        content = message["content"]
        
        # Generate filename based on export type and custom name
        if export_type.lower() == "markdown" or export_type.lower() == "md":
            # Format as markdown
            content = convert_to_markdown(content)
            filename = generate_filename("md", custom_filename)
        else:
            # Plain text export
            filename = generate_filename("txt", custom_filename)
        
        # Full path to export file
        export_path = os.path.join(export_dir, filename)
        
        # Write to file
        with open(export_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True, export_path
        
    except Exception as e:
        return False, f"Error exporting message: {str(e)}"

def convert_to_markdown(content, title=None):
    """
    Convert plain text to enhanced markdown using LLM
    This function will use the configured LLM to improve formatting
    """
    try:
        # Get LLM provider from session state
        provider = st.session_state.get("llm_provider", st.secrets.get("LLM_PROVIDER", "groq"))
        
        # Create the appropriate client based on provider
        if provider.lower() == "groq":
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=st.secrets["GROQ_API_KEY"]
            )
            model = st.session_state.get("selected_model", "llama-3.3-70b-versatile")
        elif provider.lower() == "openai":
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            model = st.session_state.get("selected_model", "gpt-3.5-turbo")
        elif provider.lower() == "anthropic":
            from anthropic import Anthropic
            client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"]) 
            model = st.session_state.get("selected_model", "claude-3-opus-20240229")
        else:
            # Fallback - just return the original content with basic formatting
            if title:
                return f"# {title}\n\n{content}"
            return content
            
        # Prepare prompt for formatting
        prompt = f"""
        Convert the following chat response into well-formatted markdown:
        
        {content}
        
        Apply appropriate markdown formatting:
        - Use headers for sections
        - Format code blocks with proper syntax highlighting
        - Use bullet points and numbered lists where appropriate
        - Highlight important information
        - Include a title if provided: {title if title else 'No title provided'}
        
        Return ONLY the formatted markdown without any explanations or additional text.
        """
        
        # Handle different provider APIs
        if provider.lower() in ["groq", "openai"]:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a markdown formatting expert."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
            
        elif provider.lower() == "anthropic":
            message = client.messages.create(
                model=model,
                system="You are a markdown formatting expert.",
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
            
    except Exception as e:
        st.error(f"Error converting to markdown: {str(e)}")
        # Fallback - return the original content with basic formatting
        if title:
            return f"# {title}\n\n{content}"
        return content
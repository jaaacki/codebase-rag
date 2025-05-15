# app_components/chat_interface.py
import streamlit as st
from token_utils import get_token_usage
from embedding_utils import perform_rag

def render_message_with_export(message, index):
    """Render a chat message with export button"""
    # Only show export button for assistant messages
    if message["role"] == "assistant":
        col1, col2 = st.columns([0.95, 0.05])
        
        # Display the message content in the first column
        with col1:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Display the export button in the second column
        with col2:
            # Position the button at the top right of the message
            st.write("")  # Add a bit of space at the top
            if st.button("💾", key=f"export_btn_{index}", help="Export this message"):
                st.session_state.export_message_id = index
                st.session_state.show_export_modal = True
                st.rerun()
    else:
        # Regular rendering for user messages
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

def show_export_modal(message_id):
    """Show a modal to export message content"""
    from export_utils import export_chat_message
    
    # Get the message by ID for filename suggestion
    message_content = ""
    if 0 <= message_id < len(st.session_state.messages):
        message = st.session_state.messages[message_id]
        message_content = message["content"]
        
        # Extract a potential filename from content (first few words)
        default_filename = message_content.split()[:3]
        default_filename = "_".join(default_filename)[:20].lower()
        
        # Clean the suggested filename
        import re
        default_filename = re.sub(r'[<>:"/\\|?*]', '', default_filename)
    else:
        default_filename = "chat_export"
    
    # Set up message export modal
    with st.sidebar.expander("Export Message", expanded=True):
        st.write("Select export format:")
        
        export_type = st.radio(
            "Export Format",
            ["Text", "Markdown"],
            key="export_format",
            horizontal=True,
            label_visibility="collapsed"
        )
        
        # Add custom filename input
        custom_filename = st.text_input(
            "Filename (without extension)",
            value=default_filename,
            help="Enter a custom filename. Extension will be added automatically."
        )
        
        if st.button("Export"):
            # Get the message by ID
            if 0 <= message_id < len(st.session_state.messages):
                message = st.session_state.messages[message_id]
                
                # Export the message with custom filename
                success, result = export_chat_message(message, export_type, custom_filename)
                
                if success:
                    st.success(f"Message exported successfully to: {result}")
                else:
                    st.error(result)
            else:
                st.error("Message not found.")
                
        if st.button("Cancel"):
            # Reset the modal state
            st.session_state.show_export_modal = False
            st.session_state.export_message_id = None
            st.rerun()

def chat_interface(pinecone_index, selected_namespace):
    """Display and handle the chat interface"""
    # Display chat messages from history on app rerun with export buttons
    for i, message in enumerate(st.session_state.messages):
        render_message_with_export(message, i)
    
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
        
        # Show export button for this new message
        last_msg_idx = len(st.session_state.messages) - 1
        col1, col2 = st.columns([0.95, 0.05])
        with col2:
            st.write("")  # Add a bit of space
            if st.button("💾", key=f"export_btn_{last_msg_idx}", help="Export this message"):
                st.session_state.export_message_id = last_msg_idx
                st.session_state.show_export_modal = True
                st.rerun()

        # Display token usage after a successful chat interaction
        if st.session_state.show_token_usage:
            token_usage = get_token_usage()
            st.info(
                f"Token usage for this interaction:\n"
                f"- Input: {token_usage.get('chat_input', 0):,} tokens\n"
                f"- Context: {token_usage.get('rag_context', 0):,} tokens\n"
                f"- Output: {token_usage.get('chat_output', 0):,} tokens\n"
                f"- Total: {token_usage.get('total', 0):,} tokens"
            )
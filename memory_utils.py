# memory_utils.py
import os
import gc
import psutil
import streamlit as st

def log_memory_usage(container=None):
    """
    Log current memory usage to a Streamlit container
    
    Args:
        container: Streamlit container to write to
    """
    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        # Format memory usage
        memory_mb = memory_info.rss / 1024 / 1024
        memory_percent = process.memory_percent()
        
        # Get system memory info
        system_memory = psutil.virtual_memory()
        system_memory_used_percent = system_memory.percent
        
        # Display memory information
        if container:
            container.info(
                f"Memory usage:\n"
                f"- App: {memory_mb:.1f} MB ({memory_percent:.1f}%)\n"
                f"- System: {system_memory_used_percent:.1f}% used"
            )
        
        return memory_mb
    except Exception as e:
        if container:
            container.error(f"Error monitoring memory: {str(e)}")
        return 0

def force_garbage_collection():
    """Force Python garbage collection to free memory"""
    gc.collect()
    
def monitor_memory_usage():
    """Add memory monitoring to Streamlit app"""
    # Get current state
    if "memory_monitoring" not in st.session_state:
        st.session_state.memory_monitoring = False
        
    # Only show memory usage if enabled in settings
    if st.session_state.memory_monitoring:
        memory_info = st.sidebar.empty()
        log_memory_usage(memory_info)
        
        # Add a button to force garbage collection
        if st.sidebar.button("Force Memory Cleanup"):
            with st.sidebar.spinner("Cleaning up memory..."):
                force_garbage_collection()
                st.sidebar.success("Memory cleanup complete.")
                # Update memory display
                log_memory_usage(memory_info)

def add_memory_monitor_settings():
    """Add memory monitoring settings to Streamlit sidebar"""
    with st.sidebar.expander("Memory Management", expanded=False):
        # Add toggle for memory monitoring
        memory_monitoring = st.checkbox(
            "Enable memory monitoring", 
            value=st.session_state.get("memory_monitoring", False),
            help="Show current memory usage statistics"
        )
        
        # Update session state if changed
        if memory_monitoring != st.session_state.get("memory_monitoring", False):
            st.session_state.memory_monitoring = memory_monitoring
            st.rerun()
        
        # Add advanced cleanup button
        if st.button("Advanced Memory Cleanup"):
            with st.spinner("Performing deep memory cleanup..."):
                # Free file system caches if possible (might require elevated permissions)
                try:
                    if os.name == 'posix':  # Linux/Unix
                        os.system("sync")  # Flush file system buffers
                except:
                    pass
                
                # Force multiple rounds of garbage collection
                for _ in range(3):
                    gc.collect()
                
                # Clear Python interpreter caches if possible
                try:
                    import sys
                    if hasattr(sys, 'getsizeof'):
                        # Clear function lookup cache if possible
                        if hasattr(sys, '_clear_type_cache'):
                            sys._clear_type_cache()
                except:
                    pass
                
                st.success("Deep memory cleanup complete.")
                
        # Display memory explanation if monitoring is enabled
        if memory_monitoring:
            st.markdown("""
            **Memory monitoring**
            
            This displays the memory usage of the Streamlit app process and the overall system memory usage.
            
            - **App Memory**: Direct memory used by this Streamlit application
            - **System Memory**: Total system memory usage percentage
            
            Use the cleanup buttons if memory usage gets too high.
            """)
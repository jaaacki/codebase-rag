# repository_storage.py
import os
import json
import streamlit as st

class RepositoryStorage:
    """Class to handle persistent storage of repository URLs and namespaces"""
    
    def __init__(self, storage_file="data/repo_data.json"):
        """Initialize the storage with a file path"""
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(storage_file), exist_ok=True)
        self.storage_file = storage_file
        self.data = self._load_data()
    
    def _load_data(self):
        """Load data from the storage file"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    return json.load(f)
            else:
                return {"repositories": {}}
        except Exception as e:
            st.error(f"Error loading repository data: {str(e)}")
            return {"repositories": {}}
    
    def _save_data(self):
        """Save data to the storage file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            
            with open(self.storage_file, 'w') as f:
                json.dump(self.data, f)
            return True
        except Exception as e:
            st.error(f"Error saving repository data: {str(e)}")
            return False
    
    def get_all_repositories(self):
        """Get all stored repositories"""
        return self.data["repositories"]
    
    def get_repository_url(self, namespace):
        """Get the URL for a specific namespace"""
        return self.data["repositories"].get(namespace, "")
    
    def store_repository(self, namespace, url):
        """Store a repository URL with its namespace"""
        self.data["repositories"][namespace] = url
        return self._save_data()
    
    def delete_repository(self, namespace):
        """Delete a repository from storage"""
        if namespace in self.data["repositories"]:
            del self.data["repositories"][namespace]
            return self._save_data()
        return True  # Return True if namespace wasn't there anyway
    
    def import_from_session_state(self):
        """Import repositories from session state"""
        if "repository_urls" in st.session_state:
            # Merge with existing data, prioritizing session state
            for namespace, url in st.session_state.repository_urls.items():
                if url and url.strip():  # Only store non-empty URLs
                    self.data["repositories"][namespace] = url
            return self._save_data()
        return False
    
    def export_to_session_state(self):
        """Export repositories to session state"""
        if "repository_urls" not in st.session_state:
            st.session_state.repository_urls = {}
        
        # Update session state with stored data
        for namespace, url in self.data["repositories"].items():
            st.session_state.repository_urls[namespace] = url
        
        return True
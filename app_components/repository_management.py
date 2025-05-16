import streamlit as st
import os
import tempfile
import shutil
import pandas as pd 
from git import Repo
from token_utils import reset_token_tracking, get_token_usage
from chunk_utils import smart_code_chunking
from pinecone_utils import delete_namespace, get_namespaces
from github_utils import index_github_repo
from st_aggrid import AgGrid, GridOptionsBuilder
from repository_storage import RepositoryStorage

# --- Utility: hierarchical repository scan ---
def scan_repository(repo_path):
    ignored_dirs = {'.git', 'node_modules', '__pycache__', 'venv', '.vscode'}
    file_list = []
    folder_set = set()
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        rel_folder = os.path.relpath(root, repo_path)
        if rel_folder != '.':
            folder_set.add(rel_folder)
        for fname in files:
            path = os.path.join(root, fname)
            rel = os.path.relpath(path, repo_path)
            try:
                size_kb = os.path.getsize(path) / 1024
                ext = os.path.splitext(fname)[1]
            except:
                size_kb, ext = 0, ''
            file_list.append({
                'path': rel,
                'size_kb': round(size_kb,2),
                'ext': ext,
                'folder': rel_folder if rel_folder!='.' else ''
            })
    return file_list, sorted(folder_set)

# --- Delete Repository Helper ---
def delete_repository(namespace_to_delete, pinecone_index, repo_storage):
    """Delete a repository namespace"""
    success, msg = delete_namespace(pinecone_index, namespace_to_delete)
    if success:
        repo_storage.delete_repository(namespace_to_delete)
        st.session_state.repository_deleted = True
        st.session_state.refresh_required = True
        st.session_state.refresh_message = f"Repository '{namespace_to_delete}' deleted"
    return success, msg

# --- Reindex Repository Helper ---
def reindex_repository(namespace, repo_url, pc, pinecone_index, pinecone_index_name, repo_storage, batch_size=10, selected_files=None):
    """Delete and re-index a repository namespace"""
    # Delete existing namespace
    success_del, msg_del = delete_namespace(pinecone_index, namespace)
    if not success_del:
        return False, f"Error deleting namespace: {msg_del}"
    # Reset token tracking
    reset_token_tracking('indexing')
    # Store URL
    repo_storage.store_repository(namespace, repo_url)
    # Perform indexing
    success_idx, msg_idx = index_github_repo(
        repo_url=repo_url,
        namespace=namespace,
        pinecone_client=pc,
        pinecone_index=pinecone_index,
        index_name=pinecone_index_name,
        batch_size=batch_size,
        selected_files=selected_files
    )
    if success_idx:
        st.session_state.repository_added = True
        st.session_state.refresh_required = True
        st.session_state.refresh_message = f"Repository '{namespace}' reindexed successfully. Tokens used: {get_token_usage('indexing'):,}"
    return success_idx, msg_idx

# --- Core Repository Management UI ---
def show_repository_management(pc, pinecone_index, pinecone_index_name, repo_storage, namespace_list):
    st.subheader("Manage GitHub Repositories")
    tabs = st.tabs(["Scan & Index", "Delete Repository"])

    # --- Scan & Index Flow ---
    with tabs[0]:
        st.markdown("### 1) Clone & Scan")

        # Reset everything
        if st.button("Reset Scan", key="reset_scan"):
            for k in (
                "scan_url","temp_dir","repo_path",
                "file_list","selected_files",
                "scan_ns","scan_bs",
                "scanned","indexed"
            ):
                st.session_state.pop(k, None)
            st.success("State cleared. Enter a new repo URL to start.")

        # Step 1: Clone & Scan (only once)
        if not st.session_state.get("scanned", False):
            with st.form("scan_form"):
                st.text_input("GitHub Repo URL", key="scan_url")
                go = st.form_submit_button("Clone & Scan")
            if go:
                url = st.session_state.get("scan_url", "").strip()
                if not url:
                    st.error("Please enter a valid repository URL.")
                else:
                    with st.spinner("Cloning repository…"):
                        temp = tempfile.mkdtemp()
                        st.session_state.temp_dir = temp
                        repo_name = os.path.basename(url).replace(".git","")
                        path = os.path.join(temp, repo_name)
                        Repo.clone_from(url, path)
                        st.session_state.repo_path = path

                    with st.spinner("Scanning files…"):
                        files, _ = scan_repository(path)
                        st.session_state.file_list = files

                    st.session_state.scanned = True
                    st.success(f"Scanned {len(st.session_state.file_list)} files.")
        else:
            # Step 2: Select via AgGrid
            repo_name = os.path.basename(st.session_state.repo_path)
            st.markdown(f"### 2) Select & Index `{repo_name}`")

            df = pd.DataFrame(st.session_state.file_list)
            gb = GridOptionsBuilder.from_dataframe(df)
            gb.configure_selection("multiple", use_checkbox=True, groupSelectsChildren=True)
            grid_opts = gb.build()

            resp = AgGrid(
                df,
                gridOptions=grid_opts,
                enable_enterprise_modules=False,
                update_mode="MODEL_CHANGED",
                height=400,
                fit_columns_on_grid_load=True
            )

            sel = resp.get("selected_rows")
            # 1) if None, no rows selected
            if sel is None:
                selected_rows = []

            # 2) if it's a DataFrame, turn it into list of dicts
            elif isinstance(sel, pd.DataFrame):
                selected_rows = sel.to_dict("records")

            # 3) otherwise assume it's already a list
            else:
                selected_rows = sel

            # now safe to build your path list
            selected = [r["path"] for r in selected_rows]
            st.session_state.selected_files = selected

            # Step 3: Namespace + Batch + Index button
            if selected and not st.session_state.get("indexed", False):
                st.text_input("Namespace", key="scan_ns", value=st.session_state.get("scan_ns",""))
                st.slider("Batch Size", 1, 50, st.session_state.get("scan_bs",10), key="scan_bs")

                if st.button("Index Selected Files", key="scan_index"):
                    ns = st.session_state.scan_ns.strip()
                    bs = st.session_state.scan_bs
                    if not ns:
                        st.error("Please enter a namespace.")
                    else:
                        reset_token_tracking("indexing")
                        repo_storage.store_repository(ns, st.session_state.scan_url)
                        success, msg = index_github_repo(
                            repo_url=st.session_state.scan_url,
                            namespace=ns,
                            pinecone_client=pc,
                            pinecone_index=pinecone_index,
                            index_name=pinecone_index_name,
                            batch_size=bs,
                            selected_files=selected
                        )
                        if success:
                            st.success(msg)
                            st.session_state.indexed = True
                        else:
                            st.error(msg)

            # Step 4: Feedback once done
            if st.session_state.get("indexed", False):
                st.info("✔ Repository has been indexed. Reset if you want to start over.")

    # --- Delete Repository Tab ---
    with tabs[1]:
        st.markdown("### Delete a Namespace")
        ns_list = get_namespaces(pinecone_index)
        if not ns_list:
            st.info("No namespaces available.")
        else:
            st.warning("⚠️ This will permanently delete all vectors in that namespace.")
            to_del = st.selectbox("Namespace", ns_list, key="del_ns")
            if st.button("Delete Repository", key="del_repo"):
                ok, msg = delete_namespace(pinecone_index, to_del)
                if ok:
                    repo_storage.delete_repository(to_del)
                    st.success(f"Deleted namespace “{to_del}”.")
                else:
                    st.error(msg)

    # --- Show Existing Namespaces ---
    st.subheader("Existing Namespaces")
    for ns in get_namespaces(pinecone_index):
        url = repo_storage.get_repository_url(ns) or ""
        st.write(f"- **{ns}** → {url}")
#!/bin/bash
set -e
echo "Starting container..."

# Make sure .streamlit directory exists
mkdir -p /app/.streamlit

echo "Contents of .streamlit directory:"
ls -la /app/.streamlit

echo "Contents of secrets.toml (redacted):"
cat /app/.streamlit/secrets.toml | sed -E 's/([A-Za-z_]+_API_KEY\s*=\s*)"[^"]+"/\1"REDACTED"/g'

echo "Starting Streamlit..."
exec streamlit run /app/streamlit_app.py --server.port=8501 --server.address=0.0.0.0
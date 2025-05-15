FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Add new dependencies for GitHub RAG
RUN echo "pygithub" >> requirements.txt \
    && echo "gitpython" >> requirements.txt \
    && echo "langchain-pinecone" >> requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Make start.sh executable
RUN chmod +x /app/start.sh

# Update start.sh to use app.py instead of streamlit_app.py
RUN sed -i 's/streamlit_app.py/app.py/g' /app/start.sh

# Expose the port Streamlit runs on
EXPOSE 8501

# Command to run the application
CMD ["/app/start.sh"]
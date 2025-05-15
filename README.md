# Dockerized Codebase RAG

This repository contains Docker configuration for the [codebase-rag](https://github.com/jaaacki/codebase-rag) project - a Retrieval Augmented Generation (RAG) system for querying and understanding codebases using Streamlit, Pinecone, and LLMs.

## Features

- 🔍 Semantic Code Search: Uses HuggingFace embeddings to find relevant code snippets
- 💬 Conversational Interface: Built with Streamlit for an intuitive chat experience
- 📚 Multiple Repository Support: Switch between different codebases using namespaces in Pinecone
- 🤖 Advanced LLM Integration: Powered by Groq's LLama models
- 🔄 Context-Aware Responses: Maintains chat history for coherent conversations

## Prerequisites

- Docker and Docker Compose installed on your machine
- Pinecone API key (sign up at [pinecone.io](https://www.pinecone.io/))
- Groq API key for LLama models (sign up at [groq.com](https://console.groq.com/))

## Getting Started

### 1. Clone the Repository

Clone both repositories - this docker configuration and the original codebase:

```bash
# First, clone the original repository
git clone https://github.com/jaaacki/codebase-rag.git
cd codebase-rag

# Copy the Dockerfile, docker-compose.yml and .env.template into the codebase-rag directory
# (assuming you've saved these files somewhere locally)
cp /path/to/Dockerfile .
cp /path/to/docker-compose.yml .
cp /path/to/.env.template .env
```

### 2. Set Up Environment Variables

Copy the `.env.template` file to `.env` and fill in your API keys and other configuration:

```bash
cp .env.template .env
```

Then edit the `.env` file with your actual API keys and configuration values.

### 3. Build and Run with Docker Compose

```bash
docker-compose up --build
```

This will:
- Build the Docker image for the application
- Start the container
- Map port 8501 from the container to your host machine
- Mount the current directory into the container for development

### 4. Access the Application

Open your browser and go to:

```
http://localhost:8501
```

## Development Workflow

With the volume mapping in place, you can edit the files in your local directory and the changes will be reflected in the container. Streamlit will automatically reload the application when it detects changes.

## Production Deployment

For production deployment, you might want to:

1. Use a specific version of Python and dependencies
2. Remove the volume mapping
3. Set up proper logging
4. Consider using a reverse proxy like Nginx
5. Set up proper authentication

Modify the Dockerfile and docker-compose.yml as needed for your production environment.

## Troubleshooting

### Common Issues

1. **Port conflict**: If port 8501 is already in use, change the port mapping in docker-compose.yml to use a different port.
2. **Memory issues**: If the container runs out of memory, you can adjust the memory allocation in docker-compose.yml by adding resource limits.

## License

This Dockerization configuration follows the same license as the original [codebase-rag](https://github.com/jaaacki/codebase-rag) project.

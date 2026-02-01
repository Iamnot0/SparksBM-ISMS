FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements (using JSON array format for paths with spaces)
COPY ["Agentic Framework/requirements.txt", "/app/agent_requirements.txt"]
COPY ["NotebookLLM/api/requirements.txt", "/app/api_requirements.txt"]

# Install dependencies
RUN pip install --no-cache-dir -r /app/agent_requirements.txt && \
    pip install --no-cache-dir -r /app/api_requirements.txt

# Copy source code (using JSON array format for paths with spaces)
COPY ["Agentic Framework", "/app/Agentic Framework"]
COPY ["NotebookLLM", "/app/NotebookLLM"]

# Set Python path to include root so imports work
ENV PYTHONPATH="${PYTHONPATH}:/app"

WORKDIR /app/NotebookLLM

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend

# Expose both microservice ports:
#   8000 → RAG & Voice Service (backend.main)
#   8001 → Tool Execution Service (backend.tool_server)
EXPOSE 8000 8001

# Default entrypoint is the RAG service.
# Override with: command: python -m backend.tool_server  (in docker-compose)
CMD ["python", "-m", "backend.main"]

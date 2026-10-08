FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY backend_pure_rag/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend_pure_rag/ /app/backend_pure_rag

EXPOSE 8000
ENV PORT=8000
ENV PURE_RAG_PORT=8000

CMD ["python", "-m", "backend_pure_rag.main"]

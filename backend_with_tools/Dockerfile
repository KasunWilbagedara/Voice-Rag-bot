FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY backend_with_tools/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend_with_tools/ /app/backend_with_tools

EXPOSE 8001
ENV PORT=8001
ENV TOOLS_RAG_PORT=8001

CMD ["python", "-m", "backend_with_tools.main"]

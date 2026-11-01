# Voice-RAG Bot: Comprehensive System Documentation

## 1. Project Overview
The **Voice-RAG Bot** is an enterprise-grade Retrieval-Augmented Generation (RAG) system built to ingest corporate documents (PDF, DOCX, CSV) and allow users to query them using natural spoken language (Sinhala and English). 

The system enforces **Strict Grounding**, ensuring the AI only answers based on the uploaded documents and never hallucinates external information.

---

## 2. System Architecture

### Pipeline Diagram

```mermaid
flowchart TD
    %% User Inputs
    User((User))
    
    %% Frontend
    subgraph Frontend [Next.js React Frontend]
        UI[Voice Interface & Chat]
    end
    
    %% Backend APIs
    subgraph Backend [Python FastAPI Backend]
        API_RAG[RAG Service]
        API_STT[STT Service]
        API_TTS[TTS Service]
        Parser[Document Parser]
    end
    
    %% Database
    subgraph Database [PostgreSQL + pgvector]
        DB[(Vector DB)]
    end
    
    %% External APIs
    subgraph External [Google Gemini API]
        Embed[Embedding Model]
        LLM[Gemini 2.0 LLM]
    end
    
    %% Flow
    User -- "Speaks (Audio)" --> UI
    UI -- "Audio Blob" --> API_STT
    API_STT -- "Transcribed Text" --> API_RAG
    
    %% RAG Flow
    API_RAG -- "Text to Embed" --> Embed
    Embed -- "Vector" --> API_RAG
    API_RAG -- "Vector Search" --> DB
    DB -- "Top Context Chunks" --> API_RAG
    API_RAG -- "Chunks + Query" --> LLM
    LLM -- "Generated Answer" --> API_RAG
    
    %% TTS Flow
    API_RAG -- "Answer Text" --> API_TTS
    API_TTS -- "Synthesized Audio" --> UI
    UI -- "Plays Audio" --> User
    
    %% Ingestion Flow
    Admin((Admin)) -- "Uploads PDF/DOCX" --> Parser
    Parser -- "Raw Text" --> API_RAG
    API_RAG -- "Chunks" --> Embed
    Embed -- "Vectors" --> DB
    
    %% Styling
    classDef default fill:#f9fafb,stroke:#d1d5db,stroke-width:1px,color:#000
    classDef user fill:#10b981,stroke:#059669,stroke-width:2px,color:#fff
    classDef frontend fill:#000000,stroke:#333333,stroke-width:2px,color:#fff
    classDef backend fill:#3b82f6,stroke:#2563eb,stroke-width:2px,color:#fff
    classDef db fill:#8b5cf6,stroke:#7c3aed,stroke-width:2px,color:#fff
    classDef external fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff
    
    class User,Admin user
    class UI frontend
    class API_RAG,API_STT,API_TTS,Parser backend
    class DB db
    class Embed,LLM external
```

The architecture is divided into a robust Python backend (FastAPI) and a modern, minimalist Next.js React frontend.

### Component Breakdown
1. **Frontend (Next.js 14, React, TailwindCSS)**
   - **Voice Interface**: Captures microphone audio, visualizes it using an HTML5 Canvas emerald waveform, and streams it to the backend.
   - **Document Manager (Admin)**: Allows authorized users to upload knowledge base files.
   - **Context Drawer**: A transparency feature letting users see exactly which document chunks were used by the AI to formulate an answer.

2. **Backend (Python FastAPI, Uvicorn)** — two services:
   - **Backend 1 (port 8000, `backend/main.py`)**: documents, hybrid search, STT/TTS, voice pipeline, memory and history.
   - **Backend 2 (port 8001, `backend/tool_server.py`)**: agentic RAG with tool calling, databases, students.
   - **RAG Engine (`backend/rag/`)**: recursive structural chunking, Gemini/OpenAI embeddings, hybrid dense + BM25 search fused with RRF, and an MMR diversity filter for Pure RAG mode.
   - **Database**: PostgreSQL with `pgvector` (cosine distance), mirrored to a local SQLite store that is used when PostgreSQL is offline.
   - **LLM Generator**: Gemini Flash models (`gemini-3.5-flash` family) or any OpenAI-compatible model.

3. **Backend modes** (UI mode switcher → `x-backend-mode` header, applied to text *and* voice):
   - **Pure RAG**: answers only from retrieved document chunks — no tool lookups.
   - **RAG + Tools**: an agentic loop that may call tools (orders, tickets, students, SQL, weather, web search, calculator) before answering.

---

## 3. Core Workflows

### A. Document Ingestion Workflow
When an Admin uploads a file:
1. **Extraction**: `backend/document_parser.py` extracts raw text from PDF/DOCX/XLSX/PPTX/images.
2. **Chunking**: `backend/rag/chunker.py` splits the text into structure-aware chunks of ~500 characters.
3. **Embedding**: The chunks are sent to the Embedding API to create mathematical vectors.
4. **Storage**: Vectors and metadata are stored securely in the PostgreSQL `pgvector` database.

### B. Voice Query Workflow
When a User speaks into the microphone:
1. **Audio Capture**: The frontend records a `.webm` or `.mp3` audio blob.
2. **STT (Speech-to-Text)**: Sent to `/api/stt`, transcribed into text (Sinhala or English).
3. **Hybrid Search**: The query is embedded and matched against stored chunks (pgvector or SQLite) and by BM25 keywords; the two rankings are fused. Pure RAG mode then applies an MMR diversity filter (top 5).
4. **LLM Generation**: The system prompt + retrieved chunks + user query are sent to Gemini.
   - *Rule Check*: If the query is ambiguous (e.g., "list all employees"), the LLM asks for clarification.
   - *Grounding Check*: If the answer is not in the documents, the LLM refuses to answer.
5. **TTS (Text-to-Speech)**: The text answer is converted into a spoken audio file.
6. **Playback**: The frontend receives the audio blob, plays it, and renders the text in the chat history.

---

## 4. Environment Configuration (.env)

To run the project, the following environment variables are required in the root `.env` file:

```env
# AI Models
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key

# Database
DATABASE_URL=postgresql://postgres:postgrespassword@postgres:5432/voicerag
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgrespassword
POSTGRES_DB=voicerag

# Application
PORT=8000
TOOL_PORT=8001
PYTHON_BACKEND_URL=http://localhost:8000
PYTHON_TOOL_BACKEND_URL=http://localhost:8001

# Optional hardening
# ADMIN_API_KEY=...        # protects upload/delete/reset/connect & raw tool calls (sent as x-admin-key)
# CORS_ORIGINS=http://localhost:3000
```

---

## 5. Deployment & Execution

The project is fully containerized for seamless cross-platform deployment.

### Running with Docker (Production/Standard)
Ensure Docker Desktop is running, then execute:
```bash
docker-compose up -d --build
```
This single command spins up:
- The PostgreSQL `pgvector` Database (Port 5433 on the host)
- Backend 1 — RAG & Voice (Port 8000)
- Backend 2 — RAG + Tools (Port 8001)
- The Next.js Web Frontend (Port 3000)

**Access the App**: [http://localhost:3000](http://localhost:3000)

### Updating Configurations
If you modify `.env` or any backend Python code, rebuild the container:
```bash
docker-compose up -d --build rag-service tool-service
```

---

## 6. Maintenance & Troubleshooting

- **No Voice Playback?** Ensure your browser allows auto-playing audio and microphone permissions are granted.
- **Hallucinations?** Use Pure RAG mode, and check the prompts in `backend/rag/prompts.py`.
- **Database Connection Issues?** Verify the PostgreSQL container is healthy via `docker ps`.

*Built for SLT-INTERN-PROJECT.*

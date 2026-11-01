# Voice-RAG Bot 🎙️⚡

Enterprise **Voice-In, Voice-Out Retrieval-Augmented Generation (Voice-RAG)** web application with a **Standalone Python (FastAPI) Backend & RAG Model** and a **Next.js Demonstration Frontend UI**. Supports natural spoken Sinhala (සිංහල) and English.

![Python FastAPI](https://img.shields.io/badge/Python-FastAPI-blue?style=for-the-badge&logo=fastapi)
![PostgreSQL pgvector](https://img.shields.io/badge/PostgreSQL-pgvector-blue?style=for-the-badge&logo=postgresql)
![Google Gemini](https://img.shields.io/badge/Google-Gemini%202.0-orange?style=for-the-badge&logo=google)
![Next.js](https://img.shields.io/badge/Next.js-Demonstration%20UI-black?style=for-the-badge&logo=next.js)

---

## 🌟 Key Architecture

### Pipeline Diagram

```mermaid
flowchart TD
    User((User)) -- "Voice / Text" --> UI[Next.js Frontend]
    UI -- "Query" --> API[FastAPI Backend]
    
    subgraph Python Backend
        API --> Embedding[Embedding Engine]
        Embedding --> DB[(pgvector DB)]
        DB -. "Relevant Chunks" .-> LLM_Prompt[System Prompt]
        LLM_Prompt --> LLM[Gemini LLM]
        LLM --> TTS[Text-to-Speech]
    end
    
    TTS -- "Audio Stream" --> UI
    UI -- "Plays Answer" --> User

    classDef default fill:#f9fafb,stroke:#d1d5db,color:#000
    classDef user fill:#10b981,stroke:#059669,color:#fff
    class User user
```

1. **Python FastAPI Backend (`backend/`)**:
   - **Framework**: FastAPI + Uvicorn (`http://localhost:8000`)
   - **Document Parsing**: PDF (`pypdf`), Word DOCX (`python-docx`), TXT, Markdown.
   - **RAG & Vector Search**: Text chunking, Gemini (`google-genai`) & OpenAI embeddings, HNSW cosine distance search in PostgreSQL (`pgvector`), and hybrid document overview retrieval.
   - **Multilingual LLM Reasoning**: Natural spoken Sinhala (සිංහල) & English prompt instructions for high accuracy.
   - **Voice Services**: Multimodal Audio Speech-to-Text (STT) and High-Fidelity Text-to-Speech (TTS) audio streaming.

2. **Next.js Demonstration Frontend (`src/`)**:
   - Web UI demonstration running on port `3000`.
   - Real-time HTML5 canvas audio waveform visualizer.
   - Transparently proxies requests to the Python backends (`PYTHON_BACKEND_URL`, `PYTHON_TOOL_BACKEND_URL`).

### Services & Backend Modes

| Service | Port | Entry point | Role |
|---|---|---|---|
| Backend 1 — Pure RAG & Voice | 8000 | `backend/main.py` | Accounts, documents, hybrid search, Pure RAG answers (`/api/rag`, `/api/rag/stream`), STT/TTS, memory & history |
| Backend 2 — RAG + Tools | 8001 | `backend/tool_server.py` | Agentic RAG (`/api/agentic-rag`, `/api/rag/stream`), 13-tool registry, databases, students, STT/TTS |
| MCP Server | 8005 | `backend/mcp_server.py` | Separate process exposing the same 13 tools to MCP clients (Claude Desktop, Cursor) over SSE or stdio |
| RAG v2 (standalone, optional) | 8002 | `rag_v2/main.py` | Streaming RAG with LLM reranking; not used by the UI |

All services share one data store: `backend/customer_datasets.db` (SQLite; override with `SQLITE_DB_PATH`), mirrored to PostgreSQL + pgvector when `DATABASE_URL` is reachable.

The UI's mode switcher is sent as the `x-backend-mode` header on **both** text and voice queries:

- **Pure RAG** (`pure`) → Backend 1: hybrid search (dense + BM25, merged with Reciprocal Rank Fusion) → MMR diversity filter → LLM grounded only in the retrieved document chunks (no tool calls).
- **RAG + Tools** (`tools`) → Backend 2: agentic multi-step LLM loop that can call tools (orders, tickets, students, SQL, weather, web search, math). The answer arrives as one piece because the agent decides on tools before answering.
- No header (direct API calls): standard RAG with contextual tool enrichment.

---

## 🚀 How to Run the Project

### 1. Environment Setup
Create `.env` or `.env.local` in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5432/voicerag
PYTHON_BACKEND_URL=http://localhost:8000
PYTHON_TOOL_BACKEND_URL=http://localhost:8001

# Optional hardening
# ADMIN_API_KEY=some-long-random-string   # required (x-admin-key) for upload/delete/reset/connect & raw tool calls
# CORS_ORIGINS=http://localhost:3000      # browser origins allowed to call the Python services directly
# AUTH_REQUIRED=false                    # turn off login (local scripts / tests only)
```

When `ADMIN_API_KEY` is set, the Next.js proxy forwards it to the backends automatically, so the
UI keeps working while direct calls to the destructive endpoints require the key. Leave it unset for
local development.

**User accounts.** Chat, voice, memory and history require a logged-in user (username + password,
created from the login screen). Each user has their own memory and conversation history. The login
token is kept in an httpOnly cookie by the Next.js proxy and forwarded to the backends. For scripts
that call the Python API directly (e.g. `eval/run_eval.py`), set `AUTH_REQUIRED=false` on the backend.

---

### 2. Start Services via Docker (Recommended)

Run PostgreSQL with `pgvector` and the Python FastAPI Backend:

```bash
docker compose up --build -d
```

- **Python Backend**: `http://localhost:8000` (API Docs: `http://localhost:8000/docs`)
- **PostgreSQL**: `localhost:5432`

---

### 3. Running Locally (Without Docker)

#### A. Start the Python backends:
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r backend/requirements.txt

# Start Backend 1 (RAG & Voice, port 8000) and Backend 2 (RAG + Tools, port 8001)
python -m backend.main
python -m backend.tool_server      # in a second terminal
```

**Upgrading an existing database?** Embeddings are now always 768-dim and tagged with the model that made them.
Re-embed old documents once (also needed after switching between a Gemini and an OpenAI key):
`python -m backend.reembed`

Run the backend tests with `pip install -r backend/requirements-dev.txt && python -m pytest backend/test`.

#### B. Start Next.js Demonstration Frontend:
```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 📁 Project Structure

```text
Voice-Rag-bot/
├── backend/                        # Python backends & RAG engine
│   ├── main.py                     # Backend 1 — RAG & Voice (port 8000)
│   ├── tool_server.py              # Backend 2 — RAG + Tools (port 8001)
│   ├── mcp_server.py               # MCP server (port 8005 / --stdio)
│   ├── config.py                   # Environment configuration & API key handling
│   ├── security.py                 # CORS settings & admin-key guard
│   ├── db.py                       # PostgreSQL pool, SQLite store, memory & chat history
│   ├── document_parser.py          # PDF, DOCX, XLSX, PPTX, image OCR, text extraction
│   ├── audio_service.py            # STT transcription & TTS audio generation
│   ├── rag/                        # chunker, embedder, retriever (hybrid + MMR), prompts,
│   │                               # generator, agentic_generator, pipeline, ingester, sql_gen
│   ├── routers/                    # documents, rag, agentic_rag, audio, memory, databases, students
│   ├── services/db_query/          # Database manager, safe read-only SQL, CSV import, students
│   ├── tools/                      # Tool registry + DB / external tools, LangChain & Composio
│   ├── test/                       # pytest suite
│   ├── requirements.txt            # Python dependencies
│   └── Dockerfile                  # Python containerization definition
├── rag_v2/                         # Standalone RAG v2 service (port 8002, optional)
├── src/                            # Next.js Demonstration Frontend UI
│   ├── app/
│   │   ├── api/                    # Thin proxy routes forwarding to the Python backends
│   │   └── page.tsx                # Main Voice-RAG dashboard interface
│   └── components/                 # Voice UI, Document/Database managers, charts, modals
└── docker-compose.yml              # PostgreSQL + both backends + web UI
```

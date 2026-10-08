# Voice-RAG Bot 🎙️⚡

Enterprise **Voice-In, Voice-Out Retrieval-Augmented Generation (Voice-RAG)** web application with **Dual Dedicated Python (FastAPI) Backends** and a **Next.js Demonstration Frontend UI**. Supports natural spoken Sinhala (සිංහල) and English.

![Python FastAPI](https://img.shields.io/badge/Python-FastAPI-blue?style=for-the-badge&logo=fastapi)
![SQLite & pgvector](https://img.shields.io/badge/Database-SQLite%20%7C%20pgvector-blue?style=for-the-badge&logo=sqlite)
![Google Gemini](https://img.shields.io/badge/Google-Gemini%202.5%20%7C%203.5-orange?style=for-the-badge&logo=google)
![Next.js](https://img.shields.io/badge/Next.js-Dual--Mode%20UI-black?style=for-the-badge&logo=next.js)

---

## 🌟 Architecture: Two Dedicated Backends

This project is separated into two independent, purpose-built backends:

```
                            ┌───────────────────────────────────────────────┐
                            │            Next.js Frontend (Port 3000)       │
                            │      [ Switcher: Pure RAG  |  RAG + Tools ]   │
                            └───────────────────────┬───────────────────────┘
                                                    │
                                  x-backend-mode    │
                         ┌──────────────────────────┴──────────────────────────┐
                         ▼                                                     ▼
        ┌──────────────────────────────────┐                 ┌──────────────────────────────────┐
        │     1. Pure RAG Backend          │                 │     2. RAG with Tools Backend    │
        │     Port 8000 (pure_rag.db)      │                 │     Port 8001 (customer_db)      │
        ├──────────────────────────────────┤                 ├──────────────────────────────────┤
        │ • Document Parsing (PDF, DOCX)   │                 │ • Document Parsing & Vector RAG  │
        │ • Gemini Vector Embeddings       │                 │ • 13 Real-Time Tools Registered  │
        │ • Document RAG Search            │                 │ • Live Weather & DateTime        │
        │ • Multilingual Voice STT / TTS   │                 │ • Safe Math Calculator           │
        │ • Pure LLM Grounded Generation   │                 │ • Live Web Search (DuckDuckGo)   │
        │ ❌ NO External Tools             │                 │ • Customer Orders & Support      │
        │ ❌ NO Multi-DB / Text-to-SQL     │                 │ • Safe Multi-DB SQL Queries      │
        │ ❌ NO Session Memory Extraction  │                 │ • Persistent Session Memory      │
        └──────────────────────────────────┘                 └──────────────────────────────────┘
```

### 1. Pure RAG Backend (`backend_pure_rag/`) — **Port 8000**
- **Focus**: Dedicated solely to clean Document Retrieval-Augmented Generation & AI reasoning.
- **Tools**: **Zero external tools.** No calculator, no weather, no order lookup, no database query tools, and no session memory extraction.
- **Grounding**: Strict document-first prompts that cite retrieved passages directly.
- **Database**: Dedicated persistent SQLite `pure_rag.db` with support for optional PostgreSQL/pgvector.
- **Voice**: Full speech-to-text (STT) and text-to-speech (TTS) voice pipeline.

### 2. RAG with Tools Backend (`backend_with_tools/`) — **Port 8001**
- **Focus**: Full-featured Agentic Voice-RAG system combining Document Knowledge with Live Tools.
- **Tools Included (13 Registered Tools)**:
  1. `get_live_weather`: Open-Meteo real-time weather forecasts.
  2. `web_search`: DuckDuckGo real-time internet search.
  3. `get_current_datetime`: Accurate current time and date in any timezone.
  4. `calculate_expression`: Safe AST-based mathematical evaluation.
  5. `track_customer_order`: Order status, delivery tracking, and item details.
  6. `track_support_ticket`: Customer support ticket resolution status.
  7. `lookup_student`: Student academic records, GPA, and department lookup.
  8. `execute_sql`: Read-only multi-database SQL executor with SQL injection protection.
  9. `list_databases`: Discover available attached SQL databases and tables.
  10. `get_database_schema`: Inspect database schema definitions and columns.
  11. `get_session_memories`: Retrieve persistent user preferences and memory keys.
  12. `save_session_memory`: Store personalized user preferences across sessions.
  13. `search_knowledge_base`: Internal document vector search tool.
- **Database**: Local SQLite `customer_datasets.db` pre-seeded with customer orders, support tickets, and student records.

---

## 🚀 Quick Start Guide

### 1. Environment Configuration
Create a `.env` file in the root directory:

```env
GEMINI_API_KEY=your_gemini_api_key_here
PURE_RAG_PORT=8000
TOOLS_RAG_PORT=8001
PURE_RAG_BACKEND_URL=http://localhost:8000
TOOLS_RAG_BACKEND_URL=http://localhost:8001
```

---

### 2. Run Locally

#### Option A: Run Everything All-in-One (Recommended ⭐)
Run both backends (Ports 8000 & 8001) and the Next.js frontend (Port 3000) simultaneously with one single command:
```bash
npm run dev:all
# OR: ./start_all.sh
# OR: make run-all
```
Open **[http://localhost:3000](http://localhost:3000)** in your browser!

---

#### Option B: Run in Separate Terminals

**Terminal 1 — Backend 1: Pure RAG (Port 8000)**:
```bash
npm run backend:pure
# OR: ./venv/bin/python -m backend_pure_rag.main
# OR: make run-pure-rag
```
*API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)*

**Terminal 2 — Backend 2: RAG with Tools (Port 8001)**:
```bash
npm run backend:tools
# OR: ./venv/bin/python -m backend_with_tools.main
# OR: make run-tools-rag
```
*API Docs: [http://localhost:8001/docs](http://localhost:8001/docs)*

**Terminal 3 — Frontend UI (Port 3000)**:
```bash
npm run dev
```
Open **[http://localhost:3000](http://localhost:3000)** in your browser.

---

### 3. Docker Compose Setup

Run both backends and PostgreSQL simultaneously with Docker Compose:

```bash
docker compose up --build -d
```

- **Pure RAG Backend**: [http://localhost:8000](http://localhost:8000) (Docs: [http://localhost:8000/docs](http://localhost:8000/docs))
- **RAG with Tools Backend**: [http://localhost:8001](http://localhost:8001) (Docs: [http://localhost:8001/docs](http://localhost:8001/docs))
- **PostgreSQL**: `localhost:5432`

---

## 🖥️ Using the Demonstration Frontend

The Next.js user interface includes a **Mode Switcher** in the top navigation bar:

1. **Pure RAG Mode**:
   - Routes requests directly to **Port 8000**.
   - Displays a green status indicator for Backend 1.
   - Shows document-focused sample queries (e.g. *"What enterprise cloud solutions does SLT offer?"*).
   - Knowledge Base manager connects to `pure_rag.db`.

2. **RAG + Tools Mode**:
   - Routes requests directly to **Port 8001**.
   - Displays a purple status indicator for Backend 2.
   - Shows tool-focused sample queries (e.g. *"What is the weather in Colombo?"*, *"Track order ORD-1002"*, *"Calculate 450 * 12 + 85"*).
   - Knowledge Base manager connects to `customer_datasets.db`.

---

## 🔌 Model Context Protocol (MCP) Server

This project includes a native **Model Context Protocol (MCP)** server built with the official `mcp` SDK, exposing all 13 tools to the wider AI ecosystem (Claude Desktop, Cursor, external IDEs, and AI agents).

### 1. Run MCP Server via Standard I/O (`stdio`):
Best for desktop applications like Claude Desktop or Cursor:
```bash
npm run mcp:server
# Or: ./venv/bin/python -m backend_with_tools.mcp_server
# Or: make run-mcp-server
```

### 2. Run MCP Server via Server-Sent Events (`SSE`):
Best for remote network access and web clients:
```bash
npm run mcp:sse
# Or: ./venv/bin/python -m backend_with_tools.mcp_server --transport sse --port 8005
```
*Live SSE Endpoint: [http://localhost:8005/sse](http://localhost:8005/sse)*

### 3. Integrated FastAPI MCP Endpoint:
When `backend_with_tools` is running on port 8001, the MCP SSE server is also directly mounted at:
`http://localhost:8001/mcp/sse`

### 4. Claude Desktop & Cursor Configuration:
Add the following to your Claude Desktop config (`claude_desktop_config.json`) or Cursor MCP settings:
```json
{
  "mcpServers": {
    "voicerag-tools": {
      "command": "/Users/uvs/SLT/Rag Voice/Voice-Rag-bot/venv/bin/python",
      "args": ["-m", "backend_with_tools.mcp_server"],
      "env": {
        "PYTHONPATH": "/Users/uvs/SLT/Rag Voice/Voice-Rag-bot"
      }
    }
  }
}
```
*(A ready-to-use template is available in [`mcp_client_config.json`](file:///Users/uvs/SLT/Rag%20Voice/Voice-Rag-bot/mcp_client_config.json))*

---

## 📁 Directory Structure

```text
Voice-Rag-bot/
├── backend_pure_rag/               # 🔹 BACKEND 1: PURE RAG (Port 8000)
│   ├── main.py                     # FastAPI entry point (/health -> mode: "pure_rag")
│   ├── config.py                   # Port 8000, pure_rag.db
│   ├── db.py                       # Pure RAG SQLite / pgvector storage
│   ├── document_parser.py          # PDF, DOCX, TXT parser
│   ├── rag_service.py              # Pure vector search & strict document grounding (ZERO tools)
│   ├── audio_service.py            # STT & TTS voice services
│   ├── routers/
│   │   ├── documents.py            # Upload, list, delete docs in pure_rag.db
│   │   ├── rag.py                  # Pure RAG query answering
│   │   ├── audio.py                # Voice pipeline (STT + Pure RAG + TTS)
│   │   └── history.py              # Pure RAG chat history
│   ├── requirements.txt
│   ├── Dockerfile
│   └── run.py
│
├── backend_with_tools/             # 🔸 BACKEND 2: RAG + TOOLS (Port 8001)
│   ├── main.py                     # FastAPI entry point (/health -> mode: "rag_with_tools")
│   ├── config.py                   # Port 8001, customer_datasets.db
│   ├── db.py                       # SQLite / pgvector storage + student seed
│   ├── tools/                      # 🛠️ Modular Tool Architecture (Each tool in its own file)
│   │   ├── __init__.py             # Central registry loader and package exports
│   │   ├── base.py                 # Registry engine, @register_tool decorator, dispatchers
│   │   ├── weather.py              # Live weather tool (get_live_weather)
│   │   ├── web_search.py           # Real-time web search (web_search)
│   │   ├── datetime_tool.py        # Date/time awareness (get_current_datetime)
│   │   ├── calculator.py           # Safe AST math evaluator (calculate_expression)
│   │   ├── order_tracking.py       # Customer orders tool (track_customer_order)
│   │   ├── ticket_tracking.py      # Support tickets tool (track_support_ticket)
│   │   ├── student_lookup.py       # Academic record tool (lookup_student)
│   │   ├── sql_executor.py         # Safe read-only SQL executor (execute_sql)
│   │   ├── database_inspection.py  # DB & schema inspection (list_databases, get_database_schema)
│   │   ├── session_memory.py       # Persistent memory tool (get_session_memories, save_session_memory)
│   │   └── knowledge_search.py     # Document vector search tool (search_knowledge_base)
│   ├── db_query_service.py         # Multi-database inspection and safe SQL runner
│   ├── document_parser.py          # PDF, DOCX, TXT parser
│   ├── rag_service.py              # Vector RAG + Tool-augmented reasoning
│   ├── audio_service.py            # STT & TTS voice services
│   ├── routers/
│   │   ├── documents.py            # Document management
│   │   ├── rag.py                  # Tool-augmented RAG query answering
│   │   ├── audio.py                # Voice pipeline (STT + Tools RAG + TTS)
│   │   ├── databases.py            # Multi-DB listing and safe SQL execution
│   │   ├── students.py             # Student lookup API
│   │   ├── memory.py               # Session memory management
│   │   └── history.py              # Chat history with tool execution metadata
│   ├── customer_datasets.db        # Pre-seeded SQLite database
│   ├── requirements.txt
│   ├── Dockerfile
│   └── run.py
│
├── src/                            # 💻 SHARED DEMONSTRATION FRONTEND (Port 3000)
│   ├── app/
│   │   ├── api/                    # Proxy endpoints dispatching via x-backend-mode
│   │   │   ├── backend-status/     # Simultaneous health check of both backends
│   │   │   ├── rag/                # Proxy to :8000 or :8001
│   │   │   ├── voice-pipeline/     # Proxy to :8000 or :8001
│   │   │   └── documents/          # Proxy to :8000 or :8001
│   │   └── page.tsx                # Dual-mode switcher & adaptive dashboard
│   ├── components/                 # VoiceInterface, DocumentManager, AudioVisualizer
│   └── lib/backend-config.ts       # Backend URL resolution helper
│
├── docker-compose.yml              # Multi-container orchestration (Pure RAG + Tools RAG + Postgres)
├── Makefile                        # Convenience commands (run-pure-rag, run-tools-rag, run-frontend)
└── package.json                    # Scripts: backend:pure, backend:tools, dev
```

---

## 🧪 Verification & Testing

Verify that both backends are running correctly:

```bash
# Check Pure RAG Backend
curl http://localhost:8000/health
# Response: {"status": "healthy", "mode": "pure_rag", "tools_enabled": false, ...}

# Check RAG with Tools Backend
curl http://localhost:8001/health
# Response: {"status": "healthy", "mode": "rag_with_tools", "tools_enabled": true, "tools": [...]}
```

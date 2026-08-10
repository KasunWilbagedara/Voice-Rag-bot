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
   - Transparently proxies requests to the Python FastAPI backend (`PYTHON_BACKEND_URL`).

---

## 🚀 How to Run the Project

### 1. Environment Setup
Create `.env` or `.env.local` in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5432/voicerag
PYTHON_BACKEND_URL=http://localhost:8000
```

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

#### A. Start Python FastAPI Backend:
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r backend/requirements.txt

# Start backend server
python -m backend.main
```

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
├── backend/                        # Full Python Backend & RAG Engine
│   ├── main.py                     # FastAPI application entry point
│   ├── config.py                   # Environment configuration & API key handling
│   ├── db.py                       # PostgreSQL pgvector connection & in-memory fallback
│   ├── document_parser.py          # PDF, DOCX, TXT document text extraction
│   ├── rag_service.py              # Chunking, vector embeddings, search & LLM generation
│   ├── audio_service.py            # STT transcription & TTS audio stream generation
│   ├── routers/
│   │   ├── documents.py            # Document upload, listing, seeding & deletion APIs
│   │   ├── rag.py                  # Text RAG generation API
│   │   └── audio.py                # STT, TTS, & unified voice pipeline APIs
│   ├── requirements.txt            # Python dependencies
│   └── Dockerfile                  # Python containerization definition
├── src/                            # Next.js Demonstration Frontend UI
│   ├── app/
│   │   ├── api/                    # Thin proxy routes forwarding to Python backend
│   │   └── page.tsx                # Main Voice-RAG dashboard interface
│   └── components/                 # Voice UI, Document Manager, Waveform Visualizer
└── docker-compose.yml              # Multi-container setup (PostgreSQL + Python Backend)
```

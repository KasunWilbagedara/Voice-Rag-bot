# Voice-RAG Bot 🎙️⚡

Production-grade **Voice-In, Voice-Out Retrieval-Augmented Generation (Voice-RAG)** web application powered by **Next.js (App Router)**, **PostgreSQL with `pgvector`**, and **OpenAI APIs**.

![Voice RAG Architecture](https://img.shields.io/badge/PostgreSQL-pgvector-blue?style=for-the-badge&logo=postgresql)
![Next.js](https://img.shields.io/badge/Next.js-14-black?style=for-the-badge&logo=next.js)
![OpenAI](https://img.shields.io/badge/OpenAI-Whisper%20%7C%20Embeddings%20%7C%20TTS-green?style=for-the-badge&logo=openai)

---

## 🌟 Key Features

1. **Document Ingestion**: Upload PDF, DOCX, TXT, or Markdown documents. Files are parsed, chunked, embedded using OpenAI `text-embedding-3-small` (1536 dimensions), and indexed in PostgreSQL using `pgvector` with **HNSW** cosine distance search (`vector_cosine_ops`).
2. **Voice Input (STT)**: Speak directly into your microphone. Web Audio API captures the speech and transcribes it into text via OpenAI Whisper (`whisper-1`).
3. **Vector Similarity Retrieval**: Spoken queries are embedded and searched against document chunks in PostgreSQL using HNSW similarity search (`ORDER BY embedding <=> query_vector`).
4. **Conversational LLM Generation**: Answers are synthesized by `gpt-4o-mini` / `gpt-4o` using voice-tuned system prompts that ground answers strictly in document context.
5. **Real-Time Voice Output (TTS)**: Answers are converted into natural speech via OpenAI TTS (`tts-1`) and played back with real-time waveform visualizers.
6. **Retrieved Context Inspector**: Interactive slide-over drawer displaying exact retrieved document chunks, match similarity percentages (e.g. `91.2% Match`), and source titles.
7. **Dynamic In-Memory Fallback**: If PostgreSQL is not active during quick local testing, an in-memory vector similarity engine automatically activates.

---

## 🏗️ Database Schema (PostgreSQL + pgvector)

Located in [`scripts/init-db.sql`](scripts/init-db.sql):

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents Table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Document Chunks with 1536-dim Embeddings
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    chunk_index INT NOT NULL,
    embedding VECTOR(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- HNSW Vector Index for Fast Similarity Search
CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- Conversation History
CREATE TABLE chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_query_text TEXT NOT NULL,
    retrieved_chunks JSONB,
    ai_response_text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Node.js**: v18+ or v20+
- **Docker** (optional, for running PostgreSQL + pgvector)
- **OpenAI API Key** (`sk-proj-...`)

### 2. Environment Setup
Create a `.env.local` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key_here
DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5432/voicerag
```

### 3. Start Database (Docker)
Launch PostgreSQL with `pgvector/pgvector:pg16`:

```bash
docker compose up -d
```

### 4. Run Next.js Development Server
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 📄 Testing with Sample Document

A pre-packaged sample document is provided in [`docs/sample_voice_rag_knowledge_base.md`](docs/sample_voice_rag_knowledge_base.md).

### Steps to Test:
1. Open the app at [http://localhost:3000](http://localhost:3000).
2. Click **Settings** (⚙️ icon) to enter your OpenAI API key (or set `OPENAI_API_KEY` in `.env.local`).
3. Drag & drop [`docs/sample_voice_rag_knowledge_base.md`](docs/sample_voice_rag_knowledge_base.md) into the **Knowledge Base Documents** area.
4. Click the **Microphone** button and ask:
   - *"What document formats are supported in Voice RAG?"*
   - *"Which model is used for generating 1536 dimensional vectors?"*
   - *"How does the PostgreSQL vector similarity search work?"*
5. Listen to the AI voice response and click **Retrieved Chunks** to inspect the matching vector text segments and cosine similarity match scores!

---

## 📁 Project Structure

```text
Voice-Rag-bot/
├── app/
│   ├── api/
│   │   ├── documents/upload/route.ts   # Document parsing & vector ingestion
│   │   ├── documents/route.ts          # Document listing & deletion
│   │   ├── stt/route.ts                # OpenAI Whisper Speech-to-Text
│   │   ├── rag/route.ts                # Vector search & LLM generation
│   │   ├── tts/route.ts                # OpenAI TTS audio stream
│   │   └── voice-pipeline/route.ts     # End-to-End unified voice route
│   ├── globals.css                     # Dark glassmorphism styles
│   ├── layout.tsx                      # Root layout
│   └── page.tsx                        # Main Voice-RAG dashboard
├── components/
│   ├── AudioVisualizer.tsx             # Live HTML5 Canvas waveform animation
│   ├── VoiceInterface.tsx              # Push-to-Talk & Hands-Free mic interface
│   ├── DocumentManager.tsx             # Drag-and-drop document dropzone
│   ├── ContextDrawer.tsx               # RAG vector chunks slide-over inspector
│   └── SettingsModal.tsx               # API key, TTS voice, & model settings
├── docs/
│   └── sample_voice_rag_knowledge_base.md # Pre-built test document
├── lib/
│   ├── db.ts                           # Postgres pool & in-memory fallback
│   ├── document-parser.ts              # PDF, DOCX, TXT, & MD parser
│   ├── rag-service.ts                  # Chunker, embeddings, HNSW search & LLM
│   └── audio-service.ts                # Whisper STT & OpenAI TTS audio
├── scripts/
│   └── init-db.sql                     # PostgreSQL + pgvector schema
└── docker-compose.yml                  # PostgreSQL pgvector container setup
```

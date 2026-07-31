# Voice-RAG Knowledge Base & System Specification

## Overview
Voice-RAG (Voice-In, Voice-Out Retrieval-Augmented Generation) is an advanced artificial intelligence system that allows users to communicate with specialized knowledge bases using natural human speech. Instead of typing text queries, users speak into their microphone. The system transcribes the speech, retrieves relevant context from stored documents, generates an accurate answer, and responds back in natural human voice audio.

## Key System Components

### 1. Document Ingestion Engine
- **Supported Formats**: PDF, DOCX, Plain Text (TXT), and Markdown (MD).
- **Text Chunking**: Documents are split into semantic chunks of approximately 500 characters with a 100-character overlap to preserve contextual continuity.
- **Vector Embeddings**: Each text chunk is processed through OpenAI's `text-embedding-3-small` model, producing a 1536-dimensional floating-point vector representation.

### 2. Database Architecture (PostgreSQL + pgvector)
- **Vector Storage**: Uses the `pgvector` PostgreSQL extension with the `VECTOR(1536)` data type.
- **Similarity Indexing**: Implements Hierarchical Navigable Small World (**HNSW**) indexes with `vector_cosine_ops` for fast, scalable vector cosine distance queries (`<=>`).
- **Relational Tables**:
  - `documents`: Tracks uploaded files, titles, file types, and timestamps.
  - `document_chunks`: Stores raw chunk text content, chunk index, document foreign key, and vector embedding column.
  - `chat_history`: Stores past user spoken queries, retrieved chunk JSON data, and AI vocal responses.

### 3. Speech Processing Pipeline
- **Speech-to-Text (STT)**: Browser audio recorded via Web Audio API `MediaRecorder` is sent to OpenAI Whisper (`whisper-1`) for precise transcription.
- **Answer Generation (LLM)**: Uses `gpt-4o-mini` or `gpt-4o` with system prompts specifically formatted for vocal delivery (concise, conversational, free of markdown symbols).
- **Text-to-Speech (TTS)**: Converts the AI response into natural high-fidelity MP3 audio using OpenAI Audio TTS (`tts-1`) with voices like `nova`, `alloy`, `echo`, `fable`, `onyx`, and `shimmer`.

## Sample Voice Questions to Try
- "What are the supported document formats in Voice RAG?"
- "How does the vector similarity search work in PostgreSQL?"
- "Which embedding model is used for generating 1536-dimensional vectors?"
- "What TTS voices are available in the system?"

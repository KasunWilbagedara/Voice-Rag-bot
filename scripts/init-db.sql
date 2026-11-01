-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Document Chunks with Vector Embeddings (OpenAI 1536 dims, Gemini gemini-embedding-001 3072 dims)
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    chunk_index INT NOT NULL,
    embedding VECTOR, -- Vector column matching active embedding model
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- NOTE: no HNSW index here. pgvector can only index a column with a fixed
-- dimension (and at most 2000 dims for `vector`), but this column stores
-- whichever provider's embeddings are active (1536 or 3072 dims). Creating the
-- index on the untyped column fails and aborts the container's init script.
-- Once you settle on one embedding model with <= 2000 dims, you can add e.g.:
--   ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1536);
--   CREATE INDEX document_chunks_embedding_hnsw_idx
--     ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- Conversation History (scoped per session)
CREATE TABLE IF NOT EXISTS chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) NOT NULL DEFAULT 'default_user',
    user_query_text TEXT NOT NULL,
    retrieved_chunks JSONB,
    ai_response_text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

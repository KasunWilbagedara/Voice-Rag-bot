import { Pool } from 'pg';

// Initialize Postgres connection pool
const connectionString = process.env.DATABASE_URL || 'postgresql://postgres:postgrespassword@localhost:5432/voicerag';

let pool: Pool | null = null;

export function getDbPool(): Pool {
  if (!pool) {
    pool = new Pool({
      connectionString,
      max: 10,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 3000,
    });
  }
  return pool;
}

// In-Memory fallback store for when PostgreSQL is not connected / active
export interface InMemoryDocument {
  id: string;
  title: string;
  file_type: string;
  created_at: string;
}

export interface InMemoryChunk {
  id: string;
  document_id: string;
  content: string;
  chunk_index: number;
  embedding: number[];
  created_at: string;
}

export interface InMemoryChat {
  id: string;
  user_query_text: string;
  retrieved_chunks: any;
  ai_response_text: string;
  created_at: string;
}

class MemoryStore {
  documents: InMemoryDocument[] = [];
  chunks: InMemoryChunk[] = [];
  chatHistory: InMemoryChat[] = [];
}

const globalForMemory = globalThis as unknown as { inMemoryStore?: MemoryStore };

export const inMemoryStore = globalForMemory.inMemoryStore || new MemoryStore();

if (process.env.NODE_ENV !== 'production') {
  globalForMemory.inMemoryStore = inMemoryStore;
}

// Utility to calculate cosine similarity between two vector arrays
export function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length) return 0;
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  if (normA === 0 || normB === 0) return 0;
  return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}

// Test database connection helper
export async function isDbConnected(): Promise<boolean> {
  try {
    const db = getDbPool();
    const res = await db.query('SELECT 1');
    return res.rowCount === 1;
  } catch (err) {
    return false;
  }
}

import { NextResponse } from 'next/server';
import {
  getEmbedding,
  searchVectorDatabase,
  generateVoiceRagAnswer,
  saveChatHistory,
} from '@/lib/rag-service';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { query, apiKey, model, language = 'si' } = body;

    if (!query || typeof query !== 'string' || !query.trim()) {
      return NextResponse.json({ error: 'Query text is required' }, { status: 400 });
    }

    // 1. Generate embedding for query (multilingual 1536 dims)
    const queryEmbedding = await getEmbedding(query, apiKey);

    // 2. Vector search using HNSW cosine similarity + Smart Hybrid Overview
    const retrievedChunks = await searchVectorDatabase(queryEmbedding, 6, query);

    // 3. LLM generation with language instructions (Sinhala 'si' or English 'en')
    const answer = await generateVoiceRagAnswer(query, retrievedChunks, apiKey, model, language);

    // 4. Save to chat history table
    await saveChatHistory(query, retrievedChunks, answer);

    return NextResponse.json({
      query,
      answer,
      retrievedChunks,
    });
  } catch (error: any) {
    console.error('RAG Pipeline Error:', error);
    return NextResponse.json(
      { error: error.message || 'RAG generation failed' },
      { status: 500 }
    );
  }
}

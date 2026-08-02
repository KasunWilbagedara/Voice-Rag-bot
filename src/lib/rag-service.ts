import OpenAI from 'openai';
import { GoogleGenerativeAI } from '@google/generative-ai';
import { getDbPool, isDbConnected, inMemoryStore, cosineSimilarity } from './db';
import { randomUUID } from 'crypto';

export interface ChunkItem {
  id: string;
  documentId: string;
  documentTitle: string;
  content: string;
  chunkIndex: number;
  similarity: number;
}

export interface IngestionResult {
  documentId: string;
  title: string;
  chunkCount: number;
  totalCharacters: number;
}

function isGeminiKey(key?: string): boolean {
  const apiKey = key || process.env.GEMINI_API_KEY || process.env.OPENAI_API_KEY || '';
  if (!apiKey) return false;
  return apiKey.startsWith('AIza') || apiKey.startsWith('AQ.') || !apiKey.startsWith('sk-');
}

function getApiKey(customApiKey?: string): string {
  const apiKey = customApiKey || process.env.GEMINI_API_KEY || process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('API Key is required. Please provide a Google Gemini API Key or OpenAI API Key.');
  }
  return apiKey;
}

function sanitizeGeminiModelName(modelName: string): string {
  const validModels = [
    'gemini-1.5-flash',
    'gemini-2.0-flash',
    'gemini-2.5-flash',
    'gemini-flash-latest',
    'gemini-3.6-flash',
    'gemini-3.5-flash',
    'gemini-1.5-pro',
  ];
  if (validModels.includes(modelName)) return modelName;
  if (modelName.includes('2.0')) return 'gemini-2.0-flash';
  if (modelName.includes('1.5')) return 'gemini-1.5-flash';
  return 'gemini-flash-latest';
}

// 1. Text Chunker with character/sentence boundaries and overlap
export function chunkText(text: string, chunkSize: number = 500, overlap: number = 100): string[] {
  const cleaned = text.replace(/\r\n/g, '\n').trim();
  if (!cleaned) return [];

  const chunks: string[] = [];
  let startIndex = 0;

  while (startIndex < cleaned.length) {
    let endIndex = startIndex + chunkSize;

    if (endIndex < cleaned.length) {
      const lastPara = cleaned.lastIndexOf('\n\n', endIndex);
      const lastSentence = cleaned.lastIndexOf('. ', endIndex);
      const lastNewline = cleaned.lastIndexOf('\n', endIndex);

      if (lastPara > startIndex + chunkSize / 2) {
        endIndex = lastPara + 2;
      } else if (lastSentence > startIndex + chunkSize / 2) {
        endIndex = lastSentence + 2;
      } else if (lastNewline > startIndex + chunkSize / 2) {
        endIndex = lastNewline + 1;
      }
    } else {
      endIndex = cleaned.length;
    }

    const chunk = cleaned.slice(startIndex, endIndex).trim();
    if (chunk.length > 10) {
      chunks.push(chunk);
    }

    if (endIndex >= cleaned.length) break;
    startIndex = Math.max(startIndex + 1, endIndex - overlap);
  }

  return chunks;
}

// 2. Generate Vector Embeddings (Gemini gemini-embedding-001/gemini-embedding-2 OR OpenAI text-embedding-3-small)
export async function getEmbedding(text: string, customApiKey?: string): Promise<number[]> {
  const apiKey = getApiKey(customApiKey);

  if (isGeminiKey(apiKey)) {
    const genAI = new GoogleGenerativeAI(apiKey);
    const modelsToTry = ['gemini-embedding-001', 'gemini-embedding-2', 'text-embedding-004', 'embedding-001'];
    let lastError: any = null;

    for (const modelName of modelsToTry) {
      try {
        const embeddingModel = genAI.getGenerativeModel({ model: modelName });
        const result = await embeddingModel.embedContent(text.replace(/\n/g, ' '));
        if (result && result.embedding && result.embedding.values) {
          return result.embedding.values;
        }
      } catch (err) {
        lastError = err;
      }
    }
    throw new Error(`Gemini embedding failed: ${lastError?.message || 'Unsupported model'}`);
  } else {
    const openai = new OpenAI({ apiKey });
    const response = await openai.embeddings.create({
      model: 'text-embedding-3-small',
      input: text.replace(/\n/g, ' '),
      encoding_format: 'float',
    });
    return response.data[0].embedding;
  }
}

// Batch Embeddings
export async function getEmbeddingsBatch(texts: string[], customApiKey?: string): Promise<number[][]> {
  const apiKey = getApiKey(customApiKey);

  if (isGeminiKey(apiKey)) {
    const genAI = new GoogleGenerativeAI(apiKey);
    const modelsToTry = ['gemini-embedding-001', 'gemini-embedding-2', 'text-embedding-004', 'embedding-001'];
    let workingModel = '';

    for (const m of modelsToTry) {
      try {
        const testModel = genAI.getGenerativeModel({ model: m });
        await testModel.embedContent('test');
        workingModel = m;
        break;
      } catch (e) {
        // try next
      }
    }

    if (!workingModel) workingModel = 'gemini-embedding-001';

    const embeddingModel = genAI.getGenerativeModel({ model: workingModel });
    const embeddings: number[][] = [];
    for (const t of texts) {
      const result = await embeddingModel.embedContent(t.replace(/\n/g, ' '));
      embeddings.push(result.embedding.values);
    }
    return embeddings;
  } else {
    const openai = new OpenAI({ apiKey });
    const response = await openai.embeddings.create({
      model: 'text-embedding-3-small',
      input: texts.map((t) => t.replace(/\n/g, ' ')),
      encoding_format: 'float',
    });
    return response.data.map((item) => item.embedding);
  }
}

// 3. Store document and its vector chunks
export async function ingestDocument(
  title: string,
  fileType: string,
  content: string,
  customApiKey?: string
): Promise<IngestionResult> {
  const rawChunks = chunkText(content);
  if (rawChunks.length === 0) {
    throw new Error('Document content is empty or contains no parseable text.');
  }

  const embeddings = await getEmbeddingsBatch(rawChunks, customApiKey);
  const dbActive = await isDbConnected();

  const docId = randomUUID();
  const createdAt = new Date().toISOString();

  if (dbActive) {
    const db = getDbPool();
    await db.query(
      `INSERT INTO documents (id, title, file_type, created_at) VALUES ($1, $2, $3, $4)`,
      [docId, title, fileType, createdAt]
    );

    for (let i = 0; i < rawChunks.length; i++) {
      const chunkId = randomUUID();
      const vectorStr = `[${embeddings[i].join(',')}]`;
      await db.query(
        `INSERT INTO document_chunks (id, document_id, content, chunk_index, embedding, created_at)
         VALUES ($1, $2, $3, $4, $5::vector, $6)`,
        [chunkId, docId, rawChunks[i], i, vectorStr, createdAt]
      );
    }
  } else {
    inMemoryStore.documents.push({
      id: docId,
      title,
      file_type: fileType,
      created_at: createdAt,
    });

    for (let i = 0; i < rawChunks.length; i++) {
      inMemoryStore.chunks.push({
        id: randomUUID(),
        document_id: docId,
        content: rawChunks[i],
        chunk_index: i,
        embedding: embeddings[i],
        created_at: createdAt,
      });
    }
  }

  return {
    documentId: docId,
    title,
    chunkCount: rawChunks.length,
    totalCharacters: content.length,
  };
}

// 4. Vector Search using HNSW cosine similarity distance + Smart Hybrid Overview Retrieval
export async function searchVectorDatabase(
  queryEmbedding: number[],
  topK: number = 6,
  queryText?: string
): Promise<ChunkItem[]> {
  const dbActive = await isDbConnected();
  const lowerQuery = (queryText || '').toLowerCase();

  const isGeneralQuery =
    !queryText ||
    lowerQuery.includes('මොනාද') ||
    lowerQuery.includes('මොනවාද') ||
    lowerQuery.includes('තියෙන්නේ') ||
    lowerQuery.includes('විස්තර') ||
    lowerQuery.includes('ලියා') ||
    lowerQuery.includes('ලේඛන') ||
    lowerQuery.includes('ඩොකියුමන්ට්') ||
    lowerQuery.includes('what') ||
    lowerQuery.includes('summary') ||
    lowerQuery.includes('overview') ||
    lowerQuery.includes('about') ||
    lowerQuery.includes('cv') ||
    lowerQuery.includes('resume') ||
    lowerQuery.includes('pdf');

  let results: ChunkItem[] = [];

  if (dbActive) {
    const db = getDbPool();
    const vectorStr = `[${queryEmbedding.join(',')}]`;
    const vectorQuery = `
      SELECT 
        c.id,
        c.document_id,
        d.title AS document_title,
        c.content,
        c.chunk_index,
        1 - (c.embedding <=> $1::vector) AS similarity
      FROM document_chunks c
      JOIN documents d ON c.document_id = d.id
      ORDER BY c.embedding <=> $1::vector
      LIMIT $2;
    `;
    const res = await db.query(vectorQuery, [vectorStr, topK]);

    results = res.rows.map((row) => ({
      id: row.id,
      documentId: row.document_id,
      documentTitle: row.document_title,
      content: row.content,
      chunkIndex: row.chunk_index,
      similarity: parseFloat(row.similarity),
    }));

    // If general query, also fetch top document overview chunks (chunk_index 0 & 1)
    if (isGeneralQuery) {
      const overviewRes = await db.query(
        `SELECT c.id, c.document_id, d.title AS document_title, c.content, c.chunk_index, 0.9 AS similarity
         FROM document_chunks c
         JOIN documents d ON c.document_id = d.id
         WHERE c.chunk_index <= 1
         LIMIT 4;`
      );
      for (const row of overviewRes.rows) {
        if (!results.some((r) => r.id === row.id)) {
          results.push({
            id: row.id,
            documentId: row.document_id,
            documentTitle: row.document_title,
            content: row.content,
            chunkIndex: row.chunk_index,
            similarity: 0.9,
          });
        }
      }
    }
  } else {
    const scoredChunks = inMemoryStore.chunks.map((chunk) => {
      const doc = inMemoryStore.documents.find((d) => d.id === chunk.document_id);
      const sim = cosineSimilarity(queryEmbedding, chunk.embedding);
      return {
        id: chunk.id,
        documentId: chunk.document_id,
        documentTitle: doc ? doc.title : 'Document',
        content: chunk.content,
        chunkIndex: chunk.chunk_index,
        similarity: sim,
      };
    });

    scoredChunks.sort((a, b) => b.similarity - a.similarity);
    results = scoredChunks.slice(0, topK);

    // If general query or limited matches, also include header chunks (index 0, 1)
    if (isGeneralQuery || results.length < topK) {
      const overviewChunks = inMemoryStore.chunks.filter((c) => c.chunk_index <= 1);
      for (const chunk of overviewChunks) {
        if (!results.some((r) => r.id === chunk.id)) {
          const doc = inMemoryStore.documents.find((d) => d.id === chunk.document_id);
          results.push({
            id: chunk.id,
            documentId: chunk.document_id,
            documentTitle: doc ? doc.title : 'Document',
            content: chunk.content,
            chunkIndex: chunk.chunk_index,
            similarity: 0.88,
          });
        }
      }
    }
  }

  return results.slice(0, Math.max(topK, 6));
}

// 5. LLM Answer Generation (Gemini gemini-flash-latest OR OpenAI gpt-4o-mini)
export async function generateVoiceRagAnswer(
  userQuery: string,
  retrievedChunks: ChunkItem[],
  customApiKey?: string,
  modelName: string = 'gemini-flash-latest',
  targetLanguage: string = 'si'
): Promise<string> {
  const apiKey = getApiKey(customApiKey);
  const isSinhala = targetLanguage === 'si';

  const contextText =
    retrievedChunks.length > 0
      ? retrievedChunks
          .map((chunk, idx) => `--- DOCUMENT CHUNK ${idx + 1} (File: ${chunk.documentTitle}) ---\n${chunk.content}`)
          .join('\n\n')
      : 'No document uploaded yet.';

  const languageInstruction = isSinhala
    ? `CRITICAL MULTILINGUAL & SINHALA VOICE REQUIREMENT:
You MUST synthesize and deliver your response as an exceptionally smart, articulate AI assistant speaking in natural, fluent SINHALA (සිංහල).
Even if the provided context documents are written in English or another language, read the English context thoroughly, extract all relevant facts, and explain them directly in smart, clear, elegant, spoken Sinhala (සිංහල).

SMART ACCURATE ANSWER RULES:
1. Thoroughly analyze the CONTEXT DOCUMENTS below to answer the user's question.
2. If the user asks a general question like "What is in this document?" or "මේ ඩොකියුමන්ට් එකේ මොනාද තියෙන්නේ?", provide a smart, comprehensive summary of the document (e.g. state candidate name, professional role, key experience, education, skills, or main purpose).
3. NEVER say you couldn't find any document or information if CONTEXT DOCUMENTS contain text!
4. Do NOT use markdown symbols (*, #, -, \`\`\`), no tables, no numbered lists, and no bracketed citations like [1] or [Source 1], as your output will be read aloud.
5. Speak warmly and conversationally in 3-5 clear sentences.`
    : `SMART ACCURATE VOICE RAG GUIDELINES:
1. Thoroughly analyze all provided CONTEXT DOCUMENTS to deliver a precise, smart, and highly accurate answer.
2. If the user asks a general query (e.g. "What is in this document?", "Summarize this file", "Tell me about this CV"), deliver an intelligent overview summarizing the main entity, title, background, skills, or purpose of the document.
3. NEVER claim you cannot find information when CONTEXT DOCUMENTS contain text.
4. Format your response strictly for voice playback: 3-5 concise, natural spoken sentences. Absolutely NO markdown syntax (no asterisks *, hashtags #, bullet points -, code blocks, or bracketed citations like [1]).`;

  const systemPrompt = `You are an exceptionally smart, articulate, and accurate AI Voice Assistant powering an enterprise Voice-RAG system.
Your goal is to provide accurate, intelligent, and insightful answers based on the provided document context.

${languageInstruction}

CONTEXT DOCUMENTS:
${contextText}`;

  if (isGeminiKey(apiKey)) {
    const genAI = new GoogleGenerativeAI(apiKey);
    const sanitizedModel = sanitizeGeminiModelName(modelName);
    const modelsToTry = [sanitizedModel, 'gemini-flash-latest', 'gemini-3.6-flash', 'gemini-3.5-flash'];
    const fullPrompt = `${systemPrompt}\n\nUSER QUESTION: ${userQuery}`;

    let lastError: any = null;
    for (const mName of modelsToTry) {
      try {
        const model = genAI.getGenerativeModel({ model: mName });
        const result = await model.generateContent(fullPrompt);
        const text = result.response.text();
        if (text && text.trim()) {
          return text.trim();
        }
      } catch (err) {
        lastError = err;
      }
    }

    throw new Error(`Gemini LLM generation failed: ${lastError?.message || 'Model error'}`);
  } else {
    const openai = new OpenAI({ apiKey });
    const activeModel = modelName.includes('gpt') ? modelName : 'gpt-4o-mini';
    const completion = await openai.chat.completions.create({
      model: activeModel,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userQuery },
      ],
      temperature: 0.3,
      max_tokens: 350,
    });

    return completion.choices[0]?.message?.content?.trim() || (isSinhala ? 'පිළිතුරක් සෑදීමට නොහැකි විය.' : 'I could not generate a response.');
  }
}

// 6. Log conversation history
export async function saveChatHistory(
  userQueryText: string,
  retrievedChunks: ChunkItem[],
  aiResponseText: string
): Promise<void> {
  const dbActive = await isDbConnected();
  const id = randomUUID();
  const createdAt = new Date().toISOString();
  const chunksJson = JSON.stringify(retrievedChunks);

  if (dbActive) {
    const db = getDbPool();
    await db.query(
      `INSERT INTO chat_history (id, user_query_text, retrieved_chunks, ai_response_text, created_at)
       VALUES ($1, $2, $3, $4, $5)`,
      [id, userQueryText, chunksJson, aiResponseText, createdAt]
    );
  } else {
    inMemoryStore.chatHistory.push({
      id,
      user_query_text: userQueryText,
      retrieved_chunks: retrievedChunks,
      ai_response_text: aiResponseText,
      created_at: createdAt,
    });
  }
}

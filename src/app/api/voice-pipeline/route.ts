import { NextResponse } from 'next/server';
import { transcribeAudio, generateSpeechAudio, TTSVoice } from '@/lib/audio-service';
import {
  getEmbedding,
  searchVectorDatabase,
  generateVoiceRagAnswer,
  saveChatHistory,
} from '@/lib/rag-service';

export async function POST(req: Request) {
  try {
    const formData = await req.formData();
    const audioFile = formData.get('audio') as File | null;
    const apiKey = (formData.get('apiKey') as string) || undefined;
    const voice = ((formData.get('voice') as string) || 'nova') as TTSVoice;
    const model = (formData.get('model') as string) || 'gemini-1.5-flash';
    const language = (formData.get('language') as string) || 'si';

    if (!audioFile) {
      return NextResponse.json({ error: 'No audio file provided' }, { status: 400 });
    }

    const arrayBuffer = await audioFile.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    // 1. Speech-to-Text (STT) - Supports both Gemini multimodal STT & OpenAI Whisper
    const userQueryText = await transcribeAudio(
      buffer,
      audioFile.name || 'recording.webm',
      apiKey,
      language
    );

    if (!userQueryText || !userQueryText.trim()) {
      return NextResponse.json(
        { error: 'Could not transcribe any speech from recording.' },
        { status: 422 }
      );
    }

    // 2. Vector Search (Gemini text-embedding-004 OR OpenAI embeddings + Smart Hybrid Overview)
    const queryEmbedding = await getEmbedding(userQueryText, apiKey);
    const retrievedChunks = await searchVectorDatabase(queryEmbedding, 6, userQueryText);

    // 3. Conversational LLM Answer Generation (Gemini 1.5/2.0 Flash OR GPT-4o)
    const aiResponseText = await generateVoiceRagAnswer(userQueryText, retrievedChunks, apiKey, model, language);

    // 4. Save Chat History
    await saveChatHistory(userQueryText, retrievedChunks, aiResponseText);

    // 5. Text-to-Speech (TTS)
    const audioBuffer = await generateSpeechAudio(aiResponseText, voice, apiKey, language);

    // Encode audio response in base64 if available (or null for Web Speech API)
    const audioBase64 = audioBuffer ? audioBuffer.toString('base64') : null;

    return NextResponse.json({
      userQueryText,
      aiResponseText,
      retrievedChunks,
      audioBase64,
      audioFormat: 'audio/mp3',
    });
  } catch (error: any) {
    console.error('Unified Voice Pipeline Error:', error);
    return NextResponse.json(
      { error: error.message || 'Unified Voice-RAG pipeline failed' },
      { status: 500 }
    );
  }
}

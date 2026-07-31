import { NextResponse } from 'next/server';
import { generateSpeechAudio, TTSVoice } from '@/lib/audio-service';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { text, voice, apiKey } = body;

    if (!text || typeof text !== 'string') {
      return NextResponse.json({ error: 'Text string is required' }, { status: 400 });
    }

    const selectedVoice: TTSVoice = voice || 'nova';
    const audioBuffer = await generateSpeechAudio(text, selectedVoice, apiKey);

    if (!audioBuffer) {
      return new Response(null, { status: 204 });
    }

    return new Response(new Uint8Array(audioBuffer), {
      headers: {
        'Content-Type': 'audio/mpeg',
        'Content-Length': audioBuffer.length.toString(),
        'Cache-Control': 'no-cache',
      },
    });
  } catch (error: any) {
    console.error('TTS API Error:', error);
    return NextResponse.json(
      { error: error.message || 'Speech audio generation failed' },
      { status: 500 }
    );
  }
}

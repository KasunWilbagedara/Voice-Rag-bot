import { NextResponse } from 'next/server';
import { transcribeAudio } from '@/lib/audio-service';

export async function POST(req: Request) {
  try {
    const formData = await req.formData();
    const audioFile = formData.get('audio') as File | null;
    const apiKey = formData.get('apiKey') as string | null;
    const language = (formData.get('language') as string) || 'si';

    if (!audioFile) {
      return NextResponse.json({ error: 'No audio file provided' }, { status: 400 });
    }

    const arrayBuffer = await audioFile.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    const transcribedText = await transcribeAudio(
      buffer,
      audioFile.name || 'recording.webm',
      apiKey || undefined,
      language
    );

    return NextResponse.json({
      text: transcribedText,
    });
  } catch (error: any) {
    console.error('STT API Error:', error);
    return NextResponse.json(
      { error: error.message || 'Speech-to-text transcription failed' },
      { status: 500 }
    );
  }
}

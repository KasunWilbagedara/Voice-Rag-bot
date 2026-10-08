import { NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-config';

export async function POST(req: Request) {
  try {
    const backendUrl = getBackendUrl(req, 'pure');
    const body = await req.json();
    const res = await fetch(`${backendUrl}/api/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({ error: 'TTS request failed' }));
      return NextResponse.json(errData, { status: res.status });
    }

    const contentType = res.headers.get('content-type') || 'audio/mpeg';
    const audioBuffer = await res.arrayBuffer();
    return new Response(audioBuffer, {
      headers: {
        'Content-Type': contentType,
        'Content-Length': audioBuffer.byteLength.toString(),
        'Cache-Control': 'no-cache',
      },
    });
  } catch (error: any) {
    console.error('TTS Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to connect to Python backend' },
      { status: 502 }
    );
  }
}

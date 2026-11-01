import { NextResponse } from 'next/server';

import { BACKEND1_URL as PYTHON_BACKEND_URL, userHeaders } from '../_lib/backend';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const res = await fetch(`${PYTHON_BACKEND_URL}/api/tts`, {
      method: 'POST',
      headers: userHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({ error: 'TTS request failed' }));
      return NextResponse.json(errData, { status: res.status });
    }

    const audioBuffer = await res.arrayBuffer();
    return new Response(audioBuffer, {
      headers: {
        'Content-Type': 'audio/mpeg',
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

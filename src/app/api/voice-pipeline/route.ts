import { NextResponse } from 'next/server';

const BACKEND1_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000'; // Pure RAG
const BACKEND2_URL = process.env.TOOL_BACKEND_URL  || 'http://localhost:8001'; // RAG + Tools

export async function POST(req: Request) {
  try {
    const formData = await req.formData();

    // Read the backend mode header sent by the frontend Mode Switcher
    const backendMode = req.headers.get('x-backend-mode') || 'pure';

    // Voice pipeline always goes to the STT/TTS endpoint —
    // both backends expose /api/voice-pipeline, but the agentic backend
    // on Port 8001 will use the agentic RAG path internally.
    const targetBase = backendMode === 'tools' ? BACKEND2_URL : BACKEND1_URL;

    const res = await fetch(`${targetBase}/api/voice-pipeline`, {
      method: 'POST',
      body: formData,
      headers: {
        'x-backend-mode': backendMode,
      },
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('Voice Pipeline Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to connect to backend' },
      { status: 502 }
    );
  }
}

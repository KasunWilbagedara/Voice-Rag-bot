import { NextResponse } from 'next/server';

const BACKEND1_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000'; // Pure RAG
const BACKEND2_URL = process.env.TOOL_BACKEND_URL  || 'http://localhost:8001'; // RAG + Tools

export async function POST(req: Request) {
  try {
    const body = await req.json();

    // Read the backend mode header sent by the frontend Mode Switcher
    const backendMode = req.headers.get('x-backend-mode') || 'pure';

    let targetUrl: string;
    let forwardMode: string;

    if (backendMode === 'tools') {
      // Route to Backend 2: Agentic RAG with tools
      targetUrl = `${BACKEND2_URL}/api/agentic-rag`;
      forwardMode = 'tools';
    } else {
      // Route to Backend 1: Pure RAG (default)
      targetUrl = `${BACKEND1_URL}/api/rag`;
      forwardMode = 'pure';
    }

    const res = await fetch(targetUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-backend-mode': forwardMode,
      },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('RAG Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to connect to backend' },
      { status: 502 }
    );
  }
}

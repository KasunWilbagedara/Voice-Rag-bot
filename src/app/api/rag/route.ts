import { NextResponse } from 'next/server';
import { BACKEND1_URL, BACKEND2_URL, backendModeFrom } from '../_lib/backend';

export async function POST(req: Request) {
  try {
    const body = await req.json();

    // Mode Switcher: 'pure' → Backend 1 strictly grounded RAG, 'tools' → Backend 2 agentic RAG
    const backendMode = backendModeFrom(req);
    const targetUrl =
      backendMode === 'tools' ? `${BACKEND2_URL}/api/agentic-rag` : `${BACKEND1_URL}/api/rag`;

    const res = await fetch(targetUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-backend-mode': backendMode,
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

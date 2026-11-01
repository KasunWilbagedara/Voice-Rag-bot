import { NextResponse } from 'next/server';
import { BACKEND1_URL, BACKEND2_URL, backendModeFrom } from '../_lib/backend';

export async function POST(req: Request) {
  try {
    const formData = await req.formData();

    // Both backends expose /api/voice-pipeline; the x-backend-mode header selects
    // the pipeline: 'pure' → grounded RAG + MMR, 'tools' → agentic RAG with tools.
    const backendMode = backendModeFrom(req);
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

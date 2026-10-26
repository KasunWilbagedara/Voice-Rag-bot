import { NextResponse } from 'next/server';

const BACKEND2_URL = process.env.TOOL_BACKEND_URL || 'http://localhost:8001';

export async function GET() {
  try {
    const res = await fetch(`${BACKEND2_URL}/health`, {
      signal: AbortSignal.timeout(3000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { status: 'offline', service: 'Backend 2 — RAG with Tools', port: 8001 },
      { status: 503 }
    );
  }
}

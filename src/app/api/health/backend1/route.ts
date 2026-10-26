import { NextResponse } from 'next/server';

const BACKEND1_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000';

export async function GET() {
  try {
    const res = await fetch(`${BACKEND1_URL}/health`, {
      signal: AbortSignal.timeout(3000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { status: 'offline', service: 'Backend 1 — Pure RAG', port: 8000 },
      { status: 503 }
    );
  }
}

import { NextResponse } from 'next/server';
import { BACKEND1_URL } from '../../_lib/backend';

export async function GET() {
  try {
    const res = await fetch(`${BACKEND1_URL}/health`, {
      signal: AbortSignal.timeout(3000),
      cache: 'no-store',
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

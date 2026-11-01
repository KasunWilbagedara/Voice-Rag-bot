import { NextResponse } from 'next/server';
import { BACKEND2_URL } from '../../_lib/backend';

export async function GET() {
  try {
    const res = await fetch(`${BACKEND2_URL}/health`, {
      signal: AbortSignal.timeout(3000),
      cache: 'no-store',
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

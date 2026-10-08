import { NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-config';

export async function POST(req: Request) {
  try {
    const backendUrl = getBackendUrl(req, 'pure');
    const body = await req.json();
    const res = await fetch(`${backendUrl}/api/rag`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('RAG Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to connect to Python backend' },
      { status: 502 }
    );
  }
}

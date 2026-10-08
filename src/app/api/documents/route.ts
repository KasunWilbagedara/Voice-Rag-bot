import { NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-config';

export async function GET(req: Request) {
  try {
    const backendUrl = getBackendUrl(req, 'pure');
    const res = await fetch(`${backendUrl}/api/documents`, {
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store',
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Failed to connect to Python backend' }, { status: 502 });
  }
}

export async function POST(req: Request) {
  try {
    const backendUrl = getBackendUrl(req, 'pure');
    const body = await req.json().catch(() => ({}));
    const res = await fetch(`${backendUrl}/api/documents/seed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Failed to connect to Python backend' }, { status: 502 });
  }
}

export async function DELETE(req: Request) {
  try {
    const backendUrl = getBackendUrl(req, 'pure');
    const { searchParams } = new URL(req.url);
    const id = searchParams.get('id');
    const clearAll = searchParams.get('clear');

    let endpoint = `${backendUrl}/api/documents`;
    if (clearAll === 'true') {
      endpoint = `${backendUrl}/api/documents/clear`;
    } else if (id) {
      endpoint = `${backendUrl}/api/documents?id=${id}`;
    } else {
      return NextResponse.json({ error: 'Missing document id or clear parameter' }, { status: 400 });
    }

    const res = await fetch(endpoint, {
      method: 'DELETE',
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Failed to connect to Python backend' }, { status: 502 });
  }
}

import { NextResponse } from 'next/server';

const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000';

export async function GET() {
  try {
    const res = await fetch(`${PYTHON_BACKEND_URL}/api/databases`, {
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
    const url = new URL(req.url);
    const action = url.searchParams.get('action');

    if (action === 'upload-csv') {
      const formData = await req.formData();
      const res = await fetch(`${PYTHON_BACKEND_URL}/api/databases/upload-csv`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      return NextResponse.json(data, { status: res.status });
    }

    if (action === 'connect') {
      const body = await req.json();
      const res = await fetch(`${PYTHON_BACKEND_URL}/api/databases/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      return NextResponse.json(data, { status: res.status });
    }

    if (action === 'query') {
      const body = await req.json();
      const res = await fetch(`${PYTHON_BACKEND_URL}/api/databases/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      return NextResponse.json(data, { status: res.status });
    }

    // Default list schemas
    const res = await fetch(`${PYTHON_BACKEND_URL}/api/databases/schemas`, {
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store',
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Failed to connect to Python backend' }, { status: 502 });
  }
}

export async function DELETE(req: Request) {
  try {
    const url = new URL(req.url);
    const dbId = url.searchParams.get('dbId');
    if (!dbId) {
      return NextResponse.json({ error: 'dbId parameter is required' }, { status: 400 });
    }

    const res = await fetch(`${PYTHON_BACKEND_URL}/api/databases/${dbId}`, {
      method: 'DELETE',
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Failed to connect to Python backend' }, { status: 502 });
  }
}

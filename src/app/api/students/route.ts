import { NextResponse } from 'next/server';

const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000';

export async function GET() {
  try {
    const res = await fetch(`${PYTHON_BACKEND_URL}/api/students`, {
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
    const body = await req.json().catch(() => ({}));
    const res = await fetch(`${PYTHON_BACKEND_URL}/api/students`, {
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

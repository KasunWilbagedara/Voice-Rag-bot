import { NextResponse } from 'next/server';

const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000';

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const userId = searchParams.get('userId') || 'local-user';
    const res = await fetch(
      `${PYTHON_BACKEND_URL}/api/chat/sessions?userId=${encodeURIComponent(userId)}`,
      { cache: 'no-store' }
    );

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('Chat Sessions Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to connect to Python backend', sessions: [] },
      { status: 502 }
    );
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const res = await fetch(`${PYTHON_BACKEND_URL}/api/chat/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('Chat Session Create Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to connect to Python backend' },
      { status: 502 }
    );
  }
}

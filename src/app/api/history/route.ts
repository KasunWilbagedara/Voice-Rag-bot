import { NextResponse } from 'next/server';

const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000';

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const limit = searchParams.get('limit') || '30';
    const res = await fetch(`${PYTHON_BACKEND_URL}/api/history?limit=${limit}`, {
      cache: 'no-store',
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('History GET Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to connect to history backend service' },
      { status: 502 }
    );
  }
}

export async function DELETE(req: Request) {
  try {
    const res = await fetch(`${PYTHON_BACKEND_URL}/api/history`, {
      method: 'DELETE',
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('History DELETE Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to clear chat history' },
      { status: 502 }
    );
  }
}

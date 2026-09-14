import { NextResponse } from 'next/server';

const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000';

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const res = await fetch(`${PYTHON_BACKEND_URL}/api/memory?${searchParams.toString()}`, {
      cache: 'no-store',
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('Memory GET Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to connect to backend memory service' },
      { status: 502 }
    );
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const res = await fetch(`${PYTHON_BACKEND_URL}/api/memory`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('Memory POST Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to save memory to backend' },
      { status: 502 }
    );
  }
}

export async function DELETE(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const res = await fetch(`${PYTHON_BACKEND_URL}/api/memory?${searchParams.toString()}`, {
      method: 'DELETE',
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('Memory DELETE Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to clear memories' },
      { status: 502 }
    );
  }
}

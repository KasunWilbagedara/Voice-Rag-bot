import { NextResponse } from 'next/server';

const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000';

interface RouteContext {
  params: {
    sessionId: string;
  };
}

export async function PATCH(req: Request, { params }: RouteContext) {
  try {
    const body = await req.json();
    const res = await fetch(
      `${PYTHON_BACKEND_URL}/api/chat/sessions/${encodeURIComponent(params.sessionId)}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }
    );

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('Chat Session Rename Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to connect to Python backend' },
      { status: 502 }
    );
  }
}

export async function DELETE(req: Request, { params }: RouteContext) {
  try {
    const { searchParams } = new URL(req.url);
    const userId = searchParams.get('userId') || 'local-user';
    const res = await fetch(
      `${PYTHON_BACKEND_URL}/api/chat/sessions/${encodeURIComponent(params.sessionId)}?userId=${encodeURIComponent(userId)}`,
      { method: 'DELETE' }
    );

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('Chat Session Delete Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to connect to Python backend' },
      { status: 502 }
    );
  }
}

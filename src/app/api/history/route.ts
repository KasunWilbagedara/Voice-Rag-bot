import { NextResponse } from 'next/server';
import { BACKEND1_URL } from '../_lib/backend';

// Forwards ?limit= and ?sessionId= so history is scoped to the caller's session.

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    if (!searchParams.get('limit')) searchParams.set('limit', '30');
    const res = await fetch(`${BACKEND1_URL}/api/history?${searchParams.toString()}`, {
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
    const { searchParams } = new URL(req.url);
    const res = await fetch(`${BACKEND1_URL}/api/history?${searchParams.toString()}`, {
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

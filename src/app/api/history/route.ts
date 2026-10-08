import { NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-config';

export async function GET(req: Request) {
  try {
    const backendUrl = getBackendUrl(req, 'pure');
    const { searchParams } = new URL(req.url);
    const limit = searchParams.get('limit') || '30';
    const res = await fetch(`${backendUrl}/api/history?limit=${limit}`, {
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
    const backendUrl = getBackendUrl(req, 'pure');
    const res = await fetch(`${backendUrl}/api/history`, {
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

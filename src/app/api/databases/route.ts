import { NextResponse } from 'next/server';
import { BACKEND2_URL, adminHeaders } from '../_lib/backend';

// Databases & SQL tools are served by the Tool Execution Service (Port 8001)

async function forward(path: string, init: RequestInit = {}) {
  const res = await fetch(`${BACKEND2_URL}${path}`, { cache: 'no-store', ...init });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function GET() {
  try {
    return await forward('/api/databases');
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Failed to connect to Python backend' }, { status: 502 });
  }
}

export async function POST(req: Request) {
  try {
    const action = new URL(req.url).searchParams.get('action');
    const json = { 'Content-Type': 'application/json' };

    switch (action) {
      case 'upload-csv':
        return await forward('/api/databases/upload-csv', {
          method: 'POST',
          headers: adminHeaders(),
          body: await req.formData(),
        });
      case 'connect':
        return await forward('/api/databases/connect', {
          method: 'POST',
          headers: adminHeaders(json),
          body: JSON.stringify(await req.json()),
        });
      case 'query':
        // Read-only SELECT queries — not an admin action.
        return await forward('/api/databases/query', {
          method: 'POST',
          headers: json,
          body: JSON.stringify(await req.json()),
        });
      case 'seed':
        return await forward('/api/databases/seed', { method: 'POST', headers: adminHeaders(json) });
      case 'reset':
        return await forward('/api/databases/reset', { method: 'POST', headers: adminHeaders(json) });
      default:
        return await forward('/api/databases/schemas');
    }
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Failed to connect to Python backend' }, { status: 502 });
  }
}

export async function DELETE(req: Request) {
  try {
    const dbId = new URL(req.url).searchParams.get('dbId');
    if (!dbId) {
      return NextResponse.json({ error: 'dbId parameter is required' }, { status: 400 });
    }
    return await forward(`/api/databases/${encodeURIComponent(dbId)}`, {
      method: 'DELETE',
      headers: adminHeaders(),
    });
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Failed to connect to Python backend' }, { status: 502 });
  }
}

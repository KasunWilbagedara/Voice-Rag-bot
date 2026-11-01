import { NextResponse } from 'next/server';
import { BACKEND1_URL, adminHeaders } from '../../_lib/backend';

export async function POST(req: Request) {
  try {
    const formData = await req.formData();
    const res = await fetch(`${BACKEND1_URL}/api/documents/upload`, {
      method: 'POST',
      headers: adminHeaders(),
      body: formData,
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('Document Upload Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to connect to Python backend' },
      { status: 502 }
    );
  }
}

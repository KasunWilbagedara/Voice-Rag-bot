import { NextResponse } from 'next/server';

import { BACKEND1_URL as PYTHON_BACKEND_URL, userHeaders } from '../_lib/backend';

export async function POST(req: Request) {
  try {
    const formData = await req.formData();
    const res = await fetch(`${PYTHON_BACKEND_URL}/api/stt`, {
      method: 'POST',
      headers: userHeaders(),
      body: formData,
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('STT Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to connect to Python backend' },
      { status: 502 }
    );
  }
}

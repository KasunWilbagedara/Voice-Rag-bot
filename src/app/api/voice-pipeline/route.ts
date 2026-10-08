import { NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-config';

export async function POST(req: Request) {
  try {
    const backendUrl = getBackendUrl(req, 'pure');
    const formData = await req.formData();
    const res = await fetch(`${backendUrl}/api/voice-pipeline`, {
      method: 'POST',
      body: formData,
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('Voice Pipeline Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to connect to Python backend' },
      { status: 502 }
    );
  }
}

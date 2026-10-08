import { NextResponse } from 'next/server';
import { PURE_RAG_BACKEND_URL, TOOLS_RAG_BACKEND_URL } from '@/lib/backend-config';

export const dynamic = 'force-dynamic';

async function checkBackend(url: string, name: string) {
  const t0 = Date.now();
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2000);
    const res = await fetch(`${url}/health`, {
      signal: controller.signal,
      cache: 'no-store',
    });
    clearTimeout(timeoutId);

    const latencyMs = Date.now() - t0;
    if (res.ok) {
      const data = await res.json();
      return {
        name,
        url,
        online: true,
        latencyMs,
        data,
      };
    } else {
      return {
        name,
        url,
        online: false,
        status: res.status,
        error: `HTTP ${res.status}`,
      };
    }
  } catch (error: any) {
    return {
      name,
      url,
      online: false,
      error: error.name === 'AbortError' ? 'Connection Timeout' : error.message,
    };
  }
}

export async function GET() {
  const [pureRagStatus, toolsRagStatus] = await Promise.all([
    checkBackend(PURE_RAG_BACKEND_URL, 'Pure RAG (Documents Only)'),
    checkBackend(TOOLS_RAG_BACKEND_URL, 'RAG + Tools (Advanced Agent)'),
  ]);

  return NextResponse.json({
    pureRag: pureRagStatus,
    toolsRag: toolsRagStatus,
    timestamp: new Date().toISOString(),
  });
}

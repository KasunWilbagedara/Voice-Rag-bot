import { BACKEND1_URL, BACKEND2_URL, backendModeFrom, userHeaders } from '../../_lib/backend';

// Streams the answer straight through to the browser
// (newline-delimited JSON events: sources, token..., done).
// Mode Switcher: 'pure' → Backend 1 (Port 8000), 'tools' → Backend 2 (Port 8001).
export async function POST(req: Request) {
  try {
    const backendMode = backendModeFrom(req);
    const targetBase = backendMode === 'tools' ? BACKEND2_URL : BACKEND1_URL;

    const res = await fetch(`${targetBase}/api/rag/stream`, {
      method: 'POST',
      headers: userHeaders({
        'Content-Type': 'application/json',
        'x-backend-mode': backendMode,
      }),
      body: await req.text(),
    });

    return new Response(res.body, {
      status: res.status,
      headers: {
        'Content-Type': res.headers.get('Content-Type') || 'application/x-ndjson',
        'Cache-Control': 'no-cache',
      },
    });
  } catch (error: any) {
    return Response.json({ error: error.message || 'Failed to connect to backend' }, { status: 502 });
  }
}

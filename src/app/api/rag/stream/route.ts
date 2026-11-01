import { BACKEND1_URL, backendModeFrom, userHeaders } from '../../_lib/backend';

// Streams the answer from Backend 1 straight through to the browser
// (newline-delimited JSON events: sources, token..., done).
export async function POST(req: Request) {
  try {
    const res = await fetch(`${BACKEND1_URL}/api/rag/stream`, {
      method: 'POST',
      headers: userHeaders({
        'Content-Type': 'application/json',
        'x-backend-mode': backendModeFrom(req),
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

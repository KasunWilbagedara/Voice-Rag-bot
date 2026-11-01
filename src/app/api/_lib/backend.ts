// Shared backend configuration for the Next.js proxy routes.
// (Folders prefixed with "_" are private in the App Router — not exposed as routes.)
import { cookies } from 'next/headers';

/** httpOnly cookie holding the user's login token (never readable by browser JS). */
export const AUTH_COOKIE = 'vr_token';

/** Adds the logged-in user's token (from the cookie) as `Authorization: Bearer`. */
export function userHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = cookies().get(AUTH_COOKIE)?.value;
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

/** Backend 1 — Pure RAG, documents, STT/TTS, memory & history (Port 8000). */
export const BACKEND1_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000';

/**
 * Backend 2 — RAG + Tools: agentic RAG, databases, students (Port 8001).
 * `PYTHON_TOOL_BACKEND_URL` is what docker-compose and `.env` set;
 * `TOOL_BACKEND_URL` is still accepted for older setups.
 */
export const BACKEND2_URL =
  process.env.PYTHON_TOOL_BACKEND_URL || process.env.TOOL_BACKEND_URL || 'http://localhost:8001';

/** Normalises the UI's mode switcher value. */
export function backendModeFrom(req: Request): 'pure' | 'tools' {
  return req.headers.get('x-backend-mode') === 'tools' ? 'tools' : 'pure';
}

/**
 * Headers for calls to protected (destructive) backend endpoints.
 * When ADMIN_API_KEY is set on the server, it is forwarded as `x-admin-key`;
 * the key never reaches the browser.
 */
export function adminHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const key = process.env.ADMIN_API_KEY;
  return key ? { ...extra, 'x-admin-key': key } : extra;
}

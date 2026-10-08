export const PURE_RAG_BACKEND_URL =
  process.env.PURE_RAG_BACKEND_URL ||
  process.env.NEXT_PUBLIC_PURE_RAG_URL ||
  'http://localhost:8000';

export const TOOLS_RAG_BACKEND_URL =
  process.env.TOOLS_RAG_BACKEND_URL ||
  process.env.NEXT_PUBLIC_TOOLS_RAG_URL ||
  'http://localhost:8001';

export type BackendMode = 'pure' | 'tools';

/**
 * Resolves which Python backend to route the request to based on:
 * 1. Request header 'x-backend-mode' ('pure' | 'tools' | 'pure_rag' | 'rag_with_tools')
 * 2. URL search parameter (?backendMode=pure or ?mode=tools)
 * 3. Default fallback mode
 */
export function getBackendUrl(req?: Request, defaultMode: BackendMode = 'pure'): string {
  if (req) {
    // 1. Check custom header
    const modeHeader = req.headers.get('x-backend-mode')?.toLowerCase();
    if (modeHeader === 'tools' || modeHeader === 'rag_with_tools') {
      return TOOLS_RAG_BACKEND_URL;
    }
    if (modeHeader === 'pure' || modeHeader === 'pure_rag') {
      return PURE_RAG_BACKEND_URL;
    }

    // 2. Check query params if URL is present
    try {
      const url = new URL(req.url);
      const queryMode = (url.searchParams.get('backendMode') || url.searchParams.get('mode'))?.toLowerCase();
      if (queryMode === 'tools' || queryMode === 'rag_with_tools') {
        return TOOLS_RAG_BACKEND_URL;
      }
      if (queryMode === 'pure' || queryMode === 'pure_rag') {
        return PURE_RAG_BACKEND_URL;
      }
    } catch {
      // Ignore URL parsing errors on relative URLs
    }
  }

  // 3. Fallback to default
  return defaultMode === 'tools' ? TOOLS_RAG_BACKEND_URL : PURE_RAG_BACKEND_URL;
}

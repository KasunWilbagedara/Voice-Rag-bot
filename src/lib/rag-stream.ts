// Client helpers for the streaming RAG endpoint (/api/rag/stream).

export interface RagResult {
  answer: string;
  retrievedChunks: any[];
}

/**
 * Sends a question and reads the streamed answer.
 * `onText` is called with the full answer-so-far each time new text arrives.
 */
export async function streamRag(
  body: Record<string, unknown>,
  backendMode: string,
  onText: (textSoFar: string) => void
): Promise<RagResult> {
  const res = await fetch('/api/rag/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-backend-mode': backendMode },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || err.detail || 'RAG query failed');
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let text = '';
  let answer = '';
  let retrievedChunks: any[] = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split('\n');
    buffer = lines.pop() || ''; // keep any partial line for the next read
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      if (event.type === 'sources') retrievedChunks = event.retrievedChunks || [];
      if (event.type === 'token') {
        text += event.text;
        onText(text);
      }
      if (event.type === 'done') answer = event.answer;
      if (event.type === 'error') throw new Error(event.message);
    }
  }

  return { answer: answer || text, retrievedChunks };
}

/** Answer text with markdown, code blocks and [Source N] markers removed, for speaking. */
export function speakableText(text: string): string {
  return text
    .replace(/```[\s\S]*?(```|$)/g, ' ')
    .replace(/\[[^\]]*\]/g, '')
    .replace(/[*#`_~|]/g, '')
    .replace(/\s+/g, ' ')
    .replace(/\s+([.,!?])/g, '$1')
    .trim();
}

/**
 * The first `count` complete sentences of `text` (for early text-to-speech),
 * or '' if that many sentences haven't arrived yet.
 */
export function firstSentences(text: string, count = 2): string {
  // A sentence ends at . ! ? or ෴ followed by a space or the end (so "99.99%" isn't split).
  const sentences = speakableText(text).match(/[\s\S]+?[.!?෴]+(?=\s|$)/g) || [];
  return sentences.length >= count ? sentences.slice(0, count).join('').trim() : '';
}

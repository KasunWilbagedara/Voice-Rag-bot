import OpenAI, { toFile } from 'openai';
import { GoogleGenerativeAI } from '@google/generative-ai';

function isGeminiKey(key?: string): boolean {
  const apiKey = key || process.env.GEMINI_API_KEY || process.env.OPENAI_API_KEY || '';
  if (!apiKey) return false;
  return apiKey.startsWith('AIza') || apiKey.startsWith('AQ.') || !apiKey.startsWith('sk-');
}

function getApiKey(customApiKey?: string): string {
  const apiKey = customApiKey || process.env.GEMINI_API_KEY || process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('API Key is required. Please provide a Google Gemini API Key or OpenAI API Key.');
  }
  return apiKey;
}

export async function transcribeAudio(
  audioBuffer: Buffer,
  filename: string = 'audio.webm',
  customApiKey?: string,
  language?: string
): Promise<string> {
  const apiKey = getApiKey(customApiKey);

  if (isGeminiKey(apiKey)) {
    const genAI = new GoogleGenerativeAI(apiKey);
    const modelsToTry = ['gemini-flash-latest', 'gemini-3.6-flash', 'gemini-3.5-flash'];

    const promptText = language === 'si'
      ? 'Transcribe this audio recording exactly into Sinhala script or English text. Output ONLY the transcribed text without additional conversational filler.'
      : 'Transcribe this spoken audio recording exactly into text. Output ONLY the transcribed text.';

    let lastError: any = null;
    for (const mName of modelsToTry) {
      try {
        const model = genAI.getGenerativeModel({ model: mName });
        const result = await model.generateContent([
          {
            inlineData: {
              mimeType: 'audio/webm',
              data: audioBuffer.toString('base64'),
            },
          },
          { text: promptText },
        ]);
        const text = result.response.text();
        if (text && text.trim()) {
          return text.trim();
        }
      } catch (err) {
        lastError = err;
      }
    }

    throw new Error(`Gemini audio transcription failed: ${lastError?.message || 'STT error'}`);
  } else {
    const openai = new OpenAI({ apiKey });
    const file = await toFile(audioBuffer, filename, { type: 'audio/webm' });

    const transcriptionParams: any = {
      file: file,
      model: 'whisper-1',
    };

    if (language && language !== 'auto') {
      transcriptionParams.language = language;
    }

    const transcription = await openai.audio.transcriptions.create(transcriptionParams);
    return transcription.text || '';
  }
}

export type TTSVoice = 'alloy' | 'echo' | 'fable' | 'onyx' | 'nova' | 'shimmer';

function splitTextForTTS(text: string, maxLen: number = 180): string[] {
  const cleaned = text.replace(/[*#\`\-_]/g, '').trim();
  if (!cleaned) return [];

  const sentences = cleaned.match(/[^.!?\n]+[.!?\n]+/g) || [cleaned];
  const chunks: string[] = [];
  let current = '';

  for (const sentence of sentences) {
    if ((current + sentence).length <= maxLen) {
      current += sentence;
    } else {
      if (current.trim()) chunks.push(current.trim());
      current = sentence;
    }
  }
  if (current.trim()) chunks.push(current.trim());
  return chunks.length > 0 ? chunks : [cleaned.slice(0, maxLen)];
}

export async function generateSpeechAudio(
  text: string,
  voice: TTSVoice = 'nova',
  customApiKey?: string,
  language: string = 'si'
): Promise<Buffer> {
  const apiKey = getApiKey(customApiKey);

  // If OpenAI key is provided, try OpenAI TTS first
  if (!isGeminiKey(apiKey)) {
    try {
      const openai = new OpenAI({ apiKey });
      const mp3 = await openai.audio.speech.create({
        model: 'tts-1',
        voice: voice,
        input: text,
        response_format: 'mp3',
        speed: 1.0,
      });

      const arrayBuffer = await mp3.arrayBuffer();
      return Buffer.from(arrayBuffer);
    } catch (e) {
      console.warn('OpenAI TTS failed, falling back to Google TTS:', e);
    }
  }

  // High-fidelity Google TTS MP3 generation for Sinhala ('si') & English ('en')
  const langCode = language === 'si' ? 'si' : 'en';
  const textChunks = splitTextForTTS(text, 180);
  const audioBuffers: Buffer[] = [];

  for (const chunk of textChunks) {
    const encodedText = encodeURIComponent(chunk);
    const ttsUrl = `https://translate.google.com/translate_tts?ie=UTF-8&q=${encodedText}&tl=${langCode}&client=tw-ob`;

    const res = await fetch(ttsUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      },
    });

    if (res.ok) {
      const arrayBuffer = await res.arrayBuffer();
      audioBuffers.push(Buffer.from(arrayBuffer));
    }
  }

  if (audioBuffers.length === 0) {
    throw new Error('Failed to generate TTS audio.');
  }

  return Buffer.concat(audioBuffers);
}

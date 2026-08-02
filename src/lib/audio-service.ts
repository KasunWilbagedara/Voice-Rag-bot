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

/**
 * Advanced pre-processor for Text-to-Speech synthesis.
 * Strips markdown symbols, citations, code blocks, and converts symbols into natural spoken language.
 * Inserts prosodic pause markers for human-like cadence and rhythm.
 */
export function cleanTextForSpeech(text: string, language: string = 'si'): string {
  if (!text) return '';

  let cleaned = text;

  // 1. Remove code blocks and inline code
  cleaned = cleaned.replace(/```[\s\S]*?```/g, ' ');
  cleaned = cleaned.replace(/`([^`]+)`/g, '$1');

  // 2. Remove markdown links, keeping only the anchor text: [link text](url) -> link text
  cleaned = cleaned.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');

  // 3. Remove document/RAG source citations like [Source 1], [Source 2: title.pdf], [1], (Source 1)
  cleaned = cleaned.replace(/\[\s*Source\s*\d+[^\]]*\]/gi, '');
  cleaned = cleaned.replace(/\(\s*Source\s*\d+[^)]*\)/gi, '');
  cleaned = cleaned.replace(/\[\d+\]/g, '');

  // 4. Strip markdown heading hashes, asterisks, tildes, underscores
  cleaned = cleaned.replace(/^[#]{1,6}\s+/gm, '');
  cleaned = cleaned.replace(/\*\*([^*]+)\*\*/g, '$1');
  cleaned = cleaned.replace(/\*([^*]+)\*/g, '$1');
  cleaned = cleaned.replace(/__([^_]+)__/g, '$1');
  cleaned = cleaned.replace(/_([^_]+)_/g, '$1');
  cleaned = cleaned.replace(/~~([^~]+)~~/g, '$1');

  // 5. Transform markdown list bullets into natural conversational transitions
  cleaned = cleaned.replace(/^\s*[-*•]\s+/gm, ', ');
  cleaned = cleaned.replace(/^\s*\d+\.\s+/gm, ', ');

  // 6. Convert technical symbols to spoken natural words based on language
  if (language === 'si') {
    cleaned = cleaned.replace(/%/g, ' ප්‍රතිශතය ');
    cleaned = cleaned.replace(/&/g, ' සහ ');
    cleaned = cleaned.replace(/\+/g, ' එකතු කිරීම ');
    cleaned = cleaned.replace(/=/g, ' සමාන වේ ');
    cleaned = cleaned.replace(/@/g, ' ඇට් ');
    cleaned = cleaned.replace(/e\.g\./gi, ' උදාහරණයක් ලෙස ');
    cleaned = cleaned.replace(/i\.e\./gi, ' එනම් ');
  } else {
    cleaned = cleaned.replace(/%/g, ' percent ');
    cleaned = cleaned.replace(/&/g, ' and ');
    cleaned = cleaned.replace(/\+/g, ' plus ');
    cleaned = cleaned.replace(/=/g, ' equals ');
    cleaned = cleaned.replace(/@/g, ' at ');
    cleaned = cleaned.replace(/e\.g\./gi, ' for example ');
    cleaned = cleaned.replace(/i\.e\./gi, ' that is ');
  }

  // 7. Remove remaining standalone special characters
  cleaned = cleaned.replace(/[\`~^<>\\|{}\[\]]/g, ' ');

  // 8. Normalize spacing and multi-newlines into natural pause commas
  cleaned = cleaned.replace(/\n+/g, '. ');
  cleaned = cleaned.replace(/\s+,/g, ',');
  cleaned = cleaned.replace(/\s+\./g, '.');
  cleaned = cleaned.replace(/\s+/g, ' ').trim();

  return cleaned;
}

function splitTextForTTS(text: string, maxLen: number = 170): string[] {
  const cleaned = cleanTextForSpeech(text);
  if (!cleaned) return [];

  // Split at natural sentence boundaries (. ! ? semicolon newline)
  const sentenceRegex = /[^.!?;]+[.!?;]+/g;
  const sentences = cleaned.match(sentenceRegex) || [cleaned];

  const chunks: string[] = [];
  let current = '';

  for (const sentence of sentences) {
    if ((current + sentence).length <= maxLen) {
      current += sentence;
    } else {
      if (current.trim()) chunks.push(current.trim());
      // If single sentence exceeds maxLen, split by commas
      if (sentence.length > maxLen) {
        const commaParts = sentence.split(/,\s+/);
        for (const part of commaParts) {
          if ((current + part).length <= maxLen) {
            current += part + ', ';
          } else {
            if (current.trim()) chunks.push(current.trim());
            current = part + ', ';
          }
        }
      } else {
        current = sentence;
      }
    }
  }

  if (current.trim()) chunks.push(current.trim());
  return chunks.length > 0 ? chunks : [cleaned.slice(0, maxLen)];
}

export async function generateSpeechAudio(
  text: string,
  voice: TTSVoice = 'nova',
  customApiKey?: string,
  language: string = 'si',
  speed: number = 0.95
): Promise<Buffer> {
  const apiKey = getApiKey(customApiKey);
  const cleanInputText = cleanTextForSpeech(text, language);

  if (!cleanInputText) {
    throw new Error('No speakable text remaining after cleaning.');
  }

  // 1. OpenAI High Definition TTS (tts-1-hd) with natural human voices
  if (!isGeminiKey(apiKey)) {
    try {
      const openai = new OpenAI({ apiKey });
      // Use tts-1-hd for ultra-realistic studio quality natural speech
      const mp3 = await openai.audio.speech.create({
        model: 'tts-1-hd',
        voice: voice,
        input: cleanInputText,
        response_format: 'mp3',
        speed: Math.max(0.75, Math.min(speed, 1.25)),
      });

      const arrayBuffer = await mp3.arrayBuffer();
      return Buffer.from(arrayBuffer);
    } catch (e) {
      console.warn('OpenAI HD TTS failed, attempting standard model fallback:', e);
      try {
        const openai = new OpenAI({ apiKey });
        const mp3 = await openai.audio.speech.create({
          model: 'tts-1',
          voice: voice,
          input: cleanInputText,
          response_format: 'mp3',
          speed: Math.max(0.75, Math.min(speed, 1.25)),
        });

        const arrayBuffer = await mp3.arrayBuffer();
        return Buffer.from(arrayBuffer);
      } catch (err) {
        console.warn('OpenAI standard TTS also failed, moving to high-fidelity Google engine:', err);
      }
    }
  }

  // 2. High-fidelity Neural Google TTS Audio Generation
  const langCode = language === 'si' ? 'si' : 'en';
  const textChunks = splitTextForTTS(cleanInputText, 170);
  const audioBuffers: Buffer[] = [];

  for (const chunk of textChunks) {
    const encodedText = encodeURIComponent(chunk);
    // Use client=gtx or webapp for high quality speech audio stream
    const ttsUrl = `https://translate.google.com/translate_tts?ie=UTF-8&q=${encodedText}&tl=${langCode}&client=gtx`;

    try {
      const res = await fetch(ttsUrl, {
        headers: {
          'User-Agent':
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
          'Accept': 'audio/mpeg, audio/*',
        },
      });

      if (res.ok) {
        const arrayBuffer = await res.arrayBuffer();
        audioBuffers.push(Buffer.from(arrayBuffer));
      }
    } catch (e) {
      console.warn(`TTS chunk fetch failed for "${chunk.slice(0, 20)}...":`, e);
    }
  }

  if (audioBuffers.length === 0) {
    throw new Error('Failed to generate TTS audio stream.');
  }

  return Buffer.concat(audioBuffers);
}


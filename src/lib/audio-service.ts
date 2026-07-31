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
    throw new Error('API Key is required. Please provide a Gemini API Key (starts with AIza) or OpenAI API Key.');
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
    const model = genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });

    const promptText = language === 'si'
      ? 'Transcribe this audio recording exactly into Sinhala script or English text. Output ONLY the transcribed text without additional conversational filler.'
      : 'Transcribe this spoken audio recording exactly into text. Output ONLY the transcribed text.';

    const result = await model.generateContent([
      {
        inlineData: {
          mimeType: 'audio/webm',
          data: audioBuffer.toString('base64'),
        },
      },
      { text: promptText },
    ]);

    return result.response.text().trim() || '';
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

export async function generateSpeechAudio(
  text: string,
  voice: TTSVoice = 'nova',
  customApiKey?: string
): Promise<Buffer | null> {
  const apiKey = getApiKey(customApiKey);

  if (!isGeminiKey(apiKey)) {
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
  } else {
    // For Gemini API keys, return null so browser Web Speech API (speechSynthesis) speaks the Sinhala/English response natively!
    return null;
  }
}

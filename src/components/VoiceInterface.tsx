'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Mic, MicOff, Volume2, Loader2, Sparkles, AlertCircle, Zap, Key } from 'lucide-react';
import { AudioVisualizer } from './AudioVisualizer';

interface VoiceInterfaceProps {
  apiKey?: string;
  voice?: string;
  model?: string;
  language?: string;
  onLanguageChange?: (lang: string) => void;
  onQueryComplete?: (data: {
    userQuery: string;
    aiResponse: string;
    retrievedChunks: any[];
  }) => void;
}

type VoiceState = 'idle' | 'listening' | 'transcribing' | 'searching' | 'speaking';

export const VoiceInterface: React.FC<VoiceInterfaceProps> = ({
  apiKey,
  voice = 'nova',
  model = 'gemini-flash-latest',
  language = 'si',
  onLanguageChange,
  onQueryComplete,
}) => {
  const [state, setState] = useState<VoiceState>('idle');
  const [isHandsFree, setIsHandsFree] = useState(false);
  const [currentQuery, setCurrentQuery] = useState('');
  const [currentResponse, setCurrentResponse] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  const isGemini = apiKey?.startsWith('AIza');

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const speakTextWithBrowserTTS = (text: string) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      setState('idle');
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = language === 'si' ? 'si-LK' : 'en-US';
    utterance.rate = 0.95;

    utterance.onend = () => {
      setState('idle');
      if (isHandsFree) {
        setTimeout(() => startRecording(), 1000);
      }
    };

    utterance.onerror = () => {
      setState('idle');
    };

    setState('speaking');
    window.speechSynthesis.speak(utterance);
  };

  const startRecording = async () => {
    setErrorMessage(null);
    audioChunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        stream.getTracks().forEach((track) => track.stop());

        if (audioBlob.size > 0) {
          await processVoiceInput(audioBlob);
        }
      };

      mediaRecorder.start(200);
      setState('listening');
    } catch (err: any) {
      console.error('Microphone access error:', err);
      setErrorMessage('Microphone access denied. Please allow microphone permissions.');
      setState('idle');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
      setState('transcribing');
    }
  };

  const processVoiceInput = async (audioBlob: Blob) => {
    try {
      setState('searching');
      const formData = new FormData();
      formData.append('audio', audioBlob, 'voice_query.webm');
      if (apiKey) formData.append('apiKey', apiKey);
      if (voice) formData.append('voice', voice);
      if (model) formData.append('model', model);
      if (language) formData.append('language', language);

      const res = await fetch('/api/voice-pipeline', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Voice RAG pipeline failed');
      }

      setCurrentQuery(data.userQueryText);
      setCurrentResponse(data.aiResponseText);

      if (onQueryComplete) {
        onQueryComplete({
          userQuery: data.userQueryText,
          aiResponse: data.aiResponseText,
          retrievedChunks: data.retrievedChunks || [],
        });
      }

      if (data.audioBase64) {
        setState('speaking');
        const audioSrc = `data:${data.audioFormat || 'audio/mp3'};base64,${data.audioBase64}`;

        if (audioPlayerRef.current) {
          audioPlayerRef.current.src = audioSrc;
          audioPlayerRef.current.onended = () => {
            setState('idle');
            if (isHandsFree) {
              setTimeout(() => startRecording(), 1000);
            }
          };
          await audioPlayerRef.current.play();
        } else {
          speakTextWithBrowserTTS(data.aiResponseText);
        }
      } else {
        // Use native Browser Web Speech API for Gemini voice playback
        speakTextWithBrowserTTS(data.aiResponseText);
      }
    } catch (err: any) {
      console.error('Voice Processing Error:', err);
      setErrorMessage(err.message || 'Error processing voice query');
      setState('idle');
    }
  };

  const toggleMic = () => {
    if (state === 'idle') {
      startRecording();
    } else if (state === 'listening') {
      stopRecording();
    }
  };

  return (
    <div className="w-full glass-panel-glow rounded-3xl p-6 md:p-8 flex flex-col items-center gap-6 relative overflow-hidden">
      <audio ref={audioPlayerRef} className="hidden" />

      {/* Header controls & language switcher */}
      <div className="w-full flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="relative flex h-3 w-3">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                state === 'listening'
                  ? 'bg-cyan-400'
                  : state === 'speaking'
                  ? 'bg-emerald-400'
                  : state === 'searching'
                  ? 'bg-violet-400'
                  : 'bg-blue-400'
              }`}
            />
            <span
              className={`relative inline-flex rounded-full h-3 w-3 ${
                state === 'listening'
                  ? 'bg-cyan-500'
                  : state === 'speaking'
                  ? 'bg-emerald-500'
                  : state === 'searching'
                  ? 'bg-violet-500'
                  : 'bg-blue-500'
              }`}
            />
          </span>
          <span className="text-xs uppercase tracking-wider font-semibold text-gray-400">
            {state === 'idle' && 'Ready for Speech'}
            {state === 'listening' && 'Listening...'}
            {state === 'transcribing' && 'Transcribing speech...'}
            {state === 'searching' && 'Vector RAG & LLM Reasoning...'}
            {state === 'speaking' && 'Streaming Sinhala voice output...'}
          </span>
        </div>

        {/* Language selector toggle */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-gray-900/90 border border-gray-800 p-1 rounded-full text-xs">
            <button
              onClick={() => onLanguageChange && onLanguageChange('si')}
              className={`px-3 py-1 rounded-full font-bold transition-all flex items-center gap-1 ${
                language === 'si'
                  ? 'bg-gradient-to-r from-amber-500 to-orange-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              🇱🇰 සිංහල (Sinhala)
            </button>
            <button
              onClick={() => onLanguageChange && onLanguageChange('en')}
              className={`px-3 py-1 rounded-full font-bold transition-all flex items-center gap-1 ${
                language === 'en'
                  ? 'bg-brand-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              🇺🇸 English
            </button>
          </div>

          <button
            onClick={() => setIsHandsFree(!isHandsFree)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all flex items-center gap-1.5 ${
              isHandsFree
                ? 'bg-brand-600/30 text-brand-400 border border-brand-500/40'
                : 'bg-gray-800/60 text-gray-400 hover:text-gray-200 border border-gray-700/50'
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            {isHandsFree ? 'Hands-Free On' : 'Hands-Free Off'}
          </button>
        </div>
      </div>

      {/* Live Waveform Canvas */}
      <AudioVisualizer isActive={state !== 'idle'} mode={state} />

      {/* Big Mic Button */}
      <div className="relative my-2">
        {state === 'listening' && (
          <div className="absolute -inset-4 rounded-full bg-cyan-500/20 animate-ping" />
        )}
        {state === 'speaking' && (
          <div className="absolute -inset-4 rounded-full bg-emerald-500/20 animate-pulse" />
        )}

        <button
          onClick={toggleMic}
          disabled={state === 'transcribing' || state === 'searching'}
          className={`relative z-10 w-24 h-24 rounded-full flex items-center justify-center transition-all transform hover:scale-105 active:scale-95 shadow-2xl ${
            state === 'listening'
              ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white glow-cyan'
              : state === 'speaking'
              ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white glow-emerald'
              : state === 'searching' || state === 'transcribing'
              ? 'bg-gradient-to-r from-violet-600 to-purple-600 text-white cursor-wait opacity-80'
              : 'bg-gradient-to-r from-amber-500 to-orange-600 text-white hover:from-amber-400 hover:to-orange-500 glow-blue'
          }`}
        >
          {state === 'transcribing' || state === 'searching' ? (
            <Loader2 className="w-10 h-10 animate-spin" />
          ) : state === 'listening' ? (
            <MicOff className="w-10 h-10 animate-pulse" />
          ) : state === 'speaking' ? (
            <Volume2 className="w-10 h-10 animate-bounce" />
          ) : (
            <Mic className="w-10 h-10" />
          )}
        </button>
      </div>

      <p className="text-sm font-medium text-gray-300 text-center">
        {state === 'idle' && (language === 'si' ? 'කතා කිරීමට මයික්‍රෆෝනය ඔබන්න (Speak in Sinhala or English)' : 'Click microphone to start speaking')}
        {state === 'listening' && 'Tap mic again when finished speaking'}
        {state === 'transcribing' && 'Transcribing speech...'}
        {state === 'searching' && 'Cross-lingual RAG retrieval & Gemini reasoning...'}
        {state === 'speaking' && 'Streaming voice output...'}
      </p>

      {/* Error notification banner */}
      {errorMessage && (
        <div className="w-full p-3 rounded-xl bg-red-950/40 border border-red-800/50 flex items-center gap-2 text-red-300 text-xs">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Live Speech & Response Preview */}
      {(currentQuery || currentResponse) && (
        <div className="w-full flex flex-col gap-3 mt-2 pt-4 border-t border-gray-800">
          {currentQuery && (
            <div className="p-3 rounded-xl bg-gray-900/60 border border-gray-800/80">
              <span className="text-[10px] font-bold tracking-wider text-cyan-400 uppercase block mb-1">
                You Spoke
              </span>
              <p className="text-sm text-gray-200 font-medium">{currentQuery}</p>
            </div>
          )}

          {currentResponse && (
            <div className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-800/40">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-bold tracking-wider text-emerald-400 uppercase flex items-center gap-1">
                  <Sparkles className="w-3 h-3" /> Voice AI Response ({language === 'si' ? 'Sinhala' : 'English'})
                </span>
              </div>
              <p className="text-sm text-gray-100 font-medium leading-relaxed">{currentResponse}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

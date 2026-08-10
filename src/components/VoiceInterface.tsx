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
  const recognitionRef = useRef<any>(null);
  const vadTimerRef = useRef<NodeJS.Timeout | null>(null);

  const [useInstantMode, setUseInstantMode] = useState<boolean>(true);
  const [liveTranscript, setLiveTranscript] = useState<string>('');

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch (e) {}
      }
      if (vadTimerRef.current) {
        clearTimeout(vadTimerRef.current);
      }
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const playServerTTS = async (textToSpeak: string) => {
    try {
      setState('speaking');
      const res = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: textToSpeak,
          voice,
          apiKey,
          language,
        }),
      });

      if (!res.ok) throw new Error('TTS fetch failed');

      const audioBlob = await res.blob();
      const audioUrl = URL.createObjectURL(audioBlob);

      if (audioPlayerRef.current) {
        audioPlayerRef.current.src = audioUrl;
        audioPlayerRef.current.onended = () => {
          setState('idle');
          if (isHandsFree) {
            setTimeout(() => startRecording(), 600);
          }
        };
        await audioPlayerRef.current.play();
      } else {
        const audio = new Audio(audioUrl);
        audio.onended = () => {
          setState('idle');
          if (isHandsFree) {
            setTimeout(() => startRecording(), 600);
          }
        };
        await audio.play();
      }
    } catch (err) {
      console.error('Server TTS Audio Playback Error:', err);
      setState('idle');
    }
  };

  const speakTextWithBrowserTTS = async (text: string) => {
    if (!text || !text.trim()) {
      setState('idle');
      return;
    }

    // Pre-clean text to remove markdown, brackets, and citations for speech
    const cleanSpeechText = text
      .replace(/\[[^\]]*\]/g, '')
      .replace(/[*#\`\-_~]/g, '')
      .replace(/\s+/g, ' ')
      .trim();

    if (!cleanSpeechText) {
      setState('idle');
      return;
    }

    const targetLangPrefix = language === 'si' ? 'si' : 'en';

    // Try browser speech synthesis ONLY if a high-quality Neural/Natural human voice exists on the OS
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const availableVoices = window.speechSynthesis.getVoices();
      const matchingVoice = availableVoices.find((v) => {
        const name = v.name.toLowerCase();
        const lang = v.lang.toLowerCase();
        return (
          lang.startsWith(targetLangPrefix) &&
          (name.includes('natural') ||
            name.includes('neural') ||
            name.includes('google') ||
            name.includes('premium') ||
            name.includes('enhanced') ||
            name.includes('studio') ||
            name.includes('siri'))
        );
      });

      if (matchingVoice) {
        const utterance = new SpeechSynthesisUtterance(cleanSpeechText);
        utterance.lang = language === 'si' ? 'si-LK' : 'en-US';
        utterance.voice = matchingVoice;
        utterance.rate = 0.92;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        utterance.onend = () => {
          setState('idle');
          if (isHandsFree) {
            setTimeout(() => startRecording(), 600);
          }
        };

        utterance.onerror = (err) => {
          console.warn('Browser SpeechSynthesis Error, switching to server audio stream:', err);
          playServerTTS(cleanSpeechText);
        };

        setState('speaking');
        window.speechSynthesis.speak(utterance);
        return;
      }
    }

    // Fall back to server MP3 audio stream (Works 100% reliably on all OS/Browsers)
    await playServerTTS(cleanSpeechText);
  };

  // Ultra-Fast Real-Time Text RAG Query execution
  const processInstantTextQuery = async (queryText: string) => {
    if (!queryText || !queryText.trim()) return;

    try {
      setState('searching');
      setCurrentQuery(queryText);

      const res = await fetch('/api/rag', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: queryText,
          apiKey,
          model: model || 'gemini-1.5-flash',
          language,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'RAG Query failed');

      setCurrentResponse(data.answer);

      if (onQueryComplete) {
        onQueryComplete({
          userQuery: queryText,
          aiResponse: data.answer,
          retrievedChunks: data.retrievedChunks || [],
        });
      }

      // Immediately speak the answer with < 300ms delay!
      speakTextWithBrowserTTS(data.answer);
    } catch (err: any) {
      console.error('Instant RAG Error:', err);
      setErrorMessage(err.message || 'Error processing query');
      setState('idle');
    }
  };

  const startRecording = async () => {
    setErrorMessage(null);
    setLiveTranscript('');
    audioChunksRef.current = [];

    // Check for native browser SpeechRecognition for live real-time VAD
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition && useInstantMode) {
      try {
        if (recognitionRef.current) {
          try {
            recognitionRef.current.abort();
          } catch (e) {}
        }

        const recognition = new SpeechRecognition();
        recognitionRef.current = recognition;
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = language === 'si' ? 'si-LK' : 'en-US';

        let finalTranscript = '';

        recognition.onresult = (event: any) => {
          let interim = '';
          for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
              finalTranscript += transcript + ' ';
            } else {
              interim += transcript;
            }
          }

          const currentText = (finalTranscript + interim).trim();
          setLiveTranscript(currentText);

          // Reset silence VAD timer (800ms silence auto-detect)
          if (vadTimerRef.current) clearTimeout(vadTimerRef.current);

          if (currentText.length > 3) {
            vadTimerRef.current = setTimeout(() => {
              recognition.stop();
            }, 850);
          }
        };

        recognition.onend = () => {
          setState('idle');
          if (finalTranscript.trim() || liveTranscript.trim()) {
            const textToQuery = (finalTranscript || liveTranscript).trim();
            processInstantTextQuery(textToQuery);
          }
        };

        recognition.onerror = (event: any) => {
          console.warn('SpeechRecognition error:', event.error);
          if (event.error !== 'no-speech') {
            startMediaRecorderFallback();
          }
        };

        recognition.start();
        setState('listening');
        return;
      } catch (e) {
        console.warn('SpeechRecognition initialization failed, falling back to MediaRecorder:', e);
      }
    }

    startMediaRecorderFallback();
  };

  const startMediaRecorderFallback = async () => {
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
    if (vadTimerRef.current) clearTimeout(vadTimerRef.current);

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
    } else if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
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
              setTimeout(() => startRecording(), 800);
            }
          };
          await audioPlayerRef.current.play();
        } else {
          speakTextWithBrowserTTS(data.aiResponseText);
        }
      } else {
        speakTextWithBrowserTTS(data.aiResponseText);
      }
    } catch (err: any) {
      console.error('Voice Processing Error:', err);
      setErrorMessage(err.message || 'Error processing voice query');
      setState('idle');
    }
  };

  const stopSpeaking = () => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    if (audioPlayerRef.current) {
      try {
        audioPlayerRef.current.pause();
        audioPlayerRef.current.currentTime = 0;
      } catch (e) {}
    }
    setState('idle');
  };

  const toggleMic = () => {
    if (state === 'speaking') {
      stopSpeaking();
      startRecording();
      return;
    }
    if (state === 'idle') {
      startRecording();
    } else if (state === 'listening') {
      stopRecording();
    }
  };

  return (
    <div className="w-full bg-white border border-gray-200 rounded p-6 md:p-8 flex flex-col items-center gap-6 relative overflow-hidden shadow-sm">
      <audio ref={audioPlayerRef} className="hidden" />

      {/* Header controls & language switcher */}
      <div className="w-full flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="relative flex h-3 w-3">
            <span
              className={`animate-ping absolute inline-flex h-full w-full opacity-75 ${
                state === 'listening'
                  ? 'bg-black'
                  : state === 'speaking'
                  ? 'bg-emerald-400'
                  : state === 'searching'
                  ? 'bg-gray-400'
                  : 'bg-gray-200'
              }`}
            />
            <span
              className={`relative inline-flex h-3 w-3 ${
                state === 'listening'
                  ? 'bg-black'
                  : state === 'speaking'
                  ? 'bg-emerald-500'
                  : state === 'searching'
                  ? 'bg-gray-500'
                  : 'bg-gray-300'
              }`}
            />
          </span>
          <span className="text-xs uppercase tracking-widest font-bold text-gray-500">
            {state === 'idle' && 'Ready for Speech'}
            {state === 'listening' && 'Listening...'}
            {state === 'transcribing' && 'Transcribing speech...'}
            {state === 'searching' && 'Vector RAG & LLM Reasoning...'}
            {state === 'speaking' && 'Streaming Sinhala voice output...'}
          </span>
        </div>

        {/* Mode & Language selector toggle */}
        <div className="flex items-center gap-2">
          {/* Instant Real-Time vs Server HD Mode */}
          <button
            onClick={() => setUseInstantMode(!useInstantMode)}
            className={`px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 border ${
              useInstantMode
                ? 'bg-black text-white border-black'
                : 'bg-white text-gray-400 border-gray-200 hover:text-black hover:border-black'
            }`}
            title="Real-Time Mode enables instant <500ms voice answers"
          >
            <Sparkles className={`w-3.5 h-3.5 ${useInstantMode ? 'text-emerald-400' : 'text-gray-400'}`} />
            {useInstantMode ? 'Instant Mode' : 'Studio HD Mode'}
          </button>

          <div className="flex items-center p-0.5 bg-gray-100 border border-gray-200 rounded text-[10px] font-bold uppercase tracking-wider">
            <button
              onClick={() => onLanguageChange && onLanguageChange('si')}
              className={`px-3 py-1 rounded transition-all flex items-center gap-1 ${
                language === 'si'
                  ? 'bg-black text-white'
                  : 'text-gray-500 hover:text-black'
              }`}
            >
              Sinhala
            </button>
            <button
              onClick={() => onLanguageChange && onLanguageChange('en')}
              className={`px-3 py-1 rounded transition-all flex items-center gap-1 ${
                language === 'en'
                  ? 'bg-black text-white'
                  : 'text-gray-500 hover:text-black'
              }`}
            >
              English
            </button>
          </div>

          <button
            onClick={() => setIsHandsFree(!isHandsFree)}
            className={`px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 border ${
              isHandsFree
                ? 'bg-black text-white border-black'
                : 'bg-white text-gray-400 border-gray-200 hover:text-black hover:border-black'
            }`}
          >
            <Zap className={`w-3.5 h-3.5 ${isHandsFree ? 'text-emerald-400' : 'text-gray-400'}`} />
            {isHandsFree ? 'Hands-Free On' : 'Hands-Free Off'}
          </button>
        </div>
      </div>

      {/* Live Waveform Canvas */}
      <AudioVisualizer isActive={state !== 'idle'} mode={state} />

      {/* Big Mic Button */}
      <div className="relative my-2">
        {state === 'listening' && (
          <div className="absolute -inset-4 rounded-full border-2 border-emerald-500 animate-ping opacity-20" />
        )}
        {state === 'speaking' && (
          <div className="absolute -inset-4 rounded-full border-2 border-emerald-500 animate-pulse opacity-20" />
        )}

        <button
          onClick={toggleMic}
          disabled={state === 'transcribing' || state === 'searching'}
          className={`relative z-10 w-24 h-24 rounded-full flex items-center justify-center transition-all transform hover:scale-105 active:scale-95 shadow-sm border ${
            state === 'listening'
              ? 'bg-black border-emerald-500 text-emerald-400'
              : state === 'speaking'
              ? 'bg-black border-black text-emerald-500'
              : state === 'searching' || state === 'transcribing'
              ? 'bg-gray-100 border-gray-200 text-gray-400 cursor-wait'
              : 'bg-black border-black text-white hover:bg-gray-900'
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
        {state === 'listening' && (liveTranscript ? ` Listening: "${liveTranscript}"` : 'Listening... speak now')}
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
        <div className="w-full flex flex-col gap-3 mt-2 pt-4 border-t border-gray-200">
          {currentQuery && (
            <div className="p-3 rounded bg-gray-50 border border-gray-200">
              <span className="text-[10px] font-bold tracking-widest text-gray-400 uppercase block mb-1">
                You Spoke
              </span>
              <p className="text-sm text-black font-bold">{currentQuery}</p>
            </div>
          )}

          {currentResponse && (
            <div className="p-4 rounded bg-white border border-gray-200 flex flex-col gap-2 shadow-sm">
              <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                <span className="text-[10px] font-bold tracking-widest text-emerald-600 uppercase flex items-center gap-1">
                  <Sparkles className="w-3 h-3" /> AI Response ({language === 'si' ? 'Sinhala' : 'English'})
                </span>

                <div className="flex items-center gap-2">
                  {state === 'speaking' ? (
                    <button
                      onClick={stopSpeaking}
                      className="px-2.5 py-1 rounded bg-gray-100 hover:bg-gray-200 text-black border border-gray-200 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 transition-all"
                    >
                      🛑 Stop Speaking
                    </button>
                  ) : (
                    <button
                      onClick={() => speakTextWithBrowserTTS(currentResponse)}
                      className="px-2.5 py-1 rounded bg-white hover:bg-gray-50 text-black border border-gray-200 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 transition-all shadow-sm"
                    >
                      🔊 Replay Voice
                    </button>
                  )}
                </div>
              </div>
              <p className="text-sm text-black font-medium leading-relaxed">{currentResponse}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

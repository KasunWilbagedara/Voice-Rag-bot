'use client';

import React, { useState, useRef, useEffect } from 'react';
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Loader2,
  Sparkles,
  AlertCircle,
  Zap,
  Copy,
  Check,
  RotateCcw,
  MessageSquarePlus,
} from 'lucide-react';
import { AudioVisualizer } from './AudioVisualizer';
import { DynamicChart, parseChartDataFromResponse } from './DynamicChart';

interface VoiceInterfaceProps {
  apiKey?: string;
  voice?: string;
  model?: string;
  provider?: string;
  baseUrl?: string;
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
  model = 'gemini-3.5-flash',
  provider = 'gemini',
  baseUrl = '',
  language = 'si',
  onLanguageChange,
  onQueryComplete,
}) => {
  const [state, setState] = useState<VoiceState>('idle');
  const [isHandsFree, setIsHandsFree] = useState(false);
  const [currentQuery, setCurrentQuery] = useState('');
  const [currentResponse, setCurrentResponse] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

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

    // Pre-clean text to remove markdown code blocks, brackets, and citations for speech
    const cleanSpeechText = text
      .replace(/```[\s\S]*?```/g, '')
      .replace(/\[[^\]]*\]/g, '')
      .replace(/[*#\`\-_~]/g, '')
      .replace(/\s+/g, ' ')
      .trim();

    if (!cleanSpeechText) {
      setState('idle');
      return;
    }

    const targetLangPrefix = language === 'si' ? 'si' : 'en';

    // Try browser speech synthesis if available
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

    // Fall back to server audio stream
    await playServerTTS(cleanSpeechText);
  };

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
          model: model || 'gemini-2.0-flash',
          provider,
          baseUrl,
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
      setErrorMessage('Microphone access denied. Please allow microphone permissions in your browser.');
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
      if (provider) formData.append('provider', provider);
      if (baseUrl) formData.append('baseUrl', baseUrl);
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

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const quickPrompts = language === 'si' ? [
    { label: 'ORD-9021 ඇණවුමේ තත්වය?', query: 'ORD-9021 ඇණවුමේ තත්වය කුමක්ද?' },
    { label: 'Amara Perera ගේ විස්තර කියන්න', query: 'Amara Perera ගේ පාරිභෝගික විස්තර කියන්න' },
    { label: 'STU1042 ශිෂ්‍යයාගේ GPA එක කීයද?', query: 'STU1042 ශිෂ්‍යයාගේ GPA සහ දෙපාර්තමේන්තුව කුමක්ද?' },
  ] : [
    { label: 'Status of Order ORD-9021?', query: 'What is the status of order ORD-9021?' },
    { label: 'Customer details for Amara Perera', query: 'Show customer details for Amara Perera' },
    { label: 'What is the official refund policy?', query: 'What is the official refund policy for subscriptions?' },
  ];

  return (
    <div className="w-full glass-panel border border-white/10 rounded-3xl p-5 md:p-7 flex flex-col items-center gap-5 relative overflow-hidden shadow-2xl">
      <audio ref={audioPlayerRef} className="hidden" />

      {/* Top Header & Controls */}
      <div className="w-full flex flex-wrap items-center justify-between gap-3 border-b border-white/5 pb-4">
        {/* Status Indicator */}
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-3 w-3">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                state === 'listening'
                  ? 'bg-amber-400'
                  : state === 'speaking'
                  ? 'bg-emerald-400'
                  : state === 'searching' || state === 'transcribing'
                  ? 'bg-violet-400'
                  : 'bg-slate-500'
              }`}
            />
            <span
              className={`relative inline-flex h-3 w-3 rounded-full ${
                state === 'listening'
                  ? 'bg-amber-500'
                  : state === 'speaking'
                  ? 'bg-emerald-500'
                  : state === 'searching' || state === 'transcribing'
                  ? 'bg-violet-500'
                  : 'bg-slate-500'
              }`}
            />
          </span>
          <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
            {state === 'idle' && 'Ready for Speech'}
            {state === 'listening' && 'Listening to Voice...'}
            {state === 'transcribing' && 'Transcribing Speech...'}
            {state === 'searching' && 'Reasoning & Grounding RAG...'}
            {state === 'speaking' && 'Streaming Spoken Audio...'}
          </span>
        </div>

        {/* Action Toggles */}
        <div className="flex items-center gap-2">
          {/* Instant Real-Time toggle */}
          <button
            onClick={() => setUseInstantMode(!useInstantMode)}
            className={`px-3 py-1.5 rounded-xl text-[11px] font-bold tracking-wide transition-all flex items-center gap-1.5 border ${
              useInstantMode
                ? 'bg-amber-500/15 text-amber-300 border-amber-500/40 shadow-sm'
                : 'bg-black/30 text-slate-400 border-white/5 hover:text-slate-200'
            }`}
            title="Real-Time Mode enables instant low-latency voice responses"
          >
            <Sparkles className={`w-3.5 h-3.5 ${useInstantMode ? 'text-amber-400' : 'text-slate-500'}`} />
            <span>{useInstantMode ? 'Instant Voice' : 'HD Server Voice'}</span>
          </button>

          {/* Language Toggle Pill */}
          <div className="flex items-center p-0.5 bg-black/40 border border-white/10 rounded-xl text-[11px] font-bold">
            <button
              onClick={() => onLanguageChange && onLanguageChange('si')}
              className={`px-2.5 py-1 rounded-lg transition-all flex items-center gap-1.5 ${
                language === 'si'
                  ? 'bg-amber-500 text-slate-950 font-extrabold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>🇱🇰</span>
              <span>සිංහල</span>
            </button>
            <button
              onClick={() => onLanguageChange && onLanguageChange('en')}
              className={`px-2.5 py-1 rounded-lg transition-all flex items-center gap-1.5 ${
                language === 'en'
                  ? 'bg-amber-500 text-slate-950 font-extrabold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>🇬🇧</span>
              <span>English</span>
            </button>
          </div>

          {/* Hands-Free Toggle */}
          <button
            onClick={() => setIsHandsFree(!isHandsFree)}
            className={`px-3 py-1.5 rounded-xl text-[11px] font-bold tracking-wide transition-all flex items-center gap-1.5 border ${
              isHandsFree
                ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40 shadow-sm'
                : 'bg-black/30 text-slate-400 border-white/5 hover:text-slate-200'
            }`}
            title="Hands-free automatically listens again after speaking"
          >
            <Zap className={`w-3.5 h-3.5 ${isHandsFree ? 'text-emerald-400' : 'text-slate-500'}`} />
            <span>{isHandsFree ? 'Hands-Free ON' : 'Hands-Free'}</span>
          </button>
        </div>
      </div>

      {/* Reactive Neon Soundwave Canvas */}
      <AudioVisualizer isActive={state !== 'idle'} mode={state} />

      {/* Center Interactive Mic Button with Glowing Rings */}
      <div className="relative my-1 flex flex-col items-center">
        {/* Ripple Rings */}
        {state === 'listening' && (
          <>
            <div className="absolute -inset-6 rounded-full border-2 border-amber-500/40 animate-ping opacity-30 pointer-events-none" />
            <div className="absolute -inset-3 rounded-full bg-amber-500/20 blur-md pointer-events-none" />
          </>
        )}
        {state === 'speaking' && (
          <>
            <div className="absolute -inset-6 rounded-full border-2 border-emerald-500/40 animate-pulse opacity-40 pointer-events-none" />
            <div className="absolute -inset-3 rounded-full bg-emerald-500/20 blur-md pointer-events-none" />
          </>
        )}
        {state === 'searching' && (
          <div className="absolute -inset-3 rounded-full bg-violet-500/20 blur-md pointer-events-none" />
        )}

        <button
          onClick={toggleMic}
          disabled={state === 'transcribing' || state === 'searching'}
          className={`relative z-10 w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 transform hover:scale-105 active:scale-95 shadow-2xl border ${
            state === 'listening'
              ? 'bg-gradient-to-tr from-amber-500 to-amber-400 border-amber-300 text-slate-950 shadow-amber-500/30'
              : state === 'speaking'
              ? 'bg-gradient-to-tr from-emerald-500 to-teal-400 border-emerald-300 text-slate-950 shadow-emerald-500/30'
              : state === 'searching' || state === 'transcribing'
              ? 'bg-slate-900 border-violet-500/40 text-violet-300 cursor-wait shadow-violet-500/20'
              : 'bg-gradient-to-tr from-amber-500 via-amber-400 to-orange-500 border-amber-300/80 text-slate-950 hover:brightness-110 shadow-amber-500/25'
          }`}
          title={state === 'listening' ? 'Click to stop listening' : 'Click to start voice query'}
        >
          {state === 'transcribing' || state === 'searching' ? (
            <Loader2 className="w-10 h-10 animate-spin text-amber-300" />
          ) : state === 'listening' ? (
            <MicOff className="w-10 h-10 animate-pulse text-slate-950" />
          ) : state === 'speaking' ? (
            <Volume2 className="w-10 h-10 animate-bounce text-slate-950" />
          ) : (
            <Mic className="w-10 h-10 text-slate-950" />
          )}
        </button>

        {/* Live Speech Recognition Bubble */}
        {state === 'listening' && liveTranscript && (
          <div className="mt-4 px-4 py-2 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs font-medium max-w-md text-center animate-fade-in shadow-lg backdrop-blur-md flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping shrink-0" />
            <span className="italic">"{liveTranscript}"</span>
          </div>
        )}
      </div>

      {/* Instructions / Prompt Guidance */}
      <p className="text-xs font-medium text-slate-400 text-center max-w-md">
        {state === 'idle' && (
          language === 'si'
            ? 'කතා කිරීමට මයික්‍රෆෝනය ඔබන්න හෝ පහත ප්‍රශ්න වලින් එකක් තෝරන්න'
            : 'Click microphone to speak in Sinhala / English, or tap a quick prompt below'
        )}
        {state === 'listening' && (!liveTranscript && 'Listening... speak clearly into your microphone')}
        {state === 'transcribing' && 'Transcribing your voice...'}
        {state === 'searching' && 'Cross-database retrieval & neural RAG reasoning...'}
        {state === 'speaking' && 'Speaking answer... click mic anytime to interrupt'}
      </p>

      {/* Clickable Quick Prompts Starter Chips */}
      {state === 'idle' && (
        <div className="w-full flex flex-wrap items-center justify-center gap-2 pt-1">
          {quickPrompts.map((p, idx) => (
            <button
              key={idx}
              onClick={() => processInstantTextQuery(p.query)}
              className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-amber-500/15 border border-white/10 hover:border-amber-500/40 text-slate-300 hover:text-amber-200 text-xs transition-all flex items-center gap-1.5 shadow-sm active:scale-95"
            >
              <MessageSquarePlus className="w-3.5 h-3.5 text-amber-400" />
              <span>{p.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* Error notification banner */}
      {errorMessage && (
        <div className="w-full p-3.5 rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-center gap-2.5 text-rose-300 text-xs">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Live AI Spoken Response Card with Controls */}
      {(currentQuery || currentResponse) && (
        <div className="w-full flex flex-col gap-3 mt-1 pt-4 border-t border-white/10">
          {currentQuery && (
            <div className="p-3.5 rounded-2xl bg-black/40 border border-white/10">
              <span className="text-[10px] font-bold tracking-wider text-cyan-400 uppercase block mb-1">
                You Spoke (Voice Input)
              </span>
              <p className="text-sm text-slate-200 font-semibold">{currentQuery}</p>
            </div>
          )}

          {currentResponse && (() => {
            const { cleanText, chartData } = parseChartDataFromResponse(currentResponse);
            return (
              <div className="p-4 rounded-2xl bg-amber-500/5 border border-amber-500/25 flex flex-col gap-3">
                <div className="flex items-center justify-between border-b border-amber-500/15 pb-2.5">
                  <span className="text-[10px] font-bold tracking-wider text-amber-400 uppercase flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5" /> AI Spoken Output
                  </span>

                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => copyToClipboard(cleanText)}
                      className="px-2 py-1 rounded-lg bg-black/40 hover:bg-black/60 text-slate-300 text-[11px] font-medium border border-white/10 flex items-center gap-1 transition-all"
                      title="Copy response text"
                    >
                      {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copied ? 'Copied' : 'Copy'}</span>
                    </button>

                    {state === 'speaking' ? (
                      <button
                        onClick={stopSpeaking}
                        className="px-2.5 py-1 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/40 text-[11px] font-bold flex items-center gap-1 transition-all"
                      >
                        <VolumeX className="w-3.5 h-3.5" />
                        <span>Stop</span>
                      </button>
                    ) : (
                      <button
                        onClick={() => speakTextWithBrowserTTS(cleanText)}
                        className="px-2.5 py-1 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/40 text-[11px] font-bold flex items-center gap-1 transition-all"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>Replay</span>
                      </button>
                    )}
                  </div>
                </div>

                <p className="text-sm text-slate-100 font-normal leading-relaxed">{cleanText}</p>

                {chartData && (
                  <div className="pt-2">
                    <DynamicChart chartData={chartData} />
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
};

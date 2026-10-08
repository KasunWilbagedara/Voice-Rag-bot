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
  Gauge,
  UserCheck,
} from 'lucide-react';
import { AudioVisualizer } from './AudioVisualizer';
import { DynamicChart, parseChartDataFromResponse } from './DynamicChart';
import { FormattedResponse } from './FormattedResponse';

interface VoiceInterfaceProps {
  apiKey?: string;
  voice?: string;
  onVoiceChange?: (voice: string) => void;
  model?: string;
  provider?: string;
  baseUrl?: string;
  language?: string;
  sessionId?: string;
  backendMode?: 'pure' | 'tools';
  onLanguageChange?: (lang: string) => void;
  onQueryComplete?: (data: {
    userQuery: string;
    aiResponse: string;
    retrievedChunks: any[];
  }) => void;
}

type VoiceState = 'idle' | 'listening' | 'transcribing' | 'searching' | 'speaking';

interface LatencyMetrics {
  stt?: number;
  rag?: number;
  tts?: number;
  total?: number;
}

export const VoiceInterface: React.FC<VoiceInterfaceProps> = ({
  apiKey,
  voice = 'thilini',
  onVoiceChange,
  model = 'gemini-3.5-flash-lite',
  provider = 'gemini',
  baseUrl = '',
  language = 'si',
  sessionId = 'default_user',
  backendMode = 'pure',
  onLanguageChange,
  onQueryComplete,
}) => {
  const [state, setState] = useState<VoiceState>('idle');
  const [isHandsFree, setIsHandsFree] = useState(false);
  const [currentQuery, setCurrentQuery] = useState('');
  const [currentResponse, setCurrentResponse] = useState('');
  const [voiceSpokenText, setVoiceSpokenText] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Speed and Voice Persona controls
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1.0);
  const [latencyMetrics, setLatencyMetrics] = useState<LatencyMetrics | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const recognitionRef = useRef<any>(null);
  const vadTimerRef = useRef<NodeJS.Timeout | null>(null);

  const [useInstantMode, setUseInstantMode] = useState<boolean>(true);
  const [liveTranscript, setLiveTranscript] = useState<string>('');

  // Default active voice persona
  const activeVoice = voice || (language === 'si' ? 'thilini' : 'ava');

  const handleVoiceSelect = (v: string) => {
    if (onVoiceChange) {
      onVoiceChange(v);
    }
  };

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
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
    };
  }, []);

  const playServerTTS = async (textToSpeak: string, customSpeed?: number) => {
    try {
      setState('speaking');
      const speedToUse = customSpeed || playbackSpeed;
      const res = await fetch('/api/tts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-backend-mode': backendMode,
        },
        body: JSON.stringify({
          text: textToSpeak,
          voice: activeVoice,
          apiKey,
          language,
          speed: speedToUse,
        }),
      });

      if (!res.ok) throw new Error('TTS fetch failed');

      const audioBlob = await res.blob();
      const audioUrl = URL.createObjectURL(audioBlob);

      if (audioPlayerRef.current) {
        audioPlayerRef.current.src = audioUrl;
        audioPlayerRef.current.playbackRate = 1.0;
        audioPlayerRef.current.onended = () => {
          setState('idle');
          if (isHandsFree) {
            setTimeout(() => startRecording(), 600);
          }
        };
        await audioPlayerRef.current.play();
      } else {
        const audio = new Audio(audioUrl);
        audio.playbackRate = 1.0;
        audio.onended = () => {
          setState('idle');
          if (isHandsFree) {
            setTimeout(() => startRecording(), 600);
          }
        };
        await audio.play();
      }
    } catch (err) {
      console.error('Server Neural TTS Error:', err);
      setState('idle');
    }
  };

  const processInstantTextQuery = async (queryText: string) => {
    if (!queryText || !queryText.trim()) return;

    try {
      setState('searching');
      setCurrentQuery(queryText);
      setLatencyMetrics(null);

      const t0 = performance.now();
      const res = await fetch('/api/rag', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-backend-mode': backendMode,
        },
        body: JSON.stringify({
          query: queryText,
          apiKey,
          model: model || 'gemini-3.5-flash-lite',
          provider,
          baseUrl,
          language,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'RAG Query failed');

      const ragTime = Number(((performance.now() - t0) / 1000).toFixed(2));
      setCurrentResponse(data.answer);

      // Clean spoken sentence for TTS
      const spokenSummary = extractSpokenSummary(data.answer);
      setVoiceSpokenText(spokenSummary);

      if (onQueryComplete) {
        onQueryComplete({
          userQuery: queryText,
          aiResponse: data.answer,
          retrievedChunks: data.retrievedChunks || [],
        });
      }

      // Synthesize neural voice
      const t1 = performance.now();
      await playServerTTS(spokenSummary || data.answer);
      const ttsTime = Number(((performance.now() - t1) / 1000).toFixed(2));

      setLatencyMetrics({
        rag: ragTime,
        tts: ttsTime,
        total: Number((ragTime + ttsTime).toFixed(2)),
      });
    } catch (err: any) {
      console.error('Instant RAG Error:', err);
      setErrorMessage(err.message || 'Error processing query');
      setState('idle');
    }
  };

  const extractSpokenSummary = (text: string): string => {
    if (!text) return '';
    return text
      .replace(/```[\s\S]*?```/g, '')
      .replace(/\[\s*Source\s*\d+[^\]]*\]/gi, '')
      .replace(/\[\d+\]/g, '')
      .replace(/[*#\`_~>]/g, '')
      .replace(/\|[^\n]+\|/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  };

  const startRecording = async () => {
    setErrorMessage(null);
    setLiveTranscript('');
    audioChunksRef.current = [];

    // Stop existing audio if playing (barge-in)
    stopSpeaking();

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition && useInstantMode && language !== 'si') {
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
        recognition.lang = 'en-US';

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

    // High quality server transcription (handles Sinhala and English with zero browser dependency)
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

      mediaRecorder.start(150);
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
      formData.append('voice', activeVoice);
      if (model) formData.append('model', model);
      if (provider) formData.append('provider', provider);
      if (baseUrl) formData.append('baseUrl', baseUrl);
      if (language) formData.append('language', language);
      formData.append('speed', playbackSpeed.toString());
      formData.append('sessionId', sessionId || 'default_user');

      const res = await fetch('/api/voice-pipeline', {
        method: 'POST',
        headers: {
          'x-backend-mode': backendMode,
        },
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Voice RAG pipeline failed');
      }

      setCurrentQuery(data.userQueryText);
      setCurrentResponse(data.aiResponseText);
      setVoiceSpokenText(data.voiceSpokenText || '');

      if (data.latency) {
        setLatencyMetrics(data.latency);
      }

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
          audioPlayerRef.current.playbackRate = 1.0;
          audioPlayerRef.current.onended = () => {
            setState('idle');
            if (isHandsFree) {
              setTimeout(() => startRecording(), 800);
            }
          };
          await audioPlayerRef.current.play();
        } else {
          await playServerTTS(data.voiceSpokenText || data.aiResponseText);
        }
      } else {
        await playServerTTS(data.voiceSpokenText || data.aiResponseText);
      }
    } catch (err: any) {
      console.error('Voice Processing Error:', err);
      setErrorMessage(err.message || 'Error processing voice query');
      setState('idle');
    }
  };

  const stopSpeaking = () => {
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

  const quickPrompts =
    language === 'si'
      ? [
          { label: 'ORD-9021 ඇණවුමේ තත්වය?', query: 'ORD-9021 ඇණවුමේ තත්වය කුමක්ද?' },
          { label: 'Amara Perera ගේ විස්තර කියන්න', query: 'Amara Perera ගේ පාරිභෝගික විස්තර කියන්න' },
          { label: 'STU1042 ශිෂ්‍යයාගේ GPA එක කීයද?', query: 'STU1042 ශිෂ්‍යයාගේ GPA සහ දෙපාර්තමේන්තුව කුමක්ද?' },
        ]
      : [
          { label: 'Status of Order ORD-9021?', query: 'What is the status of order ORD-9021?' },
          { label: 'Customer details for Amara Perera', query: 'Show customer details for Amara Perera' },
          { label: 'What is the official refund policy?', query: 'What is the official refund policy for subscriptions?' },
        ];

  return (
    <div className="w-full ios-glass-card p-5 md:p-8 flex flex-col items-center gap-6 relative overflow-hidden shadow-2xl">
      <audio ref={audioPlayerRef} className="hidden" />

      {/* Top Header & Controls */}
      <div className="w-full flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
        {/* Status Indicator */}
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-3 w-3">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                state === 'listening'
                  ? 'bg-rose-500'
                  : state === 'speaking'
                  ? 'bg-emerald-400'
                  : state === 'searching' || state === 'transcribing'
                  ? 'bg-cyan-400'
                  : 'bg-slate-500'
              }`}
            />
            <span
              className={`relative inline-flex h-3 w-3 rounded-full ${
                state === 'listening'
                  ? 'bg-rose-500 shadow-[0_0_10px_#f43f5e]'
                  : state === 'speaking'
                  ? 'bg-emerald-400 shadow-[0_0_10px_#34d399]'
                  : state === 'searching' || state === 'transcribing'
                  ? 'bg-cyan-400 shadow-[0_0_10px_#38bdf8]'
                  : 'bg-slate-500'
              }`}
            />
          </span>
          <span className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
            {state === 'idle' && 'Ready for Speech'}
            {state === 'listening' && 'Listening to Voice...'}
            {state === 'transcribing' && 'Transcribing Speech (Fast STT)...'}
            {state === 'searching' && 'Retrieving Data & Neural RAG...'}
            {state === 'speaking' && 'Streaming Neural Human Voice...'}
          </span>
        </div>

        {/* Action Toggles & Voice Pickers */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Latency badge when available */}
          {latencyMetrics && latencyMetrics.total && (
            <div className="px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-[10px] font-mono font-bold flex items-center gap-1.5 shadow-sm">
              <Gauge className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
              <span>⚡ {latencyMetrics.total}s</span>
              {latencyMetrics.stt !== undefined && (
                <span className="text-emerald-600/80 dark:text-emerald-400/70 hidden sm:inline">
                  (STT {latencyMetrics.stt}s • RAG {latencyMetrics.rag}s • TTS {latencyMetrics.tts}s)
                </span>
              )}
            </div>
          )}

          {/* Voice Persona Selector Pill */}
          <div className="ios-segmented-capsule flex items-center text-[11px] font-bold">
            {language === 'si' ? (
              <>
                <button
                  onClick={() => handleVoiceSelect('thilini')}
                  className={`px-3 py-1 rounded-full transition-all flex items-center gap-1.5 ${
                    activeVoice.toLowerCase().includes('thilini') || activeVoice === 'nova'
                      ? 'ios-glass-pill-active font-extrabold'
                      : 'text-slate-700 dark:text-slate-400 hover:text-slate-950 dark:hover:text-slate-200 font-semibold'
                  }`}
                  title="Thilini: Studio Neural Female Voice"
                >
                  <span>👩</span>
                  <span>තිළිණි</span>
                  <span className="text-[9px] px-1 rounded-full bg-white/20 uppercase font-black tracking-wider">Pro</span>
                </button>
                <button
                  onClick={() => handleVoiceSelect('sameera')}
                  className={`px-3 py-1 rounded-full transition-all flex items-center gap-1.5 ${
                    activeVoice.toLowerCase().includes('sameera')
                      ? 'ios-glass-pill-active font-extrabold'
                      : 'text-slate-700 dark:text-slate-400 hover:text-slate-950 dark:hover:text-slate-200 font-semibold'
                  }`}
                  title="Sameera: Studio Neural Male Voice"
                >
                  <span>👨</span>
                  <span>සමීර</span>
                  <span className="text-[9px] px-1 rounded-full bg-white/20 uppercase font-black tracking-wider">Pro</span>
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => handleVoiceSelect('ava')}
                  className={`px-3 py-1 rounded-full transition-all flex items-center gap-1.5 ${
                    activeVoice.toLowerCase().includes('ava') || activeVoice === 'nova'
                      ? 'ios-glass-pill-active font-extrabold'
                      : 'text-slate-700 dark:text-slate-400 hover:text-slate-950 dark:hover:text-slate-200 font-semibold'
                  }`}
                  title="Ava: Expressive Multilingual Studio Female"
                >
                  <span>👩</span>
                  <span>Ava</span>
                  <span className="text-[9px] px-1 rounded-full bg-white/20 uppercase font-black tracking-wider">HD</span>
                </button>
                <button
                  onClick={() => handleVoiceSelect('andrew')}
                  className={`px-3 py-1 rounded-full transition-all flex items-center gap-1.5 ${
                    activeVoice.toLowerCase().includes('andrew')
                      ? 'ios-glass-pill-active font-extrabold'
                      : 'text-slate-700 dark:text-slate-400 hover:text-slate-950 dark:hover:text-slate-200 font-semibold'
                  }`}
                  title="Andrew: Expressive Multilingual Studio Male"
                >
                  <span>👨</span>
                  <span>Andrew</span>
                  <span className="text-[9px] px-1 rounded-full bg-white/20 uppercase font-black tracking-wider">HD</span>
                </button>
              </>
            )}
          </div>

          {/* Speed Selector Toggle */}
          <div className="ios-segmented-capsule flex items-center text-[10px] font-bold">
            {[1.0, 1.15, 1.25].map((s) => (
              <button
                key={s}
                onClick={() => setPlaybackSpeed(s)}
                className={`px-2.5 py-1 rounded-full transition-all ${
                  playbackSpeed === s
                    ? 'ios-glass-pill-active font-extrabold'
                    : 'text-slate-700 dark:text-slate-400 hover:text-slate-950 dark:hover:text-slate-200 font-semibold'
                }`}
                title={`Playback Speed ${s}x`}
              >
                {s}x
              </button>
            ))}
          </div>

          {/* Hands-Free Toggle */}
          <button
            onClick={() => setIsHandsFree(!isHandsFree)}
            className={`px-3 py-1.5 rounded-full text-[11px] font-bold tracking-wide transition-all flex items-center gap-1.5 border ${
              isHandsFree
                ? 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border-emerald-500/40 shadow-[0_0_15px_rgba(16,185,129,0.25)]'
                : 'bg-white dark:bg-white/5 text-slate-700 dark:text-slate-400 border-slate-200 dark:border-white/10 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-50 dark:hover:bg-white/10 shadow-sm'
            }`}
            title="Hands-free automatically listens again after speaking"
          >
            <Zap className={`w-3.5 h-3.5 ${isHandsFree ? 'text-emerald-600 dark:text-emerald-400 animate-pulse' : 'text-slate-400 dark:text-slate-500'}`} />
            <span className="hidden sm:inline">{isHandsFree ? 'Hands-Free ON' : 'Hands-Free'}</span>
          </button>
        </div>
      </div>

      {/* Reactive Soundwave Canvas */}
      <AudioVisualizer isActive={state !== 'idle'} mode={state} />

      {/* Center Interactive Mic Orb (iOS 27 Siri / Apple Intelligence Liquid Glass) */}
      <div className="relative my-3 flex flex-col items-center">
        {/* Concentric Ambient Light Rings */}
        {state === 'listening' && (
          <>
            <div className="absolute -inset-10 rounded-full border border-rose-500/30 animate-ping opacity-35 pointer-events-none" />
            <div className="absolute -inset-6 rounded-full bg-rose-500/25 blur-2xl pointer-events-none" />
          </>
        )}
        {state === 'speaking' && (
          <>
            <div className="absolute -inset-10 rounded-full border border-emerald-400/30 animate-ping opacity-35 pointer-events-none" />
            <div className="absolute -inset-6 rounded-full bg-emerald-500/25 blur-2xl pointer-events-none" />
          </>
        )}
        {state === 'searching' && (
          <div className="absolute -inset-6 rounded-full bg-cyan-500/25 blur-2xl pointer-events-none animate-pulse" />
        )}

        <button
          onClick={toggleMic}
          disabled={state === 'transcribing' || state === 'searching'}
          className={`ios-voice-orb ${
            state === 'listening'
              ? 'ios-voice-orb-listening'
              : state === 'speaking'
              ? 'ios-voice-orb-speaking'
              : ''
          }`}
          title={state === 'listening' ? 'Click to stop listening' : state === 'speaking' ? 'Click to interrupt & speak' : 'Click to start voice query'}
        >
          {state === 'transcribing' || state === 'searching' ? (
            <Loader2 className="w-10 h-10 animate-spin text-white drop-shadow-md" />
          ) : state === 'listening' ? (
            <MicOff className="w-10 h-10 animate-pulse text-white drop-shadow-md" />
          ) : state === 'speaking' ? (
            <Volume2 className="w-10 h-10 animate-bounce text-white drop-shadow-md" />
          ) : (
            <Mic className="w-10 h-10 text-white drop-shadow-[0_2px_8px_rgba(0,0,0,0.5)]" />
          )}
        </button>

        {/* Live Speech Recognition Bubble */}
        {state === 'listening' && liveTranscript && (
          <div className="mt-4 px-4 py-2 rounded-full bg-slate-900/70 border border-white/20 text-rose-200 text-xs font-medium max-w-md text-center animate-fade-in shadow-2xl backdrop-blur-xl flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping shrink-0" />
            <span className="italic">"{liveTranscript}"</span>
          </div>
        )}
      </div>

      {/* Instructions / Prompt Guidance */}
      <p className="text-xs md:text-sm font-semibold text-slate-800 dark:text-slate-200 text-center max-w-md leading-relaxed">
        {state === 'idle' &&
          (language === 'si'
            ? 'කතා කිරීමට මයික්‍රෆෝනය ඔබන්න හෝ පහත ප්‍රශ්න වලින් එකක් තෝරන්න'
            : 'Tap the glass orb to speak in Sinhala / English, or choose a prompt below')}
        {state === 'listening' && !liveTranscript && 'Listening... speak naturally into your microphone'}
        {state === 'transcribing' && 'Transcribing speech with Google AI...'}
        {state === 'searching' && 'Synthesizing knowledge context & reasoning...'}
        {state === 'speaking' && 'Streaming Google Gemini Actor voice... tap orb to pause'}
      </p>

      {/* Clickable Quick Prompts Starter Chips */}
      {state === 'idle' && (
        <div className="w-full flex flex-wrap items-center justify-center gap-2 pt-1">
          {quickPrompts.map((p, idx) => (
            <button
              key={idx}
              onClick={() => processInstantTextQuery(p.query)}
              className="ios-glass-pill px-3.5 py-1.5 text-slate-800 dark:text-slate-300 hover:text-sky-600 dark:hover:text-white text-xs font-semibold flex items-center gap-2 active:scale-95 shadow-sm"
            >
              <MessageSquarePlus className="w-3.5 h-3.5 text-sky-600 dark:text-cyan-400" />
              <span>{p.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* Error notification banner */}
      {errorMessage && (
        <div className="w-full p-3.5 rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-center gap-2.5 text-rose-300 text-xs shadow-lg">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Live AI Spoken Response Card with Controls */}
      {(currentQuery || currentResponse) && (
        <div className="w-full flex flex-col gap-3 mt-1 pt-4 border-t border-white/10">
          {currentQuery && (
            <div className="p-3.5 rounded-2xl bg-black/40 border border-white/10 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-bold tracking-wider text-cyan-400 uppercase block mb-1">
                  You Spoke (Voice Input)
                </span>
                <p className="text-sm text-slate-200 font-semibold">{currentQuery}</p>
              </div>
              <span className="text-xs text-slate-400 bg-white/5 px-2 py-1 rounded-lg border border-white/10">
                {language === 'si' ? '🇱🇰 සිංහල' : '🇬🇧 English'}
              </span>
            </div>
          )}

          {currentResponse && (() => {
            const { cleanText, chartData } = parseChartDataFromResponse(currentResponse);
            return (
              <div className="p-5 rounded-3xl bg-slate-900/60 border border-white/15 backdrop-blur-2xl flex flex-col gap-3.5 shadow-2xl">
                <div className="flex items-center justify-between border-b border-white/10 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold tracking-wider text-cyan-400 uppercase flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-cyan-400" /> AI Response
                    </span>
                    <span className="text-[10px] text-slate-300 bg-white/5 px-2.5 py-0.5 rounded-full border border-white/10 flex items-center gap-1 font-medium">
                      <UserCheck className="w-3 h-3 text-cyan-400" />
                      {activeVoice.charAt(0).toUpperCase() + activeVoice.slice(1)} Actor Voice
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => copyToClipboard(cleanText)}
                      className="px-3 py-1 rounded-full ios-glass-pill text-slate-300 hover:text-white text-[11px] font-medium flex items-center gap-1 transition-all"
                      title="Copy response text"
                    >
                      {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copied ? 'Copied' : 'Copy'}</span>
                    </button>

                    {state === 'speaking' ? (
                      <button
                        onClick={stopSpeaking}
                        className="px-3 py-1 rounded-full bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-400/40 text-[11px] font-bold flex items-center gap-1 transition-all shadow-[0_0_15px_rgba(244,63,94,0.3)]"
                      >
                        <VolumeX className="w-3.5 h-3.5" />
                        <span>Stop</span>
                      </button>
                    ) : (
                      <button
                        onClick={() => playServerTTS(voiceSpokenText || cleanText)}
                        className="px-3 py-1 rounded-full bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-200 border border-cyan-400/40 text-[11px] font-bold flex items-center gap-1.5 transition-all shadow-[0_0_15px_rgba(56,189,248,0.25)]"
                      >
                        <RotateCcw className="w-3.5 h-3.5 text-cyan-300" />
                        <span>Replay Voice</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Spoken Audio Highlight Pill */}
                {voiceSpokenText && (
                  <div className="p-3.5 rounded-2xl bg-white/[0.04] border border-white/12 backdrop-blur-xl flex items-start gap-3 text-slate-200 text-xs shadow-lg">
                    <div className="w-6 h-6 rounded-full bg-cyan-500/20 border border-cyan-400/30 flex items-center justify-center shrink-0 mt-0.5">
                      <Volume2 className="w-3.5 h-3.5 text-cyan-300" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-1.5 mb-1">
                        <span className="font-bold text-cyan-300 tracking-wide uppercase text-[10px]">Spoken Voice Answer</span>
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                      </div>
                      <p className="italic text-slate-300 font-medium leading-relaxed">"{voiceSpokenText}"</p>
                    </div>
                  </div>
                )}

                {/* Full Rich Text Display */}
                <div className="text-sm text-slate-100 font-normal leading-relaxed">
                  <FormattedResponse text={cleanText} />
                </div>

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
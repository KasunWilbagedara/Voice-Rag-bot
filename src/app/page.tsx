'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Mic,
  Database,
  Settings,
  Layers,
  Sparkles,
  Send,
  MessageSquare,
  Volume2,
  FileText,
  Brain,
  Globe,
  Download,
  Trash2,
  Copy,
  Check,
  RotateCcw,
  Bot,
  User,
  ArrowRight,
  Terminal,
  Sun,
  Moon,
} from 'lucide-react';
import { VoiceInterface } from '@/components/VoiceInterface';
import { DocumentManager } from '@/components/DocumentManager';
import { DatabaseManager } from '@/components/DatabaseManager';
import { ContextDrawer } from '@/components/ContextDrawer';
import { SettingsModal } from '@/components/SettingsModal';
import { MemoryModal } from '@/components/MemoryModal';
import { DynamicChart, parseChartDataFromResponse } from '@/components/DynamicChart';
import { FormattedResponse } from '@/components/FormattedResponse';

interface ChatMessage {
  id: string;
  userQuery: string;
  aiResponse: string;
  retrievedChunks: any[];
  timestamp: string;
  language: string;
  mode?: 'voice' | 'text';
}

export default function Home() {
  const [apiKey, setApiKey] = useState<string>('');
  const [voice, setVoice] = useState<string>('thilini');
  const [model, setModel] = useState<string>('gemini-3.5-flash-lite');
  const [provider, setProvider] = useState<string>('gemini');
  const [baseUrl, setBaseUrl] = useState<string>('');
  const [language, setLanguage] = useState<string>('si'); // Default Sinhala 'si'

  // Dedicated Backend Separation:
  // 'pure': Pure Document RAG & AI Only on Port 8000 (No Tools)
  // 'tools': RAG + Multi-DB SQL + Live Tools on Port 8001
  const [backendMode, setBackendMode] = useState<'pure' | 'tools'>('pure');
  const [backendStatus, setBackendStatus] = useState<{
    pureRag?: { online: boolean; latencyMs?: number; error?: string };
    toolsRag?: { online: boolean; latencyMs?: number; error?: string };
  } | null>(null);

  const [activeRightTab, setActiveRightTab] = useState<'databases' | 'documents'>('documents');

  const [textInput, setTextInput] = useState<string>('');
  const [isSubmittingText, setIsSubmittingText] = useState<boolean>(false);

  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [activeContextChunks, setActiveContextChunks] = useState<any[]>([]);
  const [activeQueryForContext, setActiveQueryForContext] = useState<string>('');
  const [isContextDrawerOpen, setIsContextDrawerOpen] = useState<boolean>(false);

  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [isMemoryOpen, setIsMemoryOpen] = useState<boolean>(false);
  const [memoryCount, setMemoryCount] = useState<number>(0);
  const [isLightMode, setIsLightMode] = useState<boolean>(true);
  const sessionId = 'default_user';

  useEffect(() => {
    document.documentElement.classList.toggle('light', isLightMode);
    document.documentElement.classList.toggle('dark', !isLightMode);
  }, [isLightMode]);

  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);

  // Poll backend health status
  const checkBackendStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/backend-status');
      if (res.ok) {
        const data = await res.json();
        setBackendStatus(data);
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    checkBackendStatus();
    const interval = setInterval(checkBackendStatus, 6000);
    return () => clearInterval(interval);
  }, [checkBackendStatus]);

  const refreshMemoryCount = useCallback(async () => {
    if (backendMode !== 'tools') {
      setMemoryCount(0);
      return;
    }
    try {
      const res = await fetch(`/api/memory?sessionId=${encodeURIComponent(sessionId)}`);
      if (res.ok) {
        const data = await res.json();
        setMemoryCount(data.count ?? (data.memories ? data.memories.length : 0));
      }
    } catch (e) {
      console.error('Error fetching memory count:', e);
    }
  }, [sessionId, backendMode]);

  // Restore chat history and memory count on page load and on backend mode switch
  useEffect(() => {
    const initHistoryAndMemory = async () => {
      try {
        const [histRes, memRes] = await Promise.all([
          fetch('/api/history?limit=30', {
            headers: { 'x-backend-mode': backendMode },
          }),
          backendMode === 'tools'
            ? fetch(`/api/memory?sessionId=${encodeURIComponent(sessionId)}`)
            : Promise.resolve(null),
        ]);

        if (histRes.ok) {
          const histData = await histRes.json();
          if (histData.history) {
            const loaded: ChatMessage[] = histData.history.map((h: any) => ({
              id: h.id.toString(),
              userQuery: h.userQuery,
              aiResponse: h.aiResponse,
              retrievedChunks: h.retrievedChunks || [],
              timestamp: h.createdAt
                ? new Date(h.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                : 'Saved',
              language: 'si',
              mode: 'voice',
            }));
            setChatHistory(loaded);
            if (loaded[0]) {
              setActiveContextChunks(loaded[0].retrievedChunks || []);
              setActiveQueryForContext(loaded[0].userQuery);
            } else {
              setActiveContextChunks([]);
              setActiveQueryForContext('');
            }
          }
        }

        if (memRes && memRes.ok) {
          const memData = await memRes.json();
          setMemoryCount(memData.count ?? (memData.memories ? memData.memories.length : 0));
        } else if (backendMode === 'pure') {
          setMemoryCount(0);
        }
      } catch (e) {
        console.error('Initialization error:', e);
      }
    };

    initHistoryAndMemory();
  }, [sessionId, backendMode]);

  const handleQueryCompleted = (data: {
    userQuery: string;
    aiResponse: string;
    retrievedChunks: any[];
  }) => {
    const newMessage: ChatMessage = {
      id: Date.now().toString(),
      userQuery: data.userQuery,
      aiResponse: data.aiResponse,
      retrievedChunks: data.retrievedChunks || [],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      language: language,
      mode: 'voice',
    };

    setChatHistory((prev) => [newMessage, ...prev]);
    setActiveContextChunks(data.retrievedChunks || []);
    setActiveQueryForContext(data.userQuery);
    refreshMemoryCount();
  };

  const handleTextSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!textInput.trim() || isSubmittingText) return;

    const query = textInput.trim();
    setTextInput('');
    setIsSubmittingText(true);

    const historyFormatted = chatHistory.slice().reverse().map((m) => [
      { role: 'user', content: m.userQuery },
      { role: 'assistant', content: m.aiResponse },
    ]).flat();

    try {
      const res = await fetch('/api/rag', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-backend-mode': backendMode,
        },
        body: JSON.stringify({
          query,
          apiKey,
          model,
          provider,
          baseUrl,
          language,
          conversationHistory: historyFormatted,
          sessionId,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'RAG Query failed');

      const newMessage: ChatMessage = {
        id: Date.now().toString(),
        userQuery: query,
        aiResponse: data.answer,
        retrievedChunks: data.retrievedChunks || [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        language: language,
        mode: 'text',
      };

      setChatHistory((prev) => [newMessage, ...prev]);
      setActiveContextChunks(data.retrievedChunks || []);
      setActiveQueryForContext(query);
      refreshMemoryCount();

      // Play natural neural audio via TTS for the complete answer (no truncation)
      const cleanSpoken = (data.voiceSpokenText || data.answer || '')
        .replace(/```[\s\S]*?```/g, '')
        .replace(/\[[^\]]*\]/g, '')
        .replace(/[*#\`_~>]/g, '')
        .replace(/\|[^\n]+\|/g, '')
        .replace(/\s+/g, ' ')
        .trim();

      const ttsRes = await fetch('/api/tts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-backend-mode': backendMode,
        },
        body: JSON.stringify({ text: cleanSpoken, voice, apiKey, language, speed: 1.0 }),
      });

      if (ttsRes.ok) {
        const audioBlob = await ttsRes.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        await audio.play();
      }
    } catch (err: any) {
      console.error('Text RAG Error:', err);
    } finally {
      setIsSubmittingText(false);
    }
  };

  const replayMessageAudio = async (text: string) => {
    try {
      const cleanSpoken = text
        .replace(/```[\s\S]*?```/g, '')
        .replace(/\[[^\]]*\]/g, '')
        .replace(/[*#\`_~>]/g, '')
        .replace(/\|[^\n]+\|/g, '')
        .replace(/\s+/g, ' ')
        .trim();

      const ttsRes = await fetch('/api/tts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-backend-mode': backendMode,
        },
        body: JSON.stringify({ text: cleanSpoken, voice, apiKey, language, speed: 1.0 }),
      });
      if (ttsRes.ok) {
        const audioBlob = await ttsRes.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        await audio.play();
      }
    } catch (e) {
      console.error('Replay error:', e);
    }
  };

  const copyMessage = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedMsgId(id);
    setTimeout(() => setCopiedMsgId(null), 2000);
  };

  const exportChatTranscript = () => {
    if (chatHistory.length === 0) return;
    const header = 'Timestamp,Language,Mode,User Query,AI Response\n';
    const rows = chatHistory.map((m) =>
      `"${m.timestamp}","${m.language}","${m.mode || 'voice'}","${m.userQuery.replace(/"/g, '""')}","${m.aiResponse.replace(/"/g, '""')}"`
    ).join('\n');
    const csvContent = 'data:text/csv;charset=utf-8,' + header + rows;
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `voice_rag_transcript_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const clearChatHistory = async () => {
    if (chatHistory.length === 0) return;
    if (confirm('Clear all conversation history?')) {
      try {
        await fetch('/api/history', {
          method: 'DELETE',
          headers: { 'x-backend-mode': backendMode },
        });
      } catch (e) {
        console.error('Failed to clear database history:', e);
      }
      setChatHistory([]);
      setActiveContextChunks([]);
      setActiveQueryForContext('');
    }
  };

  const openContextForMessage = (msg: ChatMessage) => {
    setActiveContextChunks(msg.retrievedChunks || []);
    setActiveQueryForContext(msg.userQuery);
    setIsContextDrawerOpen(true);
  };

  return (
    <main className={`min-h-screen flex flex-col font-sans transition-colors duration-500 selection:bg-cyan-500 selection:text-white relative overflow-hidden ${
      isLightMode 
        ? 'bg-gradient-to-b from-[#f8fafc] via-[#f1f5f9] to-[#e2e8f0] text-slate-900' 
        : 'bg-[#030712] text-slate-100'
    }`}>
      {/* Ambient iOS 27 Liquid Mesh Background Orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div className={`ambient-orb-1 absolute top-[-10%] left-[-10%] w-[55vw] h-[55vw] rounded-full blur-[130px] transition-colors duration-700 ${
          isLightMode ? 'bg-sky-400/25' : 'bg-cyan-500/12'
        }`} />
        <div className={`ambient-orb-2 absolute top-[20%] right-[-10%] w-[50vw] h-[50vw] rounded-full blur-[140px] transition-colors duration-700 ${
          isLightMode ? 'bg-indigo-400/20' : 'bg-indigo-500/14'
        }`} />
        <div className={`ambient-orb-1 absolute bottom-[-10%] left-[20%] w-[60vw] h-[60vw] rounded-full blur-[150px] transition-colors duration-700 ${
          isLightMode ? 'bg-rose-300/25' : 'bg-fuchsia-500/10'
        }`} />
        <div className={`ambient-orb-2 absolute bottom-[20%] right-[10%] w-[45vw] h-[45vw] rounded-full blur-[130px] transition-colors duration-700 ${
          isLightMode ? 'bg-teal-300/20' : 'bg-emerald-500/10'
        }`} />
        <div className={`absolute inset-0 pointer-events-none transition-colors duration-500 ${
          isLightMode 
            ? 'bg-gradient-to-b from-white/40 via-transparent to-white/70' 
            : 'bg-gradient-to-b from-transparent via-[#030712]/30 to-[#030712]/85'
        }`} />
      </div>

      {/* Top Navbar */}
      <header className={`sticky top-0 z-40 w-full border-b px-4 md:px-8 py-3 flex flex-wrap items-center justify-between gap-3 backdrop-blur-2xl transition-all duration-300 ${
        isLightMode 
          ? 'bg-white/75 border-slate-200/80 shadow-sm shadow-slate-200/50' 
          : 'bg-slate-950/40 border-white/10 shadow-2xl'
      }`}>
        {/* Brand & Status */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-cyan-500 via-indigo-600 to-rose-500 p-[1px] shadow-lg flex items-center justify-center">
            <div className={`w-full h-full rounded-2xl flex items-center justify-center backdrop-blur-md ${
              isLightMode ? 'bg-white/90' : 'bg-slate-950/80'
            }`}>
              <Brain className="w-5 h-5 text-cyan-500 stroke-[2.5]" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className={`text-sm md:text-base font-extrabold tracking-tight ${isLightMode ? 'text-slate-900' : 'text-white'}`}>
                Voice-RAG Bot
              </h1>
              <span className={`text-[10px] px-2.5 py-0.5 rounded-full font-bold flex items-center gap-1 border ${
                backendMode === 'pure'
                  ? 'bg-cyan-500/15 text-cyan-600 dark:text-cyan-300 border-cyan-400/30'
                  : 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-300 border-indigo-400/30'
              }`}>
                <span>{backendMode === 'pure' ? '⚡' : '🛠️'}</span>
                <span>{backendMode === 'pure' ? 'Pure RAG (Docs Only)' : 'RAG + Tools & DBs'}</span>
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 flex items-center gap-1.5 font-medium flex-wrap">
              <span className="text-emerald-500 dark:text-emerald-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Active
              </span>
              <span className="text-slate-400 dark:text-slate-600">•</span>
              <span className="text-slate-600 dark:text-slate-300 font-mono text-[10px] uppercase">
                {provider}: {model}
              </span>
              <span className="text-slate-400 dark:text-slate-600">•</span>
              <span className="font-mono text-[10px] text-cyan-600 dark:text-cyan-300 font-semibold">
                Port {backendMode === 'pure' ? '8000' : '8001'}
              </span>
            </p>
          </div>
        </div>

        {/* Center: Dual Backend Mode Switcher (iOS Segmented Capsule) */}
        <div className="ios-segmented-capsule flex items-center">
          <button
            onClick={() => {
              setBackendMode('pure');
              setActiveRightTab('documents');
            }}
            className={`px-3.5 py-1.5 rounded-full text-xs font-bold transition-all flex items-center gap-1.5 ${
              backendMode === 'pure'
                ? 'ios-glass-pill-emerald shadow-lg'
                : 'text-slate-700 dark:text-slate-400 hover:text-slate-950 dark:hover:text-slate-200'
            }`}
            title="Pure Document RAG & AI Only on Port 8000 (No Tools)"
          >
            <Sparkles className="w-3.5 h-3.5 text-cyan-300" />
            <span>Pure RAG (:8000)</span>
          </button>
          <button
            onClick={() => setBackendMode('tools')}
            className={`px-3.5 py-1.5 rounded-full text-xs font-bold transition-all flex items-center gap-1.5 ${
              backendMode === 'tools'
                ? 'ios-glass-pill-active shadow-lg'
                : 'text-slate-700 dark:text-slate-400 hover:text-slate-950 dark:hover:text-slate-200'
            }`}
            title="RAG + Live Tools + SQL on Port 8001"
          >
            <Database className="w-3.5 h-3.5 text-pink-300" />
            <span>RAG + Tools (:8001)</span>
          </button>
        </div>

        {/* Right Header Navigation & Actions */}
        <div className="flex items-center gap-2">
          {/* Language Switcher */}
          <div className="ios-segmented-capsule hidden sm:flex items-center text-xs font-bold">
            <button
              onClick={() => setLanguage('si')}
              className={`px-3 py-1 rounded-full transition-all flex items-center gap-1.5 ${
                language === 'si'
                  ? 'ios-glass-pill-active font-extrabold'
                  : 'text-slate-700 dark:text-slate-400 hover:text-slate-950 dark:hover:text-slate-200'
              }`}
            >
              <span>🇱🇰</span>
              <span>සිංහල</span>
            </button>
            <button
              onClick={() => setLanguage('en')}
              className={`px-3 py-1 rounded-full transition-all flex items-center gap-1.5 ${
                language === 'en'
                  ? 'ios-glass-pill-active font-extrabold'
                  : 'text-slate-700 dark:text-slate-400 hover:text-slate-950 dark:hover:text-slate-200'
              }`}
            >
              <span>🇬🇧</span>
              <span>English</span>
            </button>
          </div>

          {/* Context Sources Button */}
          <button
            onClick={() => setIsContextDrawerOpen(true)}
            className="ios-glass-pill px-3 py-1.5 text-slate-800 dark:text-slate-300 hover:text-sky-600 dark:hover:text-white text-xs font-semibold flex items-center gap-2 active:scale-95 shadow-sm"
            title="Inspect retrieved RAG context sources"
          >
            <Layers className="w-4 h-4 text-sky-600 dark:text-cyan-400" />
            <span className="hidden sm:inline">Context Sources</span>
            {activeContextChunks.length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-sky-500/15 dark:bg-cyan-500/20 text-sky-700 dark:text-cyan-300 border border-sky-400/40 dark:border-cyan-400/40 text-[10px] font-extrabold">
                {activeContextChunks.length}
              </span>
            )}
          </button>

          {/* Memory Modal Button (Available in tools mode) */}
          {backendMode === 'tools' && (
            <button
              onClick={() => setIsMemoryOpen(true)}
              className="ios-glass-pill px-3 py-1.5 text-slate-800 dark:text-slate-300 hover:text-pink-600 dark:hover:text-white text-xs font-semibold flex items-center gap-2 active:scale-95 shadow-sm"
              title="Inspect and manage persistent long-term memories"
            >
              <Brain className="w-4 h-4 text-pink-500 dark:text-pink-400" />
              <span className="hidden sm:inline">Memories</span>
              <span className="px-1.5 py-0.2 rounded-full bg-pink-500/15 dark:bg-pink-500/20 text-pink-700 dark:text-pink-300 border border-pink-400/40 text-[10px] font-extrabold">
                {memoryCount}
              </span>
            </button>
          )}

          <button
            onClick={() => setIsLightMode((prev) => !prev)}
            className="ios-glass-pill p-2 text-slate-700 dark:text-slate-300 hover:text-sky-600 dark:hover:text-white transition-all shadow-sm active:scale-95"
            title={isLightMode ? 'Switch to dark mode' : 'Switch to light mode'}
            aria-label={isLightMode ? 'Switch to dark mode' : 'Switch to light mode'}
          >
            {isLightMode ? <Moon className="w-4 h-4 text-sky-600" /> : <Sun className="w-4 h-4 text-amber-300" />}
          </button>

          {/* Settings Button */}
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="ios-glass-pill p-2 text-slate-700 dark:text-slate-300 hover:text-sky-600 dark:hover:text-white transition-all shadow-sm active:scale-95"
            title="Configure LLM & Voice Persona"
          >
            <Settings className="w-4 h-4 text-sky-600 dark:text-cyan-400" />
          </button>
        </div>
      </header>

      {/* Backend Status & Mode Strip */}
      <div
        className={`w-full border-b px-4 md:px-8 py-2 text-xs flex flex-wrap items-center justify-between gap-3 backdrop-blur-xl transition-colors ${
          isLightMode
            ? 'bg-white/60 border-slate-200/80 text-slate-700 shadow-sm'
            : 'bg-slate-950/30 border-white/5 text-slate-300'
        }`}
      >
        <div className="flex items-center gap-2">
          {backendMode === 'pure' ? (
            <>
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <span className={`font-semibold ${isLightMode ? 'text-sky-700' : 'text-cyan-300'}`}>
                ⚡ Pure RAG Mode (:8000):
              </span>
              <span className={isLightMode ? 'text-slate-600' : 'text-slate-400'}>
                Strict Document RAG & Voice AI. External tools, weather, calculator, & SQL disabled.
              </span>
            </>
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
              <span className={`font-semibold ${isLightMode ? 'text-indigo-700' : 'text-indigo-300'}`}>
                🛠️ RAG + Tools Mode (:8001):
              </span>
              <span className={isLightMode ? 'text-slate-600' : 'text-slate-400'}>
                Full Agent with Document RAG, Multi-DB Text-to-SQL, Live Weather, Calculator & Memory.
              </span>
            </>
          )}
        </div>

        {/* Live Backend Heartbeats */}
        <div className="flex items-center gap-3 text-[11px] font-mono">
          <div
            className={`flex items-center gap-1.5 px-3 py-1 rounded-full border transition-colors ${
              isLightMode
                ? 'bg-white/80 border-slate-200/90 text-slate-700 shadow-sm'
                : 'bg-white/5 border-white/10 text-slate-400'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                backendStatus?.pureRag?.online
                  ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]'
                  : isLightMode
                  ? 'bg-slate-300'
                  : 'bg-slate-600'
              }`}
            />
            <span className={isLightMode ? 'text-slate-600 font-medium' : 'text-slate-400'}>Pure :8000</span>
            <span
              className={
                backendStatus?.pureRag?.online
                  ? isLightMode
                    ? 'text-emerald-600 font-bold'
                    : 'text-emerald-400 font-bold'
                  : isLightMode
                  ? 'text-slate-400'
                  : 'text-slate-500'
              }
            >
              {backendStatus?.pureRag?.online ? `${backendStatus.pureRag.latencyMs ?? 10}ms` : 'Offline'}
            </span>
          </div>
          <div
            className={`flex items-center gap-1.5 px-3 py-1 rounded-full border transition-colors ${
              isLightMode
                ? 'bg-white/80 border-slate-200/90 text-slate-700 shadow-sm'
                : 'bg-white/5 border-white/10 text-slate-400'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                backendStatus?.toolsRag?.online
                  ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]'
                  : isLightMode
                  ? 'bg-slate-300'
                  : 'bg-slate-600'
              }`}
            />
            <span className={isLightMode ? 'text-slate-600 font-medium' : 'text-slate-400'}>Tools :8001</span>
            <span
              className={
                backendStatus?.toolsRag?.online
                  ? isLightMode
                    ? 'text-emerald-600 font-bold'
                    : 'text-emerald-400 font-bold'
                  : isLightMode
                  ? 'text-slate-400'
                  : 'text-slate-500'
              }
            >
              {backendStatus?.toolsRag?.online ? `${backendStatus.toolsRag.latencyMs ?? 10}ms` : 'Offline'}
            </span>
          </div>
        </div>
      </div>

      {/* Main Content Dashboard */}
      <div className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 relative z-10">
        {/* Left Column: Hero Voice Interface & Conversation (6 Cols) */}
        <div className="lg:col-span-6 flex flex-col gap-6">
          {/* Main Hero Voice Interaction Hub */}
          <VoiceInterface
            apiKey={apiKey}
            voice={voice}
            onVoiceChange={setVoice}
            model={model}
            provider={provider}
            baseUrl={baseUrl}
            language={language}
            sessionId={sessionId}
            backendMode={backendMode}
            onLanguageChange={setLanguage}
            onQueryComplete={handleQueryCompleted}
          />

          {/* Floating iOS 27 Glass Prompt Bar */}
          <form
            onSubmit={handleTextSubmit}
            className="ios-glass-input-bar px-4 py-2.5 flex items-center gap-3 w-full shadow-lg"
          >
            <div className="text-sky-600 dark:text-cyan-400 shrink-0">
              <Terminal className="w-4 h-4" />
            </div>
            <input
              type="text"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder={
                language === 'si'
                  ? 'සිංහලෙන් හෝ ඉංග්‍රීසියෙන් ප්‍රශ්නයක් ලියන්න... (Orders, DB or docs)'
                  : 'Type a question in English or Sinhala...'
              }
              className="flex-1 bg-transparent px-2 py-1 text-xs md:text-sm text-slate-900 dark:text-slate-100 placeholder-slate-500 dark:placeholder-slate-400/70 focus:outline-none font-semibold"
            />
            <button
              type="submit"
              disabled={isSubmittingText || !textInput.trim()}
              className="w-8 h-8 rounded-full bg-sky-600 hover:bg-sky-500 dark:bg-cyan-500 dark:hover:bg-cyan-400 disabled:opacity-30 text-white dark:text-slate-950 flex items-center justify-center transition-all shadow-md active:scale-95 shrink-0"
              title="Submit query"
            >
              <Send className="w-3.5 h-3.5 stroke-[2.5]" />
            </button>
          </form>

          {/* Conversation History Timeline */}
          <div className="ios-glass-card p-5 md:p-6 flex flex-col gap-4 flex-1 shadow-2xl">
            {/* Feed Header */}
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-cyan-400" />
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Conversation Feed & Multimodal Insights
                </h3>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-slate-400">
                  {chatHistory.length} {chatHistory.length === 1 ? 'turn' : 'turns'}
                </span>

                {chatHistory.length > 0 && (
                  <>
                    <button
                      onClick={exportChatTranscript}
                      className="px-2.5 py-1 rounded-full ios-glass-pill text-cyan-300 hover:text-white text-[10px] font-bold flex items-center gap-1 transition-all"
                      title="Export chat transcript to CSV"
                    >
                      <Download className="w-3 h-3" />
                      <span>Export</span>
                    </button>

                    <button
                      onClick={clearChatHistory}
                      className="p-1 rounded-xl text-slate-400 hover:text-rose-400 hover:bg-rose-500/15 transition-all"
                      title="Clear chat feed"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Message List */}
            {chatHistory.length === 0 ? (
              <div className="py-12 text-center flex flex-col items-center justify-center gap-3 border border-slate-200 dark:border-white/5 bg-slate-50/80 dark:bg-white/[0.02] rounded-2xl p-6">
                <div className="w-10 h-10 rounded-2xl bg-sky-500/15 dark:bg-cyan-500/10 border border-sky-400/30 dark:border-cyan-400/20 flex items-center justify-center text-sky-600 dark:text-cyan-300 shadow-sm">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div className="text-center">
                  <p className="text-xs font-bold text-slate-900 dark:text-slate-300">No conversation turns yet</p>
                  <p className="text-[11px] text-slate-600 dark:text-slate-400 mt-1 max-w-sm font-semibold">
                    Press the radiant glass orb or select a quick query to interact in Sinhala or English with real-time multi-DB RAG!
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-4 max-h-[460px] overflow-y-auto pr-1 custom-scrollbar">
                {chatHistory.map((msg) => {
                  const { cleanText, chartData } = parseChartDataFromResponse(msg.aiResponse);
                  const isCopied = copiedMsgId === msg.id;

                  return (
                    <div
                      key={msg.id}
                      className="ios-glass-card-interactive p-4.5 rounded-2xl flex flex-col gap-3.5 hover:border-cyan-400/30 transition-all shadow-md"
                    >
                      {/* User Query Bubble */}
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-2.5 min-w-0">
                          <div className="w-7 h-7 rounded-xl bg-cyan-500/15 text-cyan-300 border border-cyan-400/30 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                            {msg.mode === 'text' ? <Terminal className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
                          </div>
                          <div>
                            <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider block">
                              User ({msg.language === 'si' ? '🇱🇰 Sinhala' : '🇬🇧 English'})
                            </span>
                            <p className="text-xs md:text-sm font-semibold text-slate-100 leading-snug mt-0.5">
                              {msg.userQuery}
                            </p>
                          </div>
                        </div>
                        <span className="text-[10px] text-slate-400 shrink-0 font-mono">
                          {msg.timestamp}
                        </span>
                      </div>

                      {/* AI Response Bubble */}
                      <div className="flex items-start gap-2.5 pl-3 border-l-2 border-cyan-400/60">
                        <div className="w-7 h-7 rounded-xl bg-indigo-500/20 text-indigo-300 border border-indigo-400/30 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                          <Bot className="w-3.5 h-3.5" />
                        </div>
                        <div className="flex-1 min-w-0 flex flex-col gap-2">
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-bold text-cyan-300 uppercase tracking-wider">
                              AI Voice RAG Answer
                            </span>

                            <div className="flex items-center gap-1.5">
                              <button
                                onClick={() => copyMessage(msg.id, cleanText)}
                                className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
                                title="Copy answer"
                              >
                                {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                              </button>

                              <button
                                onClick={() => replayMessageAudio(cleanText)}
                                className="p-1 text-slate-400 hover:text-cyan-300 rounded-lg hover:bg-white/5 transition-colors"
                                title="Replay voice audio"
                              >
                                <Volume2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>

                          <div className="text-xs md:text-sm text-slate-200 font-normal break-words">
                            <FormattedResponse text={cleanText} />
                          </div>

                          {/* Dynamic Recharts Chart if response contains chart data */}
                          {chartData && (
                            <div className="pt-1">
                              <DynamicChart chartData={chartData} />
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Grounded Chunks / Context Footer */}
                      {msg.retrievedChunks && msg.retrievedChunks.length > 0 && (
                        <div className="flex items-center justify-between pt-2.5 border-t border-white/5 text-xs">
                          <span className="text-[11px] text-slate-400 flex items-center gap-1.5">
                            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                            <span>Grounded in {msg.retrievedChunks.length} sources (DB SQL & Docs)</span>
                          </span>

                          <button
                            onClick={() => openContextForMessage(msg)}
                            className="text-[11px] text-cyan-300 hover:text-white font-bold hover:underline flex items-center gap-1 transition-colors"
                          >
                            <span>Inspect Evidence</span>
                            <ArrowRight className="w-3 h-3" />
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Multi-Database & Knowledge Base Workspace (6 Cols) */}
        <div className="lg:col-span-6 flex flex-col gap-6">
          {backendMode === 'pure' ? (
            <div className="ios-glass-card p-5 md:p-6 flex flex-col gap-4 shadow-2xl">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div className="flex items-center gap-2">
                  <FileText className="w-5 h-5 text-cyan-400" />
                  <h3 className="text-sm font-bold text-slate-100">Pure Document Knowledge Base (Port 8000)</h3>
                </div>
                <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-cyan-500/15 text-cyan-300 font-bold border border-cyan-400/30">
                  Docs & Vector Only
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Upload PDFs, Word DOCX, TXT, CSV, or Markdown. Queries are grounded strictly in document contents with zero external tools.
              </p>
              <DocumentManager apiKey={apiKey} backendMode={backendMode} />
            </div>
          ) : (
            <>
              {/* Tab Switcher (iOS Segmented Capsule) */}
              <div className="ios-segmented-capsule p-1 flex items-center gap-1">
                <button
                  onClick={() => setActiveRightTab('databases')}
                  className={`flex-1 py-2 px-4 rounded-full text-xs font-bold flex items-center justify-center gap-2 transition-all ${
                    activeRightTab === 'databases'
                      ? 'ios-glass-pill-active font-extrabold'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <Database className="w-4 h-4 text-cyan-400" />
                  <span>Multi-Database Hub</span>
                </button>
                <button
                  onClick={() => setActiveRightTab('documents')}
                  className={`flex-1 py-2 px-4 rounded-full text-xs font-bold flex items-center justify-center gap-2 transition-all ${
                    activeRightTab === 'documents'
                      ? 'ios-glass-pill-active font-extrabold'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <FileText className="w-4 h-4 text-indigo-400" />
                  <span>Document Knowledge</span>
                </button>
              </div>

              {/* Active Workspace View */}
              {activeRightTab === 'databases' ? (
                <DatabaseManager />
              ) : (
                <DocumentManager apiKey={apiKey} backendMode={backendMode} />
              )}
            </>
          )}

          {/* Sample Customer Support Queries Card */}
          <div className="ios-glass-card p-5 md:p-6 flex flex-col gap-3.5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-2.5">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-200 uppercase tracking-wider">
                <Globe className="w-4 h-4 text-cyan-400" />
                <span>Sample {backendMode === 'pure' ? 'Document RAG' : 'RAG + Tools'} Queries</span>
              </div>
              <span className="text-[10px] text-slate-400 font-mono">1-Click Try</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {(backendMode === 'pure' ? [
                { label: '🇱🇰 SLT Enterprise සේවා මොනවාද?', query: 'SLT Enterprise ලබා දෙන ප්‍රධාන සේවා මොනවාද?' },
                { label: '🇬🇧 Akaza Cloud capabilities & SLA?', query: 'What are the key capabilities and uptime SLA of Akaza Cloud?' },
                { label: '🇱🇰 පාරිභෝගික සහය අංක සහ ඊමේල් මොනවාද?', query: 'Enterprise පාරිභෝගික සහය අංක සහ ඊමේල් ලිපිනය කුමක්ද?' },
                { label: '🇬🇧 Optical Fiber bandwidth options?', query: 'What optical fiber connectivity bandwidth is offered?' },
              ] : [
                { label: '🇱🇰 ORD-9021 ඇණවුමේ තත්වය කුමක්ද?', query: 'ORD-9021 ඇණවුමේ තත්වය කුමක්ද?' },
                { label: '🇱🇰 Amara Perera ගේ විස්තර කියන්න', query: 'Amara Perera ගේ පාරිභෝගික විස්තර කියන්න' },
                { label: '🇬🇧 Live weather in Colombo?', query: 'What is the live current weather and temperature in Colombo?' },
                { label: '🇱🇰 STU1042 ශිෂ්‍යයාගේ GPA කුමක්ද?', query: 'STU1042 ශිෂ්‍යයාගේ GPA සහ දෙපාර්තමේන්තුව කුමක්ද?' },
              ]).map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => setTextInput(q.query)}
                  className="p-3.5 rounded-2xl ios-glass-card-interactive text-left text-xs text-slate-800 dark:text-slate-300 hover:text-sky-600 dark:hover:text-white font-semibold transition-all flex items-center justify-between group shadow-sm active:scale-98"
                >
                  <span className="truncate pr-2">{q.label}</span>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400 group-hover:text-sky-600 dark:group-hover:text-cyan-300 shrink-0 transition-transform group-hover:translate-x-0.5" />
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Context Viewer Drawer */}
      <ContextDrawer
        isOpen={isContextDrawerOpen}
        onClose={() => setIsContextDrawerOpen(false)}
        chunks={activeContextChunks}
        userQuery={activeQueryForContext}
      />

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        apiKey={apiKey}
        setApiKey={setApiKey}
        voice={voice}
        setVoice={setVoice}
        model={model}
        setModel={setModel}
        provider={provider}
        setProvider={setProvider}
        baseUrl={baseUrl}
        setBaseUrl={setBaseUrl}
      />

      {/* Persistent Memory Management Modal */}
      <MemoryModal
        isOpen={isMemoryOpen}
        onClose={() => setIsMemoryOpen(false)}
        sessionId={sessionId}
        onMemoriesUpdated={setMemoryCount}
      />
    </main>
  );
}
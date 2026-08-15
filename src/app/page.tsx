'use client';

import React, { useState } from 'react';
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
} from 'lucide-react';
import { VoiceInterface } from '@/components/VoiceInterface';
import { DocumentManager } from '@/components/DocumentManager';
import { DatabaseManager } from '@/components/DatabaseManager';
import { ContextDrawer } from '@/components/ContextDrawer';
import { SettingsModal } from '@/components/SettingsModal';
import { DynamicChart, parseChartDataFromResponse } from '@/components/DynamicChart';

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
  const [voice, setVoice] = useState<string>('nova');
  const [model, setModel] = useState<string>('gemini-3.5-flash');
  const [provider, setProvider] = useState<string>('gemini');
  const [baseUrl, setBaseUrl] = useState<string>('');
  const [language, setLanguage] = useState<string>('si'); // Default Sinhala 'si'

  const [activeRightTab, setActiveRightTab] = useState<'databases' | 'documents'>('databases');

  const [textInput, setTextInput] = useState<string>('');
  const [isSubmittingText, setIsSubmittingText] = useState<boolean>(false);

  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [activeContextChunks, setActiveContextChunks] = useState<any[]>([]);
  const [activeQueryForContext, setActiveQueryForContext] = useState<string>('');
  const [isContextDrawerOpen, setIsContextDrawerOpen] = useState<boolean>(false);

  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);

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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          apiKey,
          model,
          provider,
          baseUrl,
          language,
          conversationHistory: historyFormatted,
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

      // Play audio via TTS in Sinhala or English
      const ttsRes = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: data.answer, voice, apiKey, language }),
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
      const ttsRes = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice, apiKey, language }),
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

  const clearChatHistory = () => {
    if (chatHistory.length === 0) return;
    if (confirm('Clear all conversation history?')) {
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
    <main className="min-h-screen bg-[#070a13] text-slate-100 flex flex-col font-sans selection:bg-amber-500 selection:text-slate-950">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 w-full glass-panel border-b border-white/10 px-4 md:px-8 py-3.5 flex items-center justify-between shadow-2xl backdrop-blur-xl">
        {/* Brand & Status */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-amber-500 to-orange-600 flex items-center justify-center shadow-lg shadow-amber-500/20 border border-amber-400/40">
            <Brain className="w-5 h-5 text-slate-950 stroke-[2.5]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm md:text-base font-extrabold text-slate-100 tracking-tight">
                Voice-RAG Bot
              </h1>
              <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 font-bold flex items-center gap-1">
                <span>🇱🇰</span>
                <span>Sinhala (සිංහල) & Multi-DB RAG</span>
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5 flex items-center gap-1.5 font-medium">
              <span className="text-emerald-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Active
              </span>
              <span className="text-slate-600">•</span>
              <span className="text-slate-300 font-mono text-[10px] uppercase">
                {provider}: {model}
              </span>
              <span className="text-slate-600">•</span>
              <span className="text-amber-400/90 font-mono text-[10px]">pgvector / SQL RAG</span>
            </p>
          </div>
        </div>

        {/* Right Header Navigation & Actions */}
        <div className="flex items-center gap-2">
          {/* Language Switcher */}
          <div className="hidden sm:flex items-center p-0.5 bg-black/40 border border-white/10 rounded-xl text-xs font-bold">
            <button
              onClick={() => setLanguage('si')}
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
              onClick={() => setLanguage('en')}
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

          {/* Context Sources Button */}
          <button
            onClick={() => setIsContextDrawerOpen(true)}
            className="px-3 py-2 rounded-xl bg-black/40 hover:bg-black/60 border border-white/10 text-slate-300 hover:text-white text-xs font-semibold flex items-center gap-2 transition-all shadow-sm active:scale-95"
            title="Inspect retrieved RAG context sources"
          >
            <Layers className="w-4 h-4 text-violet-400" />
            <span className="hidden sm:inline">Context Sources</span>
            {activeContextChunks.length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-violet-500/20 text-violet-300 border border-violet-500/40 text-[10px] font-extrabold">
                {activeContextChunks.length}
              </span>
            )}
          </button>

          {/* Settings Button */}
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="p-2 rounded-xl bg-black/40 hover:bg-black/60 border border-white/10 text-slate-300 hover:text-white transition-all shadow-sm active:scale-95"
            title="Configure LLM & Voice Persona"
          >
            <Settings className="w-4 h-4 text-amber-400" />
          </button>
        </div>
      </header>

      {/* Main Content Dashboard */}
      <div className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Hero Voice Interface & Conversation (6 Cols) */}
        <div className="lg:col-span-6 flex flex-col gap-6">
          {/* Main Hero Voice Interaction Hub */}
          <VoiceInterface
            apiKey={apiKey}
            voice={voice}
            model={model}
            provider={provider}
            baseUrl={baseUrl}
            language={language}
            onLanguageChange={setLanguage}
            onQueryComplete={handleQueryCompleted}
          />

          {/* Text Input Fallback Bar */}
          <form
            onSubmit={handleTextSubmit}
            className="glass-panel p-2 rounded-2xl flex items-center gap-2 border border-white/10 focus-within:border-amber-500/60 transition-all shadow-xl"
          >
            <div className="pl-3 text-slate-500">
              <Terminal className="w-4 h-4 text-amber-400" />
            </div>
            <input
              type="text"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder={
                language === 'si'
                  ? 'සිංහලෙන් හෝ ඉංග්‍රීසියෙන් ප්‍රශ්නයක් ලියන්න... (Orders, DB or docs)'
                  : 'Type a query or DB ask in English or Sinhala...'
              }
              className="flex-1 bg-transparent px-2 py-2 text-xs md:text-sm text-slate-100 placeholder-slate-500 focus:outline-none font-medium"
            />
            <button
              type="submit"
              disabled={isSubmittingText || !textInput.trim()}
              className="p-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 disabled:opacity-40 text-slate-950 font-bold transition-all shadow-md shadow-amber-500/20 active:scale-95"
              title="Submit query"
            >
              <Send className="w-4 h-4 stroke-[2.5]" />
            </button>
          </form>

          {/* Conversation History Timeline */}
          <div className="glass-panel rounded-3xl p-5 md:p-6 flex flex-col gap-4 flex-1 shadow-2xl border border-white/10">
            {/* Feed Header */}
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-amber-400" />
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
                      className="px-2 py-1 rounded-lg bg-black/40 hover:bg-amber-500/15 border border-white/10 text-amber-300 text-[10px] font-bold flex items-center gap-1 transition-all"
                      title="Export chat transcript to CSV"
                    >
                      <Download className="w-3 h-3" />
                      <span>Export</span>
                    </button>

                    <button
                      onClick={clearChatHistory}
                      className="p-1 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/15 transition-all"
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
              <div className="py-12 text-center flex flex-col items-center justify-center gap-3 border border-white/5 bg-black/20 rounded-2xl p-6">
                <div className="w-10 h-10 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div className="text-center">
                  <p className="text-xs font-bold text-slate-300">No conversation turns yet</p>
                  <p className="text-[11px] text-slate-500 mt-1 max-w-sm">
                    Press the microphone button or select a quick query to interact in Sinhala or English with real-time multi-DB RAG!
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
                      className="p-4 rounded-2xl bg-black/40 border border-white/10 flex flex-col gap-3.5 hover:border-amber-500/30 transition-all shadow-md"
                    >
                      {/* User Query Bubble */}
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-2.5 min-w-0">
                          <div className="w-7 h-7 rounded-xl bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
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
                        <span className="text-[10px] text-slate-500 shrink-0 font-mono">
                          {msg.timestamp}
                        </span>
                      </div>

                      {/* AI Response Bubble */}
                      <div className="flex items-start gap-2.5 pl-2 border-l-2 border-amber-500/60">
                        <div className="w-7 h-7 rounded-xl bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                          <Bot className="w-3.5 h-3.5" />
                        </div>
                        <div className="flex-1 min-w-0 flex flex-col gap-2">
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider">
                              AI Voice RAG Answer
                            </span>

                            <div className="flex items-center gap-1.5">
                              <button
                                onClick={() => copyMessage(msg.id, cleanText)}
                                className="p-1 text-slate-400 hover:text-white rounded hover:bg-white/5 transition-colors"
                                title="Copy answer"
                              >
                                {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                              </button>

                              <button
                                onClick={() => replayMessageAudio(cleanText)}
                                className="p-1 text-slate-400 hover:text-amber-300 rounded hover:bg-white/5 transition-colors"
                                title="Replay voice audio"
                              >
                                <Volume2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>

                          <p className="text-xs md:text-sm text-slate-200 font-normal leading-relaxed whitespace-pre-wrap">
                            {cleanText}
                          </p>

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
                            <Sparkles className="w-3.5 h-3.5 text-violet-400" />
                            <span>Grounded in {msg.retrievedChunks.length} sources (DB SQL & Docs)</span>
                          </span>

                          <button
                            onClick={() => openContextForMessage(msg)}
                            className="text-[11px] text-amber-400 hover:text-amber-300 font-bold hover:underline flex items-center gap-1 transition-colors"
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
          {/* Tab Switcher */}
          <div className="glass-panel p-1.5 rounded-2xl flex items-center gap-2 border border-white/10 shadow-xl">
            <button
              onClick={() => setActiveRightTab('databases')}
              className={`flex-1 py-2.5 px-4 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-all ${
                activeRightTab === 'databases'
                  ? 'bg-amber-500 text-slate-950 font-extrabold shadow-md shadow-amber-500/20'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <Database className="w-4 h-4" />
              <span>Multi-Database Hub</span>
            </button>
            <button
              onClick={() => setActiveRightTab('documents')}
              className={`flex-1 py-2.5 px-4 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-all ${
                activeRightTab === 'documents'
                  ? 'bg-amber-500 text-slate-950 font-extrabold shadow-md shadow-amber-500/20'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>Document Knowledge</span>
            </button>
          </div>

          {/* Active Workspace View */}
          {activeRightTab === 'databases' ? (
            <DatabaseManager />
          ) : (
            <DocumentManager apiKey={apiKey} />
          )}

          {/* Sample Customer Support Queries Card */}
          <div className="glass-panel rounded-3xl p-5 md:p-6 flex flex-col gap-3.5 border border-amber-500/20 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-2.5">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-200 uppercase tracking-wider">
                <Globe className="w-4 h-4 text-amber-400" />
                <span>Sample Cross-Lingual Customer Queries</span>
              </div>
              <span className="text-[10px] text-slate-500 font-mono">1-Click Try</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {[
                { label: '🇱🇰 ORD-9021 ඇණවුමේ තත්වය කුමක්ද?', query: 'ORD-9021 ඇණවුමේ තත්වය කුමක්ද?' },
                { label: '🇱🇰 Amara Perera ගේ විස්තර කියන්න', query: 'Amara Perera ගේ පාරිභෝගික විස්තර කියන්න' },
                { label: '🇬🇧 Refund policy for subscriptions?', query: 'What is the official refund policy for subscriptions?' },
                { label: '🇱🇰 STU1042 ශිෂ්‍යයාගේ GPA කුමක්ද?', query: 'STU1042 ශිෂ්‍යයාගේ GPA සහ දෙපාර්තමේන්තුව කුමක්ද?' },
              ].map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => setTextInput(q.query)}
                  className="p-3 rounded-2xl bg-black/30 hover:bg-amber-500/15 border border-white/5 hover:border-amber-500/30 text-left text-xs text-slate-300 hover:text-amber-200 transition-all flex items-center justify-between group shadow-sm active:scale-98"
                >
                  <span className="truncate pr-2 font-medium">{q.label}</span>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-amber-400 shrink-0 transition-transform group-hover:translate-x-0.5" />
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
    </main>
  );
}

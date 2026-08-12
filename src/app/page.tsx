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
}

export default function Home() {
  const [apiKey, setApiKey] = useState<string>('');
  const [voice, setVoice] = useState<string>('nova');
  const [model, setModel] = useState<string>('gemini-2.0-flash');
  const [provider, setProvider] = useState<string>('gemini');
  const [baseUrl, setBaseUrl] = useState<string>('');
  const [language, setLanguage] = useState<string>('si'); // Default Sinhala 'si'

  const [activeRightTab, setActiveRightTab] = useState<'documents' | 'databases'>('databases');

  const [textInput, setTextInput] = useState<string>('');
  const [isSubmittingText, setIsSubmittingText] = useState<boolean>(false);

  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [activeContextChunks, setActiveContextChunks] = useState<any[]>([]);
  const [activeQueryForContext, setActiveQueryForContext] = useState<string>('');
  const [isContextDrawerOpen, setIsContextDrawerOpen] = useState<boolean>(false);

  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

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

      handleQueryCompleted({
        userQuery: query,
        aiResponse: data.answer,
        retrievedChunks: data.retrievedChunks || [],
      });

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

  const exportChatTranscript = () => {
    if (chatHistory.length === 0) return;
    const header = 'Timestamp,Language,User Query,AI Response\n';
    const rows = chatHistory.map((m) =>
      `"${m.timestamp}","${m.language}","${m.userQuery.replace(/"/g, '""')}","${m.aiResponse.replace(/"/g, '""')}"`
    ).join('\n');
    const csvContent = 'data:text/csv;charset=utf-8,' + header + rows;
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `voice_rag_chat_transcript_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const openContextForMessage = (msg: ChatMessage) => {
    setActiveContextChunks(msg.retrievedChunks || []);
    setActiveQueryForContext(msg.userQuery);
    setIsContextDrawerOpen(true);
  };

  return (
    <main className="min-h-screen bg-[#090d16] text-gray-100 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 w-full glass-panel border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-amber-500 to-orange-600 flex items-center justify-center shadow-lg glow-blue">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-gray-100 leading-none">Customer Voice-RAG Bot</h1>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-950/80 text-amber-300 border border-amber-800/60 font-bold">
                🇱🇰 Sinhala (සිංහල) & Multi-DB RAG
              </span>
            </div>
            <p className="text-[11px] text-gray-400 mt-1 flex items-center gap-1.5">
              <span>Multi-Database + Multi-Document Voice Chatbot</span>
              <span className="text-gray-600">•</span>
              <span className="text-amber-400 font-mono">Postgres / SQLite / Vector RAG</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsContextDrawerOpen(true)}
            className="px-3 py-2 rounded-xl bg-gray-900 hover:bg-gray-800 border border-gray-800 text-gray-300 hover:text-white text-xs font-medium flex items-center gap-2 transition-all"
          >
            <Layers className="w-4 h-4 text-violet-400" />
            <span>Context Sources</span>
            {activeContextChunks.length > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-violet-950 text-violet-400 border border-violet-800/60 text-[10px] font-bold">
                {activeContextChunks.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setIsSettingsOpen(true)}
            className="p-2 rounded-xl bg-gray-900 hover:bg-gray-800 border border-gray-800 text-gray-300 hover:text-white transition-all"
            title="Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Main Content Layout */}
      <div className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Voice Interface & Chat (6 Cols) */}
        <div className="lg:col-span-6 flex flex-col gap-6">
          {/* Main Voice Interface */}
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

          {/* Text Input Fallback */}
          <form
            onSubmit={handleTextSubmit}
            className="glass-panel p-2 rounded-2xl flex items-center gap-2 border border-gray-800/80 focus-within:border-amber-500/60 transition-all"
          >
            <input
              type="text"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder={
                language === 'si'
                  ? 'සිංහලෙන් හෝ ඉංග්‍රීසියෙන් ප්‍රශ්නයක් යොමු කරන්න... (Customer order, DB query or doc ask)'
                  : 'Ask about customer orders, DB records or uploaded docs...'
              }
              className="flex-1 bg-transparent px-4 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none"
            />
            <button
              type="submit"
              disabled={isSubmittingText || !textInput.trim()}
              className="p-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>

          {/* Conversation History Timeline */}
          <div className="glass-panel rounded-3xl p-6 flex flex-col gap-4 flex-1">
            <div className="flex items-center justify-between pb-2 border-b border-gray-800">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-brand-400" />
                <h3 className="text-sm font-bold text-gray-200 uppercase tracking-wider">
                  Voice & Text Conversation History
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">{chatHistory.length} messages</span>
                {chatHistory.length > 0 && (
                  <button
                    onClick={exportChatTranscript}
                    className="px-2 py-1 rounded bg-gray-900 hover:bg-gray-800 border border-gray-700 text-amber-300 text-[10px] font-bold flex items-center gap-1 transition-all"
                  >
                    <Download className="w-3 h-3" />
                    <span>Export CSV</span>
                  </button>
                )}
              </div>
            </div>

            {chatHistory.length === 0 ? (
              <div className="py-12 text-center text-xs text-gray-500 italic">
                No conversations yet. Speak into the mic or type a query in Sinhala or English to start!
              </div>
            ) : (
              <div className="flex flex-col gap-4 max-h-[420px] overflow-y-auto pr-1">
                {chatHistory.map((msg) => {
                  const { cleanText, chartData } = parseChartDataFromResponse(msg.aiResponse);
                  return (
                    <div
                      key={msg.id}
                      className="p-4 rounded-2xl bg-gray-900/60 border border-gray-800 flex flex-col gap-3 hover:border-gray-700 transition-colors"
                    >
                      {/* User Query */}
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-2.5">
                          <div className="w-6 h-6 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800 flex items-center justify-center shrink-0 mt-0.5">
                            <Mic className="w-3.5 h-3.5" />
                          </div>
                          <p className="text-sm font-medium text-gray-200">{msg.userQuery}</p>
                        </div>
                        <span className="text-[10px] text-gray-500 shrink-0 font-mono">
                          {msg.timestamp}
                        </span>
                      </div>

                      {/* AI Response */}
                      <div className="flex items-start gap-2.5 pl-2 border-l-2 border-amber-500/60">
                        <div className="w-6 h-6 rounded-full bg-amber-950 text-amber-400 border border-amber-800 flex items-center justify-center shrink-0 mt-0.5">
                          <Volume2 className="w-3.5 h-3.5" />
                        </div>
                        <p className="text-sm text-gray-100 font-medium leading-relaxed">{cleanText}</p>
                      </div>

                      {/* Interactive Recharts Chart Component if requested */}
                      {chartData && (
                        <div className="pl-2">
                          <DynamicChart chartData={chartData} />
                        </div>
                      )}

                      {/* Chunk Match Footer */}
                      {msg.retrievedChunks && msg.retrievedChunks.length > 0 && (
                        <div className="flex items-center justify-between pt-2 border-t border-gray-800/60 text-xs">
                          <span className="text-[11px] text-gray-400 flex items-center gap-1">
                            <Sparkles className="w-3 h-3 text-violet-400" />
                            Grounded in {msg.retrievedChunks.length} sources (DB + Docs)
                          </span>
                          <button
                            onClick={() => openContextForMessage(msg)}
                            className="text-[11px] text-amber-400 hover:text-amber-300 font-medium hover:underline flex items-center gap-1"
                          >
                            Inspect Sources &rarr;
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

        {/* Right Column: Knowledge Base & Database Manager Tabs (6 Cols) */}
        <div className="lg:col-span-6 flex flex-col gap-6">
          {/* Tab Controls for Documents vs Databases */}
          <div className="glass-panel p-2 rounded-2xl flex items-center gap-2 border border-gray-800">
            <button
              onClick={() => setActiveRightTab('databases')}
              className={`flex-1 py-2 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-all ${
                activeRightTab === 'databases'
                  ? 'bg-amber-500 text-black shadow-md'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
            >
              <Database className="w-4 h-4" />
              <span>Multi-Database Manager</span>
            </button>
            <button
              onClick={() => setActiveRightTab('documents')}
              className={`flex-1 py-2 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-all ${
                activeRightTab === 'documents'
                  ? 'bg-amber-500 text-black shadow-md'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>Document Manager</span>
            </button>
          </div>

          {/* Active Manager View */}
          {activeRightTab === 'databases' ? (
            <DatabaseManager />
          ) : (
            <DocumentManager apiKey={apiKey} />
          )}

          {/* Sample Sinhala & English Customer Queries Box */}
          <div className="glass-panel rounded-3xl p-6 flex flex-col gap-3 border border-amber-900/30">
            <div className="flex items-center gap-2 text-sm font-bold text-gray-200 uppercase tracking-wider">
              <Globe className="w-4 h-4 text-amber-400" />
              <span>Sample Multi-DB Customer Support Queries</span>
            </div>

            <div className="flex flex-col gap-2">
              {[
                { label: 'ORD-9021 ඇණවුමේ තත්වය කුමක්ද?', query: 'ORD-9021 ඇණවුමේ තත්වය කුමක්ද?' },
                { label: 'Amara Perera ගේ පාරිභෝගික විස්තර කියන්න', query: 'Amara Perera ගේ පාරිභෝගික විස්තර කියන්න' },
                { label: 'What is the official refund policy for subscriptions?', query: 'What is the official refund policy for subscriptions?' },
                { label: 'STU1042 ශිෂ්‍යයාගේ GPA සහ දෙපාර්තමේන්තුව කුමක්ද?', query: 'STU1042 ශිෂ්‍යයාගේ GPA සහ දෙපාර්තමේන්තුව කුමක්ද?' },
              ].map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setTextInput(q.query);
                  }}
                  className="p-3 rounded-xl bg-gray-900/80 hover:bg-gray-800/80 border border-gray-800 text-left text-xs text-amber-200 hover:text-white transition-all flex items-center justify-between group"
                >
                  <span>"{q.label}"</span>
                  <span className="text-gray-500 group-hover:text-amber-400 transition-colors">&rarr;</span>
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

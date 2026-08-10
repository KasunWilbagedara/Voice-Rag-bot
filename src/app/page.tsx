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
  Brain,
  Globe,
  ShieldCheck,
  User,
} from 'lucide-react';
import { VoiceInterface } from '@/components/VoiceInterface';
import { DocumentManager } from '@/components/DocumentManager';
import { ContextDrawer } from '@/components/ContextDrawer';
import { SettingsModal } from '@/components/SettingsModal';

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
  const [model, setModel] = useState<string>('gpt-4o-mini');
  const [language, setLanguage] = useState<string>('si'); // Default Sinhala 'si'

  const [activeTab, setActiveTab] = useState<'user' | 'admin'>('user');

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

    try {
      const res = await fetch('/api/rag', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, apiKey, model, language }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'RAG Query failed');

      handleQueryCompleted({
        userQuery: query,
        aiResponse: data.answer,
        retrievedChunks: data.retrievedChunks || [],
      });

      // Play audio via TTS
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

  const openContextForMessage = (msg: ChatMessage) => {
    setActiveContextChunks(msg.retrievedChunks || []);
    setActiveQueryForContext(msg.userQuery);
    setIsContextDrawerOpen(true);
  };

  return (
    <main className="min-h-screen bg-black text-gray-900 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 w-full glass-panel border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-black flex items-center justify-center shadow-sm">
            <Brain className="w-5 h-5 text-emerald-500" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-black leading-none">Voice-RAG Bot</h1>
              <span className="text-[10px] px-2 py-0.5 rounded border border-gray-300 text-gray-600 font-bold uppercase tracking-wider">
                Sinhala Enabled
              </span>
            </div>
            <p className="text-[11px] text-gray-500 mt-1 flex items-center gap-1.5 font-mono">
              <span>STRICT DATA GROUNDING</span>
              <span className="text-gray-300">•</span>
              <span className="text-emerald-600">pgvector</span>
            </p>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center p-1 bg-gray-100 rounded border border-gray-200">
          <button
            onClick={() => setActiveTab('user')}
            className={`px-6 py-1.5 rounded text-xs font-bold uppercase tracking-widest flex items-center gap-2 transition-all ${
              activeTab === 'user' ? 'bg-black text-white' : 'text-gray-500 hover:text-black'
            }`}
          >
            <User className="w-4 h-4" />
            User
          </button>
          <button
            onClick={() => setActiveTab('admin')}
            className={`px-6 py-1.5 rounded text-xs font-bold uppercase tracking-widest flex items-center gap-2 transition-all ${
              activeTab === 'admin' ? 'bg-black text-white' : 'text-gray-500 hover:text-black'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            Admin
          </button>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsContextDrawerOpen(true)}
            className="px-3 py-2 rounded bg-white hover:bg-gray-50 border border-gray-200 text-gray-700 hover:text-black text-xs font-bold uppercase tracking-wider flex items-center gap-2 transition-all"
          >
            <Layers className="w-4 h-4 text-emerald-500" />
            <span>Context</span>
            {activeContextChunks.length > 0 && (
              <span className="px-1.5 py-0.5 rounded bg-gray-100 text-emerald-600 border border-gray-200 text-[10px]">
                {activeContextChunks.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setIsSettingsOpen(true)}
            className="p-2 rounded bg-white hover:bg-gray-50 border border-gray-200 text-gray-500 hover:text-black transition-all"
            title="Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Main Content Layout */}
      <div className="flex-1 max-w-5xl w-full mx-auto p-4 md:p-6 flex flex-col gap-6">
        
        {/* === USER TAB === */}
        {activeTab === 'user' && (
          <div className="flex flex-col gap-6 w-full animate-in fade-in zoom-in-95 duration-200">
            {/* Main Voice Interface */}
            <VoiceInterface
              apiKey={apiKey}
              voice={voice}
              model={model}
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
                    ? 'සිංහලෙන් ප්‍රශ්නයක් යොමු කරන්න... (Ask in Sinhala)'
                    : 'Type a question in English...'
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
            <div className="glass-panel rounded-3xl p-6 flex flex-col gap-4 w-full">
              <div className="flex items-center justify-between pb-2 border-b border-gray-800">
                <div className="flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-brand-400" />
                  <h3 className="text-sm font-bold text-gray-200 uppercase tracking-wider">
                    Conversation History
                  </h3>
                </div>
                <span className="text-xs text-gray-500">{chatHistory.length} messages</span>
              </div>

              {chatHistory.length === 0 ? (
                <div className="py-12 text-center text-xs text-gray-500 italic">
                  No conversations yet. Speak into the mic or type a query!
                </div>
              ) : (
                <div className="flex flex-col gap-4 max-h-[500px] overflow-y-auto pr-1">
                  {chatHistory.map((msg) => (
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
                        <p className="text-sm text-gray-100 font-medium leading-relaxed">{msg.aiResponse}</p>
                      </div>

                      {/* Chunk Match Footer */}
                      {msg.retrievedChunks && msg.retrievedChunks.length > 0 && (
                        <div className="flex items-center justify-between pt-2 border-t border-gray-800/60 text-xs">
                          <span className="text-[11px] text-gray-400 flex items-center gap-1">
                            <Sparkles className="w-3 h-3 text-violet-400" />
                            Grounded in {msg.retrievedChunks.length} chunks
                          </span>
                          <button
                            onClick={() => openContextForMessage(msg)}
                            className="text-[11px] text-amber-400 hover:text-amber-300 font-medium hover:underline flex items-center gap-1"
                          >
                            Inspect Source Data &rarr;
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* === ADMIN TAB === */}
        {activeTab === 'admin' && (
          <div className="flex flex-col gap-6 w-full animate-in fade-in zoom-in-95 duration-200">
            <div className="glass-panel rounded-3xl p-6 border border-violet-900/30">
              <div className="mb-4">
                <h2 className="text-xl font-bold text-gray-100 flex items-center gap-2">
                  <Database className="w-5 h-5 text-violet-400" />
                  Knowledge Base Administration
                </h2>
                <p className="text-sm text-gray-400 mt-1">
                  Upload databases (Excel/CSV), PDFs, and Documents. The AI will strictly restrict its answers to this data.
                </p>
              </div>
              
              {/* Knowledge Base Ingestion */}
              <DocumentManager apiKey={apiKey} />
            </div>

            {/* Sample Queries Box */}
            <div className="glass-panel rounded-3xl p-6 flex flex-col gap-3 border border-gray-800/80">
              <div className="flex items-center gap-2 text-sm font-bold text-gray-200 uppercase tracking-wider">
                <Globe className="w-4 h-4 text-amber-400" />
                <span>Test Strict Mode</span>
              </div>
              <p className="text-xs text-gray-400 mb-2">
                Click a query below while on the User Tab to verify the bot rejects questions outside the uploaded database.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {[
                  { label: 'Who is the President of the US?', query: 'Who is the President of the US?' },
                  { label: 'What is the capital of France?', query: 'What is the capital of France?' },
                  { label: 'මෙම ලේඛනයේ ප්‍රධාන කරුණු මොනවාද?', query: 'මෙම ලේඛනයේ ප්‍රධාන කරුණු මොනවාද?' },
                  { label: 'What document formats are supported?', query: 'What document formats are supported?' },
                ].map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setActiveTab('user');
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
        )}
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
      />
    </main>
  );
}

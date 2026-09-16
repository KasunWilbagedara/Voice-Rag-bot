'use client';

import React, { useState } from 'react';
import { X, Key, Settings, Volume2, Cpu, Save, Check, Globe, Server, ShieldCheck } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiKey: string;
  setApiKey: (key: string) => void;
  voice: string;
  setVoice: (voice: string) => void;
  model: string;
  setModel: (model: string) => void;
  provider: string;
  setProvider: (provider: string) => void;
  baseUrl: string;
  setBaseUrl: (url: string) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  apiKey,
  setApiKey,
  voice,
  setVoice,
  model,
  setModel,
  provider,
  setProvider,
  baseUrl,
  setBaseUrl,
}) => {
  const [localKey, setLocalKey] = useState(apiKey);
  const [localBaseUrl, setLocalBaseUrl] = useState(baseUrl);
  const [customModel, setCustomModel] = useState(model);
  const [isSaved, setIsSaved] = useState(false);

  if (!isOpen) return null;

  const handleSave = () => {
    setApiKey(localKey);
    setBaseUrl(localBaseUrl);
    setModel(customModel);
    setIsSaved(true);
    setTimeout(() => {
      setIsSaved(false);
      onClose();
    }, 700);
  };

  const handleProviderSelect = (p: string) => {
    setProvider(p);
    if (p === 'gemini') {
      setCustomModel('gemini-3.5-flash-lite');
    } else if (p === 'openai') {
      setCustomModel('gpt-4o-mini');
    } else if (p === 'groq') {
      setCustomModel('llama-3.3-70b-versatile');
      if (!localBaseUrl) setLocalBaseUrl('https://api.groq.com/openai/v1');
    } else if (p === 'ollama') {
      setCustomModel('llama3.2');
      if (!localBaseUrl) setLocalBaseUrl('http://localhost:11434/v1');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-md animate-fade-in p-4">
      <div className="w-full max-w-xl glass-panel bg-[#090d18] border border-white/15 rounded-3xl p-6 md:p-7 flex flex-col gap-5 relative shadow-2xl text-slate-100 max-h-[90vh] overflow-y-auto custom-scrollbar">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-cyan-400">
              <Settings className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100">LLM Provider & Voice Settings</h2>
              <p className="text-xs text-slate-400">Configure neural models, voices, and endpoints</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-xl bg-black/40 hover:bg-black/60 border border-white/10 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* AI Provider Selector */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <Globe className="w-3.5 h-3.5 text-cyan-400" />
            <span>Select LLM Provider</span>
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {[
              { id: 'gemini', label: 'Gemini', icon: '✨', sub: 'Recommended' },
              { id: 'openai', label: 'OpenAI', icon: '🧠', sub: 'GPT-4o' },
              { id: 'groq', label: 'Groq Cloud', icon: '⚡', sub: 'Ultra Fast' },
              { id: 'ollama', label: 'Local Ollama', icon: '🦙', sub: 'On-Device' },
            ].map((p) => (
              <button
                key={p.id}
                onClick={() => handleProviderSelect(p.id)}
                className={`py-2.5 px-3 rounded-2xl text-xs font-bold transition-all flex flex-col items-center gap-0.5 border ${
                  provider === p.id
                    ? 'bg-blue-600 text-white border-blue-400 shadow-lg shadow-blue-500/20 font-extrabold'
                    : 'bg-black/40 text-slate-400 border-white/5 hover:border-white/15 hover:text-white'
                }`}
              >
                <span className="text-sm">{p.icon}</span>
                <span>{p.label}</span>
                <span className={`text-[9px] ${provider === p.id ? 'text-cyan-200 font-semibold' : 'text-slate-500'}`}>
                  {p.sub}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* API Key Input */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <Key className="w-3.5 h-3.5 text-cyan-400" />
            <span>{provider.toUpperCase()} API Key</span>
          </label>

          <input
            type="password"
            value={localKey}
            onChange={(e) => setLocalKey(e.target.value)}
            placeholder={
              provider === 'gemini'
                ? 'AIzaSy... (or set via GEMINI_API_KEY in .env)'
                : provider === 'groq'
                ? 'gsk_... (or GROQ_API_KEY in .env)'
                : provider === 'ollama'
                ? 'Optional for local Ollama'
                : 'sk-proj-... (or OPENAI_API_KEY in .env)'
            }
            className="w-full px-4 py-2.5 rounded-xl bg-black/50 border border-white/10 focus:border-blue-500/60 focus:outline-none text-xs text-slate-100 font-mono transition-colors"
          />
          <div className="flex items-center gap-1 text-[10px] text-slate-500">
            <ShieldCheck className="w-3 h-3 text-emerald-400" />
            <span>Keys are stored in your secure browser session only.</span>
          </div>
        </div>

        {/* Custom Base URL (Ollama / OpenRouter / Custom Endpoints) */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <Server className="w-3.5 h-3.5 text-cyan-400" />
            <span>Custom API Base URL (Optional)</span>
          </label>
          <input
            type="text"
            value={localBaseUrl}
            onChange={(e) => setLocalBaseUrl(e.target.value)}
            placeholder="http://localhost:11434/v1 or https://openrouter.ai/api/v1"
            className="w-full px-4 py-2.5 rounded-xl bg-black/50 border border-white/10 focus:border-blue-500/60 focus:outline-none text-xs text-slate-100 font-mono transition-colors"
          />
        </div>

        {/* LLM Model Selector */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-cyan-400" />
            <span>Model Selection</span>
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {(provider === 'gemini'
              ? [
                  { id: 'gemini-3.5-flash-lite', label: 'Gemini 3.5 Flash Lite (Fastest ⚡)' },
                  { id: 'gemini-3.5-flash', label: 'Gemini 3.5 Flash (Balanced)' },
                  { id: 'gemini-3.6-flash', label: 'Gemini 3.6 Flash' },
                  { id: 'gemini-flash-lite-latest', label: 'Gemini Flash Lite' },
                ]
              : provider === 'groq'
              ? [
                  { id: 'llama-3.3-70b-versatile', label: 'Llama 3.3 70B' },
                  { id: 'mixtral-8x7b-32768', label: 'Mixtral 8x7b' },
                ]
              : provider === 'ollama'
              ? [
                  { id: 'llama3.2', label: 'Llama 3.2' },
                  { id: 'deepseek-r1:70b', label: 'DeepSeek R1' },
                ]
              : [
                  { id: 'gpt-4o-mini', label: 'GPT-4o Mini' },
                  { id: 'gpt-4o', label: 'GPT-4o' },
                ]
            ).map((m) => (
              <button
                key={m.id}
                onClick={() => setCustomModel(m.id)}
                className={`py-2 px-3 rounded-xl text-xs font-semibold border text-center transition-all ${
                  customModel === m.id
                    ? 'bg-blue-600 text-white border-blue-400 font-bold shadow-md shadow-blue-500/20'
                    : 'bg-black/40 text-slate-400 border-white/5 hover:border-white/15 hover:text-white'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>

          <input
            type="text"
            value={customModel}
            onChange={(e) => setCustomModel(e.target.value)}
            placeholder="Or type custom model name (e.g. deepseek-r1)..."
            className="w-full px-3 py-2 rounded-xl bg-black/50 border border-white/10 focus:border-blue-500/60 focus:outline-none text-xs text-slate-200 font-mono transition-colors"
          />
        </div>

        {/* TTS Voice Selector */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <Volume2 className="w-3.5 h-3.5 text-cyan-400" />
            <span>Voice Persona (Neural AI Voices)</span>
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {[
              { id: 'thilini', label: '🇱🇰 Thilini (Natural Female)' },
              { id: 'sameera', label: '🇱🇰 Sameera (Natural Male)' },
              { id: 'ava', label: '🇬🇧 Ava (Studio Female)' },
              { id: 'andrew', label: '🇬🇧 Andrew (Studio Male)' },
              { id: 'emma', label: '🇬🇧 Emma (Expressive)' },
              { id: 'brian', label: '🇬🇧 Brian (Crisp Male)' },
            ].map((v) => (
              <button
                key={v.id}
                onClick={() => setVoice(v.id)}
                className={`py-2 px-2.5 rounded-xl text-[11px] font-semibold border text-center transition-all ${
                  voice === v.id
                    ? 'bg-blue-600 text-white border-blue-400 font-bold shadow-md shadow-blue-500/20'
                    : 'bg-black/40 text-slate-400 border-white/5 hover:border-white/15 hover:text-white'
                }`}
              >
                {v.label}
              </button>
            ))}
          </div>
        </div>

        {/* Save button */}
        <button
          onClick={handleSave}
          className="w-full py-3 rounded-2xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-sm flex items-center justify-center gap-2 transition-all shadow-lg shadow-blue-500/25 mt-2 active:scale-98"
        >
          {isSaved ? (
            <>
              <Check className="w-4 h-4 text-white stroke-[3]" /> Saved Configuration!
            </>
          ) : (
            <>
              <Save className="w-4 h-4" /> Save Settings
            </>
          )}
        </button>
      </div>
    </div>
  );
};

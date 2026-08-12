'use client';

import React, { useState } from 'react';
import { X, Key, Settings, Volume2, Cpu, Save, Check, Globe, Server } from 'lucide-react';

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
    }, 800);
  };

  const handleProviderSelect = (p: string) => {
    setProvider(p);
    if (p === 'gemini') {
      setCustomModel('gemini-2.0-flash');
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
      <div className="w-full max-w-xl glass-panel bg-slate-900/90 border border-slate-700/70 rounded-2xl p-6 md:p-8 flex flex-col gap-6 relative shadow-2xl text-gray-100 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-amber-400" />
            <h2 className="text-lg font-bold text-gray-100 tracking-wide">LLM Provider & Voice Configuration</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white rounded-xl hover:bg-gray-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* AI Provider Selector */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
            <Globe className="w-3.5 h-3.5 text-amber-400" />
            Select LLM Provider
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {[
              { id: 'gemini', label: 'Google Gemini', icon: '✨' },
              { id: 'openai', label: 'OpenAI', icon: '🧠' },
              { id: 'groq', label: 'Groq Cloud', icon: '⚡' },
              { id: 'ollama', label: 'Local / Ollama', icon: '🦙' },
            ].map((p) => (
              <button
                key={p.id}
                onClick={() => handleProviderSelect(p.id)}
                className={`py-2.5 px-3 rounded-xl text-xs font-bold transition-all flex flex-col items-center gap-1 border ${
                  provider === p.id
                    ? 'bg-amber-500 text-black border-amber-400 shadow-lg shadow-amber-500/20'
                    : 'bg-gray-950 text-gray-400 border-gray-800 hover:border-gray-700 hover:text-white'
                }`}
              >
                <span className="text-sm">{p.icon}</span>
                <span>{p.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* API Key Input */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
              <Key className="w-3.5 h-3.5 text-amber-400" />
              API Key ({provider.toUpperCase()})
            </label>
          </div>

          <input
            type="password"
            value={localKey}
            onChange={(e) => setLocalKey(e.target.value)}
            placeholder={
              provider === 'gemini'
                ? 'AIzaSy...'
                : provider === 'groq'
                ? 'gsk_...'
                : provider === 'ollama'
                ? 'Optional for local Ollama'
                : 'sk-proj-...'
            }
            className="w-full px-4 py-2.5 rounded-xl bg-gray-950 border border-gray-800 focus:border-amber-500 focus:outline-none text-sm text-gray-100 font-mono transition-colors"
          />
          <p className="text-[10px] text-gray-500">
            Keys are kept local to your browser session and never logged.
          </p>
        </div>

        {/* Custom Base URL (Ollama / OpenRouter / Custom Endpoints) */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
            <Server className="w-3.5 h-3.5 text-amber-400" />
            Custom API Base URL (Optional)
          </label>
          <input
            type="text"
            value={localBaseUrl}
            onChange={(e) => setLocalBaseUrl(e.target.value)}
            placeholder="http://localhost:11434/v1 or https://openrouter.ai/api/v1"
            className="w-full px-4 py-2.5 rounded-xl bg-gray-950 border border-gray-800 focus:border-amber-500 focus:outline-none text-sm text-gray-100 font-mono transition-colors"
          />
        </div>

        {/* LLM Model Selector */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-amber-400" />
            LLM Model ID
          </label>
          <div className="grid grid-cols-2 gap-2">
            {(provider === 'gemini'
              ? [
                  { id: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
                  { id: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
                  { id: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
                ]
              : provider === 'groq'
              ? [
                  { id: 'llama-3.3-70b-versatile', label: 'Llama 3.3 70B' },
                  { id: 'mixtral-8x7b-32768', label: 'Mixtral 8x7b' },
                ]
              : provider === 'ollama'
              ? [
                  { id: 'llama3.2', label: 'Ollama Llama 3.2' },
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
                    ? 'bg-amber-500 text-black border-amber-400 font-bold'
                    : 'bg-gray-950 text-gray-400 border-gray-800 hover:border-gray-700 hover:text-white'
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
            placeholder="Or type custom model name (e.g. deepseek-r1, llama3)..."
            className="w-full px-4 py-2 mt-1 rounded-xl bg-gray-950 border border-gray-800 focus:border-amber-500 focus:outline-none text-xs text-gray-200 transition-colors"
          />
        </div>

        {/* TTS Voice Selector */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
            <Volume2 className="w-3.5 h-3.5 text-amber-400" />
            Voice Persona
          </label>
          <div className="grid grid-cols-3 gap-2">
            {[
              { id: 'nova', label: 'Nova (Female)' },
              { id: 'alloy', label: 'Alloy (Neutral)' },
              { id: 'echo', label: 'Echo (Male)' },
              { id: 'fable', label: 'Fable (Narrator)' },
              { id: 'onyx', label: 'Onyx (Deep)' },
              { id: 'shimmer', label: 'Shimmer (Bright)' },
            ].map((v) => (
              <button
                key={v.id}
                onClick={() => setVoice(v.id)}
                className={`py-2 px-2 rounded-xl text-[11px] font-semibold border text-center transition-all ${
                  voice === v.id
                    ? 'bg-amber-500 text-black border-amber-400 font-bold'
                    : 'bg-gray-950 text-gray-400 border-gray-800 hover:border-gray-700 hover:text-white'
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
          className="w-full py-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-black font-bold text-sm flex items-center justify-center gap-2 transition-all shadow-lg shadow-amber-500/20 mt-2"
        >
          {isSaved ? (
            <>
              <Check className="w-4 h-4 text-black" /> Saved Configuration!
            </>
          ) : (
            <>
              <Save className="w-4 h-4" /> Save Configuration
            </>
          )}
        </button>
      </div>
    </div>
  );
};

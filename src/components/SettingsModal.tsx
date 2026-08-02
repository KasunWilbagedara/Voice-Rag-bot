'use client';

import React, { useState } from 'react';
import { X, Key, Settings, Volume2, Cpu, Save, Check, Sparkles } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiKey: string;
  setApiKey: (key: string) => void;
  voice: string;
  setVoice: (voice: string) => void;
  model: string;
  setModel: (model: string) => void;
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
}) => {
  const [localKey, setLocalKey] = useState(apiKey);
  const [isSaved, setIsSaved] = useState(false);

  if (!isOpen) return null;

  const handleSave = () => {
    setApiKey(localKey);
    setIsSaved(true);
    setTimeout(() => {
      setIsSaved(false);
      onClose();
    }, 800);
  };

  const isGemini = localKey.startsWith('AIza');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-fade-in">
      <div className="w-full max-w-lg glass-panel rounded-3xl p-6 md:p-8 flex flex-col gap-6 relative border border-gray-800 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-brand-400" />
            <h2 className="text-lg font-bold text-gray-100">Voice-RAG Configurations</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white rounded-xl hover:bg-gray-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* API Key Input (Google Gemini OR OpenAI) */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-1.5">
              <Key className="w-3.5 h-3.5 text-amber-400" />
              API Key (Google Gemini or OpenAI)
            </label>

            <span
              className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
                isGemini
                  ? 'bg-blue-950/80 text-blue-300 border-blue-800'
                  : 'bg-emerald-950/80 text-emerald-300 border-emerald-800'
              }`}
            >
              {isGemini ? '✨ Google Gemini API Key' : localKey ? 'OpenAI API Key' : 'Enter API Key'}
            </span>
          </div>

          <input
            type="password"
            value={localKey}
            onChange={(e) => setLocalKey(e.target.value)}
            placeholder="AIzaSy... (Gemini) or sk-proj-... (OpenAI)"
            className="w-full px-4 py-3 rounded-xl bg-gray-900 border border-gray-800 focus:border-brand-500 focus:outline-none text-sm text-gray-100 font-mono"
          />
          <p className="text-[11px] text-gray-400">
            Paste your Google Gemini API Key (starts with <code className="text-amber-300">AIzaSy</code>) or OpenAI key. Both are fully supported!
          </p>
        </div>

        {/* LLM Model Selector */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-emerald-400" />
            LLM Generation Model
          </label>
          <div className="grid grid-cols-2 gap-2">
            {[
              { id: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash (Fast Multilingual)' },
              { id: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
              { id: 'gpt-4o-mini', label: 'GPT-4o Mini' },
              { id: 'gpt-4o', label: 'GPT-4o' },
            ].map((m) => (
              <button
                key={m.id}
                onClick={() => setModel(m.id)}
                className={`py-2.5 px-3 rounded-xl text-xs font-medium border text-left transition-all ${
                  model === m.id
                    ? 'bg-amber-950/50 text-amber-300 border-amber-500/60 font-bold'
                    : 'bg-gray-900 text-gray-400 border-gray-800 hover:border-gray-700'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        {/* TTS Voice Selector & Quality */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-1.5">
              <Volume2 className="w-3.5 h-3.5 text-cyan-400" />
              Human Voice Persona & Tone
            </label>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-950/80 text-cyan-300 border border-cyan-800 font-bold flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-cyan-400" /> HD Neural Synthesis
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2">
            {[
              { id: 'nova', label: 'Nova (Warm Female)' },
              { id: 'alloy', label: 'Alloy (Neutral)' },
              { id: 'echo', label: 'Echo (Warm Male)' },
              { id: 'fable', label: 'Fable (Narrator)' },
              { id: 'onyx', label: 'Onyx (Deep Male)' },
              { id: 'shimmer', label: 'Shimmer (Bright)' },
            ].map((v) => (
              <button
                key={v.id}
                onClick={() => setVoice(v.id)}
                className={`py-2 px-2.5 rounded-xl text-xs font-medium border text-center transition-all ${
                  voice === v.id
                    ? 'bg-amber-950/50 text-amber-300 border-amber-500/60 font-bold shadow-lg'
                    : 'bg-gray-900 text-gray-400 border-gray-800 hover:border-gray-700'
                }`}
              >
                {v.label}
              </button>
            ))}
          </div>

          <p className="text-[11px] text-gray-400 mt-1">
            Audio output automatically applies speech cleaning, removing markdown symbols, list numbers, and code syntax for natural human phrasing.
          </p>
        </div>

        {/* Save button */}
        <button
          onClick={handleSave}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-white font-semibold text-sm flex items-center justify-center gap-2 transition-all shadow-lg glow-blue mt-2"
        >
          {isSaved ? (
            <>
              <Check className="w-4 h-4" /> Saved Settings!
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

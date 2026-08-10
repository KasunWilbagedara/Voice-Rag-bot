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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in p-4">
      <div className="w-full max-w-lg bg-white border border-gray-200 rounded p-6 md:p-8 flex flex-col gap-6 relative shadow-sm">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-emerald-500" />
            <h2 className="text-lg font-bold text-black uppercase tracking-wider">Configuration</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-black rounded hover:bg-gray-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* API Key Input */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1.5">
              <Key className="w-3.5 h-3.5 text-black" />
              API Key (Google Gemini or OpenAI)
            </label>
            <span
              className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider ${
                isGemini
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : 'bg-gray-100 text-gray-700 border border-gray-200'
              }`}
            >
              {isGemini ? 'Google Gemini Key' : localKey ? 'OpenAI Key' : 'Enter API Key'}
            </span>
          </div>

          <input
            type="password"
            value={localKey}
            onChange={(e) => setLocalKey(e.target.value)}
            placeholder="AIzaSy... (Gemini) or sk-proj-... (OpenAI)"
            className="w-full px-4 py-3 rounded bg-gray-50 border border-gray-200 focus:border-black focus:outline-none text-sm text-black font-mono transition-colors"
          />
          <p className="text-[10px] text-gray-500 font-bold uppercase tracking-wider">
            Your key is stored locally in your browser. Both Gemini and OpenAI are supported.
          </p>
        </div>

        {/* LLM Model Selector */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-black" />
            LLM Generation Model
          </label>
          <div className="grid grid-cols-2 gap-2">
            {[
              { id: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
              { id: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
              { id: 'gpt-4o-mini', label: 'GPT-4o Mini' },
              { id: 'gpt-4o', label: 'GPT-4o' },
            ].map((m) => (
              <button
                key={m.id}
                onClick={() => setModel(m.id)}
                className={`py-2.5 px-3 rounded text-xs font-bold uppercase tracking-wider border text-center transition-all ${
                  model === m.id
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-white text-gray-500 border-gray-200 hover:border-black hover:text-black'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        {/* TTS Voice Selector */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1.5">
              <Volume2 className="w-3.5 h-3.5 text-black" />
              Human Voice Persona
            </label>
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
                className={`py-2 px-2 rounded text-[10px] font-bold uppercase tracking-wider border text-center transition-all ${
                  voice === v.id
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-white text-gray-500 border-gray-200 hover:border-black hover:text-black'
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
          className="w-full py-3 rounded bg-black hover:bg-gray-800 text-white font-bold text-sm uppercase tracking-wider flex items-center justify-center gap-2 transition-all shadow-sm mt-2"
        >
          {isSaved ? (
            <>
              <Check className="w-4 h-4 text-emerald-400" /> Saved Successfully!
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

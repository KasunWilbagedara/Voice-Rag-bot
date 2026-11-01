'use client';

import React from 'react';
import { Brain, Wrench } from 'lucide-react';

export type BackendMode = 'pure' | 'tools';

interface BackendModeSwitcherProps {
  mode: BackendMode;
  onChange: (mode: BackendMode) => void;
  disabled?: boolean;
}

/**
 * BackendModeSwitcher
 * -------------------
 * Toggle between two backend modes:
 *   "pure"  → Backend 1 (Port 8000): Pure RAG, MMR filter, zero tool calls
 *   "tools" → Backend 2 (Port 8001): Agentic RAG + 13 tools + MCP
 *
 * The selected mode is forwarded as the `x-backend-mode` HTTP header
 * on every API request made by the parent page.
 */
export function BackendModeSwitcher({ mode, onChange, disabled = false }: BackendModeSwitcherProps) {
  return (
    <div className="flex items-center gap-1 bg-white/70 border border-sky-100 rounded-2xl p-1 shadow-sm backdrop-blur-xl select-none">
      {/* Pure RAG button */}
      <button
        onClick={() => !disabled && onChange('pure')}
        disabled={disabled}
        title="Pure RAG — Strictly grounded, MMR diversity filter, zero tool calls (Port 8000)"
        className={`
          flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
          transition-all duration-200
          ${mode === 'pure'
            ? 'bg-sky-600 text-white shadow-md shadow-sky-200/70'
            : 'text-slate-500 hover:text-slate-900 hover:bg-sky-50'
          }
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `}
      >
        <Brain size={13} />
        Pure RAG
      </button>

      {/* RAG + Tools button */}
      <button
        onClick={() => !disabled && onChange('tools')}
        disabled={disabled}
        title="RAG + Tools — Agentic LLM with 13 tools, live data, MCP server (Port 8001)"
        className={`
          flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
          transition-all duration-200
          ${mode === 'tools'
            ? 'bg-sky-600 text-white shadow-md shadow-sky-200/70'
            : 'text-slate-500 hover:text-slate-900 hover:bg-sky-50'
          }
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `}
      >
        <Wrench size={13} />
        RAG + Tools
      </button>
    </div>
  );
}

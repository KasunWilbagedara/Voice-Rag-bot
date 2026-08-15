'use client';

import React, { useState } from 'react';
import {
  X,
  Layers,
  FileText,
  CheckCircle2,
  Sparkles,
  BrainCircuit,
  Database,
  Terminal,
  Copy,
  Check,
  Filter,
} from 'lucide-react';

interface ChunkItem {
  id: string;
  documentId: string;
  documentTitle: string;
  content: string;
  chunkIndex: number;
  similarity: number;
  type?: 'database_record' | 'database_sql' | string;
}

interface ContextDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  chunks: ChunkItem[];
  userQuery?: string;
}

export const ContextDrawer: React.FC<ContextDrawerProps> = ({
  isOpen,
  onClose,
  chunks,
  userQuery,
}) => {
  const [filterType, setFilterType] = useState<'all' | 'db' | 'doc'>('all');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  if (!isOpen) return null;

  const copyChunk = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filteredChunks = chunks.filter((chunk) => {
    const isDb = chunk.type === 'database_record' || chunk.type === 'database_sql' || chunk.documentTitle?.startsWith('Database:');
    if (filterType === 'db') return isDb;
    if (filterType === 'doc') return !isDb;
    return true;
  });

  const dbCount = chunks.filter(c => c.type === 'database_record' || c.type === 'database_sql' || c.documentTitle?.startsWith('Database:')).length;
  const docCount = chunks.length - dbCount;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/75 backdrop-blur-md animate-fade-in">
      <div className="w-full max-w-xl bg-[#090d18] border-l border-white/10 h-full p-5 md:p-6 flex flex-col gap-5 shadow-2xl overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-violet-500/15 border border-violet-500/30 flex items-center justify-center text-violet-400">
              <BrainCircuit className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100">Multi-Source RAG Context</h2>
              <p className="text-xs text-slate-400">Grounded evidence and records used by the model</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-xl bg-black/40 hover:bg-black/60 border border-white/10 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* User query reference */}
        {userQuery && (
          <div className="p-3.5 rounded-2xl bg-black/40 border border-white/10 flex flex-col gap-1">
            <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider block">
              Evaluated Query
            </span>
            <p className="text-xs font-semibold text-slate-200">"{userQuery}"</p>
          </div>
        )}

        {/* Filter Category Tabs */}
        <div className="flex items-center gap-1.5 p-1 bg-black/40 border border-white/10 rounded-xl text-xs">
          <button
            onClick={() => setFilterType('all')}
            className={`flex-1 py-1.5 px-2 rounded-lg font-bold transition-all ${
              filterType === 'all'
                ? 'bg-violet-500 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All Sources ({chunks.length})
          </button>
          <button
            onClick={() => setFilterType('db')}
            className={`flex-1 py-1.5 px-2 rounded-lg font-bold transition-all ${
              filterType === 'db'
                ? 'bg-amber-500 text-slate-950 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            DB Records ({dbCount})
          </button>
          <button
            onClick={() => setFilterType('doc')}
            className={`flex-1 py-1.5 px-2 rounded-lg font-bold transition-all ${
              filterType === 'doc'
                ? 'bg-cyan-500 text-slate-950 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Vector Chunks ({docCount})
          </button>
        </div>

        {/* Chunks List */}
        <div className="flex flex-col gap-3">
          {filteredChunks.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500 italic border border-white/5 rounded-2xl bg-black/20">
              No context chunks matching this filter for the selected query.
            </div>
          ) : (
            filteredChunks.map((chunk, idx) => {
              const chunkKey = chunk.id || `chunk-${idx}`;
              const isDb = chunk.type === 'database_record' || chunk.type === 'database_sql' || chunk.documentTitle?.startsWith('Database:');
              const similarityPct = Math.round((chunk.similarity || 0.8) * 100);

              return (
                <div
                  key={chunkKey}
                  className={`p-4 rounded-2xl border transition-all flex flex-col gap-2.5 ${
                    isDb
                      ? 'bg-amber-500/5 border-amber-500/25 hover:border-amber-500/50'
                      : 'bg-black/30 border-white/10 hover:border-violet-500/40'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={`flex items-center gap-1.5 text-xs font-bold truncate ${isDb ? 'text-amber-300' : 'text-cyan-300'}`}>
                      {isDb ? <Database className="w-3.5 h-3.5 text-amber-400 shrink-0" /> : <FileText className="w-3.5 h-3.5 text-cyan-400 shrink-0" />}
                      <span className="truncate">{chunk.documentTitle}</span>
                      {!isDb && <span className="text-slate-500 font-normal">#{chunk.chunkIndex + 1}</span>}
                    </span>

                    <div className="flex items-center gap-2 shrink-0">
                      <span
                        className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                          isDb
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                            : similarityPct >= 80
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                            : 'bg-blue-500/20 text-blue-300 border border-blue-500/40'
                        }`}
                      >
                        {isDb ? 'SQL Match' : `${similarityPct}% Sim`}
                      </span>

                      <button
                        onClick={() => copyChunk(chunkKey, chunk.content)}
                        className="p-1 rounded text-slate-400 hover:text-white hover:bg-black/40 transition-colors"
                        title="Copy content"
                      >
                        {copiedId === chunkKey ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      </button>
                    </div>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed font-mono bg-black/60 p-3 rounded-xl border border-white/5 whitespace-pre-wrap max-h-48 overflow-y-auto custom-scrollbar">
                    {chunk.content}
                  </p>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};

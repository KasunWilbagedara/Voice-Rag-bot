'use client';

import React from 'react';
import { X, Layers, FileText, CheckCircle2, Sparkles, BrainCircuit, Database, Terminal } from 'lucide-react';

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
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-xl bg-[#0d1322] border-l border-gray-800 h-full p-6 flex flex-col gap-6 shadow-2xl overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <BrainCircuit className="w-5 h-5 text-violet-400" />
            <h2 className="text-lg font-bold text-gray-100">Multi-Source RAG Context</h2>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white rounded-xl hover:bg-gray-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* User query reference */}
        {userQuery && (
          <div className="p-3.5 rounded-2xl bg-gray-900/80 border border-gray-800">
            <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider block mb-1">
              Evaluated Query
            </span>
            <p className="text-sm font-medium text-gray-200">"{userQuery}"</p>
          </div>
        )}

        {/* Chunks List */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-gray-400 tracking-wider">
              {chunks.length} Retrieved Context Sources (Documents + Databases)
            </span>
          </div>

          {chunks.length === 0 ? (
            <div className="py-12 text-center text-sm text-gray-500 italic border border-gray-800 rounded-2xl">
              No RAG context chunks or database records retrieved for this query.
            </div>
          ) : (
            chunks.map((chunk, idx) => {
              const isDb = chunk.type === 'database_record' || chunk.type === 'database_sql' || chunk.documentTitle?.startsWith('Database:');
              const similarityPct = Math.round(chunk.similarity * 100);

              return (
                <div
                  key={chunk.id || idx}
                  className={`p-4 rounded-2xl border transition-all flex flex-col gap-3 ${
                    isDb
                      ? 'bg-amber-950/20 border-amber-800/60 hover:border-amber-500/60'
                      : 'bg-gray-900/90 border-gray-800/90 hover:border-violet-500/40'
                  }`}
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className={`flex items-center gap-1.5 font-semibold ${isDb ? 'text-amber-300' : 'text-cyan-300'}`}>
                      {isDb ? <Database className="w-3.5 h-3.5 text-amber-400" /> : <FileText className="w-3.5 h-3.5 text-cyan-400" />}
                      {chunk.documentTitle} {!isDb && `(Chunk #${chunk.chunkIndex + 1})`}
                    </span>

                    <span
                      className={`px-2.5 py-0.5 rounded-full font-bold text-[11px] ${
                        isDb
                          ? 'bg-amber-950/90 text-amber-300 border border-amber-700/60'
                          : similarityPct >= 80
                          ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-800/50'
                          : 'bg-blue-950/80 text-blue-400 border border-blue-800/50'
                      }`}
                    >
                      {isDb ? 'SQL Match' : `${similarityPct}% Match`}
                    </span>
                  </div>

                  <p className="text-xs text-gray-300 leading-relaxed font-mono bg-gray-950/80 p-3 rounded-xl border border-gray-800/60 whitespace-pre-wrap">
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

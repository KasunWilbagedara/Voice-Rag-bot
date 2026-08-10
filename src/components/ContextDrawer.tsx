'use client';

import React from 'react';
import { X, Layers, FileText, CheckCircle2, Sparkles, BrainCircuit } from 'lucide-react';

interface ChunkItem {
  id: string;
  documentId: string;
  documentTitle: string;
  content: string;
  chunkIndex: number;
  similarity: number;
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
      <div className="w-full max-w-xl bg-white border-l border-gray-200 h-full p-6 flex flex-col gap-6 shadow-2xl overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <BrainCircuit className="w-5 h-5 text-emerald-500" />
            <h2 className="text-lg font-bold text-black uppercase tracking-wider">Retrieved RAG Context</h2>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-black rounded hover:bg-gray-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* User query reference */}
        {userQuery && (
          <div className="p-3.5 rounded bg-gray-50 border border-gray-200">
            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-1">
              Evaluated Query
            </span>
            <p className="text-sm font-bold text-black">"{userQuery}"</p>
          </div>
        )}

        {/* Chunks List */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase text-gray-500 tracking-widest border-b border-gray-200 w-full pb-2">
              Top-{chunks.length} Vector Match Chunks
            </span>
          </div>

          {chunks.length === 0 ? (
            <div className="py-12 text-center text-xs font-bold uppercase tracking-wider text-gray-400 border border-gray-200 rounded bg-gray-50">
              No vector context chunks retrieved for this query.
            </div>
          ) : (
            chunks.map((chunk, idx) => {
              const similarityPct = Math.round(chunk.similarity * 100);
              return (
                <div
                  key={chunk.id || idx}
                  className="p-4 rounded bg-white border border-gray-200 hover:border-black transition-all flex flex-col gap-3 shadow-sm"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5 font-bold text-black">
                      <FileText className="w-3.5 h-3.5 text-gray-500" />
                      {chunk.documentTitle} (Chunk #{chunk.chunkIndex + 1})
                    </span>

                    <span
                      className={`px-2.5 py-0.5 rounded font-bold text-[10px] uppercase tracking-wider ${
                        similarityPct >= 80
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : similarityPct >= 50
                          ? 'bg-blue-50 text-blue-700 border-blue-200'
                          : 'bg-gray-100 text-gray-700 border-gray-200'
                      }`}
                    >
                      {similarityPct}% Match
                    </span>
                  </div>

                  <p className="text-xs text-gray-800 leading-relaxed font-mono bg-gray-50 p-3 rounded border border-gray-200 whitespace-pre-wrap">
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

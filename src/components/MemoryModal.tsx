'use client';

import React, { useState, useEffect } from 'react';
import {
  Brain,
  X,
  Plus,
  Trash2,
  RefreshCw,
  Tag,
  Clock,
  Sparkles,
  ShieldCheck,
  User,
  Package,
  Bookmark,
  Check,
  AlertCircle
} from 'lucide-react';

export interface UserMemory {
  id: string;
  sessionId: string;
  key: string;
  value: string;
  category: string;
  createdAt: string;
  updatedAt: string;
}

interface MemoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId?: string;
  onMemoriesUpdated?: (count: number) => void;
}

export const MemoryModal: React.FC<MemoryModalProps> = ({
  isOpen,
  onClose,
  sessionId = 'default_user',
  onMemoriesUpdated,
}) => {
  const [memories, setMemories] = useState<UserMemory[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Form State
  const [newKey, setNewKey] = useState<string>('');
  const [newValue, setNewValue] = useState<string>('');
  const [newCategory, setNewCategory] = useState<string>('identity');

  const fetchMemories = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/memory?sessionId=${encodeURIComponent(sessionId)}`);
      if (res.ok) {
        const data = await res.json();
        const memList = data.memories || [];
        setMemories(memList);
        if (onMemoriesUpdated) onMemoriesUpdated(memList.length);
      } else {
        setError('Failed to load remembered facts.');
      }
    } catch (err: any) {
      setError(err.message || 'Network error fetching memories.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchMemories();
    }
  }, [isOpen, sessionId]);

  const handleAddMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKey.trim() || !newValue.trim() || isSaving) return;

    setIsSaving(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const res = await fetch('/api/memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId,
          key: newKey.trim(),
          value: newValue.trim(),
          category: newCategory,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const memList = data.memories || [];
        setMemories(memList);
        if (onMemoriesUpdated) onMemoriesUpdated(memList.length);
        setNewKey('');
        setNewValue('');
        setSuccessMsg('Fact successfully remembered!');
        setTimeout(() => setSuccessMsg(null), 3000);
      } else {
        const data = await res.json();
        setError(data.detail || 'Could not save memory.');
      }
    } catch (err: any) {
      setError(err.message || 'Error saving memory.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteMemory = async (id: string) => {
    try {
      const res = await fetch(`/api/memory/${id}`, { method: 'DELETE' });
      if (res.ok) {
        const updated = memories.filter((m) => m.id !== id);
        setMemories(updated);
        if (onMemoriesUpdated) onMemoriesUpdated(updated.length);
      }
    } catch (err) {
      console.error('Error deleting memory:', err);
    }
  };

  const handleClearAll = async () => {
    if (memories.length === 0) return;
    if (!confirm('Are you sure you want to clear all remembered facts for this session?')) return;

    try {
      const res = await fetch(`/api/memory?sessionId=${encodeURIComponent(sessionId)}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setMemories([]);
        if (onMemoriesUpdated) onMemoriesUpdated(0);
        setSuccessMsg('All memories cleared.');
        setTimeout(() => setSuccessMsg(null), 3000);
      }
    } catch (err) {
      console.error('Error clearing memories:', err);
    }
  };

  const getCategoryBadge = (category: string) => {
    switch (category.toLowerCase()) {
      case 'identity':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30">
            <User className="w-3 h-3" /> Identity
          </span>
        );
      case 'entity':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
            <Package className="w-3 h-3" /> Tracked Entity
          </span>
        );
      case 'pinned_fact':
      case 'preference':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30">
            <Bookmark className="w-3 h-3" /> Preference
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-300 border border-purple-500/30">
            <Tag className="w-3 h-3" /> Note
          </span>
        );
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl bg-[#08080a] border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center shadow-inner">
              <Brain className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-extrabold text-slate-100 text-base tracking-tight">
                  Persistent Long-Term Memory
                </h3>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 font-bold">
                  {memories.length} Remembered
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Facts the Voice-RAG bot automatically retains across conversations & page reloads
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchMemories}
              disabled={isLoading}
              className="p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 hover:text-white transition-all text-xs flex items-center gap-1"
              title="Refresh memories"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-amber-400' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-slate-400 hover:text-white transition-all"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 custom-scrollbar">
          {/* Status Messages */}
          {error && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-xs text-emerald-300 flex items-center gap-2">
              <Check className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Add New Memory Form */}
          <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                Explicitly Teach or Pin a Fact
              </span>
              <span className="text-[11px] text-slate-400">
                Auto-extracted during voice chat or added manually
              </span>
            </div>

            <form onSubmit={handleAddMemory} className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <input
                  type="text"
                  placeholder="Key (e.g. user_name, project)"
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  className="px-3 py-2 text-xs bg-black/40 border border-white/10 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500/60"
                  required
                />
                <input
                  type="text"
                  placeholder="Value (e.g. Kasun, SLT Core Fiber)"
                  value={newValue}
                  onChange={(e) => setNewValue(e.target.value)}
                  className="sm:col-span-2 px-3 py-2 text-xs bg-black/40 border border-white/10 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500/60"
                  required
                />
              </div>

              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <label className="text-[11px] text-slate-400">Category:</label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    className="text-xs bg-black/40 border border-white/10 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-amber-500/60"
                  >
                    <option value="identity">Identity (Name, Role)</option>
                    <option value="entity">Tracked Entity (Order, Ticket)</option>
                    <option value="preference">Preference / Habit</option>
                    <option value="note">General Note</option>
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={isSaving || !newKey.trim() || !newValue.trim()}
                  className="px-4 py-1.5 rounded-lg realistic-button-amber text-black font-extrabold text-xs flex items-center gap-1.5 transition-all shadow-md shadow-amber-500/20 disabled:opacity-50"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>{isSaving ? 'Saving...' : 'Remember Fact'}</span>
                </button>
              </div>
            </form>
          </div>

          {/* Stored Facts List */}
          <div className="space-y-3">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Currently Remembered Facts
              </span>
              {memories.length > 0 && (
                <button
                  onClick={handleClearAll}
                  className="text-xs text-rose-400 hover:text-rose-300 flex items-center gap-1 transition-colors hover:underline"
                >
                  <Trash2 className="w-3 h-3" /> Clear All
                </button>
              )}
            </div>

            {memories.length === 0 ? (
              <div className="p-8 border border-dashed border-white/10 rounded-2xl text-center space-y-2">
                <Brain className="w-8 h-8 text-slate-600 mx-auto" />
                <p className="text-xs font-semibold text-slate-400">
                  No remembered facts yet.
                </p>
                <p className="text-[11px] text-slate-500 max-w-md mx-auto">
                  Speak to the bot with phrases like <em>&quot;My name is Kasun&quot;</em>, <em>&quot;Check order ORD-98214&quot;</em>, or <em>&quot;මගේ නම නිමල්&quot;</em>. The bot will automatically preserve your facts in SQLite!
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-2.5">
                {memories.map((item) => (
                  <div
                    key={item.id}
                    className="p-3 rounded-xl bg-white/[0.02] hover:bg-white/[0.04] border border-white/10 flex items-start justify-between gap-3 transition-all group"
                  >
                    <div className="space-y-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-xs font-bold text-amber-300">
                          {item.key}
                        </span>
                        {getCategoryBadge(item.category)}
                      </div>
                      <p className="text-xs font-medium text-slate-200 break-words">
                        {item.value}
                      </p>
                      <div className="flex items-center gap-2 text-[10px] text-slate-500">
                        <Clock className="w-3 h-3" />
                        <span>Saved: {item.updatedAt || item.createdAt}</span>
                      </div>
                    </div>

                    <button
                      onClick={() => handleDeleteMemory(item.id)}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors opacity-80 group-hover:opacity-100"
                      title="Forget this fact"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-white/10 flex items-center justify-between bg-white/[0.02] text-xs text-slate-400">
          <span className="flex items-center gap-1 text-[11px]">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            Stored safely in SQLite/PostgreSQL (<span className="font-mono text-slate-300">rag_user_memories</span>)
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-slate-200 font-semibold transition-all text-xs"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};

'use client';

import React, { useState } from 'react';
import { Brain, LogIn, UserPlus } from 'lucide-react';

export interface AppUser {
  id: string;
  username: string;
}

interface LoginScreenProps {
  onLogin: (user: AppUser) => void;
}

/** Username + password form for logging in or creating an account. */
export function LoginScreen({ onLogin }: LoginScreenProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const res = await fetch(`/api/auth/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Something went wrong');
      onLogin(data.user);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main
      className="min-h-screen flex items-center justify-center p-4"
      style={{ background: 'var(--page-bg)', color: 'var(--text-primary)' }}
    >
      <form onSubmit={submit} className="glass-panel w-full max-w-sm rounded-3xl p-6 flex flex-col gap-4 border border-white/10 shadow-2xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-sky-400 to-blue-600 flex items-center justify-center">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-extrabold text-slate-100">Voice-RAG Studio</h1>
            <p className="text-xs text-slate-400">{mode === 'login' ? 'Log in to continue' : 'Create your account'}</p>
          </div>
        </div>

        <label className="flex flex-col gap-1 text-xs font-semibold text-slate-300">
          Username
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
            className="px-3 py-2 rounded-xl bg-black/40 border border-white/10 text-sm text-slate-100 focus:outline-none focus:border-[#2563EB]/60"
          />
        </label>

        <label className="flex flex-col gap-1 text-xs font-semibold text-slate-300">
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            minLength={mode === 'register' ? 8 : undefined}
            required
            className="px-3 py-2 rounded-xl bg-black/40 border border-white/10 text-sm text-slate-100 focus:outline-none focus:border-[#2563EB]/60"
          />
        </label>

        {error && <p className="text-xs text-rose-400">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="btn-gradient-red py-2.5 rounded-xl text-white text-sm font-bold flex items-center justify-center gap-2 disabled:opacity-50"
        >
          {mode === 'login' ? <LogIn className="w-4 h-4" /> : <UserPlus className="w-4 h-4" />}
          {busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
        </button>

        <button
          type="button"
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login');
            setError('');
          }}
          className="text-xs text-slate-400 hover:text-slate-200"
        >
          {mode === 'login' ? "Don't have an account? Create one" : 'Already have an account? Log in'}
        </button>
      </form>
    </main>
  );
}

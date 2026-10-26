'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Server, Wifi, WifiOff } from 'lucide-react';

interface BackendStatus {
  online: boolean;
  label: string;
  mode?: string;
  toolsCount?: number;
  port: number;
}

interface BackendStatusMonitorProps {
  /** How often to ping backends in milliseconds (default: 15000 = 15s) */
  pollIntervalMs?: number;
}

/**
 * BackendStatusMonitor
 * --------------------
 * Shows live green/red health indicators for both backend services:
 *   Backend 1 (Port 8000) — Pure RAG
 *   Backend 2 (Port 8001) — RAG + Tools
 *
 * Polls /api/health/backend1 and /api/health/backend2 every 15 seconds.
 */
export function BackendStatusMonitor({ pollIntervalMs = 15000 }: BackendStatusMonitorProps) {
  const [backend1, setBackend1] = useState<BackendStatus>({
    online: false,
    label: 'Pure RAG',
    port: 8000,
  });
  const [backend2, setBackend2] = useState<BackendStatus>({
    online: false,
    label: 'RAG + Tools',
    port: 8001,
  });
  const [checking, setChecking] = useState(false);

  const checkHealth = useCallback(async () => {
    setChecking(true);
    try {
      const [res1, res2] = await Promise.allSettled([
        fetch('/api/health/backend1', { signal: AbortSignal.timeout(4000) }),
        fetch('/api/health/backend2', { signal: AbortSignal.timeout(4000) }),
      ]);

      if (res1.status === 'fulfilled' && res1.value.ok) {
        const data = await res1.value.json();
        setBackend1({
          online: data.status === 'healthy',
          label: 'Pure RAG',
          mode: data.mode,
          port: data.port ?? 8000,
        });
      } else {
        setBackend1(prev => ({ ...prev, online: false }));
      }

      if (res2.status === 'fulfilled' && res2.value.ok) {
        const data = await res2.value.json();
        setBackend2({
          online: data.status === 'healthy',
          label: 'RAG + Tools',
          mode: data.mode,
          toolsCount: data.toolsCount,
          port: data.port ?? 8001,
        });
      } else {
        setBackend2(prev => ({ ...prev, online: false }));
      }
    } catch {
      // Network failure — mark both offline
      setBackend1(prev => ({ ...prev, online: false }));
      setBackend2(prev => ({ ...prev, online: false }));
    } finally {
      setChecking(false);
    }
  }, []);

  // Initial check + polling
  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, pollIntervalMs);
    return () => clearInterval(interval);
  }, [checkHealth, pollIntervalMs]);

  return (
    <div className="flex items-center gap-2">
      <Server size={13} className="text-gray-500" />

      <BackendDot status={backend1} />
      <BackendDot status={backend2} />

      {checking && (
        <span className="text-gray-600 text-[10px]">…</span>
      )}
    </div>
  );
}

// ── Internal dot component ────────────────────────────────────────────────────

function BackendDot({ status }: { status: BackendStatus }) {
  const tooltip = status.online
    ? `${status.label} (Port ${status.port}) — Online${status.toolsCount ? ` · ${status.toolsCount} tools` : ''}`
    : `${status.label} (Port ${status.port}) — Offline`;

  return (
    <div
      title={tooltip}
      className="flex items-center gap-1 cursor-default"
    >
      <span
        className={`
          inline-block w-2 h-2 rounded-full transition-colors duration-500
          ${status.online ? 'bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.8)]' : 'bg-red-500'}
        `}
      />
      <span className={`text-[10px] font-medium hidden sm:inline ${status.online ? 'text-gray-300' : 'text-gray-600'}`}>
        {status.label}
      </span>
    </div>
  );
}

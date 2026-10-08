'use client';

import React, { useEffect, useRef } from 'react';

interface AudioVisualizerProps {
  isActive: boolean;
  mode: 'idle' | 'listening' | 'transcribing' | 'searching' | 'speaking';
}

export const AudioVisualizer: React.FC<AudioVisualizerProps> = ({ isActive, mode }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let phase = 0;

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const width = canvas.width;
      const height = canvas.height;
      const centerY = height / 2;

      const isLight = typeof document !== 'undefined' && document.documentElement.classList.contains('light');

      // Color scheme based on active state
      let topColor = '#38bdf8'; // Sky cyan
      let bottomColor = '#818cf8'; // Indigo
      let glowColor = 'rgba(56, 189, 248, 0.3)';

      if (mode === 'listening') {
        topColor = isLight ? '#e11d48' : '#f43f5e'; // Apple Siri radiant rose
        bottomColor = isLight ? '#be123c' : '#e11d48'; // Deep rose
        glowColor = 'rgba(244, 63, 94, 0.4)';
      } else if (mode === 'transcribing' || mode === 'searching') {
        topColor = isLight ? '#7c3aed' : '#c084fc'; // Purple
        bottomColor = isLight ? '#4f46e5' : '#6366f1'; // Indigo
        glowColor = 'rgba(124, 58, 237, 0.35)';
      } else if (mode === 'speaking') {
        topColor = isLight ? '#059669' : '#34d399'; // Emerald
        bottomColor = isLight ? '#047857' : '#059669'; // Dark emerald
        glowColor = 'rgba(16, 185, 129, 0.35)';
      } else {
        // Idle
        topColor = isLight ? '#0284c7' : '#64748b';
        bottomColor = isLight ? '#4f46e5' : '#334155';
        glowColor = isLight ? 'rgba(2, 132, 199, 0.25)' : 'rgba(100, 116, 139, 0.2)';
      }

      // Draw subtle background center baseline
      ctx.strokeStyle = isLight ? 'rgba(148, 163, 184, 0.35)' : 'rgba(255, 255, 255, 0.05)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, centerY);
      ctx.lineTo(width, centerY);
      ctx.stroke();

      const barCount = 42;
      const barWidth = (width / barCount) * 0.55;
      const gap = (width / barCount) * 0.45;

      phase += isActive ? (mode === 'speaking' ? 0.09 : 0.06) : 0.015;

      // Canvas shadow for neon glow
      ctx.shadowBlur = isActive ? 12 : 4;
      ctx.shadowColor = glowColor;

      for (let i = 0; i < barCount; i++) {
        const x = i * (barWidth + gap) + gap / 2;
        
        // Calculate dynamic wave amplitude
        let amplitude = 4;
        const distFromCenter = Math.abs(i - barCount / 2) / (barCount / 2);
        const centerFactor = 1 - distFromCenter * 0.35; // Center bars are slightly taller

        if (isActive) {
          if (mode === 'listening') {
            amplitude = (Math.sin(phase * 1.5 + i * 0.35) * 20 + Math.cos(phase * 2.2 + i * 0.2) * 16 + 26) * centerFactor;
          } else if (mode === 'transcribing' || mode === 'searching') {
            amplitude = (Math.sin(phase * 2.5 + i * 0.5) * 14 + 18) * centerFactor;
          } else if (mode === 'speaking') {
            amplitude = (Math.sin(phase * 3.0 + i * 0.3) * 26 + Math.cos(phase * 1.2 + i * 0.4) * 18 + 30) * centerFactor;
          }
        } else {
          amplitude = (Math.sin(phase + i * 0.2) * 3 + 5) * centerFactor;
        }

        const barHeight = Math.max(4, Math.min(height - 10, amplitude));

        const gradient = ctx.createLinearGradient(0, centerY - barHeight / 2, 0, centerY + barHeight / 2);
        gradient.addColorStop(0, topColor);
        gradient.addColorStop(1, bottomColor);

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.roundRect(x, centerY - barHeight / 2, barWidth, barHeight, barWidth / 2);
        ctx.fill();
      }

      ctx.shadowBlur = 0;
      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [isActive, mode]);

  return (
    <div className="w-full h-24 flex items-center justify-center relative overflow-hidden rounded-2xl ios-spectrum-box bg-slate-100/70 dark:bg-slate-950/50 border border-slate-200/90 dark:border-white/10 p-2 shadow-inner backdrop-blur-xl">
      <canvas
        ref={canvasRef}
        width={560}
        height={96}
        className="w-full h-full object-contain"
      />
      {/* Subtle ambient corner indicators */}
      <div className="absolute top-2 left-3 flex items-center gap-1.5">
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            isActive
              ? 'bg-sky-500 dark:bg-cyan-400 animate-pulse shadow-[0_0_8px_rgba(56,189,248,0.85)]'
              : 'bg-slate-400 dark:bg-slate-600'
          }`}
        />
        <span className="text-[9px] font-mono tracking-widest text-slate-600 dark:text-slate-400 font-bold uppercase">
          {mode === 'listening' ? 'LIVE AUDIO INPUT' : mode === 'speaking' ? 'NEURAL VOICE OUT' : 'SPECTRUM'}
        </span>
      </div>
    </div>
  );
};
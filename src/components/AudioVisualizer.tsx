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

      // Color scheme based on active state
      let topColor = '#38bdf8'; // Sky cyan
      let bottomColor = '#818cf8'; // Indigo
      let glowColor = 'rgba(56, 189, 248, 0.3)';

      if (mode === 'listening') {
        topColor = '#fbbf24'; // Amber
        bottomColor = '#f97316'; // Orange
        glowColor = 'rgba(251, 191, 36, 0.45)';
      } else if (mode === 'transcribing' || mode === 'searching') {
        topColor = '#c084fc'; // Purple
        bottomColor = '#6366f1'; // Indigo
        glowColor = 'rgba(192, 132, 252, 0.4)';
      } else if (mode === 'speaking') {
        topColor = '#34d399'; // Emerald
        bottomColor = '#059669'; // Dark emerald
        glowColor = 'rgba(52, 211, 153, 0.45)';
      } else {
        // Idle
        topColor = '#64748b';
        bottomColor = '#334155';
        glowColor = 'rgba(100, 116, 139, 0.2)';
      }

      // Draw subtle background center baseline
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
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
    <div className="w-full h-24 flex items-center justify-center relative overflow-hidden rounded-2xl bg-black/40 border border-white/10 p-2 shadow-inner backdrop-blur-md">
      <canvas
        ref={canvasRef}
        width={560}
        height={96}
        className="w-full h-full object-contain"
      />
      {/* Subtle ambient corner indicators */}
      <div className="absolute top-2 left-3 flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-amber-400 animate-pulse' : 'bg-slate-600'}`} />
        <span className="text-[9px] font-mono tracking-widest text-slate-500 uppercase">
          {mode === 'listening' ? 'LIVE AUDIO INPUT' : mode === 'speaking' ? 'NEURAL VOICE OUT' : 'SPECTRUM'}
        </span>
      </div>
    </div>
  );
};

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

      // Realistic Studio Audio Spectrum Color Gradients
      let topColor = '#fbbf24'; // Champagne Gold
      let bottomColor = '#d97706'; // Studio Amber
      let glowColor = 'rgba(245, 158, 11, 0.35)';

      if (mode === 'listening') {
        topColor = '#fde68a'; // Light Champagne Gold
        bottomColor = '#f59e0b'; // Warm Amber
        glowColor = 'rgba(245, 158, 11, 0.5)';
      } else if (mode === 'transcribing' || mode === 'searching') {
        topColor = '#fbbf24';
        bottomColor = '#10b981';
        glowColor = 'rgba(251, 191, 36, 0.45)';
      } else if (mode === 'speaking') {
        topColor = '#6ee7b7'; // Studio Mint
        bottomColor = '#059669'; // Precision Emerald
        glowColor = 'rgba(16, 185, 129, 0.5)';
      } else {
        // Idle state: subtle studio titanium standby
        topColor = '#52525b';
        bottomColor = '#27272a';
        glowColor = 'rgba(255, 255, 255, 0.05)';
      }

      // Draw realistic studio frequency grid lines
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.035)';
      ctx.lineWidth = 1;
      for (let y = 14; y < height; y += 22) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // Draw subtle center baseline
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, centerY);
      ctx.lineTo(width, centerY);
      ctx.stroke();

      const barCount = 44;
      const barWidth = (width / barCount) * 0.56;
      const gap = (width / barCount) * 0.44;

      phase += isActive ? (mode === 'speaking' ? 0.085 : 0.06) : 0.012;

      ctx.shadowBlur = isActive ? 10 : 2;
      ctx.shadowColor = glowColor;

      for (let i = 0; i < barCount; i++) {
        const x = i * (barWidth + gap) + gap / 2;

        let amplitude = 4;
        const distFromCenter = Math.abs(i - barCount / 2) / (barCount / 2);
        const centerFactor = 1 - distFromCenter * 0.38;

        if (isActive) {
          if (mode === 'listening') {
            amplitude = (Math.sin(phase * 1.5 + i * 0.35) * 20 + Math.cos(phase * 2.2 + i * 0.2) * 16 + 26) * centerFactor;
          } else if (mode === 'transcribing' || mode === 'searching') {
            amplitude = (Math.sin(phase * 2.5 + i * 0.5) * 14 + 18) * centerFactor;
          } else if (mode === 'speaking') {
            amplitude = (Math.sin(phase * 3.0 + i * 0.3) * 26 + Math.cos(phase * 1.2 + i * 0.4) * 18 + 30) * centerFactor;
          }
        } else {
          amplitude = (Math.sin(phase + i * 0.22) * 3 + 5) * centerFactor;
        }

        const barHeight = Math.max(4, Math.min(height - 12, amplitude));

        // Realistic hardware segmented LED bar appearance
        const gradient = ctx.createLinearGradient(0, centerY - barHeight / 2, 0, centerY + barHeight / 2);
        gradient.addColorStop(0, topColor);
        gradient.addColorStop(1, bottomColor);

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.roundRect(x, centerY - barHeight / 2, barWidth, barHeight, 2);
        ctx.fill();

        // Realistic segment dividers on active taller bars
        if (barHeight > 16) {
          ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
          for (let sy = centerY - barHeight / 2 + 5; sy < centerY + barHeight / 2 - 2; sy += 6) {
            ctx.fillRect(x, sy, barWidth, 1.2);
          }
        }
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
    <div className="w-full h-24 flex items-center justify-center relative overflow-hidden rounded-2xl bg-[#0b0b0e] border border-white/10 p-2 shadow-[inset_0_2px_6px_rgba(0,0,0,0.8),0_8px_20px_rgba(0,0,0,0.4)] backdrop-blur-md">
      {/* Realistic top specular glare reflection */}
      <div className="absolute top-0 inset-x-0 h-1/2 bg-gradient-to-b from-white/[0.04] to-transparent pointer-events-none" />

      <canvas
        ref={canvasRef}
        width={560}
        height={96}
        className="w-full h-full object-contain relative z-10"
      />

      {/* Realistic hardware status display pill */}
      <div className="absolute top-2 left-3 flex items-center gap-1.5 z-20">
        <span
          className={`w-1.5 h-1.5 rounded-full ${isActive
              ? mode === 'speaking'
                ? 'bg-emerald-400 shadow-[0_0_8px_#10b981]'
                : 'bg-amber-400 shadow-[0_0_8px_#f59e0b]'
              : 'bg-zinc-600'
            }`}
        />
        <span className="text-[9px] font-mono tracking-widest text-zinc-400 font-semibold uppercase">
          {mode === 'listening' ? 'LIVE AUDIO INPUT' : mode === 'speaking' ? 'NEURAL VOICE OUT' : 'SPECTRUM VU'}
        </span>
      </div>
    </div>
  );
};

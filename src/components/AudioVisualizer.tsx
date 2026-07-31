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

      // Color scheme based on state
      let primaryColor = '#3b82f6'; // Blue idle
      let secondaryColor = '#60a5fa';

      if (mode === 'listening') {
        primaryColor = '#06b6d4'; // Cyan listening
        secondaryColor = '#38bdf8';
      } else if (mode === 'transcribing' || mode === 'searching') {
        primaryColor = '#8b5cf6'; // Violet thinking
        secondaryColor = '#c084fc';
      } else if (mode === 'speaking') {
        primaryColor = '#10b981'; // Emerald speaking
        secondaryColor = '#34d399';
      }

      const barCount = 32;
      const barWidth = (width / barCount) * 0.6;
      const gap = (width / barCount) * 0.4;

      phase += isActive ? 0.08 : 0.02;

      for (let i = 0; i < barCount; i++) {
        const x = i * (barWidth + gap) + gap / 2;
        
        let amplitude = 6;
        if (isActive) {
          if (mode === 'listening') {
            amplitude = Math.sin(phase + i * 0.3) * 22 + Math.cos(phase * 1.5 + i * 0.2) * 18 + 25;
          } else if (mode === 'transcribing' || mode === 'searching') {
            amplitude = Math.sin(phase * 2 + i * 0.4) * 12 + 15;
          } else if (mode === 'speaking') {
            amplitude = Math.sin(phase * 2.5 + i * 0.2) * 28 + Math.cos(phase * 0.8 + i * 0.5) * 15 + 30;
          }
        } else {
          amplitude = Math.sin(phase + i * 0.2) * 4 + 6;
        }

        const barHeight = Math.max(4, amplitude);

        const gradient = ctx.createLinearGradient(0, centerY - barHeight / 2, 0, centerY + barHeight / 2);
        gradient.addColorStop(0, primaryColor);
        gradient.addColorStop(1, secondaryColor);

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.roundRect(x, centerY - barHeight / 2, barWidth, barHeight, barWidth / 2);
        ctx.fill();
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [isActive, mode]);

  return (
    <div className="w-full h-24 flex items-center justify-center relative overflow-hidden rounded-2xl glass-panel p-2">
      <canvas
        ref={canvasRef}
        width={480}
        height={96}
        className="w-full h-full object-contain"
      />
    </div>
  );
};

'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { BarChart3, PieChart as PieIcon, LineChart as LineIcon, Sparkles } from 'lucide-react';

export interface ChartDataset {
  label: string;
  data: number[];
}

export interface ChartDataSchema {
  type?: string;
  chartType: 'bar' | 'pie' | 'line';
  title: string;
  labels: string[];
  datasets: ChartDataset[];
}

// Helper function to extract hidden chart JSON from AI response text
export function parseChartDataFromResponse(responseText: string): {
  cleanText: string;
  chartData: ChartDataSchema | null;
} {
  if (!responseText) return { cleanText: '', chartData: null };

  let chartData: ChartDataSchema | null = null;
  let cleanText = responseText;

  // Search for ```json ... ``` code blocks
  const codeBlockRegex = /```(?:json)?\s*([\s\S]*?)\s*```/gi;
  let match;

  while ((match = codeBlockRegex.exec(responseText)) !== null) {
    const jsonStr = match[1].trim();
    try {
      const parsed = JSON.parse(jsonStr);
      if (
        parsed &&
        (parsed.type === 'chart' || parsed.chartType) &&
        Array.isArray(parsed.labels) &&
        Array.isArray(parsed.datasets)
      ) {
        chartData = {
          type: parsed.type || 'chart',
          chartType: (parsed.chartType || 'bar').toLowerCase() as 'bar' | 'pie' | 'line',
          title: parsed.title || 'Data Comparison',
          labels: parsed.labels,
          datasets: parsed.datasets,
        };
        cleanText = responseText.replace(match[0], '').trim();
        break;
      }
    } catch (e) {
      // Not a valid JSON chart block, continue
    }
  }

  // Fallback inline JSON match if code block tags were omitted
  if (!chartData) {
    const inlineJsonRegex = /\{\s*"type"\s*:\s*"chart"[\s\S]*?\}/gi;
    const inlineMatch = inlineJsonRegex.exec(responseText);
    if (inlineMatch) {
      try {
        const parsed = JSON.parse(inlineMatch[0]);
        if (Array.isArray(parsed.labels) && Array.isArray(parsed.datasets)) {
          chartData = {
            type: 'chart',
            chartType: (parsed.chartType || 'bar').toLowerCase() as 'bar' | 'pie' | 'line',
            title: parsed.title || 'Data Comparison',
            labels: parsed.labels,
            datasets: parsed.datasets,
          };
          cleanText = responseText.replace(inlineMatch[0], '').trim();
        }
      } catch (e) {}
    }
  }

  return { cleanText, chartData };
}

// Curated vibrant color palette
const VIBRANT_COLORS = [
  '#10b981', // Emerald
  '#f59e0b', // Amber
  '#06b6d4', // Cyan
  '#8b5cf6', // Violet
  '#f43f5e', // Rose
  '#3b82f6', // Blue
  '#14b8a6', // Teal
  '#eab308', // Yellow
];

interface DynamicChartProps {
  chartData: ChartDataSchema;
}

export const DynamicChart: React.FC<DynamicChartProps> = ({ chartData }) => {
  const [activeChartType, setActiveChartType] = useState<'bar' | 'pie' | 'line'>(
    chartData.chartType || 'bar'
  );

  if (!chartData || !chartData.labels || !chartData.datasets || chartData.datasets.length === 0) {
    return null;
  }

  // Transform labels and datasets into Recharts format: [{ name: "Label", Dataset1: 100, ... }]
  const formattedData = chartData.labels.map((label, idx) => {
    const item: Record<string, any> = { name: label };
    chartData.datasets.forEach((ds) => {
      item[ds.label || 'Value'] = ds.data && ds.data[idx] !== undefined ? ds.data[idx] : 0;
    });
    return item;
  });

  // Custom styled Tooltip component
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-900/95 border border-white/10 p-3 rounded-xl shadow-2xl backdrop-blur-md text-white text-xs">
          <p className="font-bold text-slate-200 mb-1.5 border-b border-white/10 pb-1">{label}</p>
          {payload.map((entry: any, i: number) => (
            <div key={i} className="flex items-center gap-2 my-1">
              <span
                className="w-2.5 h-2.5 rounded-full inline-block"
                style={{ backgroundColor: entry.color || entry.fill }}
              />
              <span className="text-slate-400">{entry.name}:</span>
              <span className="font-semibold text-amber-400">
                {typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}
              </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="w-full bg-black/40 border border-white/10 rounded-2xl p-4 md:p-5 flex flex-col gap-4 shadow-xl my-2 overflow-hidden backdrop-blur-md"
    >
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-white/10 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-slate-100 tracking-wide">
              {chartData.title || 'Data Comparison'}
            </h4>
            <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold block">
              Auto-Generated RAG Analytics
            </span>
          </div>
        </div>

        {/* Chart View Mode Switcher */}
        <div className="flex items-center p-0.5 bg-black/50 border border-white/10 rounded-xl text-xs self-end sm:self-auto">
          <button
            onClick={() => setActiveChartType('bar')}
            className={`px-2.5 py-1 rounded-lg transition-all flex items-center gap-1 font-semibold text-[11px] ${
              activeChartType === 'bar'
                ? 'bg-amber-500 text-slate-950 font-bold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Bar Chart"
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Bar</span>
          </button>

          <button
            onClick={() => setActiveChartType('pie')}
            className={`px-2.5 py-1 rounded-lg transition-all flex items-center gap-1 font-semibold text-[11px] ${
              activeChartType === 'pie'
                ? 'bg-amber-500 text-slate-950 font-bold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Pie / Donut Chart"
          >
            <PieIcon className="w-3.5 h-3.5" />
            <span>Pie</span>
          </button>

          <button
            onClick={() => setActiveChartType('line')}
            className={`px-2.5 py-1 rounded-lg transition-all flex items-center gap-1 font-semibold text-[11px] ${
              activeChartType === 'line'
                ? 'bg-amber-500 text-slate-950 font-bold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Line Trend Chart"
          >
            <LineIcon className="w-3.5 h-3.5" />
            <span>Line</span>
          </button>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="w-full h-64 md:h-72 pt-2">
        <ResponsiveContainer width="100%" height="100%">
          {activeChartType === 'bar' ? (
            <BarChart data={formattedData} margin={{ top: 10, right: 10, left: -15, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis
                dataKey="name"
                stroke="#64748b"
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                tickLine={false}
              />
              <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px', color: '#cbd5e1' }} />
              {chartData.datasets.map((ds, idx) => (
                <Bar
                  key={ds.label || idx}
                  dataKey={ds.label || 'Value'}
                  fill={VIBRANT_COLORS[idx % VIBRANT_COLORS.length]}
                  radius={[6, 6, 0, 0]}
                  animationDuration={800}
                />
              ))}
            </BarChart>
          ) : activeChartType === 'line' ? (
            <LineChart data={formattedData} margin={{ top: 10, right: 10, left: -15, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis
                dataKey="name"
                stroke="#64748b"
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                tickLine={false}
              />
              <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px', color: '#cbd5e1' }} />
              {chartData.datasets.map((ds, idx) => (
                <Line
                  key={ds.label || idx}
                  type="monotone"
                  dataKey={ds.label || 'Value'}
                  stroke={VIBRANT_COLORS[idx % VIBRANT_COLORS.length]}
                  strokeWidth={3}
                  dot={{ r: 5, fill: VIBRANT_COLORS[idx % VIBRANT_COLORS.length], strokeWidth: 2, stroke: '#070a13' }}
                  activeDot={{ r: 7, strokeWidth: 0 }}
                  animationDuration={800}
                />
              ))}
            </LineChart>
          ) : (
            <PieChart margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: '11px', color: '#cbd5e1' }} />
              <Pie
                data={formattedData.map((d) => ({
                  name: d.name,
                  value: d[chartData.datasets[0]?.label || 'Value'] || d[Object.keys(d)[1]] || 0,
                }))}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={85}
                paddingAngle={4}
                animationDuration={800}
              >
                {formattedData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={VIBRANT_COLORS[index % VIBRANT_COLORS.length]} />
                ))}
              </Pie>
            </PieChart>
          )}
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
};

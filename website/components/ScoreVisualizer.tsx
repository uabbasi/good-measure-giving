import React from 'react';

export type ScoreVariant = 'arch' | 'ring' | 'seal' | 'spider';

// GMG Score dimension max values (3-dimension framework)
const DIMENSION_MAX_VALUES = {
  credibility: 33,
  impact: 33,
  alignment: 34,
};

export interface DimensionScores {
  credibility: number;
  impact: number;
  alignment: number;
}

interface ScoreVisualizerProps {
  score: number;
  variant: ScoreVariant;
  size?: number;
  dimensions?: DimensionScores;
}

export const ScoreVisualizer: React.FC<ScoreVisualizerProps> = ({
  score,
  variant = 'arch',
  size = 200,
  dimensions
}) => {

  const getColor = (s: number) => {
    if (s >= 80) return '#10b981'; // Emerald-500
    if (s >= 60) return '#fbbf24'; // Amber-400
    return '#f43f5e'; // Rose-500
  };

  const color = getColor(score);

  // --- VARIANT 1: THE AMAL ARCH (Semi-Circle Gauge) ---
  if (variant === 'arch') {
    const r = 70;
    const strokeLen = Math.PI * r;
    const offset = strokeLen - (strokeLen * score) / 100;

    return (
      <div className="relative flex flex-col items-center justify-end h-32">
        <svg width="200" height="120" viewBox="0 0 200 120" className="overflow-visible">
          {/* Gradients */}
          <defs>
             <linearGradient id="archGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor={score >= 80 ? '#34d399' : score >= 60 ? '#fcd34d' : '#fb7185'} />
                <stop offset="100%" stopColor={color} />
             </linearGradient>
          </defs>

          {/* Background Track */}
          <path
            d="M 30 100 A 70 70 0 0 1 170 100"
            fill="none"
            stroke="#334155" // slate-700
            strokeWidth="12"
            strokeLinecap="round"
            opacity="0.2"
          />

          {/* Progress Arc */}
          <path
            d="M 30 100 A 70 70 0 0 1 170 100"
            fill="none"
            stroke="url(#archGradient)"
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={strokeLen}
            strokeDashoffset={offset}
            className="transition-all duration-1000 ease-out"
          />
        </svg>

        {/* Score Text positioned inside the arch */}
        <div className="absolute bottom-0 flex flex-col items-center">
          <div className="text-5xl font-bold font-merriweather tracking-tight text-white mb-1">
            {score}
          </div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
            out of 100
          </div>
        </div>
      </div>
    );
  }

  // --- VARIANT 2: THE DATA RING (Segmented Circle) ---
  if (variant === 'ring') {
    const r = 70;
    const circumference = 2 * Math.PI * r;
    const offset = circumference - (circumference * score) / 100;

    return (
      <div className="relative flex items-center justify-center h-40 w-40 mx-auto">
        <svg width="180" height="180" viewBox="0 0 180 180" className="transform -rotate-90">
           {/* Background Ring */}
           <circle cx="90" cy="90" r="70" stroke="#334155" strokeWidth="6" fill="none" opacity="0.2" />

           {/* Progress Ring */}
           <circle
             cx="90" cy="90" r="70"
             stroke={color}
             strokeWidth="6"
             fill="none"
             strokeDasharray={circumference}
             strokeDashoffset={offset}
             strokeLinecap="round"
             className="transition-all duration-1000 ease-out"
           />

           {/* Ticks overlay */}
           {Array.from({ length: 12 }).map((_, i) => (
             <line
               key={i}
               x1="90" y1="10" x2="90" y2="20"
               transform={`rotate(${i * 30} 90 90)`}
               stroke="white"
               strokeWidth="2"
               opacity="0.5"
             />
           ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-4xl font-bold font-merriweather text-white">{score}</span>
          <span className="text-[9px] uppercase tracking-widest text-slate-400 mt-1">Score</span>
        </div>
      </div>
    );
  }

  // --- VARIANT 3: THE GEOMETRIC SEAL (Octagon) ---
  if (variant === 'seal') {
    const path = "M100,20 L156.57,43.43 L180,100 L156.57,156.57 L100,180 L43.43,156.57 L20,100 L43.43,43.43 Z";
    const totalLen = 500; // Approx perimeter
    const offset = totalLen - (totalLen * score) / 100;

    return (
      <div className="relative flex items-center justify-center h-48 w-48 mx-auto">
        <svg width="200" height="200" viewBox="0 0 200 200" className="transform -rotate-90">
          {/* Track */}
          <path d={path} stroke="#334155" strokeWidth="4" fill="none" opacity="0.3" />

          {/* Fill */}
          <path
            d={path}
            stroke={color}
            strokeWidth="4"
            fill="none"
            strokeDasharray={totalLen}
            strokeDashoffset={offset}
            className="transition-all duration-1000 ease-out"
          />

          {/* Decorative Dots */}
          <circle cx="100" cy="20" r="2" fill={score > 0 ? color : '#334155'} />
          <circle cx="156.57" cy="43.43" r="2" fill={score > 12 ? color : '#334155'} />
          <circle cx="180" cy="100" r="2" fill={score > 25 ? color : '#334155'} />
          <circle cx="156.57" cy="156.57" r="2" fill={score > 37 ? color : '#334155'} />
          <circle cx="100" cy="180" r="2" fill={score > 50 ? color : '#334155'} />
          <circle cx="43.43" cy="156.57" r="2" fill={score > 62 ? color : '#334155'} />
          <circle cx="20" cy="100" r="2" fill={score > 75 ? color : '#334155'} />
          <circle cx="43.43" cy="43.43" r="2" fill={score > 87 ? color : '#334155'} />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="text-5xl font-bold font-merriweather text-white mb-1">{score}</div>
          <div className="px-2 py-0.5 rounded bg-slate-800 text-[9px] font-bold uppercase tracking-widest text-emerald-400 border border-slate-700">
             Impact
          </div>
        </div>
      </div>
    );
  }

  // --- VARIANT 4: THE SPIDER CHART (Radar with 3 dimensions) ---
  if (variant === 'spider') {
    // Default dimensions if not provided (derive from score proportionally)
    const dims = dimensions || {
      credibility: Math.round((score / 100) * DIMENSION_MAX_VALUES.credibility),
      impact: Math.round((score / 100) * DIMENSION_MAX_VALUES.impact),
      alignment: Math.round((score / 100) * DIMENSION_MAX_VALUES.alignment),
    };

    const cx = 140;  // Center X
    const cy = 120;  // Center Y
    const maxR = 55;

    // Calculate points for each axis (3 axes at 120° intervals)
    const getPoint = (value: number, maxValue: number, angle: number) => {
      const r = (value / maxValue) * maxR;
      const rad = (angle - 90) * (Math.PI / 180);
      return {
        x: cx + r * Math.cos(rad),
        y: cy + r * Math.sin(rad)
      };
    };

    const points = [
      getPoint(dims.credibility, DIMENSION_MAX_VALUES.credibility, 0),     // Top
      getPoint(dims.impact, DIMENSION_MAX_VALUES.impact, 120),             // Bottom-right
      getPoint(dims.alignment, DIMENSION_MAX_VALUES.alignment, 240),       // Bottom-left
    ];

    // Grid lines (triangular)
    const gridLevels = [0.25, 0.5, 0.75, 1];

    return (
      <div className="relative flex items-center justify-center h-56 w-full mx-auto">
        <svg width="280" height="240" viewBox="0 0 280 240" className="overflow-visible">
          {/* Grid triangles */}
          {gridLevels.map((level, i) => {
            const r = maxR * level;
            const gridPoints = [
              { x: cx, y: cy - r },
              { x: cx + r * Math.cos(30 * Math.PI / 180), y: cy + r * Math.sin(30 * Math.PI / 180) },
              { x: cx - r * Math.cos(30 * Math.PI / 180), y: cy + r * Math.sin(30 * Math.PI / 180) },
            ];
            return (
              <polygon
                key={i}
                points={gridPoints.map(p => `${p.x},${p.y}`).join(' ')}
                fill="none"
                stroke="#475569"
                strokeWidth="1"
                opacity={0.25}
              />
            );
          })}

          {/* Axis lines */}
          <line x1={cx} y1={cy} x2={cx} y2={cy - maxR} stroke="#475569" strokeWidth="1" opacity="0.25" />
          <line x1={cx} y1={cy} x2={cx + maxR * Math.cos(30 * Math.PI / 180)} y2={cy + maxR * Math.sin(30 * Math.PI / 180)} stroke="#475569" strokeWidth="1" opacity="0.25" />
          <line x1={cx} y1={cy} x2={cx - maxR * Math.cos(30 * Math.PI / 180)} y2={cy + maxR * Math.sin(30 * Math.PI / 180)} stroke="#475569" strokeWidth="1" opacity="0.25" />

          {/* Data polygon fill */}
          <polygon
            points={points.map(p => `${p.x},${p.y}`).join(' ')}
            fill={color}
            fillOpacity="0.25"
            className="transition-all duration-700 ease-out"
          />

          {/* Data polygon stroke */}
          <polygon
            points={points.map(p => `${p.x},${p.y}`).join(' ')}
            fill="none"
            stroke={color}
            strokeWidth="2.5"
            className="transition-all duration-700 ease-out"
          />

          {/* Data points */}
          {points.map((p, i) => (
            <circle
              key={i}
              cx={p.x}
              cy={p.y}
              r="5"
              fill={color}
              stroke="white"
              strokeWidth="2"
              className="transition-all duration-700 ease-out"
            />
          ))}

          {/* Axis labels */}
          {/* Top: Credibility */}
          <text x={cx} y={cy - maxR - 28} textAnchor="middle" className="fill-slate-400 text-[10px] font-bold uppercase tracking-wide">
            Credibility
          </text>
          <text x={cx} y={cy - maxR - 16} textAnchor="middle" className="fill-white text-[12px] font-bold">
            {dims.credibility}/33
          </text>

          {/* Bottom-right: Impact */}
          <text x={cx + maxR * Math.cos(30 * Math.PI / 180) + 12} y={cy + maxR * Math.sin(30 * Math.PI / 180) - 8} textAnchor="start" className="fill-slate-400 text-[10px] font-bold uppercase tracking-wide">
            Impact
          </text>
          <text x={cx + maxR * Math.cos(30 * Math.PI / 180) + 12} y={cy + maxR * Math.sin(30 * Math.PI / 180) + 6} textAnchor="start" className="fill-white text-[12px] font-bold">
            {dims.impact}/33
          </text>

          {/* Bottom-left: Alignment */}
          <text x={cx - maxR * Math.cos(30 * Math.PI / 180) - 12} y={cy + maxR * Math.sin(30 * Math.PI / 180) - 8} textAnchor="end" className="fill-slate-400 text-[10px] font-bold uppercase tracking-wide">
            Alignment
          </text>
          <text x={cx - maxR * Math.cos(30 * Math.PI / 180) - 12} y={cy + maxR * Math.sin(30 * Math.PI / 180) + 6} textAnchor="end" className="fill-white text-[12px] font-bold">
            {dims.alignment}/34
          </text>
        </svg>

        {/* Center score */}
        <div className="absolute flex flex-col items-center justify-center pointer-events-none" style={{ left: '50%', top: '45%', transform: 'translate(-50%, -50%)' }}>
          <div className="text-4xl font-bold font-merriweather text-white">{score}</div>
          <div className="text-[9px] uppercase tracking-widest text-slate-400 mt-0.5">total</div>
        </div>
      </div>
    );
  }

  return null;
};

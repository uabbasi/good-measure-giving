/**
 * Pillar Scatter Plot - 2x2 matrix using actual pillar scores
 *
 * X-axis: Impact Potential (Effectiveness + Fit, 0-50)
 * Y-axis: Operational Quality (Trust + Evidence, 0-50)
 *
 * Quadrants:
 * - Top-right: Strong operations + High impact (best bets)
 * - Top-left: Strong operations, conventional impact
 * - Bottom-right: High potential, needs operational maturity
 * - Bottom-left: Early stage / developing
 */

import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';

interface CharityPoint {
  id: string;
  name: string;
  amalScore: number;
  walletTag: string;
  pillarScores: {
    trust: number;
    evidence: number;
    effectiveness: number;
    fit: number;
  };
  category?: string | null;
}

interface PillarScatterPlotProps {
  charities: CharityPoint[];
  height?: string;
}

export const PillarScatterPlot: React.FC<PillarScatterPlotProps> = ({
  charities,
  height = 'aspect-square',
}) => {
  const { isDark } = useLandingTheme();
  const [hoveredCharity, setHoveredCharity] = useState<string | null>(null);

  const getWalletColor = (tag?: string) => {
    if (tag?.includes('ZAKAT')) return isDark ? 'bg-emerald-500' : 'bg-emerald-500';
    return isDark ? 'bg-slate-400' : 'bg-slate-400';
  };

  const getWalletLabel = (tag?: string) => {
    if (tag?.includes('ZAKAT')) return 'Zakat Eligible';
    return 'Sadaqah';
  };

  return (
    <div className={`rounded-2xl p-6 md:p-8 ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
      {/* Matrix Grid */}
      <div className={`relative ${height} max-w-2xl mx-auto`}>
        {/* Background Grid */}
        <div className={`absolute inset-0 rounded-lg ${isDark ? 'border border-slate-700 bg-slate-800' : 'border border-slate-200 bg-slate-50'}`}>
          {/* Quadrant Labels */}
          <div className={`absolute top-3 left-3 text-[10px] font-bold uppercase leading-tight ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Strong Ops<br/>Lower Potential
          </div>
          <div className={`absolute top-3 right-3 text-[10px] font-bold uppercase leading-tight text-right ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
            Top<br/>Performers
          </div>
          <div className={`absolute bottom-3 left-3 text-[10px] font-bold uppercase leading-tight ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Early<br/>Stage
          </div>
          <div className={`absolute bottom-3 right-3 text-[10px] font-bold uppercase leading-tight text-right ${isDark ? 'text-blue-400' : 'text-blue-500'}`}>
            High Potential<br/>Needs Support
          </div>

          {/* Center Lines - at 25 (midpoint of 0-50 scale) */}
          <div className={`absolute left-0 w-full h-px border-t border-dashed ${isDark ? 'border-slate-600' : 'border-slate-300'}`} style={{ top: '50%' }}></div>
          <div className={`absolute top-0 h-full w-px border-l border-dashed ${isDark ? 'border-slate-600' : 'border-slate-300'}`} style={{ left: '50%' }}></div>
        </div>

        {/* Charity Dots */}
        {charities.map((charity) => {
          // X = Effectiveness + Fit (impact potential)
          const impactPotential = charity.pillarScores.effectiveness + charity.pillarScores.fit;
          // Y = Trust + Evidence (operational quality)
          const operationalQuality = charity.pillarScores.trust + charity.pillarScores.evidence;

          // Scale to percentage (0-50 maps to 0-100%)
          const x = (impactPotential / 50) * 100;
          const y = (operationalQuality / 50) * 100;
          const isHovered = hoveredCharity === charity.id;

          return (
            <Link
              key={charity.id}
              to={`/charity/${charity.id}`}
              className="absolute transform -translate-x-1/2 translate-y-1/2 z-10 group"
              style={{
                left: `${x}%`,
                bottom: `${y}%`,
              }}
              onMouseEnter={() => setHoveredCharity(charity.id)}
              onMouseLeave={() => setHoveredCharity(null)}
            >
              <div
                className={`w-3.5 h-3.5 rounded-full border-2 border-white shadow-md transition-all duration-200 ${getWalletColor(charity.walletTag)} ${isHovered ? 'scale-150 ring-4 ring-slate-900/10' : 'hover:scale-125'}`}
              />
              {isHovered && (
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 bg-slate-900 text-white text-xs rounded-lg p-3 shadow-xl z-20 pointer-events-none">
                  <div className="font-bold mb-1 truncate">{charity.name}</div>
                  <div className="flex justify-between text-slate-300 mb-1">
                    <span>Score: {charity.amalScore}</span>
                    <span>{getWalletLabel(charity.walletTag)}</span>
                  </div>
                  <div className="text-slate-400 text-[10px] grid grid-cols-2 gap-x-2">
                    <span>Trust: {charity.pillarScores.trust}/25</span>
                    <span>Evidence: {charity.pillarScores.evidence}/25</span>
                    <span>Effectiveness: {charity.pillarScores.effectiveness}/25</span>
                    <span>Fit: {charity.pillarScores.fit}/25</span>
                  </div>
                  <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-full">
                    <div className="border-8 border-transparent border-t-slate-900"></div>
                  </div>
                </div>
              )}
            </Link>
          );
        })}

        {/* Axis Labels */}
        <div className={`absolute -bottom-8 left-1/2 -translate-x-1/2 text-xs font-bold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          Impact Potential →
        </div>
        <div className={`absolute -left-12 top-1/2 -translate-y-1/2 -rotate-90 text-xs font-bold uppercase tracking-wider whitespace-nowrap ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          Operational Quality →
        </div>
      </div>

      {/* Legend */}
      <div className={`flex flex-wrap justify-center gap-6 mt-10 pt-6 border-t ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
          <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Zakat Eligible</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-slate-400"></div>
          <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Sadaqah</span>
        </div>
      </div>

      <p className={`text-center text-xs mt-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
        Hover over dots to see details. Click to view full evaluation.
      </p>
    </div>
  );
};

export default PillarScatterPlot;

/**
 * Impact Matrix Component
 *
 * 2x2 matrix visualization showing charities plotted by:
 * - X-axis: Execution Capability (Tier 2)
 * - Y-axis: Strategic Fit (Tier 1)
 *
 * Reusable for both public methodology page and admin dashboard.
 */

import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';

interface CharityPoint {
  id: string;
  ein?: string;
  name: string;
  amal_score: number;
  tier_1_score: number;
  tier_2_score: number;
  wallet_tag: string;
}

interface ImpactMatrixProps {
  charities: CharityPoint[];
  linkToCharityPage?: (charity: CharityPoint) => string;
  showLegend?: boolean;
  height?: string;
}

export const ImpactMatrix: React.FC<ImpactMatrixProps> = ({
  charities,
  linkToCharityPage = (charity) => `/charity/${charity.id}`,
  showLegend = true,
  height = 'aspect-square',
}) => {
  const { isDark } = useLandingTheme();
  const [hoveredCharity, setHoveredCharity] = useState<string | null>(null);

  const getWalletColor = (tag?: string) => {
    if (tag?.includes('ZAKAT-ELIGIBLE') || tag?.includes('ZAKAT-CONSENSUS') || tag?.includes('ZAKAT-TRADITIONAL')) return 'bg-emerald-500';
    if (tag?.includes('SADAQAH-STRATEGIC') || tag?.includes('STRATEGIC-SADAQAH') || tag?.includes('SADAQAH-CATALYTIC')) return 'bg-indigo-500';
    if (tag?.includes('INSUFFICIENT-DATA')) return 'bg-slate-400';
    return 'bg-slate-400';
  };

  const getWalletLabel = (tag?: string) => {
    const cleanTag = tag?.replace(/[\[\]]/g, '') || '';

    if (cleanTag.includes('ZAKAT-ELIGIBLE') || cleanTag.includes('ZAKAT-CONSENSUS') || cleanTag.includes('ZAKAT-TRADITIONAL')) return 'Zakat Eligible';
    if (cleanTag.includes('SADAQAH-STRATEGIC') || cleanTag.includes('STRATEGIC-SADAQAH') || cleanTag.includes('SADAQAH-CATALYTIC')) return 'Strategic Sadaqah';
    if (cleanTag.includes('INSUFFICIENT-DATA')) return 'Insufficient Data';
    if (cleanTag.includes('SADAQAH-GENERAL')) return 'General Sadaqah';
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
            High Potential<br/>Needs Support
          </div>
          <div className={`absolute top-3 right-3 text-[10px] font-bold uppercase leading-tight text-right ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
            Top<br/>Performers
          </div>
          <div className={`absolute bottom-3 left-3 text-[10px] font-bold uppercase leading-tight ${isDark ? 'text-rose-400' : 'text-rose-400'}`}>
            Early<br/>Stage
          </div>
          <div className={`absolute bottom-3 right-3 text-[10px] font-bold uppercase leading-tight text-right ${isDark ? 'text-blue-400' : 'text-blue-400'}`}>
            Strong Ops<br/>Less Strategic
          </div>

          {/* Center Lines - 50% = midpoint of 50-point scale (25,25) */}
          <div className={`absolute left-0 w-full h-px border-t border-dashed ${isDark ? 'bg-slate-600 border-slate-600' : 'bg-slate-300 border-slate-300'}`} style={{ top: '50%' }}></div>
          <div className={`absolute top-0 h-full w-px border-l border-dashed ${isDark ? 'bg-slate-600 border-slate-600' : 'bg-slate-300 border-slate-300'}`} style={{ left: '50%' }}></div>
        </div>

        {/* Charity Dots */}
        {charities.map((charity) => {
          const x = (charity.tier_2_score / 50) * 100;
          const y = (charity.tier_1_score / 50) * 100;
          const isHovered = hoveredCharity === charity.id;

          return (
            <Link
              key={charity.id}
              to={linkToCharityPage(charity)}
              className="absolute transform -translate-x-1/2 translate-y-1/2 z-10 group"
              style={{
                left: `${x}%`,
                bottom: `${y}%`,
              }}
              onMouseEnter={() => setHoveredCharity(charity.id)}
              onMouseLeave={() => setHoveredCharity(null)}
            >
              <div
                className={`w-4 h-4 rounded-full border-2 border-white shadow-md transition-all duration-200 ${getWalletColor(charity.wallet_tag)} ${isHovered ? 'scale-150 ring-4 ring-slate-900/10' : 'hover:scale-125'}`}
              />
              {isHovered && (
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 bg-slate-900 text-white text-xs rounded-lg p-3 shadow-xl z-20">
                  <div className="font-bold mb-1 truncate">{charity.name}</div>
                  <div className="flex justify-between text-slate-300">
                    <span>Score: {charity.amal_score}</span>
                    <span>{getWalletLabel(charity.wallet_tag)}</span>
                  </div>
                  <div className="text-slate-400 mt-1">
                    Strategic: {charity.tier_1_score}/50 · Execution: {charity.tier_2_score}/50
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
          Execution Capability →
        </div>
        <div className={`absolute -left-8 top-1/2 -translate-y-1/2 -rotate-90 text-xs font-bold uppercase tracking-wider whitespace-nowrap ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          Strategic Fit →
        </div>
      </div>

      {/* Legend */}
      {showLegend && (
        <>
          <div className={`flex flex-wrap justify-center gap-4 mt-8 pt-6 border-t ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
              <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Zakat Eligible</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-amber-500"></div>
              <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Sadaqah (Strategic)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-slate-400"></div>
              <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Sadaqah</span>
            </div>
          </div>

          <p className={`text-center text-xs mt-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Hover over dots to see charity details. Click to view full evaluation.
          </p>
        </>
      )}
    </div>
  );
};

export default ImpactMatrix;

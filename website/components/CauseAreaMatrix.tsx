/**
 * Cause Area Matrix - Interactive 2x2 with drill-down
 *
 * Initial view: Bubbles representing cause areas, positioned by average pillar scores
 * Click to drill down: Shows all charities within that cause area
 *
 * X-axis: Alignment (0-50)
 * Y-axis: Impact (0-50)
 */

import React, { useState, useMemo, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { ArrowLeft, Users } from 'lucide-react';

interface CharityWithPillars {
  id: string;
  name: string;
  amalScore: number;
  walletTag: string;
  category: string;
  pillarScores: {
    impact: number;
    alignment: number;
    dataConfidence?: number;
  };
  totalRevenue?: number | null;
}

interface CauseAreaMatrixProps {
  charities: CharityWithPillars[];
}

// Map granular categories to consolidated groups (6-7 major cause areas)
const CATEGORY_GROUPS: Record<string, string> = {
  'HUMANITARIAN': 'HUMANITARIAN',
  'BASIC_NEEDS': 'HUMANITARIAN',
  'MEDICAL_HEALTH': 'HEALTH',
  'EDUCATION_K12_RELIGIOUS': 'EDUCATION',
  'EDUCATION_HIGHER_RELIGIOUS': 'EDUCATION',
  'EDUCATION_INTERNATIONAL': 'EDUCATION',
  'RELIGIOUS_CONGREGATION': 'MOSQUES_RELIGIOUS',
  'RELIGIOUS_OUTREACH': 'MOSQUES_RELIGIOUS',
  'CIVIL_RIGHTS_LEGAL': 'CIVIL_RIGHTS_ADVOCACY',
  'ADVOCACY_CIVIC': 'CIVIL_RIGHTS_ADVOCACY',
  'RESEARCH_POLICY': 'CIVIL_RIGHTS_ADVOCACY',
  'SOCIAL_SERVICES': 'SOCIAL_SERVICES',
  'WOMENS_SERVICES': 'SOCIAL_SERVICES',
  'PHILANTHROPY_GRANTMAKING': 'OTHER',
  'ENVIRONMENT_CLIMATE': 'OTHER',
  'MEDIA_JOURNALISM': 'OTHER',
  'OTHER': 'OTHER',
};

// Friendly labels for consolidated groups
const CATEGORY_LABELS: Record<string, string> = {
  'HUMANITARIAN': 'Humanitarian',
  'HEALTH': 'Health',
  'EDUCATION': 'Education',
  'MOSQUES_RELIGIOUS': 'Mosques & Faith',
  'CIVIL_RIGHTS_ADVOCACY': 'Civil Rights',
  'SOCIAL_SERVICES': 'Social Services',
  'OTHER': 'Other',
};

// Colors for consolidated cause areas
const CAUSE_COLORS: Record<string, string> = {
  'HUMANITARIAN': 'bg-rose-500',
  'HEALTH': 'bg-pink-500',
  'EDUCATION': 'bg-amber-500',
  'MOSQUES_RELIGIOUS': 'bg-purple-500',
  'CIVIL_RIGHTS_ADVOCACY': 'bg-blue-500',
  'SOCIAL_SERVICES': 'bg-teal-500',
  'OTHER': 'bg-slate-500',
};

export const CauseAreaMatrix: React.FC<CauseAreaMatrixProps> = ({ charities }) => {
  const { isDark } = useLandingTheme();
  const [selectedCause, setSelectedCause] = useState<string | null>(null);
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);

  // Animation state
  const [explodeFrom, setExplodeFrom] = useState<{ x: number; y: number } | null>(null);
  const [isAnimating, setIsAnimating] = useState(false);

  // Aggregate charities by consolidated cause area
  const causeAggregates = useMemo(() => {
    const byCause: Record<string, {
      charities: CharityWithPillars[];
      avgImpact: number;
      avgAlignment: number;
      totalRevenue: number;
      topCharity: CharityWithPillars | null;
    }> = {};

    charities.forEach(c => {
      // Map granular category to consolidated group
      const originalCat = c.category || 'OTHER';
      const cat = CATEGORY_GROUPS[originalCat] || 'OTHER';
      if (!byCause[cat]) {
        byCause[cat] = {
          charities: [],
          avgImpact: 0,
          avgAlignment: 0,
          totalRevenue: 0,
          topCharity: null,
        };
      }
      byCause[cat].charities.push(c);
      byCause[cat].avgImpact += c.pillarScores.impact;
      byCause[cat].avgAlignment += c.pillarScores.alignment;
      byCause[cat].totalRevenue += c.totalRevenue || 0;
      if (!byCause[cat].topCharity || c.amalScore > byCause[cat].topCharity.amalScore) {
        byCause[cat].topCharity = c;
      }
    });

    // Calculate averages
    return Object.entries(byCause)
      .map(([category, data]) => ({
        category,
        label: CATEGORY_LABELS[category] || category,
        color: CAUSE_COLORS[category] || 'bg-slate-500',
        count: data.charities.length,
        charities: data.charities.sort((a, b) => b.amalScore - a.amalScore),
        avgImpact: data.avgImpact / data.charities.length,
        avgAlignment: data.avgAlignment / data.charities.length,
        totalRevenue: data.totalRevenue,
        topCharity: data.topCharity,
      }))
      .filter(c => c.count >= 2) // Only show causes with 2+ charities
      .sort((a, b) => b.count - a.count);
  }, [charities]);

  // Calculate bounds for "zoomed in" view - normalize to actual data range
  const bounds = useMemo(() => {
    if (causeAggregates.length === 0) return { minX: 0, maxX: 50, minY: 0, maxY: 50 };

    const impacts = causeAggregates.map(c => c.avgAlignment);
    const ops = causeAggregates.map(c => c.avgImpact);

    // Get actual range with 10% padding
    const minX = Math.min(...impacts);
    const maxX = Math.max(...impacts);
    const minY = Math.min(...ops);
    const maxY = Math.max(...ops);

    const padX = (maxX - minX) * 0.15 || 5;
    const padY = (maxY - minY) * 0.15 || 5;

    return {
      minX: Math.max(0, minX - padX),
      maxX: Math.min(50, maxX + padX),
      minY: Math.max(0, minY - padY),
      maxY: Math.min(50, maxY + padY),
    };
  }, [causeAggregates]);

  // Normalize a value to 0-100% based on bounds
  const normalizeX = (val: number) => {
    const range = bounds.maxX - bounds.minX;
    if (range === 0) return 50;
    return ((val - bounds.minX) / range) * 100;
  };

  const normalizeY = (val: number) => {
    const range = bounds.maxY - bounds.minY;
    if (range === 0) return 50;
    return ((val - bounds.minY) / range) * 100;
  };

  // Get charities for selected cause
  const selectedCauseData = selectedCause
    ? causeAggregates.find(c => c.category === selectedCause)
    : null;

  // Calculate bubble size (based on charity count, log scale)
  const getBubbleSize = (count: number) => {
    const minSize = 40;
    const maxSize = 80;
    const maxCount = Math.max(...causeAggregates.map(c => c.count));
    const normalized = Math.log(count + 1) / Math.log(maxCount + 1);
    return minSize + normalized * (maxSize - minSize);
  };

  // Calculate charity dot size based on revenue - wider range for visibility
  const getCharityDotSize = (revenue: number | null | undefined, allCharities: CharityWithPillars[]) => {
    const minSize = 10;
    const maxSize = 48;

    if (!revenue || revenue <= 0) return minSize;

    const revenues = allCharities
      .map(c => c.totalRevenue || 0)
      .filter(r => r > 0);

    if (revenues.length === 0) return minSize;

    const maxRevenue = Math.max(...revenues);
    const minRevenue = Math.min(...revenues);

    if (maxRevenue === minRevenue) return (minSize + maxSize) / 2;

    // Use log scale for better distribution
    const logMin = Math.log(minRevenue + 1);
    const logMax = Math.log(maxRevenue + 1);
    const logVal = Math.log(revenue + 1);

    const normalized = (logVal - logMin) / (logMax - logMin);
    return minSize + normalized * (maxSize - minSize);
  };

  // Calculate bounds for charity drill-down view - spread across full chart
  const charityBounds = useMemo(() => {
    if (!selectedCauseData) return null;

    const charities = selectedCauseData.charities;
    if (charities.length === 0) return null;

    const xValues = charities.map(c => c.pillarScores.alignment);
    const yValues = charities.map(c => c.pillarScores.impact);

    const minX = Math.min(...xValues);
    const maxX = Math.max(...xValues);
    const minY = Math.min(...yValues);
    const maxY = Math.max(...yValues);

    // Add 10% padding on each side
    const padX = Math.max((maxX - minX) * 0.1, 2);
    const padY = Math.max((maxY - minY) * 0.1, 2);

    return {
      minX: minX - padX,
      maxX: maxX + padX,
      minY: minY - padY,
      maxY: maxY + padY,
    };
  }, [selectedCauseData]);

  // Normalize charity positions to spread across full chart
  const normalizeCharityX = (val: number) => {
    if (!charityBounds) return 50;
    const range = charityBounds.maxX - charityBounds.minX;
    if (range === 0) return 50;
    return ((val - charityBounds.minX) / range) * 100;
  };

  const normalizeCharityY = (val: number) => {
    if (!charityBounds) return 50;
    const range = charityBounds.maxY - charityBounds.minY;
    if (range === 0) return 50;
    return ((val - charityBounds.minY) / range) * 100;
  };

  const getWalletColor = (tag?: string) => {
    if (tag?.includes('ZAKAT')) return 'bg-emerald-500';
    return 'bg-slate-400';
  };

  // Handle cause selection with animation
  const handleCauseClick = (category: string, x: number, y: number) => {
    setExplodeFrom({ x, y });
    setIsAnimating(true);
    setSelectedCause(category);

    // Allow animation to play
    setTimeout(() => {
      setIsAnimating(false);
    }, 50);
  };

  // Handle back button
  const handleBack = () => {
    setSelectedCause(null);
    setExplodeFrom(null);
    setIsAnimating(false);
  };

  return (
    <div className={`rounded-2xl border ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
      {/* Header */}
      <div className={`px-6 py-4 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
        {selectedCause ? (
          <div className="flex items-center gap-3">
            <button
              onClick={handleBack}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                isDark ? 'bg-slate-800 hover:bg-slate-700 text-slate-300' : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
              }`}
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </button>
            <div>
              <h3 className={`font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                {selectedCauseData?.label}
              </h3>
              <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                {selectedCauseData?.count} charities • sized by budget
              </p>
            </div>
          </div>
        ) : (
          <div>
            <h3 className={`font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
              Charities by Cause Area
            </h3>
            <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              Click a bubble to see all charities in that cause
            </p>
          </div>
        )}
      </div>

      {/* Matrix */}
      <div className="p-6 pl-24">
        <div className="relative aspect-square max-w-lg mx-auto">
          {/* Background Grid */}
          <div className={`absolute inset-0 rounded-lg ${isDark ? 'border border-slate-700 bg-slate-800' : 'border border-slate-200 bg-slate-50'}`}>
            {/* Corner gradient hint for "best" area */}
            <div className={`absolute top-0 right-0 w-1/3 h-1/3 rounded-tr-lg ${isDark ? 'bg-gradient-to-bl from-emerald-900/20 to-transparent' : 'bg-gradient-to-bl from-emerald-100/50 to-transparent'}`}></div>

            {/* Direction indicators */}
            <div className={`absolute top-2 right-2 text-[9px] font-medium text-right ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
              Best →
            </div>
            <div className={`absolute bottom-2 left-2 text-[9px] font-medium ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              ← Lower scores
            </div>
          </div>

          {/* Bubbles/Dots */}
          {selectedCause && selectedCauseData ? (
            // Drilled-down view: individual charities with explosion animation
            selectedCauseData.charities.map((charity, index) => {
              // Normalize positions to spread charities across the full chart
              const rawX = charity.pillarScores.alignment;
              const rawY = charity.pillarScores.impact;
              const finalX = normalizeCharityX(rawX);
              const finalY = normalizeCharityY(rawY);
              const isHovered = hoveredItem === charity.id;
              const dotSize = getCharityDotSize(charity.totalRevenue, selectedCauseData.charities);

              // Use explodeFrom position if animating, otherwise final position
              const currentX = isAnimating && explodeFrom ? explodeFrom.x : finalX;
              const currentY = isAnimating && explodeFrom ? explodeFrom.y : finalY;

              return (
                <Link
                  key={charity.id}
                  to={`/charity/${charity.id}`}
                  className={`absolute transform -translate-x-1/2 translate-y-1/2 ${isHovered ? 'z-50' : 'z-10'}`}
                  style={{
                    left: `${currentX}%`,
                    bottom: `${currentY}%`,
                    transition: isAnimating ? 'none' : `all 500ms cubic-bezier(0.34, 1.56, 0.64, 1) ${index * 20}ms`,
                  }}
                  onMouseEnter={() => setHoveredItem(charity.id)}
                  onMouseLeave={() => setHoveredItem(null)}
                >
                  <div
                    className={`rounded-full border-2 border-white shadow-md transition-transform duration-200 ${getWalletColor(charity.walletTag)} ${isHovered ? 'scale-125 ring-4 ring-slate-900/10' : 'hover:scale-110'}`}
                    style={{
                      width: dotSize,
                      height: dotSize,
                      opacity: isAnimating ? 0 : 1,
                      transform: isAnimating ? 'scale(0)' : 'scale(1)',
                      transition: isAnimating ? 'none' : `opacity 300ms ${index * 20}ms, transform 500ms cubic-bezier(0.34, 1.56, 0.64, 1) ${index * 20}ms`,
                    }}
                  />
                  {isHovered && (
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 bg-slate-900 text-white text-xs rounded-lg p-3 shadow-xl z-30 pointer-events-none">
                      <div className="font-bold mb-1 truncate">{charity.name}</div>
                      <div className="flex justify-between text-slate-300">
                        <span>Score: {charity.amalScore}</span>
                        <span>{charity.walletTag?.includes('ZAKAT') ? 'Zakat' : 'Sadaqah'}</span>
                      </div>
                      {charity.totalRevenue && (
                        <div className="text-slate-400 text-[10px] mt-1">
                          ${(charity.totalRevenue / 1000000).toFixed(1)}M budget
                        </div>
                      )}
                      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-full">
                        <div className="border-8 border-transparent border-t-slate-900"></div>
                      </div>
                    </div>
                  )}
                </Link>
              );
            })
          ) : (
            // Aggregated view: cause area bubbles
            causeAggregates.map((cause) => {
              const x = normalizeX(cause.avgAlignment);
              const y = normalizeY(cause.avgImpact);
              const size = getBubbleSize(cause.count);
              const isHovered = hoveredItem === cause.category;

              return (
                <button
                  key={cause.category}
                  className={`absolute transform -translate-x-1/2 translate-y-1/2 ${isHovered ? 'z-50' : 'z-10'} group`}
                  style={{ left: `${x}%`, bottom: `${y}%` }}
                  onClick={() => handleCauseClick(cause.category, x, y)}
                  onMouseEnter={() => setHoveredItem(cause.category)}
                  onMouseLeave={() => setHoveredItem(null)}
                >
                  <div
                    className={`rounded-full border-3 border-white shadow-lg transition-all duration-200 flex items-center justify-center ${cause.color} ${isHovered ? 'scale-110 ring-4 ring-slate-900/20' : 'hover:scale-105'}`}
                    style={{ width: size, height: size }}
                  >
                    <span className="text-white text-xs font-bold">{cause.count}</span>
                  </div>
                  {isHovered && (
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-52 bg-slate-900 text-white text-xs rounded-lg p-3 shadow-xl z-30 pointer-events-none">
                      <div className="font-bold mb-1">{cause.label}</div>
                      <div className="text-slate-300 mb-2">{cause.count} charities evaluated</div>
                      <div className="text-slate-400 text-[10px]">
                        <div>Avg Score: {Math.round((cause.avgAlignment + cause.avgImpact))} / 100</div>
                        <div>Top: {cause.topCharity?.name} ({cause.topCharity?.amalScore})</div>
                      </div>
                      <div className="mt-2 text-emerald-400 text-[10px] font-medium">Click to explore →</div>
                      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-full">
                        <div className="border-8 border-transparent border-t-slate-900"></div>
                      </div>
                    </div>
                  )}
                </button>
              );
            })
          )}

          {/* Axis Labels */}
          <div className={`absolute -bottom-8 left-1/2 -translate-x-1/2 text-center ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            <div className="text-[10px] font-bold uppercase tracking-wider">Alignment →</div>
            <div className={`text-[8px] ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Donor Fit</div>
          </div>
          <div className={`absolute -left-[4.5rem] top-1/2 -translate-y-1/2 -rotate-90 text-center whitespace-nowrap ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            <div className="text-[10px] font-bold uppercase tracking-wider">Impact →</div>
            <div className={`text-[8px] ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Effectiveness</div>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className={`px-6 pb-6`}>
        {selectedCause ? (
          <div className={`flex flex-wrap justify-center gap-4 pt-4 border-t ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
              <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Zakat Eligible</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-slate-400"></div>
              <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Sadaqah</span>
            </div>
            <div className={`flex items-center gap-2 text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-slate-300 border border-slate-400"></div>
                <span className="text-[8px]">→</span>
                <div className="w-4 h-4 rounded-full bg-slate-300 border border-slate-400"></div>
              </div>
              <span>Size = budget</span>
            </div>
          </div>
        ) : (
          <div className={`flex flex-wrap justify-center gap-3 pt-4 border-t ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
            {causeAggregates.slice(0, 6).map(cause => (
              <button
                key={cause.category}
                onClick={() => {
                  const x = normalizeX(cause.avgAlignment);
                  const y = normalizeY(cause.avgImpact);
                  handleCauseClick(cause.category, x, y);
                }}
                className="flex items-center gap-1.5 group"
              >
                <div className={`w-2.5 h-2.5 rounded-full ${cause.color}`}></div>
                <span className={`text-[10px] group-hover:underline ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  {cause.label}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CauseAreaMatrix;

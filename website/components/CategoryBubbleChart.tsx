/**
 * Category Bubble Chart - Charities grouped by cause area
 *
 * Y-axis: Amal Score (0-100)
 * Columns: Cause categories
 * Bubble size: Revenue (log scale)
 * Color: Zakat vs Sadaqah
 */

import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';

interface CharityBubble {
  id: string;
  name: string;
  amalScore: number;
  walletTag: string;
  category: string;
  totalRevenue: number | null;
}

interface CategoryBubbleChartProps {
  charities: CharityBubble[];
  height?: string;
}

// Friendly category labels
const CATEGORY_LABELS: Record<string, string> = {
  'HUMANITARIAN': 'Humanitarian',
  'EDUCATION': 'Education',
  'CIVIL_RIGHTS_LEGAL': 'Civil Rights',
  'RESEARCH_POLICY': 'Research',
  'MEDIA_JOURNALISM': 'Media',
  'RELIGIOUS_CULTURAL': 'Religious',
  'ECONOMIC_DEVELOPMENT': 'Economic Dev',
  'HEALTH': 'Health',
  'OTHER': 'Other',
};

export const CategoryBubbleChart: React.FC<CategoryBubbleChartProps> = ({
  charities,
  height = 'h-80',
}) => {
  const { isDark } = useLandingTheme();
  const [hoveredCharity, setHoveredCharity] = useState<string | null>(null);

  // Group charities by category and get unique categories
  const { categories, charityByCategory } = useMemo(() => {
    const byCategory: Record<string, CharityBubble[]> = {};
    charities.forEach(c => {
      const cat = c.category || 'OTHER';
      if (!byCategory[cat]) byCategory[cat] = [];
      byCategory[cat].push(c);
    });
    // Sort categories by count (most charities first)
    const sortedCategories = Object.keys(byCategory).sort(
      (a, b) => byCategory[b].length - byCategory[a].length
    );
    return { categories: sortedCategories, charityByCategory: byCategory };
  }, [charities]);

  // Calculate bubble size from revenue (log scale, 8-24px range)
  const getBubbleSize = (revenue: number | null) => {
    if (!revenue || revenue <= 0) return 10;
    const logRev = Math.log10(revenue);
    // Revenue typically ranges from 100K ($5) to 1B ($9)
    const minLog = 5;
    const maxLog = 9;
    const normalized = Math.min(1, Math.max(0, (logRev - minLog) / (maxLog - minLog)));
    return 8 + normalized * 16; // 8-24px range
  };

  const getWalletColor = (tag?: string) => {
    if (tag?.includes('ZAKAT')) return 'bg-emerald-500';
    return 'bg-slate-400';
  };

  const getWalletLabel = (tag?: string) => {
    if (tag?.includes('ZAKAT')) return 'Zakat Eligible';
    return 'Sadaqah';
  };

  const formatRevenue = (revenue: number | null) => {
    if (!revenue) return 'N/A';
    if (revenue >= 1_000_000_000) return `$${(revenue / 1_000_000_000).toFixed(1)}B`;
    if (revenue >= 1_000_000) return `$${(revenue / 1_000_000).toFixed(1)}M`;
    if (revenue >= 1_000) return `$${(revenue / 1_000).toFixed(0)}K`;
    return `$${revenue.toFixed(0)}`;
  };

  const columnWidth = 100 / Math.max(categories.length, 1);

  return (
    <div className={`rounded-2xl p-6 md:p-8 ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
      {/* Chart Area */}
      <div className={`relative ${height}`}>
        {/* Y-axis labels */}
        <div className={`absolute left-0 top-0 bottom-8 w-8 flex flex-col justify-between text-[10px] ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
          <span>100</span>
          <span>75</span>
          <span>50</span>
          <span>25</span>
          <span>0</span>
        </div>

        {/* Grid lines */}
        <div className="absolute left-10 right-0 top-0 bottom-8">
          {[0, 25, 50, 75].map(score => (
            <div
              key={score}
              className={`absolute left-0 right-0 border-t ${isDark ? 'border-slate-800' : 'border-slate-100'}`}
              style={{ top: `${100 - score}%` }}
            />
          ))}
        </div>

        {/* Category columns with bubbles */}
        <div className="absolute left-10 right-0 top-0 bottom-8 flex">
          {categories.map((cat, catIndex) => (
            <div
              key={cat}
              className="relative flex-1 flex flex-col items-center"
              style={{ width: `${columnWidth}%` }}
            >
              {/* Category divider */}
              {catIndex > 0 && (
                <div className={`absolute left-0 top-0 bottom-0 w-px ${isDark ? 'bg-slate-800' : 'bg-slate-100'}`} />
              )}

              {/* Bubbles for this category */}
              {charityByCategory[cat]?.map((charity, idx) => {
                const size = getBubbleSize(charity.totalRevenue);
                const y = 100 - charity.amalScore;
                // Spread bubbles horizontally within column to reduce overlap
                const spreadX = ((idx % 5) - 2) * 8; // -16 to +16 px spread
                const isHovered = hoveredCharity === charity.id;

                return (
                  <Link
                    key={charity.id}
                    to={`/charity/${charity.id}`}
                    className="absolute transform -translate-x-1/2 -translate-y-1/2 z-10"
                    style={{
                      top: `${y}%`,
                      left: `calc(50% + ${spreadX}px)`,
                    }}
                    onMouseEnter={() => setHoveredCharity(charity.id)}
                    onMouseLeave={() => setHoveredCharity(null)}
                  >
                    <div
                      className={`rounded-full border-2 border-white shadow-md transition-all duration-200 ${getWalletColor(charity.walletTag)} ${isHovered ? 'scale-125 ring-4 ring-slate-900/10 z-20' : 'hover:scale-110'}`}
                      style={{ width: size, height: size }}
                    />
                    {isHovered && (
                      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 bg-slate-900 text-white text-xs rounded-lg p-3 shadow-xl z-30 pointer-events-none">
                        <div className="font-bold mb-1 truncate">{charity.name}</div>
                        <div className="flex justify-between text-slate-300">
                          <span>Score: {charity.amalScore}</span>
                          <span>{getWalletLabel(charity.walletTag)}</span>
                        </div>
                        <div className="text-slate-400 mt-1">
                          Revenue: {formatRevenue(charity.totalRevenue)}
                        </div>
                        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-full">
                          <div className="border-8 border-transparent border-t-slate-900"></div>
                        </div>
                      </div>
                    )}
                  </Link>
                );
              })}
            </div>
          ))}
        </div>

        {/* Category labels */}
        <div className="absolute left-10 right-0 bottom-0 h-8 flex">
          {categories.map(cat => (
            <div
              key={cat}
              className={`flex-1 text-center text-[10px] font-medium truncate px-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}
            >
              {CATEGORY_LABELS[cat] || cat}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className={`flex flex-wrap justify-center gap-6 mt-6 pt-6 border-t ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
          <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Zakat Eligible</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-slate-400"></div>
          <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Sadaqah</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-slate-400"></div>
          <span className={`text-[10px] ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Smaller</span>
          <div className="w-4 h-4 rounded-full bg-slate-400 mx-1"></div>
          <span className={`text-[10px] ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Larger revenue</span>
        </div>
      </div>

      <p className={`text-center text-xs mt-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
        Charities grouped by cause area. Bubble size indicates annual revenue.
      </p>
    </div>
  );
};

export default CategoryBubbleChart;

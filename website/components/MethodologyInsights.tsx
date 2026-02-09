/**
 * Methodology Insights - Meaningful visualizations that tell a story
 *
 * Shows:
 * 1. What separates top performers from average charities
 * 2. Average scores by cause area
 * 3. Common strengths and gaps
 */

import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { TrendingUp, Minus } from 'lucide-react';

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
}

interface MethodologyInsightsProps {
  charities: CharityWithPillars[];
}

// Friendly category labels
const CATEGORY_LABELS: Record<string, string> = {
  'HUMANITARIAN': 'Humanitarian Relief',
  'RELIGIOUS_CONGREGATION': 'Mosques & Islamic Centers',
  'CIVIL_RIGHTS_LEGAL': 'Civil Rights & Legal',
  'MEDICAL_HEALTH': 'Health & Medical',
  'EDUCATION_K12_RELIGIOUS': 'Islamic Schools (K-12)',
  'ENVIRONMENT_CLIMATE': 'Environment & Climate',
  'EDUCATION_HIGHER_RELIGIOUS': 'Islamic Higher Education',
  'SOCIAL_SERVICES': 'Social Services',
  'PHILANTHROPY_GRANTMAKING': 'Grantmaking',
  'BASIC_NEEDS': 'Basic Needs (Food, Shelter)',
  'RESEARCH_POLICY': 'Research & Policy',
  'RELIGIOUS_OUTREACH': 'Dawah & Outreach',
  'EDUCATION_INTERNATIONAL': 'International Education',
  'WOMENS_SERVICES': "Women's Services",
  'MEDIA_JOURNALISM': 'Media & Journalism',
  'ADVOCACY_CIVIC': 'Civic Advocacy',
  'EDUCATION': 'Education',
  'ECONOMIC_DEVELOPMENT': 'Economic Development',
  'HEALTH': 'Health',
  'OTHER': 'Other',
};

export const MethodologyInsights: React.FC<MethodologyInsightsProps> = ({ charities }) => {
  const { isDark } = useLandingTheme();

  // Calculate insights
  const insights = useMemo(() => {
    if (charities.length === 0) return null;

    // Split into tiers
    const exceptional = charities.filter(c => c.amalScore >= 80);
    const strong = charities.filter(c => c.amalScore >= 70 && c.amalScore < 80);
    const good = charities.filter(c => c.amalScore >= 50 && c.amalScore < 70);

    // Calculate average pillars for each tier
    const avgPillars = (group: CharityWithPillars[]) => {
      if (group.length === 0) return { impact: 0, alignment: 0 };
      return {
        impact: Math.round(group.reduce((sum, c) => sum + c.pillarScores.impact, 0) / group.length),
        alignment: Math.round(group.reduce((sum, c) => sum + c.pillarScores.alignment, 0) / group.length),
      };
    };

    const exceptionalAvg = avgPillars(exceptional);
    const goodAvg = avgPillars(good);

    // Calculate by cause area
    const byCause: Record<string, { count: number; avgScore: number; topCharity: string; topCharityId: string; topScore: number }> = {};
    charities.forEach(c => {
      const cat = c.category || 'OTHER';
      if (!byCause[cat]) {
        byCause[cat] = { count: 0, avgScore: 0, topCharity: '', topCharityId: '', topScore: 0 };
      }
      byCause[cat].count++;
      byCause[cat].avgScore += c.amalScore;
      if (c.amalScore > byCause[cat].topScore) {
        byCause[cat].topCharity = c.name;
        byCause[cat].topCharityId = c.id;
        byCause[cat].topScore = c.amalScore;
      }
    });

    // Finalize averages and sort by top score (most impressive top charity first)
    const causeStats = Object.entries(byCause)
      .map(([cat, stats]) => ({
        category: cat,
        label: CATEGORY_LABELS[cat] || cat.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase()),
        count: stats.count,
        avgScore: Math.round(stats.avgScore / stats.count),
        topCharity: stats.topCharity,
        topCharityId: stats.topCharityId,
        topScore: stats.topScore,
      }))
      .filter(c => c.count >= 2) // Only show categories with at least 2 charities
      .sort((a, b) => b.topScore - a.topScore);

    return {
      exceptionalAvg,
      goodAvg,
      causeStats,
      totalCount: charities.length,
      exceptionalCount: exceptional.length,
    };
  }, [charities]);

  if (!insights) return null;

  // Calculate the difference between exceptional and good charities
  const pillarDiffs = {
    impact: insights.exceptionalAvg.impact - insights.goodAvg.impact,
    alignment: insights.exceptionalAvg.alignment - insights.goodAvg.alignment,
  };

  // Find the biggest differentiator
  const biggestDiff = Object.entries(pillarDiffs).sort((a, b) => b[1] - a[1])[0];

  return (
    <div className="space-y-8">
      {/* Insight 1: What separates top performers - narrative style */}
      <div className={`rounded-2xl border p-6 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
        <h3 className={`font-bold mb-4 ${isDark ? 'text-white' : 'text-slate-900'}`}>
          What Makes a Top-Rated Charity?
        </h3>

        <div className="space-y-4">
          {/* The key differentiator */}
          <div className={`p-4 rounded-xl ${isDark ? 'bg-emerald-900/20 border border-emerald-800/30' : 'bg-emerald-50 border border-emerald-200'}`}>
            <div className="flex items-start gap-3">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${isDark ? 'bg-emerald-600' : 'bg-emerald-500'} text-white font-bold`}>
                #1
              </div>
              <div>
                <h4 className={`font-bold mb-1 ${isDark ? 'text-emerald-300' : 'text-emerald-800'}`}>
                  {biggestDiff[0] === 'impact' && "They're more effective with your donation"}
                  {biggestDiff[0] === 'alignment' && "They serve neglected communities and align with your values"}
                </h4>
                <p className={`text-sm ${isDark ? 'text-emerald-200/70' : 'text-emerald-700'}`}>
                  {biggestDiff[0] === 'impact' && `Our top ${insights.exceptionalCount} charities score ${biggestDiff[1]} points higher on impact. They deliver more impact per dollar, have strong evidence quality, and room to absorb additional funding.`}
                  {biggestDiff[0] === 'alignment' && `Our top ${insights.exceptionalCount} charities score ${biggestDiff[1]} points higher on alignment. They work in areas where your donation makes more difference.`}
                </p>
              </div>
            </div>
          </div>

          {/* Secondary insights */}
          <div className="grid md:grid-cols-2 gap-3">
            {[
              { key: 'impact', label: 'Impact', desc: 'Effectiveness, efficiency, evidence & governance' },
              { key: 'alignment', label: 'Alignment', desc: 'Mission fit, cause urgency & funding gap' },
            ]
              .filter(({ key }) => key !== biggestDiff[0]) // Don't repeat the #1
              .slice(0, 3)
              .map(({ key, label, desc }) => {
                const diff = pillarDiffs[key as keyof typeof pillarDiffs];
                return (
                  <div key={key} className={`p-3 rounded-lg ${isDark ? 'bg-slate-800' : 'bg-slate-100'}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{label}</span>
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        diff >= 5 ? isDark ? 'bg-emerald-900/50 text-emerald-400' : 'bg-emerald-100 text-emerald-700'
                        : diff >= 2 ? isDark ? 'bg-blue-900/50 text-blue-400' : 'bg-blue-100 text-blue-700'
                        : isDark ? 'bg-slate-700 text-slate-400' : 'bg-slate-200 text-slate-500'
                      }`}>
                        +{diff} pts
                      </span>
                    </div>
                    <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{desc}</p>
                  </div>
                );
              })}
          </div>
        </div>

        <p className={`text-xs mt-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
          Based on comparing {insights.exceptionalCount} charities scoring 80+ against {insights.totalCount - insights.exceptionalCount} others.
        </p>
      </div>

      {/* Insight 2: Top Picks by Cause */}
      <div className={`rounded-2xl border p-6 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
        <h3 className={`font-bold mb-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
          Top Pick by Cause Area
        </h3>
        <p className={`text-sm mb-6 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
          If you care about a specific cause, here's our highest-rated charity in each area:
        </p>

        <div className="grid md:grid-cols-2 gap-3">
          {insights.causeStats.slice(0, 8).map((cause) => (
            <Link
              key={cause.category}
              to={`/charity/${cause.topCharityId}`}
              className={`flex items-center justify-between p-3 rounded-lg transition-colors ${
                isDark
                  ? 'bg-slate-800 hover:bg-slate-700'
                  : 'bg-slate-50 hover:bg-slate-100'
              }`}
            >
              <div className="min-w-0 flex-1">
                <div className={`text-xs font-medium mb-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  {cause.label}
                </div>
                <div className={`text-sm font-medium truncate ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>
                  {cause.topCharity}
                </div>
              </div>
              <div className={`ml-3 px-2 py-1 rounded text-sm font-bold ${
                cause.topScore >= 80
                  ? isDark ? 'bg-emerald-900/50 text-emerald-400' : 'bg-emerald-100 text-emerald-700'
                  : cause.topScore >= 70
                  ? isDark ? 'bg-blue-900/50 text-blue-400' : 'bg-blue-100 text-blue-700'
                  : isDark ? 'bg-slate-700 text-slate-300' : 'bg-slate-200 text-slate-600'
              }`}>
                {cause.topScore}
              </div>
            </Link>
          ))}
        </div>

        <p className={`text-xs mt-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
          Click any charity to see their full evaluation. We've evaluated {insights.totalCount} charities across {insights.causeStats.length} cause areas.
        </p>
      </div>
    </div>
  );
};

export default MethodologyInsights;

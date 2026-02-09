import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Lock, Sparkles, Info } from 'lucide-react';
import { CharityProfile } from '../../types';
import { useLandingTheme } from '../../contexts/LandingThemeContext';
import { getWalletType, formatWalletTag, getWalletStyles } from '../utils/walletUtils';
import { isUnderReview, getUnderReviewStyles, getScoreColorClass } from '../utils/scoreConstants';
import { getScoreRating } from '../utils/scoreUtils';
import { trackCharityCardClick } from '../utils/analytics';
import { BookmarkButton } from './BookmarkButton';
import { CompareButton } from './CompareButton';

/**
 * Format revenue for compact display: $18M, $1.2M, $450K
 */
const formatRevenue = (revenue: number | null | undefined): string | null => {
  if (!revenue || revenue <= 0) return null;
  if (revenue >= 1_000_000_000) return `$${(revenue / 1_000_000_000).toFixed(1)}B`;
  if (revenue >= 1_000_000) return `$${(revenue / 1_000_000).toFixed(1)}M`;
  if (revenue >= 1_000) return `$${Math.round(revenue / 1_000)}K`;
  return `$${revenue}`;
};

/**
 * Format primaryCategory for display.
 * e.g., "HUMANITARIAN" -> "Humanitarian", "CIVIL_RIGHTS_LEGAL" -> "Civil Rights"
 */
const formatPrimaryCategory = (category: string | null | undefined): string | null => {
  if (!category) return null;
  const mapping: Record<string, string> = {
    'HUMANITARIAN': 'Humanitarian',
    'RELIGIOUS_CONGREGATION': 'Religious',
    'CIVIL_RIGHTS_LEGAL': 'Civil Rights',
    'MEDICAL_HEALTH': 'Health',
    'EDUCATION_K12_RELIGIOUS': 'Education',
    'EDUCATION_HIGHER_RELIGIOUS': 'Education',
    'ENVIRONMENT_CLIMATE': 'Environment',
    'BASIC_NEEDS': 'Basic Needs',
    'PHILANTHROPY_GRANTMAKING': 'Grantmaking',
    'SOCIAL_SERVICES': 'Social Services',
    'EDUCATION_INTERNATIONAL': 'Education',
    'RELIGIOUS_OUTREACH': 'Religious',
    'RESEARCH_POLICY': 'Research',
    'WOMENS_SERVICES': "Women's Services",
    'ADVOCACY_CIVIC': 'Civic',
    'MEDIA_JOURNALISM': 'Media',
  };
  return mapping[category] || category.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
};

/**
 * Format cause tag for display.
 * Country names and service tags formatted for compact display.
 */
const formatCauseTag = (tag: string): string => {
  const mapping: Record<string, string> = {
    // Countries
    'usa': 'USA',
    'palestine': 'Palestine',
    'syria': 'Syria',
    'yemen': 'Yemen',
    'afghanistan': 'Afghanistan',
    'pakistan': 'Pakistan',
    'bangladesh': 'Bangladesh',
    'india': 'India',
    'kashmir': 'Kashmir',
    'somalia': 'Somalia',
    'sudan': 'Sudan',
    'kenya': 'Kenya',
    'ethiopia': 'Ethiopia',
    'nigeria': 'Nigeria',
    'south-africa': 'S. Africa',
    'lebanon': 'Lebanon',
    'jordan': 'Jordan',
    'iraq': 'Iraq',
    'egypt': 'Egypt',
    'turkey': 'Turkey',
    'indonesia': 'Indonesia',
    'malaysia': 'Malaysia',
    'myanmar': 'Myanmar',
    'uyghur': 'Uyghur',
    'haiti': 'Haiti',
    // Services & populations
    'emergency-response': 'Emergency',
    'water-sanitation': 'Water',
    'medical': 'Medical',
    'food': 'Food',
    'advocacy': 'Advocacy',
    'grantmaking': 'Grants',
    'research': 'Research',
    'refugees': 'Refugees',
    'orphans': 'Orphans',
    'women': 'Women',
    'youth': 'Youth',
    'prisoners': 'Prisoners',
    'homeless': 'Homeless',
    'widows': 'Widows',
    'converts': 'Converts',
    'psychosocial': 'Mental Health',
    'legal-aid': 'Legal Aid',
    'microfinance': 'Microfinance',
  };
  return mapping[tag] || tag.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
};


interface CharityCardProps {
  charity: CharityProfile;
  /** Show larger card variant for featured section */
  featured?: boolean;
  /** Compact mode: tighter spacing, no 4-pillar breakdown */
  compact?: boolean;
  /** List position for analytics tracking */
  position?: number;
}

// Tooltip badge component for evaluation track badges
const TooltipBadge: React.FC<{
  label: string;
  tooltip?: string;
  colorClass: string;
  isDark: boolean;
}> = ({ label, tooltip, colorClass }) => {
  const [showTooltip, setShowTooltip] = useState(false);

  if (!tooltip) {
    return (
      <span className={`px-2 py-1 text-[10px] font-bold uppercase tracking-wider rounded ${colorClass}`}>
        {label}
      </span>
    );
  }

  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <span className={`inline-flex items-center gap-1 px-2 py-1 text-[10px] font-bold uppercase tracking-wider rounded cursor-help ${colorClass}`}>
        {label}
        <Info className="w-3 h-3 opacity-60" aria-hidden="true" />
      </span>
      {showTooltip && (
        <div className="absolute z-50 bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-slate-900 text-white text-xs rounded-lg shadow-lg w-64 text-center font-normal normal-case tracking-normal">
          {tooltip}
          <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-slate-900"></div>
        </div>
      )}
    </span>
  );
};

export const CharityCard: React.FC<CharityCardProps> = ({ charity, featured = false, compact = false, position }) => {
  const { isDark } = useLandingTheme();
  const amal = charity.amalEvaluation;

  // AMAL score (single scoring framework)
  const score: number | null = amal?.amal_score ?? null;
  const maxScore = 100;
  const scoreColorClass = score != null ? getScoreColorClass(score, isDark) : '';

  const walletType = getWalletType(amal?.wallet_tag);
  // Only show wallet badge for zakat-eligible charities (binary classification)
  const walletStyles = walletType === 'zakat'
    ? getWalletStyles(amal?.wallet_tag, isDark)
    : null;
  const WalletIcon = walletType === 'zakat' ? Lock : null;

  // Get extended charity data (headline, revenue, primaryCategory, causeTags, impact indicators)
  const extendedCharity = charity as CharityProfile & {
    primaryCategory?: string | null;
    causeTags?: string[] | null;
    headline?: string | null;
    totalRevenue?: number | null;
    impactTier?: string | null;
    categoryMetadata?: { neglectedness?: string | null } | null;
    evaluationTrack?: string | null;
    foundedYear?: number | null;
  };
  const primaryCategory = formatPrimaryCategory(extendedCharity.primaryCategory);
  const headline = extendedCharity.headline || amal?.baseline_narrative?.headline;
  const revenue = formatRevenue(extendedCharity.totalRevenue || charity.financials?.totalRevenue || charity.rawData?.total_revenue);
  const programRatio = charity.financials?.programExpenseRatio || charity.rawData?.program_expense_ratio;
  const programPct = programRatio ? Math.round(programRatio * (programRatio > 1 ? 1 : 100)) : null;

  // Filter out low-value tags for browse cards
  const excludeTags = new Set([
    'faith-based', 'muslim-led', 'usa', 'international', 'direct-service',
    'clothing', 'disabled', 'capacity-building', 'educational', 'low-income',
    'long-term-development', 'vocational', 'shelter', 'elderly'
  ]);
  const causeTags = (extendedCharity.causeTags || [])
    .filter(tag => !excludeTags.has(tag))
    .slice(0, 2);  // Show max 2 tags

  // Differentiator tags: prioritized list of impact/approach indicators (max 2)
  // Each tag has a unique color scheme and optional tooltip for special tracks
  type DifferentiatorTag = {
    label: string;
    priority: number;
    colorLight: string;  // bg + text for light mode
    colorDark: string;   // bg + text for dark mode
    tooltip?: string;    // Explanatory tooltip for special evaluation tracks
  };
  const differentiatorTags: DifferentiatorTag[] = [];
  const allCauseTags = extendedCharity.causeTags || [];

  // Get pillar scores for evidence-based tags
  const pillarScores = (charity as CharityProfile & {
    amalEvaluation?: { confidence_scores?: { impact?: number; alignment?: number; dataConfidence?: number } }
  }).amalEvaluation?.confidence_scores;

  // Calculate years operating
  const currentYear = new Date().getFullYear();
  const yearsOperating = extendedCharity.foundedYear
    ? currentYear - extendedCharity.foundedYear
    : null;

  // Evaluation track badges (NEW_ORG, RESEARCH_POLICY)
  if (extendedCharity.evaluationTrack === 'NEW_ORG') {
    differentiatorTags.push({
      label: 'Emerging',
      priority: 0,  // Highest priority
      colorLight: 'bg-amber-100 text-amber-700',
      colorDark: 'bg-amber-900/50 text-amber-400'
    });
  }
  if (extendedCharity.evaluationTrack === 'RESEARCH_POLICY') {
    differentiatorTags.push({
      label: 'Research/Policy',
      priority: 0,
      colorLight: 'bg-indigo-100 text-indigo-700',
      colorDark: 'bg-indigo-900/50 text-indigo-400'
    });
  }

  // Verified Data: high data confidence (verification + transparency + data quality)
  if (pillarScores?.dataConfidence && pillarScores.dataConfidence >= 0.7) {
    differentiatorTags.push({
      label: 'Verified Data',
      priority: 1,
      colorLight: 'bg-cyan-100 text-cyan-700',
      colorDark: 'bg-cyan-900/50 text-cyan-400'
    });
  }

  if (extendedCharity.impactTier === 'HIGH') {
    differentiatorTags.push({
      label: 'High Impact',
      priority: 2,
      colorLight: 'bg-rose-100 text-rose-700',
      colorDark: 'bg-rose-900/50 text-rose-400'
    });
  }

  // Emergency Response: urgent relief work
  if (allCauseTags.includes('emergency-response')) {
    differentiatorTags.push({
      label: 'Emergency',
      priority: 3,
      colorLight: 'bg-orange-100 text-orange-700',
      colorDark: 'bg-orange-900/50 text-orange-400'
    });
  }

  if (extendedCharity.categoryMetadata?.neglectedness === 'HIGH') {
    differentiatorTags.push({
      label: 'Neglected Cause',
      priority: 4,
      colorLight: 'bg-violet-100 text-violet-700',
      colorDark: 'bg-violet-900/50 text-violet-400'
    });
  }
  if (allCauseTags.includes('systemic-change')) {
    differentiatorTags.push({
      label: 'Systemic',
      priority: 5,
      colorLight: 'bg-blue-100 text-blue-700',
      colorDark: 'bg-blue-900/50 text-blue-400'
    });
  }
  if (allCauseTags.includes('scalable-model')) {
    differentiatorTags.push({
      label: 'Scalable',
      priority: 6,
      colorLight: 'bg-teal-100 text-teal-700',
      colorDark: 'bg-teal-900/50 text-teal-400'
    });
  }

  // Grantmaker: organizations that fund other charities
  if (allCauseTags.includes('grantmaking')) {
    differentiatorTags.push({
      label: 'Grantmaker',
      priority: 7,
      colorLight: 'bg-yellow-100 text-yellow-700',
      colorDark: 'bg-yellow-900/50 text-yellow-400'
    });
  }

  // Established: 25+ years of operation (track record)
  if (yearsOperating && yearsOperating >= 25) {
    differentiatorTags.push({
      label: 'Established',
      priority: 8,
      colorLight: 'bg-stone-200 text-stone-700',
      colorDark: 'bg-stone-800/50 text-stone-400'
    });
  }

  // Sort by priority and take top 2
  const topDifferentiators = differentiatorTags
    .sort((a, b) => a.priority - b.priority)
    .slice(0, 2);

  // Abbreviated wallet tag for mobile (e.g., "Zakat" instead of "Zakat Eligible")
  const walletTagShort = amal?.wallet_tag ? formatWalletTag(amal.wallet_tag).split(' ')[0] : null;

  return (
    <>
      {/* Mobile: Compact Horizontal Layout */}
      <Link
        to={`/charity/${charity.id}`}
        onClick={() => trackCharityCardClick(
          charity.id || charity.ein || '',
          charity.name,
          charity.tier || 'baseline',
          position ?? 0
        )}
        className={`group sm:hidden flex items-center gap-3 p-3 rounded-lg border transition-colors active:scale-[0.99] ${
          isDark
            ? 'border-slate-700 bg-slate-800 active:bg-slate-750'
            : 'border-slate-200 bg-white active:bg-slate-50'
        }`}
      >
        {/* Score Column - Fixed Width Left */}
        <div className="flex-shrink-0 w-11 text-center">
          {score != null && !isUnderReview(score) ? (
            <>
              <div className={`text-xl font-bold ${scoreColorClass} leading-none`}>{score}</div>
              <div className={`text-[10px] ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>/{maxScore}</div>
              <div className={`text-[9px] font-medium ${scoreColorClass}`}>{getScoreRating(score)}</div>
            </>
          ) : score != null ? (
            <div className={`text-[9px] font-semibold px-1 py-0.5 rounded ${getUnderReviewStyles(isDark).bg} ${getUnderReviewStyles(isDark).text}`}>No Data</div>
          ) : (
            <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>--</div>
          )}
        </div>

        {/* Name + Headline - Flex Grow */}
        <div className="flex-1 min-w-0">
          <h3 className={`font-bold text-sm line-clamp-2 ${
            isDark ? 'text-white' : 'text-slate-900'
          }`}>
            {charity.name}
          </h3>
          {headline && (
            <p className={`text-xs truncate ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              {headline}
            </p>
          )}
        </div>

        {/* Tags Column - Stacked Right */}
        <div className="flex-shrink-0 flex flex-col items-end gap-1">
          {walletStyles && WalletIcon && walletTagShort && (
            <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[9px] font-bold uppercase rounded ${walletStyles.bg} ${walletStyles.text}`}>
              <WalletIcon className="w-2.5 h-2.5" aria-hidden="true" />
              {walletTagShort}
            </span>
          )}
          {topDifferentiators.length > 0 && (
            <span className={`px-1.5 py-0.5 text-[9px] font-bold uppercase rounded ${
              isDark ? topDifferentiators[0].colorDark : topDifferentiators[0].colorLight
            }`}>
              {topDifferentiators[0].label}
            </span>
          )}
          {!topDifferentiators.length && primaryCategory && (
            <span className={`px-1.5 py-0.5 text-[9px] font-medium rounded ${
              isDark ? 'bg-slate-700 text-slate-400' : 'bg-slate-100 text-slate-500'
            }`}>
              {primaryCategory}
            </span>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 flex-shrink-0">
          <CompareButton
            charityEin={charity.ein || charity.id || ''}
            charityName={charity.name}
            size="sm"
            showLabel={false}
          />
          <BookmarkButton
            charityEin={charity.ein || charity.id || ''}
            charityName={charity.name}
            size="sm"
          />
        </div>

        {/* Chevron */}
        <ArrowRight className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-slate-600' : 'text-slate-300'}`} aria-hidden="true" />
      </Link>

      {/* Desktop: Vertical Card Layout */}
      <Link
        to={`/charity/${charity.id}`}
        onClick={() => trackCharityCardClick(
          charity.id || charity.ein || '',
          charity.name,
          charity.tier || 'baseline',
          position ?? 0
        )}
        className={`group hidden sm:flex rounded-xl border shadow-sm hover:shadow-lg transition-[colors,shadow,transform] flex-col h-full hover:-translate-y-1 ${
          isDark ? 'border-slate-700 bg-slate-800' : 'border-slate-200 bg-white'
        }`}
      >
        <div className={`flex-1 flex flex-col ${compact ? 'p-4' : 'p-6'}`}>
          {/* Header: Category + Wallet Tag + Location tags */}
          <div className="flex flex-wrap items-center gap-2 mb-3">
            {primaryCategory && (
              <span className={`px-2 py-1 text-[10px] font-bold uppercase tracking-wider rounded ${
                isDark ? 'bg-slate-700 text-slate-400' : 'bg-slate-100 text-slate-500'
              }`}>
                {primaryCategory}
              </span>
            )}
            {walletStyles && WalletIcon && (
              <span className={`inline-flex items-center gap-1 px-2 py-1 text-[10px] font-bold uppercase tracking-wider rounded border ${walletStyles.bg} ${walletStyles.text} ${walletStyles.border}`}>
                <WalletIcon className="w-3 h-3" aria-hidden="true" />
                {formatWalletTag(amal?.wallet_tag)}
              </span>
            )}
            {topDifferentiators.map(tag => (
              <TooltipBadge
                key={tag.label}
                label={tag.label}
                tooltip={tag.tooltip}
                colorClass={isDark ? tag.colorDark : tag.colorLight}
                isDark={isDark}
              />
            ))}
            {causeTags.filter(() => topDifferentiators.length < 2).slice(0, 2 - topDifferentiators.length).map(tag => (
              <span key={tag} className={`px-2 py-1 text-[10px] font-medium rounded ${
                isDark ? 'bg-slate-700/50 text-slate-500' : 'bg-slate-50 text-slate-400'
              }`}>
                {formatCauseTag(tag)}
              </span>
            ))}
            {/* Asnaf categories (zakat-eligible charities) */}
            {charity.asnafServed && charity.asnafServed.length > 0 && walletType === 'zakat' && (
              charity.asnafServed.slice(0, 2).map(asnaf => (
                <span key={asnaf} className={`px-2 py-1 text-[10px] font-medium rounded ${
                  isDark ? 'bg-emerald-900/30 text-emerald-500' : 'bg-emerald-50 text-emerald-600'
                }`}>
                  {asnaf}
                </span>
              ))
            )}
          </div>

          {/* Name and score */}
          <div className="flex justify-between items-start mb-3">
            <h3 className={`font-bold font-merriweather leading-tight transition-colors flex-1 pr-4 ${
              compact ? 'text-base' : featured ? 'text-xl' : 'text-lg'
            } ${isDark ? 'text-white group-hover:text-emerald-400' : 'text-slate-900 group-hover:text-emerald-700'}`}>
              {charity.name}
            </h3>
            <div className="flex items-start gap-2 flex-shrink-0">
              <BookmarkButton
                charityEin={charity.ein || charity.id || ''}
                charityName={charity.name}
                size="md"
              />
              {score != null && !isUnderReview(score) && (
                <div className="text-right">
                  <div className={`font-bold ${scoreColorClass} leading-none ${compact ? 'text-2xl' : 'text-3xl'}`}>{score}</div>
                  <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>/ {maxScore}</div>
                  <div className={`text-xs font-medium ${scoreColorClass}`}>{getScoreRating(score)}</div>
                </div>
              )}
              {score != null && isUnderReview(score) && (
                <div className={`text-xs font-semibold px-2 py-1 rounded ${getUnderReviewStyles(isDark).bg} ${getUnderReviewStyles(isDark).text}`}>
                  Insufficient Data
                </div>
              )}
            </div>
          </div>

          {/* Headline - what they do (1 line, truncated) */}
          {headline && (
            <p className={`text-sm leading-relaxed line-clamp-2 mt-auto ${
              isDark ? 'text-slate-400' : 'text-slate-600'
            }`}>
              {headline}
            </p>
          )}
        </div>

        <div className={`${compact ? 'px-4 py-3' : 'px-6 py-4'} border-t flex justify-between items-center ${
          isDark ? 'bg-slate-900/50 border-slate-700' : 'bg-slate-50 border-slate-100'
        }`}>
          <CompareButton
            charityEin={charity.ein || charity.id || ''}
            charityName={charity.name}
            size="sm"
          />
          {revenue && <span className={`text-xs font-medium ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{revenue} revenue</span>}
          <ArrowRight aria-hidden="true" className={`w-4 h-4 transition-colors transform group-hover:translate-x-1 ${
            isDark ? 'text-slate-600 group-hover:text-white' : 'text-slate-400 group-hover:text-slate-900'
          }`} />
        </div>
      </Link>
    </>
  );
};

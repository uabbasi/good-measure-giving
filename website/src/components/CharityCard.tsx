import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Lock, Info, Heart, ShieldCheck } from 'lucide-react';
import { CharityProfile } from '../../types';
import { useLandingTheme } from '../../contexts/LandingThemeContext';
import { getWalletType } from '../utils/walletUtils';
import { getEvidenceStageClasses, getEvidenceStageLabel, getGivingTagClasses } from '../utils/scoreConstants';
import { deriveUISignalsFromCharity } from '../utils/scoreUtils';
import { trackCharityCardClick } from '../utils/analytics';
import { formatShortRevenue } from '../utils/formatters';
import { cleanNarrativeText } from '../utils/cleanNarrativeText';
import { BookmarkButton } from './BookmarkButton';
import { CompareButton } from './CompareButton';
import { AddToGivingButton } from './AddToGivingButton';

type PrimaryTag = {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
};

const getShortLabel = (label: string): string => {
  const mapping: Record<string, string> = {
    'Accepts Zakat': 'Zakat',
    'Women & Girls': 'Women',
    'Emergency Relief': 'Relief',
    'Advocacy & Policy': 'Policy',
    'Research & Policy': 'Research',
    'Direct Services': 'Service',
    'Community Programs': 'Community',
  };
  return mapping[label] || label;
};

/**
 * Title-case a slug: "muslim civil rights" → "Muslim Civil Rights"
 */
const titleCaseSlug = (slug: string): string =>
  slug.replace(/\b\w/g, c => c.toUpperCase());

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
  const uiSignals = charity.ui_signals_v1 || deriveUISignalsFromCharity(charity);
  const archetypeLabel = uiSignals.archetype_label;
  const evidenceStage = uiSignals.evidence_stage;
  const evidenceStageLabel = getEvidenceStageLabel(evidenceStage);

  const walletType = getWalletType(amal?.wallet_tag);
  const givingTypeClasses = getGivingTagClasses(walletType === 'zakat' ? 'zakat' : 'sadaqah', isDark);

  // Get extended charity data
  const extendedCharity = charity as CharityProfile & {
    primaryCategory?: string | null;
    causeTags?: string[] | null;
    programFocusTags?: string[] | null;
    headline?: string | null;
    totalRevenue?: number | null;
    impactTier?: string | null;
    categoryMetadata?: { neglectedness?: string | null } | null;
    evaluationTrack?: string | null;
    foundedYear?: number | null;
  };
  const slug = charity.slug;
  const revenue = formatShortRevenue(extendedCharity.totalRevenue || charity.financials?.totalRevenue || charity.rawData?.total_revenue);

  const allCauseTags = extendedCharity.causeTags || [];
  const givingTypeTag: PrimaryTag = walletType === 'zakat'
    ? { label: 'Accepts Zakat', icon: Lock }
    : { label: 'Sadaqah', icon: Heart };

  // Differentiator tags: prioritized list of impact/approach indicators
  type DifferentiatorTag = {
    label: string;
    priority: number;
    colorLight: string;
    colorDark: string;
    tooltip?: string;
  };
  const differentiatorTags: DifferentiatorTag[] = [];

  const pillarScores = (charity as CharityProfile & {
    amalEvaluation?: { confidence_scores?: { impact?: number; alignment?: number; dataConfidence?: number } }
  }).amalEvaluation?.confidence_scores;

  const currentYear = new Date().getFullYear();
  const yearsOperating = extendedCharity.foundedYear
    ? currentYear - extendedCharity.foundedYear
    : null;

  if (extendedCharity.evaluationTrack === 'NEW_ORG') {
    differentiatorTags.push({
      label: 'Emerging',
      priority: 0,
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
      label: 'Highest Impact',
      priority: 2,
      colorLight: 'bg-rose-100 text-rose-700',
      colorDark: 'bg-rose-900/50 text-rose-400'
    });
  }
  if ((pillarScores?.alignment || 0) >= 42) {
    differentiatorTags.push({
      label: 'Maximum Alignment',
      priority: 2,
      colorLight: 'bg-emerald-100 text-emerald-700',
      colorDark: 'bg-emerald-900/50 text-emerald-400'
    });
  }

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
      label: 'Tackles Root Causes',
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

  if (allCauseTags.includes('grantmaking')) {
    differentiatorTags.push({
      label: 'Funds Other Orgs',
      priority: 7,
      colorLight: 'bg-yellow-100 text-yellow-700',
      colorDark: 'bg-yellow-900/50 text-yellow-400'
    });
  }

  if (yearsOperating && yearsOperating >= 25) {
    differentiatorTags.push({
      label: '25+ Years',
      priority: 8,
      colorLight: 'bg-stone-200 text-stone-700',
      colorDark: 'bg-stone-800/50 text-stone-400'
    });
  }

  // Sort by priority and take top 1 differentiator
  const topDifferentiators = differentiatorTags
    .sort((a, b) => a.priority - b.priority)
    .slice(0, 1);

  // Show evidence stage badge only for Verified or Established (desktop only)
  const showEvidenceBadge = evidenceStage === 'Verified' || evidenceStage === 'Established';

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
        className={`group sm:hidden flex items-center gap-3 p-3 rounded-lg border border-l-4 transition-colors active:scale-[0.99] ${
          walletType === 'zakat' ? 'border-l-emerald-500' : isDark ? 'border-l-slate-600' : 'border-l-slate-300'
        } ${
          isDark
            ? 'border-slate-700 bg-slate-800 active:bg-slate-750'
            : 'border-slate-200 bg-white active:bg-slate-50'
        }`}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h3 className={`font-bold text-sm line-clamp-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
              {charity.name}
            </h3>
            {revenue && (
              <span className={`text-[10px] font-medium whitespace-nowrap ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                {revenue}
              </span>
            )}
          </div>

          {/* Slug subtitle */}
          {slug && (
            <p className={`text-sm font-medium mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              {titleCaseSlug(slug)}
            </p>
          )}

          {/* Headline snippet */}
          {extendedCharity.headline && (
            <p className={`text-xs line-clamp-1 mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
              {cleanNarrativeText(extendedCharity.headline)}
            </p>
          )}

          {/* Badges: max 2 on mobile — giving type + top differentiator */}
          <div className="mt-1.5 flex flex-wrap items-center gap-1">
            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-semibold border ${givingTypeClasses}`}>
              <givingTypeTag.icon className="w-3 h-3" aria-hidden="true" />
              {getShortLabel(givingTypeTag.label)}
            </span>
            {topDifferentiators.map(tag => (
              <span key={tag.label} className={`px-1.5 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider ${isDark ? tag.colorDark : tag.colorLight}`}>
                {tag.label}
              </span>
            ))}
          </div>

        </div>

        {/* Tap affordance */}
        <span className={`text-xs font-semibold flex-shrink-0 whitespace-nowrap ${
          isDark ? 'text-emerald-400' : 'text-emerald-600'
        }`}>
          View →
        </span>
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
          {/* Name + bookmark */}
          <div className="flex justify-between items-start mb-1">
            <h3 className={`font-bold font-merriweather leading-tight transition-colors flex-1 pr-4 ${
              compact ? 'text-base' : featured ? 'text-xl' : 'text-lg'
            } ${isDark ? 'text-white group-hover:text-emerald-400' : 'text-slate-900 group-hover:text-emerald-700'}`}>
              {charity.name}
            </h3>
            <div className="flex items-start gap-2 flex-shrink-0">
              <BookmarkButton
                charityEin={charity.ein || charity.id || ''}
                charityName={charity.name}
                causeTags={allCauseTags.length > 0 ? allCauseTags : undefined}
                size="md"
              />
            </div>
          </div>

          {/* Add to giving action row (desktop) */}
          <div
            className="flex justify-end mb-2"
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}
          >
            <AddToGivingButton
              charityEin={charity.ein || charity.id || ''}
              charityName={charity.name}
              size="md"
            />
          </div>

          {/* Slug subtitle */}
          {slug && (
            <p className={`text-sm font-medium mb-3 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              {titleCaseSlug(slug)}
            </p>
          )}

          {/* Badges: max 3 on desktop — giving type + top differentiator + evidence (Verified/Established only) */}
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className={`inline-flex items-center gap-1 px-2 py-1 text-[10px] font-semibold border rounded ${givingTypeClasses}`}>
              <givingTypeTag.icon className="w-3 h-3" aria-hidden="true" />
              {getShortLabel(givingTypeTag.label)}
            </span>
            {topDifferentiators.map(tag => (
              <TooltipBadge
                key={tag.label}
                label={tag.label}
                tooltip={tag.tooltip}
                colorClass={isDark ? tag.colorDark : tag.colorLight}
                isDark={isDark}
              />
            ))}
            {showEvidenceBadge && (
              <span className={`inline-flex items-center gap-1 px-2 py-1 text-[10px] font-semibold border rounded ${getEvidenceStageClasses(evidenceStage, isDark)}`}>
                <ShieldCheck className="w-3 h-3" aria-hidden="true" />
                {evidenceStageLabel}
              </span>
            )}
          </div>

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

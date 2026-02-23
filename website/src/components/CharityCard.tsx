import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Lock, Info, Heart, Users, BookOpen, Zap, Compass, ShieldCheck, Landmark } from 'lucide-react';
import { CharityProfile } from '../../types';
import { useLandingTheme } from '../../contexts/LandingThemeContext';
import { getWalletType } from '../utils/walletUtils';
import { getEvidenceStageClasses, getEvidenceStageLabel, getGivingTagClasses, getHowTagClasses } from '../utils/scoreConstants';
import { deriveUISignalsFromCharity } from '../utils/scoreUtils';
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

type PrimaryTag = {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
};

const getWhoTag = (causeTags: string[], asnafServed: string[] | null | undefined): PrimaryTag | null => {
  if (causeTags.includes('refugees')) return { label: 'Refugees', icon: Users };
  if (causeTags.includes('orphans')) return { label: 'Orphans', icon: Users };
  if (causeTags.includes('women')) return { label: 'Women & Girls', icon: Users };
  if (causeTags.includes('youth')) return { label: 'Youth', icon: Users };
  if (causeTags.includes('converts') || (asnafServed || []).includes('Muallaf')) return { label: 'Converts', icon: Users };
  if (causeTags.includes('prisoners')) return { label: 'Prisoners', icon: Users };
  if (causeTags.includes('widows')) return { label: 'Widows', icon: Users };
  if ((asnafServed || []).some(a => ['Fuqara', 'Masakin'].includes(a))) return { label: 'Low-Income', icon: Users };
  return null;
};

const getHowTag = (causeTags: string[], programFocusTags: string[] | null | undefined, archetypeLabel: string): PrimaryTag => {
  const focus = programFocusTags || [];
  if (causeTags.includes('emergency-response')) return { label: 'Emergency Relief', icon: Zap };
  if (causeTags.includes('advocacy') || causeTags.includes('legal-aid') || causeTags.includes('systemic-change')) {
    return { label: 'Advocacy & Policy', icon: Compass };
  }
  if (causeTags.includes('grantmaking') || archetypeLabel === 'Grantmaker') return { label: 'Grantmaking', icon: Landmark };
  if (
    causeTags.includes('educational') ||
    focus.includes('education-k12') ||
    focus.includes('education-higher') ||
    archetypeLabel.includes('Education')
  ) {
    return { label: 'Education', icon: BookOpen };
  }
  if (focus.includes('research-policy') || causeTags.includes('research')) return { label: 'Research & Policy', icon: Compass };
  if (causeTags.includes('medical') || causeTags.includes('food') || causeTags.includes('water-sanitation')) {
    return { label: 'Direct Services', icon: Heart };
  }
  return { label: 'Community Programs', icon: Users };
};

const getCueDisplayLabel = (cue: string): string => {
  if (cue === 'Strong Match') return 'Maximum Alignment';
  if (cue === 'Good Match') return 'Strong Alignment';
  if (cue === 'Limited Match') return 'Needs Verification';
  return 'Mixed Signals';
};

const getShortLabel = (label: string): string => {
  const mapping: Record<string, string> = {
    'Zakat Eligible': 'Zakat',
    'Women & Girls': 'Women',
    'Emergency Relief': 'Relief',
    'Advocacy & Policy': 'Policy',
    'Research & Policy': 'Research',
    'Direct Services': 'Service',
    'Community Programs': 'Community',
  };
  return mapping[label] || label;
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
  const uiSignals = charity.ui_signals_v1 || deriveUISignalsFromCharity(charity);
  const archetypeLabel = uiSignals.archetype_label;
  const evidenceStage = uiSignals.evidence_stage;
  const evidenceStageLabel = getEvidenceStageLabel(evidenceStage);

  const walletType = getWalletType(amal?.wallet_tag);
  // Systematic families:
  // - Giving tags: green family (emerald/teal)
  // - How tags: purple family (with rose for emergency)
  // - Evidence tags: lower-ink border style for readability
  const givingTypeClasses = getGivingTagClasses(walletType === 'zakat' ? 'zakat' : 'sadaqah', isDark);

  // Get extended charity data (headline, revenue, primaryCategory, causeTags, impact indicators)
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
  const allCauseTags = extendedCharity.causeTags || [];
  const howTag = getHowTag(allCauseTags, extendedCharity.programFocusTags, archetypeLabel);
  const givingTypeTag: PrimaryTag = walletType === 'zakat'
    ? { label: 'Zakat Eligible', icon: Lock }
    : { label: 'Sadaqah', icon: Heart };

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

  // Grantmaker: organizations that fund other charities
  if (allCauseTags.includes('grantmaking')) {
    differentiatorTags.push({
      label: 'Funds Other Orgs',
      priority: 7,
      colorLight: 'bg-yellow-100 text-yellow-700',
      colorDark: 'bg-yellow-900/50 text-yellow-400'
    });
  }

  // Established: 25+ years of operation (track record)
  if (yearsOperating && yearsOperating >= 25) {
    differentiatorTags.push({
      label: '25+ Years',
      priority: 8,
      colorLight: 'bg-stone-200 text-stone-700',
      colorDark: 'bg-stone-800/50 text-stone-400'
    });
  }

  // Sort by priority and take top 2
  const topDifferentiators = differentiatorTags
    .sort((a, b) => a.priority - b.priority)
    .slice(0, 2);

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

          <div className="mt-1 flex flex-wrap items-center gap-1">
            {topDifferentiators.map(tag => (
              <span key={tag.label} className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${isDark ? tag.colorDark : tag.colorLight}`}>
                {tag.label}
              </span>
            ))}
            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold border ${givingTypeClasses}`}>
              <givingTypeTag.icon className="w-2.5 h-2.5" aria-hidden="true" />
              {getShortLabel(givingTypeTag.label)}
            </span>
            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold border ${getHowTagClasses(howTag.label, isDark)}`}>
              <howTag.icon className="w-2.5 h-2.5" aria-hidden="true" />
              {getShortLabel(howTag.label)}
            </span>
            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold border ${getEvidenceStageClasses(evidenceStage, isDark)}`}>
              <ShieldCheck className="w-2.5 h-2.5" aria-hidden="true" />
              {evidenceStageLabel}
            </span>
          </div>

          {headline && (
            <p className={`text-xs line-clamp-2 mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              {headline}
            </p>
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
          {/* Header: donor-useful primary tags */}
          <div className="flex flex-wrap items-center gap-2 mb-3">
            {topDifferentiators.map(tag => (
              <TooltipBadge
                key={tag.label}
                label={tag.label}
                tooltip={tag.tooltip}
                colorClass={isDark ? tag.colorDark : tag.colorLight}
                isDark={isDark}
              />
            ))}
            <span className={`inline-flex items-center gap-1 px-2 py-1 text-[10px] font-semibold border rounded ${givingTypeClasses}`}>
              <givingTypeTag.icon className="w-3 h-3" aria-hidden="true" />
              {getShortLabel(givingTypeTag.label)}
            </span>
            <span className={`inline-flex items-center gap-1 px-2 py-1 text-[10px] font-semibold border rounded ${getHowTagClasses(howTag.label, isDark)}`}>
              <howTag.icon className="w-3 h-3" aria-hidden="true" />
              {getShortLabel(howTag.label)}
            </span>
            <span className={`inline-flex items-center gap-1 px-2 py-1 text-[10px] font-semibold border rounded ${getEvidenceStageClasses(evidenceStage, isDark)}`}>
              <ShieldCheck className="w-3 h-3" aria-hidden="true" />
              {evidenceStageLabel}
            </span>
          </div>

          {/* Name + bookmark */}
          <div className="flex justify-between items-start mb-2">
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
            </div>
          </div>

          {/* Headline - narrative-first */}
          {headline && (
            <p className={`text-sm leading-relaxed line-clamp-3 mt-auto ${
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

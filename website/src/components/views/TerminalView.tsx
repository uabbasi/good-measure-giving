/**
 * TerminalView: Bloomberg-style data terminal view for charity details.
 * 3-column layout: left panel + center content + right panel.
 * Dense information display with monospace data.
 */

import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { getCharityAddress } from '../../utils/formatters';
import {
  ArrowLeft,
  ExternalLink,
  CheckCircle2,
  TrendingUp,
  AlertTriangle,
  Target,
  Scale,
  AlertCircle,
  Lock,
  Shield,
  Landmark,
  ChevronDown,
  Plus,
  LogIn,
  Sparkles,
  Rocket,
  Award,
} from 'lucide-react';
import { CharityProfile } from '../../../types';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import { useAuth } from '../../auth/useAuth';
import { SignInButton } from '../../auth/SignInButton';
import { BookmarkButton } from '../BookmarkButton';
import { trackCharityView, trackOutboundClick, trackDonateClick } from '../../utils/analytics';
import { useCharities } from '../../hooks/useCharities';
import { useGivingHistory } from '../../hooks/useGivingHistory';
import { ReportIssueButton } from '../ReportIssueButton';
import { SourceLinkedText } from '../SourceLinkedText';
import { ActionsBar } from '../ActionsBar';
import { AddDonationModal } from '../giving/AddDonationModal';
import { getCauseCategoryTagClasses, getEvidenceStageClasses, getEvidenceStageLabel } from '../../utils/scoreConstants';
import { deriveUISignalsFromCharity, getArchetypeDescription } from '../../utils/scoreUtils';
import { ScoreBreakdown } from '../ScoreBreakdown';
import { RecommendationCue } from '../RecommendationCue';
import { OrganizationEngagement } from '../OrganizationEngagement';
import { resolveCitationUrls, resolveSourceUrl } from '../../utils/citationUrls';

interface TerminalViewProps {
  charity: CharityProfile;
}

interface NarrativeCitation {
  id?: string;
  source_name?: string;
  source_url?: string | null;
  claim?: string;
}

// Format currency helper
const formatCurrency = (value: number | null | undefined): string => {
  if (!value) return 'N/A';
  if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `$${(value / 1000).toFixed(0)}K`;
  return `$${value}`;
};

// Format wallet tag - binary system (ZAKAT-ELIGIBLE or SADAQAH-ELIGIBLE)
const formatWalletTag = (tag: string): string => {
  const cleanTag = tag?.replace(/[\[\]]/g, '') || '';
  if (cleanTag.includes('ZAKAT')) return 'Zakat';
  return 'Sadaqah';
};

// Extract source URL from zakat claim evidence string
const extractZakatPolicyUrl = (evidence: string): string | undefined => {
  const match = evidence.match(/\(Source:\s*(https?:\/\/[^\s)]+)\)/);
  return match?.[1];
};

// Population tags (who they serve)
const POPULATION_TAGS = new Set([
  'women', 'youth', 'children', 'disabled', 'refugees', 'low-income',
  'orphans', 'elderly', 'families', 'students', 'veterans', 'homeless',
  'fuqara', 'masakin', 'muallaf', 'fisabilillah', 'ibn-al-sabil', 'amil'
]);

// Geographic tags (where they work)
const GEOGRAPHIC_TAGS = new Set([
  'usa', 'india', 'pakistan', 'bangladesh', 'afghanistan', 'palestine',
  'syria', 'sudan', 'yemen', 'somalia', 'turkey', 'jordan', 'lebanon',
  'iraq', 'gaza', 'global', 'south-africa', 'kenya', 'indonesia', 'malaysia',
  'ukraine', 'egypt', 'morocco', 'tunisia', 'nigeria', 'ethiopia'
]);

// Intervention tags (what services they provide)
const INTERVENTION_TAGS = new Set([
  'educational', 'medical', 'food', 'water-sanitation', 'shelter', 'clothing',
  'legal-aid', 'vocational', 'microfinance', 'mental-health'
]);

// Change type tags (how they create change)
const CHANGE_TYPE_TAGS = new Set([
  'emergency-response', 'direct-relief', 'direct-service', 'long-term-development',
  'advocacy', 'capacity-building', 'grantmaking', 'research', 'policy',
  'scalable-model', 'systemic-change'
]);

// Format tag for display (kebab-case to Title Case)
const formatTag = (tag: string): string => {
  const specialCases: Record<string, string> = {
    'fuqara': 'Fuqara',
    'masakin': 'Masakin',
    'muallaf': 'Muallaf',
    'fisabilillah': 'Fi Sabilillah',
    'ibn-al-sabil': 'Ibn al-Sabil',
    'amil': 'Amil',
    'usa': 'USA',
  };
  if (specialCases[tag.toLowerCase()]) {
    return specialCases[tag.toLowerCase()];
  }
  return tag.split('-').map(word =>
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ');
};

const getTheoryOfChangeCitations = (citations: NarrativeCitation[], limit = 2): NarrativeCitation[] => {
  if (!citations || citations.length === 0) return [];
  const tocPattern = /(theory of change|our model|logic model|impact framework|impact report|evaluation and learning)/i;
  const ranked = citations
    .filter(c => !!c.source_url)
    .map(c => {
      const haystack = `${c.claim || ''} ${c.source_name || ''} ${c.source_url || ''}`;
      return { citation: c, score: tocPattern.test(haystack) ? 2 : 0 };
    })
    .sort((a, b) => b.score - a.score);

  const matched = ranked.filter(r => r.score > 0).slice(0, limit).map(r => r.citation);
  if (matched.length > 0) return matched;
  return ranked.slice(0, limit).map(r => r.citation);
};

// Categorize cause tags into 4 categories
const categorizeTags = (tags: string[] | null | undefined): {
  populations: string[];
  geography: string[];
  interventions: string[];
  changeTypes: string[];
} => {
  if (!tags || tags.length === 0) {
    return { populations: [], geography: [], interventions: [], changeTypes: [] };
  }

  const populations: string[] = [];
  const geography: string[] = [];
  const interventions: string[] = [];
  const changeTypes: string[] = [];

  tags.forEach(tag => {
    const lowerTag = tag.toLowerCase();
    if (POPULATION_TAGS.has(lowerTag)) {
      populations.push(tag);
    } else if (GEOGRAPHIC_TAGS.has(lowerTag)) {
      geography.push(tag);
    } else if (INTERVENTION_TAGS.has(lowerTag)) {
      interventions.push(tag);
    } else if (CHANGE_TYPE_TAGS.has(lowerTag)) {
      changeTypes.push(tag);
    }
  });

  return { populations, geography, interventions, changeTypes };
};

/** Clean up raw NTEE program descriptions to human-readable labels */
function formatProgramTag(raw: string): string {
  // Remove trailing "measure" or "measures"
  let cleaned = raw.replace(/\s+measures?\s*$/i, '');
  // Remove leading "Assist " prefix common in NTEE codes
  cleaned = cleaned.replace(/^Assist\s+/i, '');
  // Title-case cleanup
  cleaned = cleaned.replace(/\band\b/gi, '&').replace(/\b\w/g, c => c.toUpperCase());
  return cleaned;
}

/** Compute differentiator tags for detail page hero (mirrors CharityCard logic) */
function getDifferentiatorTags(charity: CharityProfile, isDark: boolean): Array<{ label: string; colorClass: string }> {
  const tags: Array<{ label: string; priority: number; colorClass: string }> = [];
  const extended = charity as any;
  const allCauseTags = (charity.causeTags || []).map((t: string) => t.toLowerCase());
  const alignmentScore = charity.amalEvaluation?.confidence_scores?.alignment || 0;

  if (extended.impactTier === 'HIGH') {
    tags.push({ label: 'Maximum Leverage', priority: 2, colorClass: isDark ? 'bg-rose-900/50 text-rose-400' : 'bg-rose-100 text-rose-700' });
  }
  if (alignmentScore >= 42) {
    tags.push({ label: 'Maximum Alignment', priority: 2, colorClass: isDark ? 'bg-emerald-900/50 text-emerald-400' : 'bg-emerald-100 text-emerald-700' });
  }
  if (allCauseTags.includes('emergency-response')) {
    tags.push({ label: 'Emergency', priority: 3, colorClass: isDark ? 'bg-orange-900/50 text-orange-400' : 'bg-orange-100 text-orange-700' });
  }
  // Neglected cause already shown as separate badge in detail view, skip to avoid duplicate
  if (allCauseTags.includes('systemic-change')) {
    tags.push({ label: 'Systemic', priority: 5, colorClass: isDark ? 'bg-blue-900/50 text-blue-400' : 'bg-blue-100 text-blue-700' });
  }
  if (allCauseTags.includes('scalable-model')) {
    tags.push({ label: 'Scalable', priority: 6, colorClass: isDark ? 'bg-teal-900/50 text-teal-400' : 'bg-teal-100 text-teal-700' });
  }
  if (allCauseTags.includes('grantmaking')) {
    tags.push({ label: 'Grantmaker', priority: 7, colorClass: isDark ? 'bg-yellow-900/50 text-yellow-400' : 'bg-yellow-100 text-yellow-700' });
  }
  const yearsOperating = extended.foundedYear ? (new Date().getFullYear() - extended.foundedYear) : null;
  if (yearsOperating && yearsOperating >= 25) {
    tags.push({ label: 'Established', priority: 8, colorClass: isDark ? 'bg-stone-800/50 text-stone-400' : 'bg-stone-200 text-stone-700' });
  }

  return tags.sort((a, b) => a.priority - b.priority).slice(0, 3);
}

// Data row component
const DataRow: React.FC<{
  label: string;
  value: string | number | undefined;
  isDark: boolean;
  highlight?: boolean;
  mono?: boolean;
}> = ({ label, value, isDark, highlight = false, mono = true }) => (
  <div className={`flex justify-between py-2 border-b ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
    <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{label}</span>
    <span className={`text-sm font-medium ${
      highlight
        ? isDark ? 'text-emerald-400' : 'text-emerald-600'
        : isDark ? 'text-white' : 'text-slate-900'
    } ${mono ? 'font-mono' : ''}`}>
      {value ?? '—'}
    </span>
  </div>
);

export const TerminalView: React.FC<TerminalViewProps> = ({ charity }) => {
  const { isDark } = useLandingTheme();
  const { isSignedIn } = useAuth();
  const { charities: allCharities } = useCharities();
  const { addDonation, getPaymentSources } = useGivingHistory();
  const [showDonationModal, setShowDonationModal] = useState(false);

  const amal = charity.amalEvaluation;
  const baseline = amal?.baseline_narrative;
  const rich = amal?.rich_narrative;
  const hasRich = !!rich;
  const idealDonorProfile = rich?.ideal_donor_profile;
  // Check both rich and baseline narratives for citations
  const rawCitations = (rich?.all_citations || baseline?.all_citations || []) as NarrativeCitation[];
  const citations = useMemo(
    () => resolveCitationUrls(rawCitations, charity),
    [rawCitations, charity]
  );
  const theoryOfChangeCitations = useMemo(
    () => getTheoryOfChangeCitations(citations as NarrativeCitation[]),
    [citations]
  );
  const scores = amal?.confidence_scores;
  const financials = charity.financials || charity.rawData?.financials;
  const revenue = financials?.totalRevenue || charity.rawData?.total_revenue;
  const beneficiariesCount = charity.beneficiariesServedAnnually;
  const beneficiarySourceUrl = (charity as any)?.sourceAttribution?.beneficiaries_served_annually?.source_url;
  const beneficiarySourceName = (charity as any)?.sourceAttribution?.beneficiaries_served_annually?.source_name
    || (charity as any)?.beneficiariesSource?.source_name
    || 'Charity Website';
  const resolvedBeneficiarySourceUrl = useMemo(
    () => resolveSourceUrl(beneficiarySourceUrl, charity, {
      source_name: beneficiarySourceName,
      claim: 'Beneficiaries served annually (self-reported)',
    }),
    [beneficiarySourceUrl, beneficiarySourceName, charity]
  );
  const beneficiariesVerified = charity.beneficiariesConfidence != null
    ? charity.beneficiariesConfidence === 'verified'
    : (typeof beneficiarySourceUrl === 'string' && beneficiarySourceUrl.startsWith('http'));
  const beneficiariesExcludedFromScoring = charity.beneficiariesExcludedFromScoring
    ?? Boolean(beneficiariesCount && !beneficiariesVerified);

  // Create a lookup map from charity names to their IDs (case-insensitive)
  const charityNameToId = useMemo(() => {
    const map = new Map<string, string>();
    allCharities.forEach(c => {
      map.set(c.name.toLowerCase(), c.id ?? c.ein ?? '');
    });
    return map;
  }, [allCharities]);

  // Helper to find charity ID by name (fuzzy match)
  const findCharityId = (name: string): string | null => {
    const lowerName = name.toLowerCase();
    // Exact match first
    if (charityNameToId.has(lowerName)) {
      return charityNameToId.get(lowerName) || null;
    }
    // Try partial match (name contains or is contained by)
    for (const [charityName, id] of charityNameToId.entries()) {
      if (charityName.includes(lowerName) || lowerName.includes(charityName)) {
        return id;
      }
    }
    return null;
  };

  React.useEffect(() => {
    trackCharityView(charity.id ?? charity.ein ?? '', charity.name, 'terminal');
  }, [charity.id, charity.name]);

  const handleDonateClick = () => {
    trackDonateClick(charity.id ?? charity.ein ?? '', charity.name, charity.donationUrl || charity.website || '');
  };

  // Calculate expense ratios with proper edge case handling
  const totalExpenses = financials?.totalExpenses ?? 0;
  const hasExpenseData = totalExpenses > 0;
  const rawProgramRatio = hasExpenseData && financials?.programExpenses
    ? ((financials.programExpenses / totalExpenses) * 100)
    : 0;
  const programRatio = Math.min(rawProgramRatio, 100);
  const adminRatio = hasExpenseData && financials?.adminExpenses
    ? ((financials.adminExpenses / totalExpenses) * 100)
    : 0;
  const fundRatio = hasExpenseData && financials?.fundraisingExpenses
    ? ((financials.fundraisingExpenses / totalExpenses) * 100)
    : 0;

  // Mobile collapsible section state
  const [openSections, setOpenSections] = useState<Set<string>>(new Set(['about']));
  const toggleSection = (id: string) => {
    setOpenSections(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  // Get strengths for "Why give here" section
  const strengths = rich?.strengths || baseline?.strengths || [];
  const headline = rich?.headline || baseline?.headline || '';
  const isZakatEligible = amal?.wallet_tag?.includes('ZAKAT');
  const uiSignals = charity.ui_signals_v1 || deriveUISignalsFromCharity(charity);
  const amalScore = amal?.amal_score || 0;
  const donateUrl = charity.donationUrl ?? charity.website ?? undefined;

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950' : 'bg-slate-100'}`}>
      {/* ═══════════════════════════════════════════════════════════════════════
          MOBILE HERO SECTION - Replaces cramped header with beautiful landing
          ═══════════════════════════════════════════════════════════════════════ */}
      <div className="lg:hidden">
        {/* Sticky mini-header with back */}
        <div className={`sticky top-0 z-30 border-b backdrop-blur-sm ${
          isDark
            ? 'bg-slate-900/95 border-slate-800'
            : 'bg-white/95 border-slate-200'
        }`}>
          <div className="px-4 py-3 flex items-center">
            <Link
              to="/browse"
              aria-label="Back to browse"
              className={`p-2 -ml-2 rounded-lg ${
                isDark ? 'text-slate-400 hover:text-white hover:bg-slate-800' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <ArrowLeft className="w-5 h-5" aria-hidden="true" />
            </Link>
          </div>
        </div>

        {/* Hero Content */}
        <div className={`px-4 pt-5 pb-3 ${isDark ? 'bg-slate-950' : 'bg-slate-100'}`}>
          {/* Mobile actions: above title */}
          <div className="mb-3">
            <div className={`grid gap-2 ${isSignedIn ? 'grid-cols-3' : 'grid-cols-[2fr_1fr]'}`}>
              {isSignedIn ? (
                <>
                  <button
                    onClick={() => setShowDonationModal(true)}
                    className={`inline-flex items-center justify-center gap-1.5 h-10 px-2.5 rounded-lg text-[13px] font-medium border transition-colors ${
                      isDark
                        ? 'bg-slate-900/70 text-emerald-300 border-slate-700 hover:bg-slate-800'
                        : 'bg-white text-emerald-700 border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Log Donation
                  </button>
                  <BookmarkButton
                    charityEin={charity.ein || charity.id || ''}
                    charityName={charity.name}
                    showLabel
                    fullWidth
                    size="sm"
                    className="w-full"
                    buttonClassName={`h-10 !min-h-0 !rounded-lg border !px-2.5 !py-0 ${
                      isDark
                        ? 'bg-slate-900/70 border-slate-700 hover:bg-slate-800'
                        : 'bg-white border-slate-200 hover:bg-slate-50'
                    }`}
                    labelClassName="text-[13px] font-medium"
                  />
                </>
              ) : (
                <SignInButton variant="custom" isDark={isDark}>
                  <span className={`w-full inline-flex items-center justify-center gap-1.5 h-10 px-2.5 rounded-lg text-[13px] font-medium border cursor-pointer ${
                    isDark
                      ? 'bg-slate-900/70 text-emerald-300 border-slate-700'
                      : 'bg-white text-emerald-700 border-slate-200'
                  }`}>
                    <LogIn className="w-3.5 h-3.5" />
                    Sign in to save
                  </span>
                </SignInButton>
              )}
              {donateUrl && (
                <a
                  href={donateUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={handleDonateClick}
                  className={`inline-flex items-center justify-center gap-1.5 h-10 px-2.5 rounded-lg text-[13px] font-semibold whitespace-nowrap ${
                    isDark
                      ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                      : 'bg-emerald-600 hover:bg-emerald-700 text-white'
                  }`}
                >
                  Donate
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}
            </div>
          </div>

          {/* Name + Headline */}
          <h1 className={`text-xl font-bold leading-tight ${isDark ? 'text-white' : 'text-slate-900'}`}>
            {charity.name}
          </h1>
          {getCharityAddress(charity) && (
            <p className={`mt-1 text-xs font-mono ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
              {getCharityAddress(charity)}
            </p>
          )}
          {/* Evaluation Track Badge */}
          {charity.evaluationTrack === 'NEW_ORG' && (
            <div className={`mt-2 inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium ${
              isDark ? 'bg-amber-900/50 text-amber-300 border border-amber-700/50' : 'bg-amber-100 text-amber-700 border border-amber-200'
            }`}>
              <TrendingUp className="w-3 h-3" />
              Emerging Organization
              {charity.foundedYear && (
                <span className={isDark ? 'text-amber-400/70' : 'text-amber-600'}>
                  · Est. {charity.foundedYear}
                </span>
              )}
              <span className={`ml-1 ${isDark ? 'text-amber-400/50' : 'text-amber-500/70'}`}>
                — Scored with emerging-org rubric
              </span>
            </div>
          )}
          {charity.evaluationTrack === 'RESEARCH_POLICY' && (
            <div className={`mt-2 inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium ${
              isDark ? 'bg-indigo-900/50 text-indigo-300 border border-indigo-700/50' : 'bg-indigo-100 text-indigo-700 border border-indigo-200'
            }`}>
              <Landmark className="w-3 h-3" />
              Research & Policy Organization
              <span className={`ml-1 ${isDark ? 'text-indigo-400/50' : 'text-indigo-500/70'}`}>
                — Scored with research/policy rubric
              </span>
            </div>
          )}
          {/* Differentiator Tags */}
          {(() => {
            const diffTags = getDifferentiatorTags(charity, isDark);
            if (diffTags.length === 0) return null;
            return (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {diffTags.map((tag, i) => (
                  <span key={i} className={`inline-flex px-2 py-0.5 rounded text-xs font-semibold ${tag.colorClass}`}>
                    {tag.label}
                  </span>
                ))}
              </div>
            );
          })()}
          {headline && (
            <p className={`mt-2 text-sm leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              <SourceLinkedText text={headline} citations={citations} isDark={isDark} subtle />
            </p>
          )}

          {/* Tag Categories */}
          {(() => {
            const tagCategories = categorizeTags(charity.causeTags);
            const hasPopulations = tagCategories.populations.length > 0;
            const hasGeography = tagCategories.geography.length > 0;
            const hasInterventions = tagCategories.interventions.length > 0;
            const hasChangeTypes = tagCategories.changeTypes.length > 0;
            const hasAnyTags = hasPopulations || hasGeography || hasInterventions || hasChangeTypes;
            if (!hasAnyTags) return null;
            return (
              <div className="mt-3 space-y-1">
                {hasPopulations && (
                  <div className="flex flex-wrap items-center gap-1">
                    <span className={`text-xs w-16 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Pop:</span>
                    {tagCategories.populations.slice(0, 3).map(tag => (
                      <span key={tag} className={`px-1.5 py-0.5 rounded text-xs border ${getCauseCategoryTagClasses('population', isDark)}`}>
                        {formatTag(tag)}
                      </span>
                    ))}
                  </div>
                )}
                {hasInterventions && (
                  <div className="flex flex-wrap items-center gap-1">
                    <span className={`text-xs w-16 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Service:</span>
                    {tagCategories.interventions.slice(0, 3).map(tag => (
                      <span key={tag} className={`px-1.5 py-0.5 rounded text-xs border ${getCauseCategoryTagClasses('intervention', isDark)}`}>
                        {formatTag(tag)}
                      </span>
                    ))}
                  </div>
                )}
                {hasGeography && (
                  <div className="flex flex-wrap items-center gap-1">
                    <span className={`text-xs w-16 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Region:</span>
                    {tagCategories.geography.slice(0, 3).map(tag => (
                      <span key={tag} className={`px-1.5 py-0.5 rounded text-xs border ${getCauseCategoryTagClasses('geography', isDark)}`}>
                        {formatTag(tag)}
                      </span>
                    ))}
                  </div>
                )}
                {hasChangeTypes && (
                  <div className="flex flex-wrap items-center gap-1">
                    <span className={`text-xs w-16 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Approach:</span>
                    {tagCategories.changeTypes.slice(0, 3).map(tag => (
                      <span key={tag} className={`px-1.5 py-0.5 rounded text-xs border ${getCauseCategoryTagClasses('approach', isDark)}`}>
                        {formatTag(tag)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })()}

          {/* Qualitative Snapshot Row */}
          <div className="mt-4 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`px-2 py-1 rounded text-xs font-semibold border ${isDark ? 'bg-slate-800 text-slate-300 border-slate-700' : 'bg-slate-100 text-slate-600 border-slate-200'}`}
                title={getArchetypeDescription(uiSignals.archetype_code || charity.archetype)}
              >
                {uiSignals.archetype_label}
              </span>
              <span className={`px-2 py-1 rounded text-xs font-semibold border ${getEvidenceStageClasses(uiSignals.evidence_stage, isDark)}`}>
                {getEvidenceStageLabel(uiSignals.evidence_stage)}
              </span>
              <RecommendationCue cue={uiSignals.recommendation_cue} rationale={null} isDark={isDark} compact />
              <span className={`inline-flex items-center gap-1.5 text-sm ${
                isZakatEligible
                  ? isDark ? 'text-emerald-400' : 'text-emerald-600'
                  : isDark ? 'text-slate-400' : 'text-slate-500'
              }`}>
                <Shield className="w-3.5 h-3.5" />
                {isZakatEligible ? 'Zakat Eligible' : 'Sadaqah'}
              </span>
            </div>
          </div>

          {/* Quick Stats Grid */}
          <div className={`grid grid-cols-2 gap-2.5 mt-4 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
            {programRatio > 0 && (
              <div className="flex items-center gap-2">
                <CheckCircle2 className={`w-4 h-4 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                <span>{programRatio.toFixed(0)}% to programs{rawProgramRatio > 100 ? ' (incl. in-kind)' : ''}</span>
              </div>
            )}
            {revenue && (
              <div className="flex items-center gap-2">
                <TrendingUp className={`w-4 h-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                <span>{formatCurrency(revenue)} revenue</span>
              </div>
            )}
            {rich?.bbb_assessment?.meets_all_standards && (
              <div className="flex items-center gap-2">
                <Shield className={`w-4 h-4 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                <span>BBB Accredited</span>
              </div>
            )}
            {rich?.long_term_outlook?.founded_year && (
              <div className="flex items-center gap-2">
                <Landmark className={`w-4 h-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                <span>Founded {rich.long_term_outlook.founded_year}</span>
              </div>
            )}
          </div>

          {/* Why Give Here */}
          {strengths.length > 0 && (
            <div className={`mt-4 p-3.5 rounded-2xl ${
              isDark ? 'bg-emerald-900/20 border border-emerald-800/30' : 'bg-emerald-50 border border-emerald-100'
            }`}>
              <h3 className={`text-sm font-semibold mb-2 ${isDark ? 'text-emerald-400' : 'text-emerald-700'}`}>
                Why give here?
              </h3>
              <ul className={`space-y-1.5 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                {strengths.slice(0, 2).map((s, i) => {
                  const text = typeof s === 'object' ? s.point : s;
                  return (
                    <li key={i} className="flex items-start gap-2">
                      <span className={isDark ? 'text-emerald-400' : 'text-emerald-600'}>•</span>
                      <span><SourceLinkedText text={text} citations={citations} isDark={isDark} subtle /></span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {/* Scroll Incentive */}
          <div className={`mt-5 text-center ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            <ChevronDown className="w-5 h-5 mx-auto motion-safe:animate-bounce" aria-hidden="true" />
            <span className="text-xs">See full evaluation</span>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════
          DESKTOP TOP BAR - Hidden on mobile
          ═══════════════════════════════════════════════════════════════════════ */}
      <div className={`hidden lg:block sticky top-0 z-30 border-b ${
        isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
      }`}>
        <div className="px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              to="/browse"
              aria-label="Back to browse"
              className={`inline-flex items-center gap-1 text-sm ${
                isDark ? 'text-slate-400 hover:text-white' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <ArrowLeft className="w-4 h-4" aria-hidden="true" />
            </Link>
            <span className={`font-mono font-semibold truncate max-w-xs sm:max-w-md lg:max-w-xl ${isDark ? 'text-white' : 'text-slate-900'}`}>
              {charity.name.toUpperCase()}
            </span>
            {/* Conflict Zone Badge */}
            {!!charity.trustSignals?.isConflictZone && (
              <span className={`hidden sm:inline-flex px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wide ${
                isDark ? 'bg-orange-900/50 text-orange-400' : 'bg-orange-100 text-orange-700'
              }`}>
                Conflict Zone
              </span>
            )}
            {/* Neglected Cause Badge */}
            {charity.categoryMetadata?.neglectedness === 'HIGH' && (
              <span className={`hidden sm:inline-flex px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wide ${
                isDark ? 'bg-violet-900/50 text-violet-400' : 'bg-violet-100 text-violet-700'
              }`}>
                Neglected Cause
              </span>
            )}
            {/* Archetype Label */}
            {charity.archetype && (
              <span className={`hidden sm:inline-flex px-2 py-0.5 rounded text-xs font-semibold ${
                isDark ? 'bg-slate-800 text-slate-400' : 'bg-slate-100 text-slate-500'
              }`} title={getArchetypeDescription(uiSignals.archetype_code || charity.archetype)}>
                {uiSignals.archetype_label}
              </span>
            )}
            {/* Differentiator Tags */}
            {getDifferentiatorTags(charity, isDark).map((tag, i) => (
              <span key={i} className={`hidden sm:inline-flex px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wide ${tag.colorClass}`}>
                {tag.label}
              </span>
            ))}
          </div>
          <div className="flex items-center gap-3">
            {charity.website && (
              <a
                href={charity.website}
                target="_blank"
                rel="noopener noreferrer"
                className={`hidden sm:inline-flex items-center gap-1 text-sm ${
                  isDark ? 'text-slate-400 hover:text-slate-300' : 'text-slate-500 hover:text-slate-600'
                }`}
              >
                {charity.website.replace(/^https?:\/\//, '').replace(/\/$/, '')}
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Terminal-style Actions Bar */}
      <ActionsBar
        charityEin={charity.ein!}
        charityName={charity.name}
        onLogDonation={() => setShowDonationModal(true)}
        variant="terminal"
        donateUrl={donateUrl}
        onDonateClick={handleDonateClick}
        walletTag={amal?.wallet_tag}
        causeArea={rich?.donor_fit_matrix?.cause_area}
        showMobileQuickActions={false}
        zakatPolicyUrl={charity.zakatClaimEvidence?.[0] ? extractZakatPolicyUrl(charity.zakatClaimEvidence[0]) : undefined}
      />

      {/* ═══════════════════════════════════════════════════════════════════════
          MOBILE CONTENT FLOW - Below hero, proper information architecture
          ═══════════════════════════════════════════════════════════════════════ */}
      <div className="lg:hidden px-4 pb-6 space-y-3">
        {/* === Mobile Section 1: Narrative / About === */}
        {(() => {
          // GMG about
          if (rich?.summary || baseline?.summary) {
            return (
              <div className={`p-3.5 rounded-2xl ${
                isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'
              }`}>
                <h2 className={`text-sm font-semibold uppercase tracking-wide mb-2 ${
                  isDark ? 'text-slate-400' : 'text-slate-500'
                }`}>
                  About
                </h2>
                <p className={`text-sm leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  <SourceLinkedText text={rich?.summary || baseline?.summary || ''} citations={citations} isDark={isDark} subtle />
                </p>
              </div>
            );
          }

          return null;
        })()}

        {/* === Mobile Section 2: Best For === */}
        {(() => {
          const donorProfile = isSignedIn ? idealDonorProfile : null;
          if (!donorProfile) return null;
          return (
            <div className={`border-l-4 p-3.5 rounded-r-lg ${
              isDark ? 'bg-emerald-900/20 border-emerald-500' : 'bg-emerald-50 border-emerald-600'
            }`}>
              <div className={`text-xs uppercase tracking-widest font-semibold mb-2 ${
                isDark ? 'text-emerald-400' : 'text-emerald-700'
              }`}>
                Best For
              </div>
              <p className={`text-sm font-medium mb-2 ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                {donorProfile.best_for_summary}
              </p>
              <div className="grid grid-cols-1 gap-3">
                {donorProfile.donor_motivations?.length > 0 && (
                  <div>
                    <div className={`text-xs font-semibold mb-1 flex items-center gap-1 ${
                      isDark ? 'text-emerald-400' : 'text-emerald-600'
                    }`}>
                      <Target className="w-3 h-3" />
                      Ideal for donors who:
                    </div>
                    <ul className={`text-xs space-y-0.5 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                      {donorProfile.donor_motivations.slice(0, 4).map((m: string, i: number) => (
                        <li key={i} className="flex items-start gap-1">
                          <span className="text-emerald-500">•</span>
                          {m}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {donorProfile.giving_considerations?.length > 0 && (
                  <div>
                    <div className={`text-xs font-semibold mb-1 flex items-center gap-1 ${
                      isDark ? 'text-slate-400' : 'text-slate-500'
                    }`}>
                      <Scale className="w-3 h-3" />
                      Consider:
                    </div>
                    <ul className={`text-xs space-y-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                      {donorProfile.giving_considerations.slice(0, 3).map((c: string, i: number) => (
                        <li key={i} className="flex items-start gap-1">
                          <span>•</span>
                          {c}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              {donorProfile.not_ideal_for && (
                <div className={`mt-2 pt-2 border-t text-xs flex items-start gap-1 ${
                  isDark ? 'border-slate-700 text-amber-400' : 'border-slate-200 text-amber-600'
                }`}>
                  <AlertCircle className="w-3 h-3 shrink-0 mt-0.5" />
                  <span><strong>Not ideal for:</strong> {donorProfile.not_ideal_for}</span>
                </div>
              )}
            </div>
          );
        })()}

        {/* === Mobile Section 3: Methodology Details (always open) === */}
        {amal?.score_details && (
          <div className={`rounded-2xl overflow-hidden ${
            isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'
          }`}>
            <div className={`px-3.5 pt-3.5 text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
              Methodology details
            </div>
            <div className="px-1.5 pb-1.5">
              <ScoreBreakdown
                scoreDetails={amal.score_details}
                confidenceScores={scores}
                amalScore={amalScore}
                citations={citations}
                isSignedIn={isSignedIn}
                isDark={isDark}
                dimensionExplanations={rich?.dimension_explanations || baseline?.dimension_explanations}
                amalScoreRationale={isSignedIn ? rich?.amal_score_rationale : undefined}
                scoreSummary={charity.scoreSummary}
                strengths={isSignedIn ? rich?.strengths : baseline?.strengths}
                areasForImprovement={
                  (isSignedIn ? rich?.areas_for_improvement : baseline?.areas_for_improvement) as
                    Array<string | { area: string; context: string; citation_ids: string[] }> | undefined
                }
              />
            </div>
          </div>
        )}

        {/* Financials - Collapsible (shared across all lenses) */}
        <div className={`rounded-2xl overflow-hidden ${
          isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'
        }`}>
          <button
            onClick={() => toggleSection('financials')}
            className={`w-full px-3.5 py-3 flex items-center justify-between ${
              isDark ? 'hover:bg-slate-800/50' : 'hover:bg-slate-50'
            }`}
          >
            <span className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
              Financials
            </span>
            <ChevronDown className={`w-5 h-5 transition-transform ${
              openSections.has('financials') ? 'rotate-180' : ''
            } ${isDark ? 'text-slate-400' : 'text-slate-500'}`} />
          </button>
          {openSections.has('financials') && (
            <div className="px-3.5 pb-3.5">
              {/* Revenue */}
              <div className={`mb-3 pb-2.5 border-b ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                <div className={`text-2xl font-mono font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {formatCurrency(revenue)}
                </div>
                <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Annual Revenue</div>
              </div>

              {/* Form 990 Exempt Notice */}
              {!!charity.form990Exempt && !revenue && (
                <div className={`mb-3 p-2.5 rounded-lg text-sm ${isDark ? 'bg-slate-800 text-slate-300' : 'bg-amber-50 text-amber-800'}`}>
                  <div className="font-medium mb-1">Form 990 Exempt</div>
                  <div className={`text-xs ${isDark ? 'text-slate-400' : 'text-amber-700'}`}>
                    {charity.form990ExemptReason || 'Religious organization'} — not required to file public financial disclosures.
                  </div>
                </div>
              )}

              {/* Expense Breakdown */}
              {hasExpenseData && (
                <div className="space-y-2">
                  <div className={`h-2 rounded-full overflow-hidden flex ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}>
                    <div className="bg-emerald-500" style={{ width: `${programRatio}%` }} />
                    <div className={isDark ? 'bg-slate-500' : 'bg-slate-400'} style={{ width: `${adminRatio}%` }} />
                    <div className="bg-amber-500" style={{ width: `${fundRatio}%` }} />
                  </div>
                  <div className={`space-y-1.5 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-emerald-500" />
                        Programs
                      </span>
                      <span className="font-mono">{programRatio.toFixed(0)}%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${isDark ? 'bg-slate-500' : 'bg-slate-400'}`} />
                        Admin
                      </span>
                      <span className="font-mono">{adminRatio.toFixed(0)}%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-amber-500" />
                        Fundraising
                      </span>
                      <span className="font-mono">{fundRatio.toFixed(0)}%</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* External Links */}
        <div className={`p-3.5 rounded-2xl ${
          isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'
        }`}>
          <h2 className={`text-sm font-semibold uppercase tracking-wide mb-2 ${
            isDark ? 'text-slate-400' : 'text-slate-500'
          }`}>
            Verify Sources
          </h2>
          <div className="space-y-2">
            {charity.website && (
              <a
                href={charity.website}
                target="_blank"
                rel="noopener noreferrer"
                className={`flex items-center gap-2 text-sm py-1.5 ${
                  isDark ? 'text-emerald-400 hover:text-emerald-300' : 'text-emerald-600 hover:text-emerald-700'
                }`}
              >
                Website <ExternalLink className="w-3 h-3" />
              </a>
            )}
            <a
              href={`https://www.charitynavigator.org/ein/${(charity.ein ?? charity.id ?? '').replace(/-/g, '')}`}
              target="_blank"
              rel="noopener noreferrer"
              className={`flex items-center gap-2 text-sm py-1.5 ${
                isDark ? 'text-slate-400 hover:text-slate-300' : 'text-slate-500 hover:text-slate-600'
              }`}
            >
              Charity Navigator <ExternalLink className="w-3 h-3" />
            </a>
            <a
              href={`https://projects.propublica.org/nonprofits/organizations/${(charity.ein ?? charity.id ?? '').replace(/-/g, '')}`}
              target="_blank"
              rel="noopener noreferrer"
              className={`flex items-center gap-2 text-sm py-1.5 ${
                isDark ? 'text-slate-400 hover:text-slate-300' : 'text-slate-500 hover:text-slate-600'
              }`}
            >
              ProPublica 990 <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>

        {/* Mobile Report Issue */}
        <div className={`flex items-center justify-center gap-4 pt-1 pb-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
          <ReportIssueButton charityId={charity.id ?? charity.ein ?? ''} charityName={charity.name} />
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════
          DESKTOP MAIN GRID - 3 columns, hidden on mobile
          ═══════════════════════════════════════════════════════════════════════ */}
      <div className="hidden lg:grid lg:grid-cols-12">
        {/* Left Panel */}
        <aside className={`lg:col-span-3 pl-6 pr-4 py-4 border-b lg:border-b-0 lg:border-r ${
          isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
        }`}>
          {/* Qualitative Snapshot */}
          <div className="mb-4 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`px-2 py-1 rounded text-[11px] font-semibold border ${isDark ? 'bg-slate-800 text-slate-300 border-slate-700' : 'bg-slate-100 text-slate-600 border-slate-200'}`}
                title={getArchetypeDescription(uiSignals.archetype_code || charity.archetype)}
              >
                {uiSignals.archetype_label}
              </span>
              <span className={`px-2 py-1 rounded text-[11px] font-semibold border ${getEvidenceStageClasses(uiSignals.evidence_stage, isDark)}`}>
                {getEvidenceStageLabel(uiSignals.evidence_stage)}
              </span>
            </div>
            <RecommendationCue cue={uiSignals.recommendation_cue} rationale={uiSignals.recommendation_rationale} isDark={isDark} />
          </div>

          {/* Divider between qualitative snapshot and focus areas */}
          <div className={`mb-5 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`} />

          {/* Tag Categories - Bullet-separated layout */}
          {(() => {
            const tagCategories = categorizeTags(charity.causeTags);
            const ZAKAT_TERMS = new Set(['fuqara', 'masakin', 'muallaf', 'fisabilillah', 'ibn-al-sabil', 'amil']);
            const nonZakatPopulations = tagCategories.populations.filter(p => !ZAKAT_TERMS.has(p.toLowerCase()));
            const zakatAsnaf = rich?.donor_fit_matrix?.zakat_asnaf_served || [];

            // Row 1: Who (Zakat + Population)
            const whoTags = [...zakatAsnaf, ...nonZakatPopulations.map(t => formatTag(t))];
            // Row 2: What (Services + Approach)
            const whatTags = [
              ...tagCategories.interventions.map(t => formatTag(t)),
              ...tagCategories.changeTypes.map(t => formatTag(t))
            ];
            // Row 3: Where (Geography only)
            const whereTags = tagCategories.geography.map(t => formatTag(t));
            // Row 4: Programs (limit to 4)
            const programTags = (charity.programs || []).slice(0, 4);
            const programOverflow = (charity.programs || []).length > 4 ? (charity.programs || []).length - 4 : 0;

            const hasAnyTags = whoTags.length > 0 || whatTags.length > 0 || whereTags.length > 0 || programTags.length > 0;
            if (!hasAnyTags) return null;

            return (
              <div className={`mb-6 p-3 rounded-lg ${isDark ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
                <div className={`text-xs uppercase tracking-widest font-semibold mb-2 ${
                  isDark ? 'text-slate-500' : 'text-slate-400'
                }`}>
                  Focus Areas
                </div>
                <div className="space-y-1.5 text-xs">
                  {whoTags.length > 0 && (
                    <div className="flex">
                      <span className={`font-medium w-12 flex-shrink-0 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Who:</span>
                      <span className={isDark ? 'text-emerald-400' : 'text-emerald-700'}>
                        {whoTags.join(' • ')}
                      </span>
                    </div>
                  )}
                  {whatTags.length > 0 && (
                    <div className="flex">
                      <span className={`font-medium w-12 flex-shrink-0 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>What:</span>
                      <span className={isDark ? 'text-amber-400' : 'text-amber-700'}>
                        {whatTags.join(' • ')}
                      </span>
                    </div>
                  )}
                  {whereTags.length > 0 && (
                    <div className="flex">
                      <span className={`font-medium w-12 flex-shrink-0 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Where:</span>
                      <span className={isDark ? 'text-blue-400' : 'text-blue-700'}>
                        {whereTags.join(' • ')}
                      </span>
                    </div>
                  )}
                  {programTags.length > 0 && (
                    <div className="flex">
                      <span className={`font-medium w-12 flex-shrink-0 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>How:</span>
                      <span className={isDark ? 'text-cyan-400' : 'text-cyan-700'}>
                        {programTags.map(t => formatProgramTag(t)).join(' • ')}
                        {programOverflow > 0 && ` +${programOverflow}`}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            );
          })()}

          {/* Beneficiaries Served (self-reported) */}
          {beneficiariesCount != null && beneficiariesCount > 0 && (
            <div className={`mb-6 p-3 rounded-lg ${isDark ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
              <div className={`text-2xl font-mono font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                {beneficiariesCount.toLocaleString()}
              </div>
              <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                Beneficiaries Served Annually
                <span className={`ml-1 italic ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>(self-reported)</span>
              </div>
              {!beneficiariesVerified && (
                <div className={`mt-1.5 flex items-center gap-1 text-xs ${isDark ? 'text-amber-400' : 'text-amber-700'}`}>
                  <AlertTriangle className="w-3 h-3" />
                  <span>No cited source yet; excluded from cost-per-beneficiary scoring</span>
                </div>
              )}
              {beneficiariesVerified && resolvedBeneficiarySourceUrl && (
                <a
                  href={resolvedBeneficiarySourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`mt-1.5 inline-flex items-center gap-1 text-xs underline underline-offset-2 ${
                    isDark ? 'text-slate-400 hover:text-slate-200' : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  View beneficiary source
                </a>
              )}
              {beneficiariesExcludedFromScoring && !beneficiariesVerified && (
                <div className={`mt-1 text-[11px] ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                  Ranking favors verified cost signals when available.
                </div>
              )}
            </div>
          )}

          {/* Financials */}
          <div className="mb-6">
            <div className={`text-xs uppercase tracking-widest font-semibold mb-3 ${
              isDark ? 'text-slate-500' : 'text-slate-400'
            }`}>
              Financials
            </div>

            {/* Revenue - Hero number or Emerging Org message */}
            <div className={`mb-4 pb-3 border-b ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
              {revenue ? (
                <>
                  <div className={`text-2xl font-mono font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {formatCurrency(revenue)}
                  </div>
                  <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Annual Revenue</div>
                </>
              ) : charity.evaluationTrack === 'NEW_ORG' ? (
                <>
                  <div className={`flex items-center gap-2 ${isDark ? 'text-sky-400' : 'text-sky-600'}`}>
                    <Rocket className="w-5 h-5" />
                    <span className="text-lg font-semibold">Pre-990</span>
                  </div>
                  <div className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    New org · First 990 filing pending
                  </div>
                </>
              ) : (
                <>
                  <div className={`text-2xl font-mono font-bold ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    N/A
                  </div>
                  <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Annual Revenue</div>
                </>
              )}
            </div>

            {/* Form 990 Exempt Notice */}
            {!!charity.form990Exempt && !revenue && (
              <div className={`mb-4 p-3 rounded-lg text-sm ${isDark ? 'bg-slate-800 text-slate-300' : 'bg-amber-50 text-amber-800'}`}>
                <div className="font-medium mb-1">Form 990 Exempt</div>
                <div className={`text-xs ${isDark ? 'text-slate-400' : 'text-amber-700'}`}>
                  {charity.form990ExemptReason || 'Religious organization'} — not required to file public financial disclosures.
                </div>
              </div>
            )}

            {/* Candid Seal - show when no expense data but we have seal info */}
            {!hasExpenseData && charity.awards?.candidSeal && (
              <div className={`flex items-center justify-between py-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                <span className="text-sm">Candid Transparency</span>
                <a
                  href={charity.awards.candidUrl || `https://www.guidestar.org/search?q=${charity.ein}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`font-semibold hover:underline ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}
                >
                  {charity.awards.candidSeal} Seal
                </a>
              </div>
            )}

            {/* Expense Breakdown */}
            {hasExpenseData && (
              <div className="space-y-2">
                {/* Expense Bar */}
                <div className={`h-2 rounded-full overflow-hidden flex ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}>
                  <div className="bg-emerald-500" style={{ width: `${programRatio}%` }} />
                  <div className={isDark ? 'bg-slate-500' : 'bg-slate-400'} style={{ width: `${adminRatio}%` }} />
                  <div className="bg-amber-500" style={{ width: `${fundRatio}%` }} />
                </div>

                {/* Legend with amounts */}
                <div className={`space-y-1.5 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-emerald-500" />
                      Programs
                    </span>
                    <span className="font-mono">
                      {formatCurrency(financials?.programExpenses)}
                      <span className={`ml-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>({programRatio.toFixed(0)}%)</span>
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${isDark ? 'bg-slate-500' : 'bg-slate-400'}`} />
                      Admin
                    </span>
                    <span className="font-mono">
                      {formatCurrency(financials?.adminExpenses)}
                      <span className={`ml-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>({adminRatio.toFixed(0)}%)</span>
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-amber-500" />
                      Fundraising
                    </span>
                    <span className="font-mono">
                      {formatCurrency(financials?.fundraisingExpenses)}
                      <span className={`ml-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>({fundRatio.toFixed(0)}%)</span>
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Balance Sheet */}
            {(financials?.totalAssets || financials?.totalLiabilities || financials?.netAssets) && (
              <div className={`mt-3 pt-3 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                <div className={`text-xs font-semibold mb-2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Balance Sheet
                </div>
                <div className="space-y-1.5 text-xs">
                  {financials?.totalAssets && (
                    <div className="flex justify-between items-center">
                      <span className={isDark ? 'text-slate-400' : 'text-slate-500'}>Total Assets</span>
                      <span className={`font-mono ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                        {formatCurrency(financials.totalAssets)}
                      </span>
                    </div>
                  )}
                  {financials?.totalLiabilities && (
                    <div className="flex justify-between items-center">
                      <span className={isDark ? 'text-slate-400' : 'text-slate-500'}>Total Liabilities</span>
                      <span className={`font-mono ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                        {formatCurrency(financials.totalLiabilities)}
                      </span>
                    </div>
                  )}
                  {financials?.netAssets && (
                    <div className={`flex justify-between items-center pt-1.5 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                      <span className={`font-medium ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>Net Assets</span>
                      <span className={`font-mono font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                        {formatCurrency(financials.netAssets)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Working Capital Months */}
            {financials?.workingCapitalMonths != null && (
              <div className={`mt-3 pt-3 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                <div className="flex justify-between items-center text-xs">
                  <span className={isDark ? 'text-slate-400' : 'text-slate-500'}>Working Capital</span>
                  <span className={`font-mono font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {Number(financials.workingCapitalMonths).toFixed(1)} months
                  </span>
                </div>
              </div>
            )}

            {/* Financial Deep Dive - 3-Year History (Rich only, authenticated) */}
            {isSignedIn && rich?.financial_deep_dive?.yearly_financials && rich.financial_deep_dive.yearly_financials.length > 0 && (
              <div className={`mt-3 pt-3 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                <div className={`text-xs font-semibold mb-2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  3-Year History
                </div>
                <div className="space-y-1.5 text-xs">
                  {rich.financial_deep_dive.yearly_financials.map((year) => (
                    <div key={year.year} className="flex justify-between items-center">
                      <span className={`font-mono ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{year.year}</span>
                      <span className={`font-mono ${isDark ? 'text-white' : 'text-slate-900'}`}>
                        {formatCurrency(year.revenue)}
                      </span>
                    </div>
                  ))}
                </div>
                {rich.financial_deep_dive.revenue_cagr_3yr && (
                  <div className={`mt-2 pt-2 border-t flex justify-between items-center ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                    <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>3yr CAGR</span>
                    <span className={`text-xs font-mono font-semibold ${
                      rich.financial_deep_dive.revenue_cagr_3yr > 0
                        ? isDark ? 'text-emerald-400' : 'text-emerald-600'
                        : isDark ? 'text-red-400' : 'text-red-600'
                    }`}>
                      {rich.financial_deep_dive.revenue_cagr_3yr > 0 ? '↑' : '↓'} {Math.abs(rich.financial_deep_dive.revenue_cagr_3yr).toFixed(1)}%
                    </span>
                  </div>
                )}
                {rich.financial_deep_dive.reserves_months && (
                  <div className={`flex justify-between items-center mt-1 ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                    <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Reserves</span>
                    <span className={`text-xs font-mono ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                      {rich.financial_deep_dive.reserves_months.toFixed(1)} mo
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Recognition / Awards - only show verified awards from awards object */}
          {(charity.awards?.cnBeacons?.length || charity.awards?.candidSeal || charity.awards?.bbbStatus || charity.awards?.bbbReviewUrl) && (
            <div className="mb-6">
              <div className={`text-xs uppercase tracking-widest font-semibold mb-3 ${
                isDark ? 'text-slate-500' : 'text-slate-400'
              }`}>
                Recognition
              </div>
              <div className="space-y-2">
                {/* CN Beacons/Awards */}
                {charity.awards?.cnBeacons?.map((beacon, i) => (
                  <div key={i} className={`flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    <Award className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-amber-400' : 'text-amber-500'}`} />
                    {charity.awards?.cnUrl ? (
                      <a
                        href={charity.awards.cnUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`text-sm hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}
                      >
                        {beacon}
                      </a>
                    ) : (
                      <span className="text-sm">{beacon}</span>
                    )}
                    <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>· Charity Navigator</span>
                  </div>
                ))}
                {/* Candid Seal - only from verified awards export */}
                {charity.awards?.candidSeal && (
                  <div className={`flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    <Award className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-amber-400' : 'text-amber-500'}`} />
                    {charity.awards.candidUrl ? (
                      <a
                        href={charity.awards.candidUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`text-sm hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}
                      >
                        {String(charity.awards.candidSeal).charAt(0).toUpperCase() +
                         String(charity.awards.candidSeal).slice(1)} Seal
                      </a>
                    ) : (
                      <span className="text-sm">
                        {String(charity.awards.candidSeal).charAt(0).toUpperCase() +
                         String(charity.awards.candidSeal).slice(1)} Seal
                      </span>
                    )}
                    <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>· Candid</span>
                  </div>
                )}
                {/* BBB Wise Giving Alliance - show status with link, or just link for transparency */}
                {charity.awards?.bbbStatus && (
                  <div className={`flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    <Award className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-amber-400' : 'text-amber-500'}`} />
                    {charity.awards.bbbReviewUrl ? (
                      <a
                        href={charity.awards.bbbReviewUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`text-sm hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}
                      >
                        {charity.awards.bbbStatus}
                      </a>
                    ) : (
                      <span className="text-sm">{charity.awards.bbbStatus}</span>
                    )}
                    <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>· BBB Wise Giving</span>
                  </div>
                )}
                {/* BBB Review link even when not accredited (for transparency) */}
                {!charity.awards?.bbbStatus && charity.awards?.bbbReviewUrl && (
                  <div className={`flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    <ExternalLink className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-slate-400' : 'text-slate-500'}`} />
                    <a
                      href={charity.awards.bbbReviewUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`text-sm hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}
                    >
                      View BBB Evaluation
                    </a>
                    <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>· BBB Wise Giving</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Long-Term Outlook (Rich only, authenticated) */}
          {isSignedIn && rich?.long_term_outlook && (
            <div className="mb-6">
              <div className={`text-xs uppercase tracking-widest font-semibold mb-3 ${
                isDark ? 'text-slate-500' : 'text-slate-400'
              }`}>
                Long-Term Outlook
              </div>

              <DataRow label="Founded" value={rich.long_term_outlook.founded_year} isDark={isDark} />
              <DataRow label="Years Operating" value={rich.long_term_outlook.years_operating} isDark={isDark} />
              <DataRow label="Maturity" value={rich.long_term_outlook.maturity_stage} isDark={isDark} mono={false} />
              <DataRow label="Room for Funding" value={rich.long_term_outlook.room_for_funding} isDark={isDark} />

              {(rich.long_term_outlook.strategic_priorities?.length ?? 0) > 0 && (
                <div className={`mt-3 pt-3 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                  <div className={`text-xs font-semibold mb-1.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    Strategic Priorities
                  </div>
                  <ul className={`text-xs space-y-0.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {rich.long_term_outlook.strategic_priorities?.slice(0, 3).map((priority, i) => (
                      <li key={i} className="flex items-start gap-1">
                        <span className="text-emerald-500">•</span>
                        {priority}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Donor Fit Matrix (Rich only, authenticated) */}
          {isSignedIn && rich?.donor_fit_matrix && (
            <div className="mb-6">
              <div className={`text-xs uppercase tracking-widest font-semibold mb-3 ${
                isDark ? 'text-slate-500' : 'text-slate-400'
              }`}>
                Donor Fit
              </div>

              <DataRow label="Cause Area" value={rich.donor_fit_matrix.cause_area
                ?.replace(/_/g, ' ')
                .toLowerCase()
                .replace(/\b\w/g, (c: string) => c.toUpperCase())
                .replace(/\bAnd\b/g, '&')
              } isDark={isDark} mono={false} />
              <DataRow label="Giving Style" value={rich.donor_fit_matrix.giving_style} isDark={isDark} mono={false} />
              <DataRow label="Evidence Rigor" value={rich.donor_fit_matrix.evidence_rigor?.split(' - ')[0]} isDark={isDark} />

              {(rich.donor_fit_matrix.geographic_focus?.length ?? 0) > 0 && (
                <div className={`py-2 border-b ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                  <span className={`text-sm block mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Geographic Focus</span>
                  <span className={`text-xs ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {rich.donor_fit_matrix.geographic_focus?.slice(0, 3).join(', ')}
                  </span>
                </div>
              )}

            </div>
          )}

          {/* Impact Evidence (Rich only, authenticated) */}
          {isSignedIn && rich?.impact_evidence && (
            <div className={`mb-6 p-4 rounded-lg border ${
              isDark ? 'bg-slate-800/50 border-slate-700' : 'bg-slate-50 border-slate-200'
            }`}>
              <div className={`text-xs uppercase tracking-widest font-semibold mb-3 ${
                isDark ? 'text-slate-400' : 'text-slate-500'
              }`}>
                Impact Evidence
              </div>

              {/* NEW_ORG context note */}
              {charity.evaluationTrack === 'NEW_ORG' && (
                <div className={`mb-3 p-2 rounded text-xs ${
                  isDark ? 'bg-sky-900/30 text-sky-300 border border-sky-800/50' : 'bg-sky-50 text-sky-700 border border-sky-200'
                }`}>
                  <strong>Emerging org evaluation:</strong> As a newer organization{charity.foundedYear ? ` (est. ${charity.foundedYear})` : ''},
                  evidence is assessed on theory of change and early indicators rather than years of outcome data.
                </div>
              )}

              {/* Evidence Grade */}
              <div className="flex items-start gap-2 mb-3">
                <span className={`px-2 py-1 rounded font-mono font-bold text-sm flex-shrink-0 ${
                  rich.impact_evidence.evidence_grade === 'A' || rich.impact_evidence.evidence_grade === 'B'
                    ? isDark ? 'bg-emerald-900/50 text-emerald-400' : 'bg-emerald-100 text-emerald-700'
                    : rich.impact_evidence.evidence_grade === 'C' || rich.impact_evidence.evidence_grade === 'D'
                    ? isDark ? 'bg-amber-900/50 text-amber-400' : 'bg-amber-100 text-amber-700'
                    : isDark ? 'bg-red-900/50 text-red-400' : 'bg-red-100 text-red-700'
                }`}>
                  {rich.impact_evidence.evidence_grade}
                </span>
                <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  <SourceLinkedText
                    text={rich.impact_evidence.evidence_grade_explanation || ''}
                    citations={citations}
                    isDark={isDark}
                  />
                </span>
              </div>

              {/* Key indicators */}
              <div className={`space-y-1.5 text-xs ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                <div className="flex justify-between">
                  <span>RCT Available</span>
                  <span className={`font-mono ${
                    rich.impact_evidence.rct_available
                      ? isDark ? 'text-emerald-400' : 'text-emerald-600'
                      : isDark ? 'text-slate-500' : 'text-slate-400'
                  }`}>
                    {rich.impact_evidence.rct_available ? 'YES' : 'NO'}
                  </span>
                </div>
                {rich.impact_evidence.theory_of_change && (
                  <div className="flex justify-between">
                    <span>Theory of Change</span>
                    <span className="font-mono">{rich.impact_evidence.theory_of_change.toUpperCase()}</span>
                  </div>
                )}
              </div>

              {rich.impact_evidence.theory_of_change_summary && (
                <div className={`mt-3 pt-3 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                  <div className={`text-xs font-semibold mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    Theory of Change Summary
                  </div>
                  <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    <SourceLinkedText
                      text={rich.impact_evidence.theory_of_change_summary}
                      citations={citations}
                      isDark={isDark}
                    />
                  </p>
                  {theoryOfChangeCitations.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {theoryOfChangeCitations.map((c, i) => (
                        <a
                          key={`${c.id || 'toc'}-${i}`}
                          href={c.source_url || undefined}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] border ${
                            isDark
                              ? 'border-emerald-800/60 text-emerald-400 hover:bg-emerald-900/20'
                              : 'border-emerald-200 text-emerald-700 hover:bg-emerald-50'
                          }`}
                          title={c.source_name || 'Source'}
                        >
                          {(c.source_name || `Source ${i + 1}`).replace(/^Charity Website\s*-\s*/i, '')}
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* External Evaluations */}
              {rich.impact_evidence.external_evaluations && rich.impact_evidence.external_evaluations.length > 0 && (
                <div className={`mt-2 pt-2 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                  <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>External Evaluations</div>
                  <div className={`text-xs mt-1 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                    {rich.impact_evidence.external_evaluations.slice(0, 2).join(', ')}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Similar Organizations (Rich only, links gated behind auth) */}
          {(rich?.similar_organizations || rich?.peer_comparison) && (
            <div className={`mb-6 p-4 rounded-lg border ${
              isDark ? 'bg-slate-800/50 border-slate-700' : 'bg-slate-50 border-slate-200'
            }`}>
              <div className={`text-xs uppercase tracking-widest font-semibold mb-3 ${
                isDark ? 'text-slate-400' : 'text-slate-500'
              }`}>
                Similar Orgs
              </div>

              {/* Peer Group */}
              {rich?.peer_comparison && (
                <div className={`mb-3 pb-2 border-b ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                  <div className={`text-xs font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {rich.peer_comparison.peer_group}
                  </div>
                </div>
              )}

              {/* Similar Orgs List */}
              {rich?.similar_organizations && rich.similar_organizations.length > 0 && (
                <div className="space-y-1.5">
                  {rich.similar_organizations.slice(0, isSignedIn ? 4 : 3).map((org, i) => {
                    const orgName = typeof org === 'string' ? org : org.name;
                    const linkedId = findCharityId(orgName);
                    return (
                      <div key={i} className="text-xs">
                        {isSignedIn && linkedId ? (
                          <Link
                            to={`/charity/${linkedId}`}
                            className={`flex items-center gap-1 ${
                              isDark ? 'text-emerald-400 hover:text-emerald-300' : 'text-emerald-600 hover:text-emerald-700'
                            }`}
                          >
                            {orgName}
                            <ExternalLink className="w-2.5 h-2.5" />
                          </Link>
                        ) : (
                          <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>{orgName}</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Sign-in prompt for unauthenticated users */}
              {!isSignedIn && (
                <SignInButton
                  variant="custom"
                  className={`mt-3 pt-2 border-t text-xs flex items-center gap-1.5 w-full text-left cursor-pointer hover:opacity-80 transition-opacity ${
                    isDark ? 'border-slate-700 text-emerald-400' : 'border-slate-200 text-emerald-600'
                  }`}
                >
                  <Lock className="w-3 h-3 flex-shrink-0" />
                  <span>
                    <span className="underline font-medium">Sign in</span>
                    {' '}to compare
                  </span>
                </SignInButton>
              )}
            </div>
          )}

        </aside>

        {/* Center Content */}
        <main className={`lg:col-span-6 px-6 pt-0 pb-6 ${isDark ? 'bg-slate-950' : 'bg-slate-100'}`}>
          {/* === Section 1: Narrative / About === */}
          {(() => {
            // GMG: signed in with rich/baseline content
            if (isSignedIn && (rich?.summary || baseline?.summary)) {
              return (
                <div className={`border-l-4 p-5 rounded-r-lg mb-6 ${
                  isDark ? 'bg-slate-900 border-slate-600' : 'bg-white border-slate-300'
                }`}>
                  <div className={`text-xs uppercase tracking-widest font-semibold mb-3 ${
                    isDark ? 'text-slate-400' : 'text-slate-500'
                  }`}>
                    About
                  </div>
                  <p className={`text-base font-medium leading-relaxed ${isDark ? 'text-slate-100' : 'text-slate-800'}`}>
                    <SourceLinkedText
                      text={rich?.headline || baseline?.headline || ''}
                      citations={citations}
                      isDark={isDark}
                    />
                  </p>
                  <p className={`text-sm mt-3 leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                    <SourceLinkedText
                      text={rich?.summary || baseline?.summary || ''}
                      citations={citations}
                      isDark={isDark}
                    />
                  </p>
                </div>
              );
            }

            // GMG: not signed in, has rich (show baseline + sign-in prompt)
            if (!isSignedIn && hasRich) {
              return (
                <div className={`border-l-4 p-4 rounded-r-lg mb-6 ${
                  isDark ? 'bg-slate-800/50 border-slate-600' : 'bg-slate-50 border-slate-300'
                }`}>
                  <div className={`text-xs uppercase tracking-widest font-semibold mb-2 ${
                    isDark ? 'text-slate-400' : 'text-slate-500'
                  }`}>
                    About
                  </div>
                  <p className={`text-sm ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                    <strong>
                      <SourceLinkedText
                        text={baseline?.headline || ''}
                        citations={citations}
                        isDark={isDark}
                      />
                    </strong>
                  </p>
                  {baseline?.summary && (
                    <p className={`text-sm mt-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                      <SourceLinkedText
                        text={baseline.summary}
                        citations={citations}
                        isDark={isDark}
                      />
                    </p>
                  )}
                  <SignInButton
                    variant="custom"
                    className={`mt-3 pt-3 border-t text-sm flex items-center gap-2 w-full text-left cursor-pointer hover:opacity-80 transition-opacity ${
                      isDark ? 'border-slate-700 text-emerald-400' : 'border-slate-200 text-emerald-600'
                    }`}
                  >
                    <Lock className="w-3.5 h-3.5 flex-shrink-0" />
                    <span>
                      <span className="underline font-medium">Sign in</span>
                      {' '}to unlock full analysis with evidence grades and source citations
                    </span>
                  </SignInButton>
                </div>
              );
            }

            // GMG: not signed in, baseline only
            if (!isSignedIn && baseline) {
              return (
                <div className={`border-l-4 p-4 rounded-r-lg mb-6 ${
                  isDark ? 'bg-slate-900 border-slate-600' : 'bg-white border-slate-300'
                }`}>
                  <div className={`text-xs uppercase tracking-widest font-semibold mb-2 ${
                    isDark ? 'text-slate-400' : 'text-slate-500'
                  }`}>
                    About
                  </div>
                  <p className={`text-sm ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                    <strong>
                      <SourceLinkedText
                        text={baseline?.headline || ''}
                        citations={citations}
                        isDark={isDark}
                      />
                    </strong>
                  </p>
                  {baseline?.summary && (
                    <p className={`text-sm mt-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                      <SourceLinkedText
                        text={baseline.summary}
                        citations={citations}
                        isDark={isDark}
                      />
                    </p>
                  )}
                </div>
              );
            }

            return null;
          })()}

          {/* === Section 2: Best For (moved above Score Analysis) === */}
          {(() => {
            const donorProfile = isSignedIn ? idealDonorProfile : null;

            if (!donorProfile) return null;

            return (
              <div className={`border-l-4 p-4 rounded-r-lg mb-6 ${
                isDark ? 'bg-emerald-900/20 border-emerald-500' : 'bg-emerald-50 border-emerald-600'
              }`}>
                <div className={`text-xs uppercase tracking-widest font-semibold mb-2 ${
                  isDark ? 'text-emerald-400' : 'text-emerald-700'
                }`}>
                  Best For
                </div>
                <p className={`text-sm font-medium mb-3 ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                  {donorProfile.best_for_summary}
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {donorProfile.donor_motivations?.length > 0 && (
                    <div>
                      <div className={`text-xs font-semibold mb-1 flex items-center gap-1 ${
                        isDark ? 'text-emerald-400' : 'text-emerald-600'
                      }`}>
                        <Target className="w-3 h-3" />
                        Ideal for donors who:
                      </div>
                      <ul className={`text-xs space-y-0.5 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                        {donorProfile.donor_motivations.slice(0, 4).map((m: string, i: number) => (
                          <li key={i} className="flex items-start gap-1">
                            <span className="text-emerald-500">•</span>
                            {m}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {donorProfile.giving_considerations?.length > 0 && (
                    <div>
                      <div className={`text-xs font-semibold mb-1 flex items-center gap-1 ${
                        isDark ? 'text-slate-400' : 'text-slate-500'
                      }`}>
                        <Scale className="w-3 h-3" />
                        Consider:
                      </div>
                      <ul className={`text-xs space-y-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                        {donorProfile.giving_considerations.slice(0, 3).map((c: string, i: number) => (
                          <li key={i} className="flex items-start gap-1">
                            <span>•</span>
                            {c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {donorProfile.not_ideal_for && (
                  <div className={`mt-3 pt-2 border-t text-xs flex items-start gap-1 ${
                    isDark ? 'border-slate-700 text-amber-400' : 'border-slate-200 text-amber-600'
                  }`}>
                    <AlertCircle className="w-3 h-3 shrink-0 mt-0.5" />
                    <span><strong>Not ideal for:</strong> {donorProfile.not_ideal_for}</span>
                  </div>
                )}
              </div>
            );
          })()}

          {/* === Section 3: Methodology Details (always open) === */}
          {amal?.score_details && (
            <div className={`mb-6 rounded-lg border ${isDark ? 'border-slate-700 bg-slate-900/40' : 'border-slate-200 bg-white'}`}>
              <div className={`px-4 py-3 text-sm font-semibold ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                Methodology details
              </div>
              <div className="px-2 pb-2">
                <ScoreBreakdown
                  scoreDetails={amal.score_details}
                  confidenceScores={scores}
                  amalScore={amalScore}
                  citations={citations}
                  isSignedIn={isSignedIn}
                  isDark={isDark}
                  dimensionExplanations={rich?.dimension_explanations || baseline?.dimension_explanations}
                  amalScoreRationale={isSignedIn ? rich?.amal_score_rationale : undefined}
                  scoreSummary={charity.scoreSummary}
                  strengths={isSignedIn ? rich?.strengths : baseline?.strengths}
                  areasForImprovement={
                    (isSignedIn ? rich?.areas_for_improvement : baseline?.areas_for_improvement) as
                      Array<string | { area: string; context: string; citation_ids: string[] }> | undefined
                  }
                />
              </div>
            </div>
          )}

          {/* === Evidence Quality Checklist === */}
          {charity.evidenceQuality && (
            <div className={`rounded-lg border p-5 mb-6 ${isDark ? 'bg-slate-800/50 border-slate-700' : 'bg-slate-50 border-slate-200'}`}>
              <div className={`text-xs uppercase tracking-widest font-semibold mb-3 flex items-center gap-2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                <Shield className="w-4 h-4" />
                Evidence Quality
              </div>
              <div className="space-y-2">
                {[
                  { key: 'hasOutcomeMethodology', label: 'Outcome methodology documented' },
                  { key: 'hasMultiYearMetrics', label: 'Multi-year metrics tracked' },
                  { key: 'thirdPartyEvaluated', label: 'Third-party evaluated' },
                  { key: 'receivesFoundationGrants', label: 'Receives foundation grants' },
                ].map(({ key, label }) => {
                  const val = (charity.evidenceQuality as Record<string, unknown>)?.[key];
                  if (val === null || val === undefined) return null;
                  return (
                    <div key={key} className="flex items-center gap-2 text-sm">
                      {val ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                      ) : (
                        <AlertCircle className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-slate-600' : 'text-slate-400'}`} />
                      )}
                      <span className={val ? (isDark ? 'text-slate-300' : 'text-slate-700') : (isDark ? 'text-slate-500' : 'text-slate-400')}>
                        {label}
                      </span>
                    </div>
                  );
                })}
                {charity.evidenceQuality.evaluationSources && charity.evidenceQuality.evaluationSources.length > 0 && (
                  <div className={`mt-2 pt-2 border-t text-xs ${isDark ? 'border-slate-700 text-slate-500' : 'border-slate-200 text-slate-400'}`}>
                    Sources: {charity.evidenceQuality.evaluationSources.join(', ')}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* === Theory of Change (baseline fallback) === */}
          {!rich?.impact_evidence && charity.theoryOfChange && (
            <div className={`rounded-lg border p-5 mb-6 ${isDark ? 'bg-slate-800/50 border-slate-700' : 'bg-slate-50 border-slate-200'}`}>
              <div className={`text-xs uppercase tracking-widest font-semibold mb-3 flex items-center gap-2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                <Target className="w-4 h-4" />
                Theory of Change
              </div>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                <SourceLinkedText text={charity.theoryOfChange} citations={citations} isDark={isDark} />
              </p>
              {theoryOfChangeCitations.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {theoryOfChangeCitations.map((c, i) => (
                    <a
                      key={`${c.id || 'toc-fallback'}-${i}`}
                      href={c.source_url || undefined}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] border ${
                        isDark
                          ? 'border-emerald-800/60 text-emerald-400 hover:bg-emerald-900/20'
                          : 'border-emerald-200 text-emerald-700 hover:bg-emerald-50'
                      }`}
                      title={c.source_name || 'Source'}
                    >
                      {(c.source_name || `Source ${i + 1}`).replace(/^Charity Website\s*-\s*/i, '')}
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* === Section 6: Balanced View === */}
          {isSignedIn && rich?.case_against && (
            <div className={`rounded-lg border-2 p-5 mb-6 ${
              isDark ? 'bg-violet-900/10 border-violet-600/50' : 'bg-violet-50 border-violet-300'
            }`}>
              <div className={`text-xs uppercase tracking-widest font-semibold mb-3 flex items-center gap-2 ${
                isDark ? 'text-violet-400' : 'text-violet-700'
              }`}>
                <Scale className="w-4 h-4" />
                Balanced View
              </div>
              <p className={`text-sm mb-3 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                <SourceLinkedText text={rich.case_against.summary} citations={citations} isDark={isDark} />
              </p>
              {rich.case_against.risk_factors?.length > 0 && (
                <div className="space-y-2">
                  <div className={`text-xs font-semibold flex items-center gap-1 ${isDark ? 'text-violet-400' : 'text-violet-600'}`}>
                    <AlertTriangle className="w-3 h-3" />
                    Risk Factors
                  </div>
                  <ul className={`text-xs space-y-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {rich.case_against.risk_factors.map((risk, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-violet-500 mt-0.5">•</span>
                        <SourceLinkedText text={risk} citations={citations} isDark={isDark} />
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {rich.case_against.mitigation_notes && (
                <div className={`mt-3 pt-2 border-t text-xs ${isDark ? 'border-slate-700 text-slate-500' : 'border-slate-200 text-slate-500'}`}>
                  <span className="font-semibold">Mitigation:</span> {rich.case_against.mitigation_notes}
                </div>
              )}
            </div>
          )}
        </main>

        {/* Right Panel */}
        <aside className={`lg:col-span-3 pr-6 pl-4 py-4 border-t lg:border-t-0 lg:border-l ${
          isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
        }`}>
          {/* 1. Reference metadata / Emerging Org card */}
          {charity.evaluationTrack === 'NEW_ORG' ? (
            <div className={`mb-6 p-4 rounded-lg border-2 ${
              isDark
                ? 'bg-gradient-to-br from-sky-900/40 via-indigo-900/30 to-purple-900/20 border-sky-700/60'
                : 'bg-gradient-to-br from-sky-50 via-indigo-50 to-purple-50 border-sky-300'
            }`}>
              {/* Header with icon */}
              <div className="flex items-center gap-2 mb-3">
                <div className={`p-1.5 rounded-lg ${isDark ? 'bg-sky-800/50' : 'bg-sky-200/70'}`}>
                  <Rocket className={`w-4 h-4 ${isDark ? 'text-sky-400' : 'text-sky-600'}`} />
                </div>
                <div>
                  <div className={`text-xs uppercase tracking-widest font-bold ${
                    isDark ? 'text-sky-400' : 'text-sky-700'
                  }`}>
                    Emerging Organization
                  </div>
                  {charity.foundedYear && (
                    <div className={`text-xs ${isDark ? 'text-sky-300/70' : 'text-sky-600/80'}`}>
                      Est. {charity.foundedYear} · Building Track Record
                    </div>
                  )}
                </div>
              </div>

              {/* Encouraging message */}
              <p className={`text-sm leading-relaxed mb-4 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                This organization is in its early stages. We evaluate emerging orgs on
                <span className={`font-medium ${isDark ? 'text-sky-300' : 'text-sky-700'}`}> vision and early indicators </span>
                rather than years of data.
              </p>

              {/* What we know - checkmarks */}
              <div className={`space-y-2 mb-4`}>
                <div className={`text-xs font-semibold uppercase tracking-wide ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Early Indicators
                </div>
                {(() => {
                  // Gather positive indicators
                  const indicators: Array<{label: string, detail?: string}> = [];

                  // Candid seal
                  const candidSeal = charity.sourceAttribution?.candid_seal?.value;
                  if (candidSeal) {
                    indicators.push({
                      label: `Candid ${String(candidSeal).charAt(0).toUpperCase() + String(candidSeal).slice(1)} Seal`,
                      detail: 'Transparency verified'
                    });
                  }

                  // 501c3 status (if we have EIN, they're registered)
                  if (charity.ein) {
                    indicators.push({ label: '501(c)(3) Status', detail: 'IRS registered' });
                  }

                  // Theory of change from score details
                  const toc = amal?.score_details?.evidence?.theory_of_change;
                  if (toc && toc !== 'NONE' && toc !== 'ABSENT') {
                    indicators.push({
                      label: 'Theory of Change',
                      detail: toc === 'DOCUMENTED' ? 'Documented' : 'Articulated'
                    });
                  }

                  // Website
                  if (charity.website) {
                    indicators.push({ label: 'Active Web Presence' });
                  }

                  return (
                    <div className="space-y-1.5">
                      {indicators.map((ind, i) => (
                        <div key={i} className="flex items-center gap-2">
                          <CheckCircle2 className={`w-3.5 h-3.5 flex-shrink-0 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                          <span className={`text-sm ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                            {ind.label}
                          </span>
                          {ind.detail && (
                            <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                              · {ind.detail}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  );
                })()}
              </div>

              {/* Call to action */}
              <div className={`p-3 rounded-lg ${isDark ? 'bg-sky-950/50' : 'bg-white/70'}`}>
                <div className="flex items-start gap-2">
                  <Sparkles className={`w-4 h-4 mt-0.5 flex-shrink-0 ${isDark ? 'text-amber-400' : 'text-amber-500'}`} />
                  <div>
                    <div className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                      Early-Stage Opportunity
                    </div>
                    <p className={`text-xs mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                      Supporting emerging organizations can have outsized impact. Your donation helps them build the track record they need.
                    </p>
                  </div>
                </div>
              </div>

              {/* EIN, address, and eval date */}
              <div className={`mt-4 pt-3 border-t text-xs space-y-1 ${isDark ? 'border-sky-800/50 text-slate-500' : 'border-sky-200 text-slate-400'}`}>
                <div className="flex justify-between">
                  <span>EIN</span>
                  <span className="font-mono">{charity.ein || charity.id}</span>
                </div>
                {getCharityAddress(charity) && (
                  <div className="flex justify-between">
                    <span>HQ</span>
                    <span className="text-right">{getCharityAddress(charity)}</span>
                  </div>
                )}
                {amal?.evaluation_date && (
                  <div className="flex justify-between">
                    <span>Evaluated</span>
                    <span>{new Date(amal.evaluation_date).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}</span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* Reference metadata */
            <div className={`mb-6 space-y-1 text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              <div className={`text-xs uppercase tracking-widest font-semibold mb-2 ${
                isDark ? 'text-slate-500' : 'text-slate-400'
              }`}>
                Reference
              </div>
              <div className="flex justify-between">
                <span>EIN</span>
                <span className="font-mono">{charity.ein || charity.id}</span>
              </div>
              {getCharityAddress(charity) && (
                <div className="flex justify-between">
                  <span>HQ</span>
                  <span className="text-right">{getCharityAddress(charity)}</span>
                </div>
              )}
              {rich?.data_confidence?.form_990_tax_year && (
                <div className="flex justify-between">
                  <span>990 Year</span>
                  <span className="font-mono">{rich.data_confidence.form_990_tax_year}</span>
                </div>
              )}
              {amal?.evaluation_date && (
                <div className="flex justify-between">
                  <span>Evaluated</span>
                  <span>{new Date(amal.evaluation_date).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}</span>
                </div>
              )}
            </div>
          )}

          {/* 2. Leadership & Governance (Rich only, authenticated) */}
          {isSignedIn && rich?.organizational_capacity && (
            <div className={`mb-6 p-4 rounded-lg border ${
              isDark ? 'bg-slate-800/50 border-slate-700' : 'bg-slate-50 border-slate-200'
            }`}>
              <div className={`text-xs uppercase tracking-widest font-semibold mb-3 ${
                isDark ? 'text-slate-400' : 'text-slate-500'
              }`}>
                Leadership
              </div>

              {/* CEO */}
              {rich.organizational_capacity.ceo_name && (
                <div className={`mb-3 pb-3 border-b ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                  <div className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {rich.organizational_capacity.ceo_name}
                  </div>
                  <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    CEO/Executive Director
                    {!!rich.organizational_capacity.ceo_compensation && (
                      <span className="ml-2 font-mono">
                        ({formatCurrency(rich.organizational_capacity.ceo_compensation)})
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Governance Stats */}
              <div className={`space-y-1.5 text-xs ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                {!!rich.organizational_capacity.board_size && (
                  <div className="flex justify-between">
                    <span>Board Size</span>
                    <span className="font-mono">{rich.organizational_capacity.board_size}</span>
                  </div>
                )}
                {rich.organizational_capacity.independent_board_pct !== undefined && (
                  <div className="flex justify-between">
                    <span>Independent</span>
                    <span className="font-mono">{(rich.organizational_capacity.independent_board_pct * 100).toFixed(0)}%</span>
                  </div>
                )}
                {!!rich.organizational_capacity.employees_count && (
                  <div className="flex justify-between">
                    <span>Employees</span>
                    <span className="font-mono">{rich.organizational_capacity.employees_count}</span>
                  </div>
                )}
                {rich.organizational_capacity.volunteers_count !== undefined && rich.organizational_capacity.volunteers_count > 0 && (
                  <div className="flex justify-between">
                    <span>Volunteers</span>
                    <span className="font-mono">{rich.organizational_capacity.volunteers_count}</span>
                  </div>
                )}
              </div>

              {/* Governance Checklist */}
              <div className={`mt-3 pt-3 border-t grid grid-cols-2 gap-2 text-xs ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                <div className="flex items-center gap-1.5">
                  {rich.organizational_capacity.has_conflict_policy ? (
                    <CheckCircle2 className={`w-3 h-3 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                  ) : (
                    <AlertCircle className={`w-3 h-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                  )}
                  <span className={isDark ? 'text-slate-400' : 'text-slate-600'}>COI Policy</span>
                </div>
                <div className="flex items-center gap-1.5">
                  {rich.organizational_capacity.has_financial_audit ? (
                    <CheckCircle2 className={`w-3 h-3 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                  ) : (
                    <AlertCircle className={`w-3 h-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                  )}
                  <span className={isDark ? 'text-slate-400' : 'text-slate-600'}>Audited</span>
                </div>
              </div>
            </div>
          )}

          {/* 2b. Baseline Governance - for charities without rich narratives */}
          {!rich?.organizational_capacity && charity.baselineGovernance && (
            <div className="mb-6">
              <div className={`text-xs uppercase tracking-widest font-semibold mb-3 ${
                isDark ? 'text-slate-500' : 'text-slate-400'
              }`}>
                Governance
              </div>
              <div className={`space-y-1.5 text-xs ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                {!!charity.baselineGovernance.boardSize && (
                  <div className="flex justify-between">
                    <span className={isDark ? 'text-slate-400' : 'text-slate-500'}>Board Size</span>
                    <span className="font-mono">{charity.baselineGovernance.boardSize}</span>
                  </div>
                )}
                {!!charity.baselineGovernance.independentBoardMembers && (
                  <div className="flex justify-between">
                    <span className={isDark ? 'text-slate-400' : 'text-slate-500'}>Independent Members</span>
                    <span className="font-mono">{charity.baselineGovernance.independentBoardMembers}</span>
                  </div>
                )}
                {!!charity.baselineGovernance.ceoCompensation && (
                  <div className="flex justify-between">
                    <span className={isDark ? 'text-slate-400' : 'text-slate-500'}>CEO Compensation</span>
                    <span className="font-mono">{formatCurrency(charity.baselineGovernance.ceoCompensation)}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 3. Citation Stats / Sources (Rich only, authenticated) */}
          {isSignedIn && rich?.citation_stats && (
            <div className={`mb-6 p-4 rounded-lg border ${
              isDark ? 'bg-slate-800/50 border-slate-700' : 'bg-slate-50 border-slate-200'
            }`}>
              <div className={`text-xs uppercase tracking-widest font-semibold mb-3 ${
                isDark ? 'text-slate-400' : 'text-slate-500'
              }`}>
                Sources
              </div>
              <div className={`space-y-1.5 text-xs ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                <div className="flex justify-between">
                  <span>Total Citations</span>
                  <span className="font-mono">{rich.citation_stats.total_count}</span>
                </div>
                <div className="flex justify-between">
                  <span>Unique Sources</span>
                  <span className="font-mono">{rich.citation_stats.unique_sources}</span>
                </div>
                <div className="flex justify-between">
                  <span>Strong Sources</span>
                  <span className={`font-mono ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                    {rich.citation_stats.high_confidence_count}
                  </span>
                </div>
              </div>
              {rich.citation_stats.by_source_type && (
                <div className={`mt-2 pt-2 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(rich.citation_stats.by_source_type).map(([type, count]) => (
                      <span key={type} className={`px-1.5 py-0.5 rounded text-xs ${
                        isDark ? 'bg-slate-700 text-slate-300' : 'bg-slate-200 text-slate-600'
                      }`}>
                        {type}: {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 4. BBB Wise Giving */}
          {isSignedIn && rich?.bbb_assessment && (
            rich.bbb_assessment.meets_all_standards ||
            (rich.bbb_assessment.standards_met && rich.bbb_assessment.standards_met > 0) ||
            (rich.bbb_assessment.standards_not_met && rich.bbb_assessment.standards_not_met.length > 0) ||
            rich.bbb_assessment.review_url ||
            rich.bbb_assessment.summary ||
            rich.bbb_assessment.audit_type
          ) && (
            <div className={`mb-6 p-4 rounded-lg border-l-4 ${
              rich.bbb_assessment.meets_all_standards
                ? isDark ? 'bg-emerald-900/20 border-emerald-500' : 'bg-emerald-50 border-emerald-500'
                : isDark ? 'bg-slate-800/50 border-amber-500' : 'bg-amber-50/50 border-amber-500'
            }`}>
              <div className={`text-xs uppercase tracking-widest font-bold mb-3 flex items-center gap-2 ${
                rich.bbb_assessment.meets_all_standards
                  ? isDark ? 'text-emerald-400' : 'text-emerald-700'
                  : isDark ? 'text-amber-400' : 'text-amber-700'
              }`}>
                <Shield className="w-3.5 h-3.5" />
                BBB Wise Giving
              </div>
              <div className="flex items-center gap-2 mb-3">
                {rich.bbb_assessment.meets_all_standards ? (
                  <CheckCircle2 className={`w-5 h-5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                ) : (
                  <AlertTriangle className={`w-5 h-5 ${isDark ? 'text-amber-400' : 'text-amber-600'}`} />
                )}
                <span className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {rich.bbb_assessment.meets_all_standards ? 'Meets All Standards' : 'Standards Review'}
                </span>
                {rich.bbb_assessment.standards_met !== undefined && rich.bbb_assessment.standards_met > 0 && (
                  <span className={`text-xs font-mono ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    ({rich.bbb_assessment.standards_met}/20)
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-1.5 mb-3">
                {['governance', 'effectiveness', 'finances'].map((category) => {
                  const statusKey = `${category}_status` as 'governance_status' | 'effectiveness_status' | 'finances_status';
                  const status = rich.bbb_assessment![statusKey];
                  const isPassing = status === 'pass' || status === 'Pass' || status === 'PASS';
                  return status && status !== 'NEUTRAL' ? (
                    <div key={category} className="flex items-center gap-1.5 text-xs">
                      {isPassing ? (
                        <CheckCircle2 className={`w-3 h-3 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                      ) : (
                        <AlertCircle className={`w-3 h-3 ${isDark ? 'text-amber-400' : 'text-amber-600'}`} />
                      )}
                      <span className={`capitalize ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                        {category}
                      </span>
                    </div>
                  ) : null;
                })}
                {rich.bbb_assessment.audit_type && (
                  <div className="flex items-center gap-1.5 text-xs">
                    <CheckCircle2 className={`w-3 h-3 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                    <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>
                      {rich.bbb_assessment.audit_type}
                    </span>
                  </div>
                )}
              </div>
              {rich.bbb_assessment.summary && (
                <p className={`text-xs mb-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  <SourceLinkedText text={rich.bbb_assessment.summary} citations={citations} isDark={isDark} subtle />
                </p>
              )}
              {rich.bbb_assessment.standards_not_met && rich.bbb_assessment.standards_not_met.length > 0 && (
                <div className={`pt-2 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                  <div className={`text-xs font-semibold mb-1 flex items-center gap-1 ${
                    isDark ? 'text-amber-400' : 'text-amber-600'
                  }`}>
                    <AlertTriangle className="w-3 h-3" />
                    Not Met
                  </div>
                  <ul className={`text-xs space-y-0.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {rich.bbb_assessment.standards_not_met.slice(0, 3).map((std, i) => (
                      <li key={i}>• {std}</li>
                    ))}
                  </ul>
                </div>
              )}
              {rich.bbb_assessment.review_url && (
                <a
                  href={rich.bbb_assessment.review_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => trackOutboundClick(charity.id ?? charity.ein ?? '', charity.name, 'give.org')}
                  className={`mt-2 inline-flex items-center gap-1 text-xs font-medium ${
                    isDark ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'
                  }`}
                >
                  View on give.org
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          )}

          {/* Populations Served */}
          {charity.populationsServed && charity.populationsServed.length > 0 && (
            <div className="mb-6">
              <div className={`text-xs uppercase tracking-widest font-semibold mb-2 ${
                isDark ? 'text-slate-500' : 'text-slate-400'
              }`}>
                Populations
              </div>
              <div className={`text-sm leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                {charity.populationsServed.slice(0, 5).join(', ')}
              </div>
            </div>
          )}

          {/* Grantmaking Profile (Rich only, authenticated) */}
          {isSignedIn && rich?.grantmaking_profile && rich.grantmaking_profile.is_significant_grantmaker && (
            <div className={`mb-6 p-4 rounded-lg border ${
              isDark ? 'bg-slate-800/50 border-slate-700' : 'bg-slate-50 border-slate-200'
            }`}>
              <div className={`text-xs uppercase tracking-widest font-semibold mb-3 flex items-center gap-2 ${
                isDark ? 'text-slate-400' : 'text-slate-500'
              }`}>
                <Landmark className="w-3 h-3" />
                Grantmaking
              </div>
              {rich.grantmaking_profile.total_grants && (
                <div className={`mb-3 pb-2 border-b ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                  <div className={`text-xl font-mono font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {formatCurrency(rich.grantmaking_profile.total_grants)}
                  </div>
                  <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    Total Grants ({rich.grantmaking_profile.grant_count || 0} recipients)
                  </div>
                </div>
              )}
              <div className={`space-y-1 text-xs ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                {rich.grantmaking_profile.domestic_grants !== undefined && (
                  <div className="flex justify-between">
                    <span>Domestic</span>
                    <span className="font-mono">{formatCurrency(rich.grantmaking_profile.domestic_grants)}</span>
                  </div>
                )}
                {rich.grantmaking_profile.foreign_grants !== undefined && (
                  <div className="flex justify-between">
                    <span>International</span>
                    <span className="font-mono">{formatCurrency(rich.grantmaking_profile.foreign_grants)}</span>
                  </div>
                )}
              </div>
              {rich.grantmaking_profile.top_recipients && rich.grantmaking_profile.top_recipients.length > 0 && (
                <div className={`mt-2 pt-2 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                  <div className={`text-xs font-semibold mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    Top Recipients
                  </div>
                  <ul className={`text-xs space-y-0.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {rich.grantmaking_profile.top_recipients.slice(0, 3).map((recipient, i) => (
                      <li key={i}>• {recipient}</li>
                    ))}
                  </ul>
                </div>
              )}
              {rich.grantmaking_profile.regions_served && rich.grantmaking_profile.regions_served.length > 0 && (
                <div className={`mt-2 pt-2 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                  <div className="flex flex-wrap gap-1">
                    {rich.grantmaking_profile.regions_served.slice(0, 4).map((region, i) => (
                      <span key={i} className={`px-1.5 py-0.5 rounded text-xs ${
                        isDark ? 'bg-slate-700 text-slate-300' : 'bg-slate-200 text-slate-600'
                      }`}>
                        {region}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 5. External Links */}
          <div>
            <div className={`text-xs uppercase tracking-widest font-semibold mb-2 ${
              isDark ? 'text-slate-500' : 'text-slate-400'
            }`}>
              External
            </div>
            <div className="space-y-2">
              {charity.website && (
                <a
                  href={charity.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`flex items-center gap-2 text-sm ${
                    isDark ? 'text-emerald-400 hover:text-emerald-300' : 'text-emerald-600 hover:text-emerald-700'
                  }`}
                >
                  Website <ExternalLink className="w-3 h-3" />
                </a>
              )}
              <a
                href={`https://www.charitynavigator.org/ein/${(charity.ein ?? charity.id ?? '').replace(/-/g, '')}`}
                target="_blank"
                rel="noopener noreferrer"
                className={`flex items-center justify-between text-sm ${
                  isDark ? 'text-slate-400 hover:text-slate-300' : 'text-slate-500 hover:text-slate-600'
                }`}
              >
                <span className="flex items-center gap-1">
                  Charity Navigator
                  <ExternalLink className="w-3 h-3" />
                </span>
                {charity.scores?.overall && (
                  <span className={`font-mono ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                    {Math.round(charity.scores.overall)}
                  </span>
                )}
              </a>
              <a
                href={`https://projects.propublica.org/nonprofits/organizations/${(charity.ein ?? charity.id ?? '').replace(/-/g, '')}`}
                target="_blank"
                rel="noopener noreferrer"
                className={`flex items-center gap-2 text-sm ${
                  isDark ? 'text-slate-400 hover:text-slate-300' : 'text-slate-500 hover:text-slate-600'
                }`}
              >
                ProPublica 990 <ExternalLink className="w-3 h-3" />
              </a>
              {rich?.bbb_assessment?.review_url && (
                <a
                  href={rich.bbb_assessment.review_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => trackOutboundClick(charity.id ?? charity.ein ?? '', charity.name, 'give.org')}
                  className={`flex items-center justify-between text-sm ${
                    isDark ? 'text-slate-400 hover:text-slate-300' : 'text-slate-500 hover:text-slate-600'
                  }`}
                >
                  <span className="flex items-center gap-1">
                    BBB Wise Giving
                    <ExternalLink className="w-3 h-3" />
                  </span>
                  {rich.bbb_assessment.meets_all_standards && (
                    <span className={`font-medium ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                      ✓ Accredited
                    </span>
                  )}
                </a>
              )}
            </div>
          </div>
        </aside>
      </div>

      {/* Footer */}
      <div className={`hidden lg:block border-t mt-8 pt-6 pb-8 ${
        isDark ? 'border-slate-800' : 'border-slate-200'
      }`}>
        <div className={`max-w-7xl mx-auto px-6 flex items-center justify-center gap-2 text-xs ${
          isDark ? 'text-slate-500' : 'text-slate-400'
        }`}>
          <span>EIN: {charity.ein}</span>
          {amal?.evaluation_date && (
            <>
              <span>·</span>
              <span>Last evaluated {new Date(amal.evaluation_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
            </>
          )}
          <span>·</span>
          <ReportIssueButton
            charityId={charity.ein!}
            charityName={charity.name}
            variant="text"
            isDark={isDark}
            className={`font-medium ${isDark ? 'text-slate-500 hover:text-slate-300' : 'text-slate-400 hover:text-slate-600'}`}
          />
        </div>
      </div>

      {/* Organization Engagement */}
      <div className="px-4 lg:px-6 pb-4">
        <OrganizationEngagement
          charityName={charity.name}
          charityEin={charity.ein!}
          isDark={isDark}
        />
      </div>

      {/* Donation Modal */}
      <AddDonationModal
        isOpen={showDonationModal}
        onClose={() => setShowDonationModal(false)}
        onSave={addDonation as any}
        paymentSources={getPaymentSources()}
        prefillCharity={{ ein: charity.ein!, name: charity.name }}
      />
    </div>
  );
};

export default TerminalView;

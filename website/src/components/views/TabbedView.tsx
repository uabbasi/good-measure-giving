/**
 * TabbedView: Clean tabbed layout for charity details (desktop only).
 * 5 tabs: Overview, Impact, Giving, Financials, Organization.
 * Niche.com-inspired card-based design as alternative to Bloomberg terminal layout.
 */

import React, { useMemo, useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getCharityAddress, formatCauseArea, formatShortRevenue } from '../../utils/formatters';
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
  Plus,
  LogIn,
  Sparkles,
  Rocket,
  Award,
  BarChart3,
  Users,
  Globe,
  BookOpen,
  FileText,
  Heart,
} from 'lucide-react';
import { CharityProfile } from '../../../types';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import { useAuth } from '../../auth/useAuth';
import { SignInButton } from '../../auth/SignInButton';
import { BookmarkButton } from '../BookmarkButton';
import { trackCharityView, trackOutboundClick, trackDonateClick, trackTabClick, trackSimilarOrgClick, trackExternalLinkClick } from '../../utils/analytics';
import { useCharities } from '../../hooks/useCharities';
import { useGivingHistory } from '../../hooks/useGivingHistory';
import { ReportIssueButton } from '../ReportIssueButton';
import { SourceLinkedText } from '../SourceLinkedText';
import { AddDonationModal } from '../giving/AddDonationModal';
import { getCauseCategoryTagClasses, getEvidenceStageClasses, getEvidenceStageLabel } from '../../utils/scoreConstants';
import { deriveUISignalsFromCharity, getArchetypeDescription } from '../../utils/scoreUtils';
import { ScoreBreakdown } from '../ScoreBreakdown';
import { RecommendationCue } from '../RecommendationCue';
import { InfoTip } from '../InfoTip';
import { GLOSSARY } from '../../data/glossary';
import { OrganizationEngagement } from '../OrganizationEngagement';
import { ContentPreview } from '../ContentPreview';
import { resolveCitationUrls, resolveSourceUrl } from '../../utils/citationUrls';
import { ShareButton } from '../ShareButton';
import { CompareButton } from '../CompareButton';

interface TabbedViewProps {
  charity: CharityProfile;
}

interface NarrativeCitation {
  id?: string;
  source_name?: string;
  source_url?: string | null;
  claim?: string;
}

type TabId = 'overview' | 'impact' | 'giving' | 'financials';

// --- Utility functions (same as TerminalView) ---

const formatCurrency = (value: number | null | undefined): string => {
  if (value == null) return 'N/A';
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}K`;
  return `$${value}`;
};

const formatWalletTag = (tag: string): string => {
  const cleanTag = tag?.replace(/[\[\]]/g, '') || '';
  if (cleanTag.includes('ZAKAT')) return 'Accepts Zakat';
  return 'Sadaqah';
};

const extractZakatPolicyUrl = (evidence: string): string | undefined => {
  const match = evidence.match(/\(Source:\s*(https?:\/\/[^\s)]+)\)/);
  return match?.[1];
};


const POPULATION_TAGS = new Set([
  'women', 'youth', 'children', 'disabled', 'refugees', 'low-income',
  'orphans', 'elderly', 'families', 'students', 'veterans', 'homeless',
  'fuqara', 'masakin', 'muallaf', 'fisabilillah', 'ibn-al-sabil', 'amil'
]);

const GEOGRAPHIC_TAGS = new Set([
  'usa', 'india', 'pakistan', 'bangladesh', 'afghanistan', 'palestine',
  'syria', 'sudan', 'yemen', 'somalia', 'turkey', 'jordan', 'lebanon',
  'iraq', 'gaza', 'global', 'south-africa', 'kenya', 'indonesia', 'malaysia',
  'ukraine', 'egypt', 'morocco', 'tunisia', 'nigeria', 'ethiopia'
]);

const INTERVENTION_TAGS = new Set([
  'educational', 'medical', 'food', 'water-sanitation', 'shelter', 'clothing',
  'legal-aid', 'vocational', 'microfinance', 'mental-health'
]);

const CHANGE_TYPE_TAGS = new Set([
  'emergency-response', 'direct-relief', 'direct-service', 'long-term-development',
  'advocacy', 'capacity-building', 'grantmaking', 'research', 'policy',
  'scalable-model', 'systemic-change'
]);

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

const categorizeTags = (tags: string[] | null | undefined) => {
  if (!tags || tags.length === 0) {
    return { populations: [] as string[], geography: [] as string[], interventions: [] as string[], changeTypes: [] as string[] };
  }
  const populations: string[] = [];
  const geography: string[] = [];
  const interventions: string[] = [];
  const changeTypes: string[] = [];
  tags.forEach(tag => {
    const lowerTag = tag.toLowerCase();
    if (POPULATION_TAGS.has(lowerTag)) populations.push(tag);
    else if (GEOGRAPHIC_TAGS.has(lowerTag)) geography.push(tag);
    else if (INTERVENTION_TAGS.has(lowerTag)) interventions.push(tag);
    else if (CHANGE_TYPE_TAGS.has(lowerTag)) changeTypes.push(tag);
  });
  return { populations, geography, interventions, changeTypes };
};

function formatProgramTag(raw: string): string {
  let cleaned = raw.replace(/\s+measures?\s*$/i, '');
  cleaned = cleaned.replace(/^Assist\s+/i, '');
  cleaned = cleaned.replace(/\band\b/gi, '&').replace(/\b\w/g, c => c.toUpperCase());
  return cleaned;
}

function getDifferentiatorTags(charity: CharityProfile, isDark: boolean): Array<{ label: string; colorClass: string }> {
  const tags: Array<{ label: string; priority: number; colorClass: string }> = [];
  const extended = charity as any;
  const allCauseTags = (charity.causeTags || []).map((t: string) => t.toLowerCase());
  const alignmentScore = charity.amalEvaluation?.confidence_scores?.alignment || 0;

  if (extended.impactTier === 'HIGH') {
    tags.push({ label: 'Highest Impact', priority: 2, colorClass: isDark ? 'bg-rose-900/50 text-rose-400' : 'bg-rose-100 text-rose-700' });
  }
  if (alignmentScore >= 42) {
    tags.push({ label: 'Maximum Alignment', priority: 2, colorClass: isDark ? 'bg-emerald-900/50 text-emerald-400' : 'bg-emerald-100 text-emerald-700' });
  }
  if (allCauseTags.includes('emergency-response')) {
    tags.push({ label: 'Emergency', priority: 3, colorClass: isDark ? 'bg-orange-900/50 text-orange-400' : 'bg-orange-100 text-orange-700' });
  }
  if (allCauseTags.includes('systemic-change')) {
    tags.push({ label: 'Tackles Root Causes', priority: 5, colorClass: isDark ? 'bg-blue-900/50 text-blue-400' : 'bg-blue-100 text-blue-700' });
  }
  if (allCauseTags.includes('scalable-model')) {
    tags.push({ label: 'Scalable', priority: 6, colorClass: isDark ? 'bg-teal-900/50 text-teal-400' : 'bg-teal-100 text-teal-700' });
  }
  if (allCauseTags.includes('grantmaking')) {
    tags.push({ label: 'Funds Other Orgs', priority: 7, colorClass: isDark ? 'bg-yellow-900/50 text-yellow-400' : 'bg-yellow-100 text-yellow-700' });
  }
  const yearsOperating = extended.foundedYear ? (new Date().getFullYear() - extended.foundedYear) : null;
  if (yearsOperating && yearsOperating >= 25) {
    tags.push({ label: 'Established', priority: 8, colorClass: isDark ? 'bg-stone-800/50 text-stone-400' : 'bg-stone-200 text-stone-700' });
  }

  return tags.sort((a, b) => a.priority - b.priority).slice(0, 3);
}

// Grade badge color helper
// --- Reusable sub-components ---

const SectionCard: React.FC<{
  children: React.ReactNode;
  isDark: boolean;
  className?: string;
}> = ({ children, isDark, className = '' }) => (
  <div className={`rounded-xl p-5 ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'} ${className}`}>
    {children}
  </div>
);

const SectionHeader: React.FC<{
  icon: React.ElementType;
  title: string;
  isDark: boolean;
  infoTip?: string;
}> = ({ icon: Icon, title, isDark, infoTip }) => (
  <div className={`flex items-center gap-2 mb-4 pb-2 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
    <Icon className={`w-4 h-4 ${isDark ? 'text-slate-400' : 'text-slate-500'}`} />
    <h3 className={`text-sm font-semibold uppercase tracking-wide ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
      {title}
    </h3>
    {infoTip && <InfoTip text={infoTip} isDark={isDark} />}
  </div>
);

const DataRow: React.FC<{
  label: string;
  value: string | number | null | undefined;
  isDark: boolean;
  highlight?: boolean;
  mono?: boolean;
}> = ({ label, value, isDark, highlight = false, mono = true }) => (
  <div className={`flex justify-between py-2 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
    <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{label}</span>
    <span className={`text-sm font-medium ${
      highlight
        ? isDark ? 'text-emerald-400' : 'text-emerald-600'
        : isDark ? 'text-white' : 'text-slate-900'
    } ${mono ? 'font-mono' : ''}`}>
      {value ?? '\u2014'}
    </span>
  </div>
);

// --- Main Component ---

export const TabbedView: React.FC<TabbedViewProps> = ({ charity }) => {
  const { isDark } = useLandingTheme();
  const { isSignedIn } = useAuth();
  const { charities: allCharities } = useCharities();
  const { addDonation, getPaymentSources } = useGivingHistory();
  const [showDonationModal, setShowDonationModal] = useState(false);
  const validTabs: TabId[] = ['overview', 'giving', 'impact', 'financials'];
  const hashTab = window.location.hash.replace('#', '') as TabId;
  const [activeTab, setActiveTab] = useState<TabId>(validTabs.includes(hashTab) ? hashTab : 'overview');
  const handleTabChange = useCallback((tab: TabId) => {
    setActiveTab(tab);
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#${tab}`);
  }, []);

  const amal = charity.amalEvaluation;
  const baseline = amal?.baseline_narrative;
  const rich = amal?.rich_narrative;
  const hasRich = !!rich;
  const idealDonorProfile = rich?.ideal_donor_profile;

  const rawCitations = (
    isSignedIn
      ? (rich?.all_citations || baseline?.all_citations || [])
      : (baseline?.all_citations || [])
  ) as NarrativeCitation[];
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

  const charityNameToId = useMemo(() => {
    const map = new Map<string, string>();
    allCharities.forEach(c => {
      map.set(c.name.toLowerCase(), c.id ?? c.ein ?? '');
    });
    return map;
  }, [allCharities]);

  const findCharityId = (name: string): string | null => {
    const lowerName = name.toLowerCase();
    if (charityNameToId.has(lowerName)) return charityNameToId.get(lowerName) || null;
    for (const [charityName, id] of charityNameToId.entries()) {
      if (charityName.includes(lowerName) || lowerName.includes(charityName)) return id;
    }
    return null;
  };

  const trackedEinRef = React.useRef<string | null>(null);
  useEffect(() => {
    const ein = charity.id ?? charity.ein ?? '';
    if (!ein || ein === trackedEinRef.current) return;
    trackedEinRef.current = ein;
    trackCharityView(ein, charity.name, 'terminal');
  }, [charity.id, charity.ein, charity.name]);

  const handleDonateClick = () => {
    trackDonateClick(charity.id ?? charity.ein ?? '', charity.name, charity.donationUrl || charity.website || '');
  };

  const totalExpenses = financials?.totalExpenses ?? 0;
  const hasExpenseData = totalExpenses > 0;
  const rawProgramRatio = hasExpenseData && financials?.programExpenses
    ? ((financials.programExpenses / totalExpenses) * 100) : 0;
  const programRatio = Math.min(rawProgramRatio, 100);
  const adminRatio = hasExpenseData && financials?.adminExpenses
    ? ((financials.adminExpenses / totalExpenses) * 100) : 0;
  const fundRatio = hasExpenseData && financials?.fundraisingExpenses
    ? ((financials.fundraisingExpenses / totalExpenses) * 100) : 0;
  const hasSignificantNoncash = (financials?.noncashRatio ?? 0) >= 0.25;
  const cashAdjProgramRatio = financials?.cashAdjustedProgramRatio != null
    ? financials.cashAdjustedProgramRatio * 100 : null;

  const strengths = (isSignedIn ? (rich?.strengths || baseline?.strengths) : baseline?.strengths) || [];
  const headline = isSignedIn ? (rich?.headline || baseline?.headline || '') : (baseline?.headline || '');
  const aboutSummary = isSignedIn ? (rich?.summary || baseline?.summary || '') : (baseline?.summary || '');
  const isZakatEligible = amal?.wallet_tag?.includes('ZAKAT');
  const uiSignals = charity.ui_signals_v1 || deriveUISignalsFromCharity(charity);
  const amalScore = amal?.amal_score ?? null;
  const donateUrl = charity.donationUrl ?? charity.website ?? undefined;
  const keyConcerns = charity.keyConcerns ?? [];

  const areasForImprovement = (
    isSignedIn ? rich?.areas_for_improvement : baseline?.areas_for_improvement
  ) as Array<string | { area: string; context: string; citation_ids: string[] }> | undefined;

  // Key Concerns render helper (same as TerminalView)
  const renderKeyConcerns = (concerns: typeof keyConcerns) => {
    if (!concerns.length) return null;
    return (
      <div className="space-y-2">
        {concerns.map((concern, i) => {
          const isHigh = concern.severity === 'high';
          const borderColor = isHigh
            ? (isDark ? 'border-red-500/60' : 'border-red-400')
            : (isDark ? 'border-amber-500/50' : 'border-amber-400');
          const bgColor = isHigh
            ? (isDark ? 'bg-red-950/30' : 'bg-red-50')
            : (isDark ? 'bg-amber-950/20' : 'bg-amber-50');
          const iconColor = isHigh
            ? (isDark ? 'text-red-400' : 'text-red-600')
            : (isDark ? 'text-amber-400' : 'text-amber-600');
          const headlineColor = isHigh
            ? (isDark ? 'text-red-300' : 'text-red-800')
            : (isDark ? 'text-amber-300' : 'text-amber-800');

          return (
            <div key={i} className={`rounded-lg border-2 ${borderColor} ${bgColor} p-3`}>
              <div className="flex items-start gap-2">
                <AlertTriangle className={`w-4 h-4 mt-0.5 flex-shrink-0 ${iconColor}`} />
                <div className="flex-1 min-w-0">
                  <div className={`text-sm font-semibold ${headlineColor}`}>
                    {concern.headline}
                  </div>
                  <div className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {concern.detail}
                  </div>
                  {concern.data_points && Object.keys(concern.data_points).length > 0 && (
                    <div className={`flex flex-wrap gap-3 mt-2 text-xs font-mono ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                      {concern.type === 'gik_inflation' && concern.data_points.noncash_ratio != null && (
                        <span>Noncash: {(concern.data_points.noncash_ratio * 100).toFixed(0)}%</span>
                      )}
                      {concern.type === 'gik_inflation' && concern.data_points.cash_adjusted_program_ratio != null && (
                        <span>Cash-adj program ratio: {(concern.data_points.cash_adjusted_program_ratio * 100).toFixed(0)}%</span>
                      )}
                      {concern.type === 'domestic_burn' && concern.data_points.domestic_burn_rate != null && (
                        <span>Domestic spend: {(concern.data_points.domestic_burn_rate * 100).toFixed(0)}%</span>
                      )}
                      {concern.type === 'zakat_hoarding' && concern.data_points.reserves_months != null && (
                        <span>Reserves: {concern.data_points.reserves_months.toFixed(0)} months</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  // --- Tab definitions ---
  const tabs: { id: TabId; label: string; icon: React.ElementType }[] = [
    { id: 'overview', label: 'Overview', icon: BookOpen },
    { id: 'giving', label: 'Giving', icon: Heart },
    { id: 'impact', label: 'Impact', icon: Target },
    { id: 'financials', label: 'Financials', icon: BarChart3 },
  ];

  // ==========================================================================
  // RENDER: Overview Tab
  // ==========================================================================
  const renderOverviewTab = () => (
    <div className="space-y-5">
      {/* Emerging Org notice */}
      {charity.evaluationTrack === 'NEW_ORG' && (
        <SectionCard isDark={isDark}>
          <div className="flex items-center gap-3 mb-3">
            <div className={`p-2 rounded-lg ${isDark ? 'bg-sky-800/50' : 'bg-sky-100'}`}>
              <Rocket className={`w-5 h-5 ${isDark ? 'text-sky-400' : 'text-sky-600'}`} />
            </div>
            <div>
              <div className={`text-sm font-bold ${isDark ? 'text-sky-300' : 'text-sky-700'}`}>
                Emerging Organization
              </div>
              {charity.foundedYear && (
                <div className={`text-xs ${isDark ? 'text-sky-400/70' : 'text-sky-600/80'}`}>
                  Est. {charity.foundedYear} -- Building Track Record
                </div>
              )}
            </div>
          </div>
          <p className={`text-sm leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
            This organization is too early to rate numerically.
            We show qualitative context and early indicators while it builds a longer public track record.
          </p>
        </SectionCard>
      )}

      {/* About */}
      {(headline || aboutSummary) && (
        <SectionCard isDark={isDark}>
          <SectionHeader icon={BookOpen} title="About" isDark={isDark} />
          {headline && (
            <p className={`text-base font-medium leading-relaxed mb-3 ${isDark ? 'text-slate-100' : 'text-slate-800'}`}>
              <SourceLinkedText text={headline} citations={citations} isDark={isDark} />
            </p>
          )}
          {aboutSummary && (
            <p className={`text-sm leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
              <SourceLinkedText text={aboutSummary} citations={citations} isDark={isDark} />
            </p>
          )}
          {!isSignedIn && hasRich && (
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
          )}
        </SectionCard>
      )}

      {/* Quick Facts */}
      <SectionCard isDark={isDark}>
        <SectionHeader icon={FileText} title="Quick Facts" isDark={isDark} />
        <div className="space-y-0">
          {beneficiariesCount != null && beneficiariesCount > 0 && (
            <DataRow label="Beneficiaries Served" value={beneficiariesCount.toLocaleString()} isDark={isDark} highlight />
          )}
          {(() => {
            const tagCategories = categorizeTags(charity.causeTags);
            return (
              <>
                {tagCategories.populations.length > 0 && (
                  <DataRow label="Populations" value={tagCategories.populations.slice(0, 3).map(t => formatTag(t)).join(', ')} isDark={isDark} mono={false} />
                )}
                {tagCategories.geography.length > 0 && (
                  <DataRow label="Geography" value={tagCategories.geography.slice(0, 3).map(t => formatTag(t)).join(', ')} isDark={isDark} mono={false} />
                )}
                {tagCategories.interventions.length > 0 && (
                  <DataRow label="Services" value={tagCategories.interventions.slice(0, 3).map(t => formatTag(t)).join(', ')} isDark={isDark} mono={false} />
                )}
              </>
            );
          })()}
          {(charity.programs || []).length > 0 && (
            <DataRow label="Programs" value={(charity.programs || []).slice(0, 3).map(t => formatProgramTag(t)).join(', ')} isDark={isDark} mono={false} />
          )}
          {rich?.long_term_outlook?.founded_year && (
            <DataRow label="Founded" value={rich.long_term_outlook.founded_year} isDark={isDark} />
          )}
          {revenue != null && (
            <DataRow label="Annual Revenue" value={formatCurrency(revenue)} isDark={isDark} />
          )}
          <DataRow label="EIN" value={charity.ein || charity.id} isDark={isDark} />
          {getCharityAddress(charity) && (
            <DataRow label="Location" value={getCharityAddress(charity)} isDark={isDark} mono={false} />
          )}
        </div>
      </SectionCard>

      {/* Leadership & Governance */}
      {rich?.organizational_capacity && (
        isSignedIn ? (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={Users} title="Leadership & Governance" isDark={isDark} />
            {rich.organizational_capacity.ceo_name && (
              <div className={`mb-3 pb-3 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <div className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {rich.organizational_capacity.ceo_name}
                </div>
                <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  CEO/Executive Director
                  {!!rich.organizational_capacity.ceo_compensation && (
                    <span className="ml-2 font-mono">({formatCurrency(rich.organizational_capacity.ceo_compensation)})</span>
                  )}
                </div>
              </div>
            )}
            <div className={`space-y-1.5 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              {!!rich.organizational_capacity.board_size && (
                <div className="flex justify-between">
                  <span>Board Size</span>
                  <span className="font-mono">{rich.organizational_capacity.board_size}</span>
                </div>
              )}
              {rich.organizational_capacity.independent_board_pct != null && (
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
              {rich.organizational_capacity.volunteers_count != null && rich.organizational_capacity.volunteers_count > 0 && (
                <div className="flex justify-between">
                  <span>Volunteers</span>
                  <span className="font-mono">{rich.organizational_capacity.volunteers_count}</span>
                </div>
              )}
            </div>
            <div className={`mt-3 pt-3 border-t grid grid-cols-2 gap-2 text-sm ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
              <div className="flex items-center gap-1.5">
                {rich.organizational_capacity.has_conflict_policy ? (
                  <CheckCircle2 className={`w-4 h-4 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                ) : (
                  <AlertCircle className={`w-4 h-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                )}
                <span className={isDark ? 'text-slate-400' : 'text-slate-600'}>COI Policy</span>
              </div>
              <div className="flex items-center gap-1.5">
                {rich.organizational_capacity.has_financial_audit ? (
                  <CheckCircle2 className={`w-4 h-4 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                ) : (
                  <AlertCircle className={`w-4 h-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                )}
                <span className={isDark ? 'text-slate-400' : 'text-slate-600'}>Audited</span>
              </div>
            </div>
          </SectionCard>
        ) : (
          <ContentPreview title="Leadership & Governance" description="leadership and governance details" />
        )
      )}

      {/* Baseline Governance fallback */}
      {!rich?.organizational_capacity && charity.baselineGovernance && (
        <SectionCard isDark={isDark}>
          <SectionHeader icon={Users} title="Governance" isDark={isDark} />
          <div className={`space-y-1.5 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
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
        </SectionCard>
      )}

      {/* Long-Term Outlook */}
      {rich?.long_term_outlook && (
        isSignedIn ? (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={TrendingUp} title="Long-Term Outlook" isDark={isDark} infoTip={GLOSSARY['Long-Term Outlook']} />
            <DataRow label="Founded" value={rich.long_term_outlook.founded_year} isDark={isDark} />
            <DataRow label="Years Operating" value={rich.long_term_outlook.years_operating} isDark={isDark} />
            <DataRow label="Maturity" value={rich.long_term_outlook.maturity_stage} isDark={isDark} mono={false} />
            <DataRow label="Room for Funding" value={rich.long_term_outlook.room_for_funding} isDark={isDark} />
            {(rich.long_term_outlook.strategic_priorities?.length ?? 0) > 0 && (
              <div className={`mt-3 pt-3 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <div className={`text-xs font-semibold mb-1.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Strategic Priorities
                </div>
                <ul className={`text-sm space-y-0.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  {rich.long_term_outlook.strategic_priorities?.slice(0, 3).map((priority, i) => (
                    <li key={i} className="flex items-start gap-1">
                      <span className="text-emerald-500">-</span>
                      {priority}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </SectionCard>
        ) : (
          <ContentPreview title="Long-Term Outlook" description="sustainability and future direction" teaser="Analysis of organizational maturity, strategic priorities, room for additional funding, and long-term sustainability trajectory." />
        )
      )}

      {/* Recognition & Awards */}
      {(charity.awards?.cnBeacons?.length || charity.awards?.candidSeal || charity.awards?.bbbStatus || charity.awards?.bbbReviewUrl) && (
        <SectionCard isDark={isDark}>
          <SectionHeader icon={Award} title="Recognition & Awards" isDark={isDark} />
          <div className="space-y-2">
            {charity.awards?.cnBeacons?.map((beacon, i) => (
              <div key={i} className={`flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                <Award className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-amber-400' : 'text-amber-500'}`} />
                {charity.awards?.cnUrl ? (
                  <a href={charity.awards.cnUrl} target="_blank" rel="noopener noreferrer"
                    className={`text-sm hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>
                    {beacon}
                  </a>
                ) : (
                  <span className="text-sm">{beacon}</span>
                )}
                <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>-- Charity Navigator</span>
              </div>
            ))}
            {charity.awards?.candidSeal && (
              <div className={`flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                <Award className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-amber-400' : 'text-amber-500'}`} />
                {charity.awards.candidUrl ? (
                  <a href={charity.awards.candidUrl} target="_blank" rel="noopener noreferrer"
                    className={`text-sm hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>
                    {String(charity.awards.candidSeal).charAt(0).toUpperCase() + String(charity.awards.candidSeal).slice(1)} Seal
                  </a>
                ) : (
                  <span className="text-sm">{String(charity.awards.candidSeal).charAt(0).toUpperCase() + String(charity.awards.candidSeal).slice(1)} Seal</span>
                )}
                <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>-- Candid</span>
              </div>
            )}
            {charity.awards?.bbbStatus && (
              <div className={`flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                <Award className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-amber-400' : 'text-amber-500'}`} />
                {charity.awards.bbbReviewUrl ? (
                  <a href={charity.awards.bbbReviewUrl} target="_blank" rel="noopener noreferrer"
                    className={`text-sm hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>
                    {charity.awards.bbbStatus}
                  </a>
                ) : (
                  <span className="text-sm">{charity.awards.bbbStatus}</span>
                )}
                <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>-- BBB Wise Giving</span>
              </div>
            )}
            {!charity.awards?.bbbStatus && charity.awards?.bbbReviewUrl && (
              <div className={`flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                <ExternalLink className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-slate-400' : 'text-slate-500'}`} />
                <a href={charity.awards.bbbReviewUrl} target="_blank" rel="noopener noreferrer"
                  className={`text-sm hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>
                  View BBB Evaluation
                </a>
                <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>-- BBB Wise Giving</span>
              </div>
            )}
          </div>
        </SectionCard>
      )}

      {/* External Links */}
      <SectionCard isDark={isDark}>
        <SectionHeader icon={Globe} title="External Links" isDark={isDark} />
        <div className="space-y-2">
          {charity.website && (
            <a
              href={charity.website}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackExternalLinkClick(charity.id ?? charity.ein ?? '', 'website', charity.website!)}
              className={`flex items-center gap-2 text-sm py-1 ${isDark ? 'text-emerald-400 hover:text-emerald-300' : 'text-emerald-600 hover:text-emerald-700'}`}
            >
              Website <ExternalLink className="w-3 h-3" />
            </a>
          )}
          <a
            href={`https://www.charitynavigator.org/ein/${(charity.ein ?? charity.id ?? '').replace(/-/g, '')}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => trackExternalLinkClick(charity.id ?? charity.ein ?? '', 'source', `https://www.charitynavigator.org/ein/${(charity.ein ?? charity.id ?? '').replace(/-/g, '')}`)}
            className={`flex items-center justify-between text-sm py-1 ${isDark ? 'text-slate-400 hover:text-slate-300' : 'text-slate-500 hover:text-slate-600'}`}
          >
            <span className="flex items-center gap-1">Charity Navigator <ExternalLink className="w-3 h-3" /></span>
            {charity.scores?.overall && (
              <span className={`font-mono ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{Math.round(charity.scores.overall)}</span>
            )}
          </a>
          <a
            href={`https://projects.propublica.org/nonprofits/organizations/${(charity.ein ?? charity.id ?? '').replace(/-/g, '')}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => trackExternalLinkClick(charity.id ?? charity.ein ?? '', 'source', `https://projects.propublica.org/nonprofits/organizations/${(charity.ein ?? charity.id ?? '').replace(/-/g, '')}`)}
            className={`flex items-center gap-2 text-sm py-1 ${isDark ? 'text-slate-400 hover:text-slate-300' : 'text-slate-500 hover:text-slate-600'}`}
          >
            ProPublica 990 <ExternalLink className="w-3 h-3" />
          </a>
          {rich?.bbb_assessment?.review_url && (
            <a
              href={rich.bbb_assessment.review_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackOutboundClick(charity.id ?? charity.ein ?? '', charity.name, 'give.org')}
              className={`flex items-center justify-between text-sm py-1 ${isDark ? 'text-slate-400 hover:text-slate-300' : 'text-slate-500 hover:text-slate-600'}`}
            >
              <span className="flex items-center gap-1">BBB Wise Giving <ExternalLink className="w-3 h-3" /></span>
              {rich.bbb_assessment.meets_all_standards && (
                <span className={`font-medium text-xs ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>Accredited</span>
              )}
            </a>
          )}
        </div>
      </SectionCard>

    </div>
  );

  // ==========================================================================
  // RENDER: Impact Tab
  // ==========================================================================
  const renderImpactTab = () => (
    <div className="space-y-5">
      {/* Methodology Details */}
      {amal?.score_details && (
        charity.evaluationTrack === 'NEW_ORG' ? (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={BarChart3} title="Methodology" isDark={isDark} />
            <p className={`text-sm leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              This organization is too early to rate numerically.
              We show qualitative context and early indicators while it builds a longer public track record.
            </p>
          </SectionCard>
        ) : (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={BarChart3} title="Methodology Details" isDark={isDark} />
            <ScoreBreakdown
              scoreDetails={amal.score_details}
              confidenceScores={scores}
              amalScore={amalScore ?? 0}
              citations={citations}
              isSignedIn={isSignedIn}
              isDark={isDark}
              dimensionExplanations={rich?.dimension_explanations || baseline?.dimension_explanations}
              amalScoreRationale={isSignedIn ? rich?.amal_score_rationale : undefined}
              scoreSummary={charity.scoreSummary}
              strengths={isSignedIn ? rich?.strengths : baseline?.strengths}
              areasForImprovement={areasForImprovement}
              theoryOfChangeSummary={rich?.impact_evidence?.theory_of_change_summary || charity.theoryOfChange}
            />
          </SectionCard>
        )
      )}

      {/* Evidence */}
      {(rich?.impact_evidence || charity.evidenceQuality || rich?.citation_stats) && (
        isSignedIn || charity.evidenceQuality ? (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={Shield} title="Evidence" isDark={isDark} infoTip={GLOSSARY['Impact Evidence']} />
            {/* Impact Evidence grade + details (signed-in with rich) */}
            {rich?.impact_evidence && isSignedIn && (
              <>
                {charity.evaluationTrack === 'NEW_ORG' && (
                  <div className={`mb-3 p-2 rounded text-xs ${
                    isDark ? 'bg-sky-900/30 text-sky-300 border border-sky-800/50' : 'bg-sky-50 text-sky-700 border border-sky-200'
                  }`}>
                    <strong>Emerging org evaluation:</strong> As a newer organization{charity.foundedYear ? ` (est. ${charity.foundedYear})` : ''},
                    evidence is assessed on theory of change and early indicators rather than years of outcome data.
                  </div>
                )}
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
                    <SourceLinkedText text={rich.impact_evidence.evidence_grade_explanation || ''} citations={citations} isDark={isDark} />
                  </span>
                </div>
                <div className={`space-y-1.5 text-xs ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  <div className="flex justify-between">
                    <span>RCT Available</span>
                    <span className={`font-mono ${rich.impact_evidence.rct_available ? isDark ? 'text-emerald-400' : 'text-emerald-600' : isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                      {rich.impact_evidence.rct_available ? 'YES' : 'NO'}
                    </span>
                  </div>
                  {rich.impact_evidence.theory_of_change && (
                    <div className="flex justify-between">
                      <span className="flex items-center gap-1">Theory of Change <InfoTip text={GLOSSARY['Theory of Change']} isDark={isDark} /></span>
                      <span className="font-mono">{rich.impact_evidence.theory_of_change.toUpperCase()}</span>
                    </div>
                  )}
                </div>
                {rich.impact_evidence.theory_of_change_summary && (
                  <div className={`mt-3 pt-3 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                    <div className={`text-xs font-semibold mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                      Theory of Change Summary
                    </div>
                    <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                      <SourceLinkedText text={rich.impact_evidence.theory_of_change_summary} citations={citations} isDark={isDark} />
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
                              isDark ? 'border-emerald-800/60 text-emerald-400 hover:bg-emerald-900/20' : 'border-emerald-200 text-emerald-700 hover:bg-emerald-50'
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
                {rich.impact_evidence.external_evaluations && rich.impact_evidence.external_evaluations.length > 0 && (
                  <div className={`mt-2 pt-2 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                    <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>External Evaluations</div>
                    <div className={`text-xs mt-1 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                      {rich.impact_evidence.external_evaluations.slice(0, 2).join(', ')}
                    </div>
                  </div>
                )}
              </>
            )}
            {/* Evidence quality checklist */}
            {charity.evidenceQuality && (
              <div className={`${rich?.impact_evidence && isSignedIn ? `mt-4 pt-4 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}` : ''}`}>
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
                    <div className={`mt-2 pt-2 border-t text-xs ${isDark ? 'border-slate-800 text-slate-500' : 'border-slate-200 text-slate-400'}`}>
                      Sources: {charity.evidenceQuality.evaluationSources.join(', ')}
                    </div>
                  )}
                </div>
              </div>
            )}
            {/* Citation stats (signed-in only) */}
            {rich?.citation_stats && isSignedIn && (
              <div className={`mt-4 pt-4 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <div className={`space-y-1.5 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
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
                  <div className={`mt-2 pt-2 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(rich.citation_stats.by_source_type).map(([type, count]) => (
                        <span key={type} className={`px-1.5 py-0.5 rounded text-xs ${isDark ? 'bg-slate-700 text-slate-300' : 'bg-slate-200 text-slate-600'}`}>
                          {type}: {count}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {rich?.data_confidence?.form_990_tax_year && (
                  <div className={`mt-2 pt-2 border-t text-xs ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                    <div className="flex justify-between">
                      <span className={isDark ? 'text-slate-500' : 'text-slate-400'}>990 Tax Year</span>
                      <span className={`font-mono ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{rich.data_confidence.form_990_tax_year}</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </SectionCard>
        ) : (
          <ContentPreview title="Evidence" description="evidence quality and evaluation details" />
        )
      )}
    </div>
  );

  // ==========================================================================
  // RENDER: Giving Tab
  // ==========================================================================
  const renderGivingTab = () => (
    <div className="space-y-5">
      {/* Best For */}
      {idealDonorProfile && (
        isSignedIn ? (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={Target} title="Best For" isDark={isDark} />
            <p className={`text-sm font-medium mb-3 ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
              {idealDonorProfile.best_for_summary}
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {idealDonorProfile.donor_motivations?.length > 0 && (
                <div>
                  <div className={`text-xs font-semibold mb-1 flex items-center gap-1 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                    <Target className="w-3 h-3" />
                    Ideal for donors who:
                  </div>
                  <ul className={`text-xs space-y-0.5 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                    {idealDonorProfile.donor_motivations.slice(0, 4).map((m: string, i: number) => (
                      <li key={i} className="flex items-start gap-1">
                        <span className="text-emerald-500">+</span>
                        {m}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {idealDonorProfile.giving_considerations?.length > 0 && (
                <div>
                  <div className={`text-xs font-semibold mb-1 flex items-center gap-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    <Scale className="w-3 h-3" />
                    Consider:
                  </div>
                  <ul className={`text-xs space-y-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    {idealDonorProfile.giving_considerations.slice(0, 3).map((c: string, i: number) => (
                      <li key={i} className="flex items-start gap-1"><span>-</span>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            {idealDonorProfile.not_ideal_for && (
              <div className={`mt-3 pt-2 border-t text-xs flex items-start gap-1 ${isDark ? 'border-slate-700 text-amber-400' : 'border-slate-200 text-amber-600'}`}>
                <Scale className="w-3 h-3 shrink-0 mt-0.5" />
                <span><strong>May not fit donors who:</strong> {idealDonorProfile.not_ideal_for}</span>
              </div>
            )}
          </SectionCard>
        ) : (
          <ContentPreview title="Best For" description="which donors this charity fits best" teaser={idealDonorProfile?.best_for_summary || "Discover which donor profiles and giving styles align best with this charity's strengths."} />
        )
      )}

      {/* Key Concerns */}
      {keyConcerns.length > 0 && (
        <SectionCard isDark={isDark}>
          <SectionHeader icon={AlertTriangle} title="Key Concerns" isDark={isDark} />
          {renderKeyConcerns(keyConcerns)}
        </SectionCard>
      )}

      {/* Strengths & Growth Areas */}
      {(strengths.length > 0 || (areasForImprovement && areasForImprovement.length > 0)) && (
        <SectionCard isDark={isDark}>
          <SectionHeader icon={TrendingUp} title="Strengths & Growth Areas" isDark={isDark} />
          {strengths.length > 0 && (
            <div className="mb-4">
              <div className={`text-xs font-semibold mb-2 ${isDark ? 'text-emerald-400' : 'text-emerald-700'}`}>
                Why give here?
              </div>
              <ul className={`space-y-1.5 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                {strengths.map((s, i) => {
                  const text = typeof s === 'object' ? s.point : s;
                  return (
                    <li key={i} className="flex items-start gap-2">
                      <span className={isDark ? 'text-emerald-400' : 'text-emerald-600'}>+</span>
                      <SourceLinkedText text={text} citations={citations} isDark={isDark} subtle />
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
          {areasForImprovement && areasForImprovement.length > 0 && (
            <div>
              <div className={`text-xs font-semibold mb-2 ${isDark ? 'text-amber-400' : 'text-amber-700'}`}>
                Growth areas
              </div>
              <ul className={`space-y-1.5 text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                {areasForImprovement.slice(0, 4).map((a, i) => {
                  const text = typeof a === 'object' ? a.area : a;
                  return (
                    <li key={i} className="flex items-start gap-2">
                      <span className={isDark ? 'text-amber-400' : 'text-amber-600'}>-</span>
                      <SourceLinkedText text={text} citations={citations} isDark={isDark} subtle />
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </SectionCard>
      )}

      {/* Things to Know / Balanced View */}
      {rich?.case_against && (
        isSignedIn ? (
          <SectionCard isDark={isDark} className={`!border-2 ${isDark ? '!border-violet-600/50 !bg-violet-900/10' : '!border-violet-300 !bg-violet-50'}`}>
            <SectionHeader icon={Scale} title="Things to Know" isDark={isDark} infoTip={GLOSSARY['Things to Know']} />
            <p className={`text-sm mb-3 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              <SourceLinkedText text={rich.case_against.summary} citations={citations} isDark={isDark} />
            </p>
            {rich.case_against.risk_factors?.length > 0 && (
              <div className="space-y-2">
                <div className={`text-xs font-semibold flex items-center gap-1 ${isDark ? 'text-violet-400' : 'text-violet-600'}`}>
                  <Scale className="w-3 h-3" />
                  Considerations
                </div>
                <ul className={`text-xs space-y-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  {rich.case_against.risk_factors.map((risk, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-violet-500 mt-0.5">-</span>
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
          </SectionCard>
        ) : (
          <ContentPreview title="Things to Know" description="important context and considerations" teaser={rich?.case_against?.summary || "Our analysis covers risk factors, governance concerns, and important context every donor should consider before giving."} />
        )
      )}

      {/* Baseline Things to Know (when no rich narrative) */}
      {!rich?.case_against && (charity.scoreSummary || amal?.score_details?.score_summary || uiSignals?.signal_states) && (
        <SectionCard isDark={isDark}>
          <SectionHeader icon={Scale} title="Things to Know" isDark={isDark} />
          {(charity.scoreSummary || amal?.score_details?.score_summary) && (
            <p className={`text-sm mb-3 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              {charity.scoreSummary || amal?.score_details?.score_summary}
            </p>
          )}
          {uiSignals?.signal_states && (
            <div className="flex flex-wrap gap-2 mb-2">
              {(Object.entries(uiSignals.signal_states) as [string, string][]).map(([key, state]) => {
                const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                const pillClasses = state === 'Strong'
                  ? (isDark ? 'bg-emerald-900/40 text-emerald-400 border-emerald-700' : 'bg-emerald-50 text-emerald-700 border-emerald-300')
                  : state === 'Moderate'
                  ? (isDark ? 'bg-amber-900/30 text-amber-400 border-amber-700' : 'bg-amber-50 text-amber-700 border-amber-300')
                  : (isDark ? 'bg-slate-700/50 text-slate-400 border-slate-600' : 'bg-slate-100 text-slate-500 border-slate-300');
                return (
                  <span key={key} className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border ${pillClasses}`}>
                    {label}: {state}
                  </span>
                );
              })}
            </div>
          )}
          {uiSignals?.recommendation_rationale && (
            <p className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              {uiSignals.recommendation_rationale}
            </p>
          )}
        </SectionCard>
      )}

      {/* Zakat Claim Evidence */}
      {isZakatEligible && charity.zakatClaimEvidence && charity.zakatClaimEvidence.length > 0 && (
        <SectionCard isDark={isDark} className={`!border-2 ${isDark ? '!border-emerald-700/50 !bg-emerald-900/10' : '!border-emerald-300 !bg-emerald-50'}`}>
          <SectionHeader icon={Shield} title="Zakat Claim Evidence" isDark={isDark} />
          <div className="space-y-2">
            {charity.zakatClaimEvidence.map((evidence, i) => {
              const policyUrl = extractZakatPolicyUrl(evidence);
              const cleanEvidence = evidence.replace(/\(Source:\s*https?:\/\/[^\s)]+\)/, '').trim();
              return (
                <div key={i} className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  {cleanEvidence}
                  {policyUrl && (
                    <a
                      href={policyUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`ml-2 inline-flex items-center gap-1 text-xs ${
                        isDark ? 'text-emerald-400 hover:text-emerald-300' : 'text-emerald-600 hover:text-emerald-700'
                      }`}
                    >
                      View policy <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        </SectionCard>
      )}

      {/* Donor Fit Matrix */}
      {rich?.donor_fit_matrix && (
        isSignedIn ? (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={Users} title="Donor Fit" isDark={isDark} infoTip={GLOSSARY['Donor Fit']} />
            <DataRow label="Cause Area" value={rich.donor_fit_matrix.cause_area ? formatCauseArea(rich.donor_fit_matrix.cause_area) : undefined} isDark={isDark} mono={false} />
            <DataRow label="Giving Style" value={rich.donor_fit_matrix.giving_style} isDark={isDark} mono={false} />
            <DataRow label="Evidence Rigor" value={rich.donor_fit_matrix.evidence_rigor?.split(' - ')[0]} isDark={isDark} />
            {(rich.donor_fit_matrix.geographic_focus?.length ?? 0) > 0 && (
              <div className={`py-2 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <span className={`text-sm block mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Geographic Focus</span>
                <span className={`text-xs ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {rich.donor_fit_matrix.geographic_focus?.slice(0, 3).join(', ')}
                </span>
              </div>
            )}
          </SectionCard>
        ) : (
          <ContentPreview title="Donor Fit" description="donor fit and giving style analysis" />
        )
      )}

      {/* BBB Wise Giving Assessment */}
      {rich?.bbb_assessment && (
        isSignedIn ? (
          (rich.bbb_assessment.meets_all_standards ||
           (rich.bbb_assessment.standards_met && rich.bbb_assessment.standards_met > 0) ||
           (rich.bbb_assessment.standards_not_met && rich.bbb_assessment.standards_not_met.length > 0) ||
           rich.bbb_assessment.review_url || rich.bbb_assessment.summary || rich.bbb_assessment.audit_type) ? (
            <SectionCard isDark={isDark} className={`!border-l-4 ${
              rich.bbb_assessment.meets_all_standards
                ? isDark ? '!border-emerald-500' : '!border-emerald-500'
                : isDark ? '!border-amber-500' : '!border-amber-500'
            }`}>
              <SectionHeader icon={Shield} title="BBB Wise Giving" isDark={isDark} infoTip={GLOSSARY['BBB Wise Giving']} />
              <div className="flex items-center gap-2 mb-3">
                {rich.bbb_assessment.meets_all_standards ? (
                  <CheckCircle2 className={`w-5 h-5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                ) : (
                  <AlertTriangle className={`w-5 h-5 ${isDark ? 'text-amber-400' : 'text-amber-600'}`} />
                )}
                <span className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {rich.bbb_assessment.meets_all_standards ? 'Meets All Standards' : 'Standards Review'}
                </span>
                {rich.bbb_assessment.standards_met != null && rich.bbb_assessment.standards_met > 0 && (
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
                    <div key={category} className="flex items-center gap-1.5 text-sm">
                      {isPassing ? (
                        <CheckCircle2 className={`w-4 h-4 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                      ) : (
                        <AlertCircle className={`w-4 h-4 ${isDark ? 'text-amber-400' : 'text-amber-600'}`} />
                      )}
                      <span className={`capitalize ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{category}</span>
                    </div>
                  ) : null;
                })}
                {rich.bbb_assessment.audit_type && (
                  <div className="flex items-center gap-1.5 text-sm">
                    <CheckCircle2 className={`w-4 h-4 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                    <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>{rich.bbb_assessment.audit_type}</span>
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
                  <div className={`text-xs font-semibold mb-1 flex items-center gap-1 ${isDark ? 'text-amber-400' : 'text-amber-600'}`}>
                    <AlertTriangle className="w-3 h-3" />
                    Not Met
                  </div>
                  <ul className={`text-xs space-y-0.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {rich.bbb_assessment.standards_not_met.slice(0, 3).map((std, i) => (
                      <li key={i}>- {std}</li>
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
                  className={`mt-2 inline-flex items-center gap-1 text-xs font-medium ${isDark ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'}`}
                >
                  View on give.org <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </SectionCard>
          ) : null
        ) : (
          <ContentPreview title="BBB Assessment" description="BBB Wise Giving standards review" />
        )
      )}

      {/* Similar Organizations */}
      {(rich?.similar_organizations || rich?.peer_comparison) && (
        <SectionCard isDark={isDark}>
          <SectionHeader icon={Users} title="Similar Organizations" isDark={isDark} />
          {rich?.peer_comparison && (
            <div className={`mb-3 pb-2 border-b text-sm font-medium ${isDark ? 'border-slate-800 text-slate-200' : 'border-slate-200 text-slate-700'}`}>
              {rich.peer_comparison.peer_group}
            </div>
          )}
          {rich?.similar_organizations && rich.similar_organizations.length > 0 && (
            <div className="space-y-2">
              {rich.similar_organizations.slice(0, isSignedIn ? 5 : 3).map((org, i) => {
                const orgName = typeof org === 'string' ? org : org.name;
                const linkedId = findCharityId(orgName);
                return (
                  <div key={i} className="text-sm">
                    {isSignedIn && linkedId ? (
                      <Link
                        to={`/charity/${linkedId}`}
                        onClick={() => trackSimilarOrgClick(charity.id ?? charity.ein ?? '', linkedId!, orgName, i)}
                        className={`flex items-center gap-1.5 ${
                          isDark ? 'text-emerald-400 hover:text-emerald-300' : 'text-emerald-600 hover:text-emerald-700'
                        }`}
                      >
                        {orgName}
                        <ExternalLink className="w-3 h-3" />
                      </Link>
                    ) : (
                      <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>{orgName}</span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          {!isSignedIn && (
            <SignInButton
              variant="custom"
              className={`mt-3 pt-2 border-t text-xs flex items-center gap-1.5 w-full text-left cursor-pointer hover:opacity-80 transition-opacity ${
                isDark ? 'border-slate-700 text-emerald-400' : 'border-slate-200 text-emerald-600'
              }`}
            >
              <Lock className="w-3 h-3 flex-shrink-0" />
              <span><span className="underline font-medium">Sign in</span> to compare</span>
            </SignInButton>
          )}
        </SectionCard>
      )}
    </div>
  );

  // ==========================================================================
  // RENDER: Financials Tab
  // ==========================================================================
  const renderFinancialsTab = () => (
    <div className="space-y-5">
      {/* Financial Overview */}
      <SectionCard isDark={isDark}>
        <SectionHeader icon={BarChart3} title="Financial Overview" isDark={isDark} />
        {revenue != null ? (
          <div className={`mb-4 pb-3 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
            <div className={`text-3xl font-mono font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
              {formatCurrency(revenue)}
            </div>
            <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Annual Revenue</div>
          </div>
        ) : charity.evaluationTrack === 'NEW_ORG' ? (
          <div className={`mb-4 pb-3 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
            <div className={`flex items-center gap-2 ${isDark ? 'text-sky-400' : 'text-sky-600'}`}>
              <Rocket className="w-5 h-5" />
              <span className="text-lg font-semibold">Pre-990</span>
            </div>
            <div className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              New org -- First 990 filing pending
            </div>
          </div>
        ) : null}

        {!!charity.form990Exempt && !revenue && (
          <div className={`mb-4 p-3 rounded-lg text-sm ${isDark ? 'bg-slate-800 text-slate-300' : 'bg-amber-50 text-amber-800'}`}>
            <div className="font-medium mb-1">Form 990 Exempt</div>
            <div className={`text-xs ${isDark ? 'text-slate-400' : 'text-amber-700'}`}>
              {charity.form990ExemptReason || 'Religious organization'} -- not required to file public financial disclosures.
            </div>
          </div>
        )}

        <div className="space-y-0">
          {financials?.totalExpenses != null && (
            <DataRow label="Total Expenses" value={formatCurrency(financials.totalExpenses)} isDark={isDark} />
          )}
          {financials?.netAssets != null && (
            <DataRow label="Net Assets" value={formatCurrency(financials.netAssets)} isDark={isDark} />
          )}
          {financials?.workingCapitalMonths != null && (
            <DataRow label="Working Capital" value={`${Number(financials.workingCapitalMonths).toFixed(1)} months`} isDark={isDark} />
          )}
          {financials?.totalAssets != null && (
            <DataRow label="Total Assets" value={formatCurrency(financials.totalAssets)} isDark={isDark} />
          )}
          {financials?.totalLiabilities != null && (
            <DataRow label="Total Liabilities" value={formatCurrency(financials.totalLiabilities)} isDark={isDark} />
          )}
        </div>
      </SectionCard>

      {/* Expense Breakdown */}
      {hasExpenseData && (
        <SectionCard isDark={isDark}>
          <SectionHeader icon={BarChart3} title="Expense Breakdown" isDark={isDark} />
          <div className={`h-3 rounded-full overflow-hidden flex mb-4 ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}>
            <div className="bg-emerald-500 transition-all" style={{ width: `${programRatio}%` }} />
            <div className={`${isDark ? 'bg-slate-500' : 'bg-slate-400'} transition-all`} style={{ width: `${adminRatio}%` }} />
            <div className="bg-amber-500 transition-all" style={{ width: `${fundRatio}%` }} />
          </div>
          <div className={`space-y-2 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-emerald-500" />
                Programs
              </span>
              <span className="font-mono">
                {formatCurrency(financials?.programExpenses)}
                {hasSignificantNoncash && cashAdjProgramRatio != null ? (
                  <>
                    <span className={`ml-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>({cashAdjProgramRatio.toFixed(0)}% cash-adjusted)</span>
                    <span className={`ml-1 text-xs ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>({programRatio.toFixed(0)}% reported)</span>
                  </>
                ) : (
                  <>
                    <span className={`ml-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>({programRatio.toFixed(0)}%)</span>
                    {financials?.cashAdjustedProgramRatio != null && (
                      <span className={`ml-1 text-xs ${isDark ? 'text-amber-400' : 'text-amber-600'}`}>
                        ({(financials.cashAdjustedProgramRatio * 100).toFixed(0)}% cash-adj)
                      </span>
                    )}
                  </>
                )}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className={`w-3 h-3 rounded-full ${isDark ? 'bg-slate-500' : 'bg-slate-400'}`} />
                Admin
              </span>
              <span className="font-mono">
                {formatCurrency(financials?.adminExpenses)}
                <span className={`ml-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>({adminRatio.toFixed(0)}%)</span>
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-amber-500" />
                Fundraising
              </span>
              <span className="font-mono">
                {formatCurrency(financials?.fundraisingExpenses)}
                <span className={`ml-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>({fundRatio.toFixed(0)}%)</span>
              </span>
            </div>
          </div>
        </SectionCard>
      )}

      {/* Financial History (3-year) */}
      {rich?.financial_deep_dive?.yearly_financials && rich.financial_deep_dive.yearly_financials.length > 0 && (
        isSignedIn ? (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={TrendingUp} title="Financial History" isDark={isDark} />
            <div className="space-y-2 text-sm">
              {rich.financial_deep_dive.yearly_financials.map((year) => (
                <div key={year.year} className="flex justify-between items-center">
                  <span className={`font-mono ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{year.year}</span>
                  <span className={`font-mono font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {formatCurrency(year.revenue)}
                  </span>
                </div>
              ))}
            </div>
            {rich.financial_deep_dive.revenue_cagr_3yr && (
              <div className={`mt-3 pt-3 border-t flex justify-between items-center ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>3yr CAGR</span>
                <span className={`text-sm font-mono font-semibold ${
                  rich.financial_deep_dive.revenue_cagr_3yr > 0
                    ? isDark ? 'text-emerald-400' : 'text-emerald-600'
                    : isDark ? 'text-red-400' : 'text-red-600'
                }`}>
                  {rich.financial_deep_dive.revenue_cagr_3yr > 0 ? '\u2191' : '\u2193'} {Math.abs(rich.financial_deep_dive.revenue_cagr_3yr).toFixed(1)}%
                </span>
              </div>
            )}
            {rich.financial_deep_dive.reserves_months && (
              <div className="flex justify-between items-center mt-1">
                <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Reserves</span>
                <span className={`text-sm font-mono ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  {rich.financial_deep_dive.reserves_months.toFixed(1)} mo
                </span>
              </div>
            )}
          </SectionCard>
        ) : (
          <ContentPreview title="3-Year Financials" description="three years of financial data" />
        )
      )}

      {/* Grantmaking */}
      {rich?.grantmaking_profile && rich.grantmaking_profile.is_significant_grantmaker && (
        isSignedIn ? (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={Landmark} title="Grantmaking" isDark={isDark} infoTip={GLOSSARY['Grantmaking']} />
            {rich.grantmaking_profile.total_grants && (
              <div className={`mb-3 pb-2 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <div className={`text-2xl font-mono font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {formatCurrency(rich.grantmaking_profile.total_grants)}
                </div>
                <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  Total Grants ({rich.grantmaking_profile.grant_count || 0} recipients)
                </div>
              </div>
            )}
            <div className={`space-y-1 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
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
              <div className={`mt-3 pt-2 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <div className={`text-xs font-semibold mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Top Recipients</div>
                <ul className={`text-xs space-y-0.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  {rich.grantmaking_profile.top_recipients.slice(0, 3).map((r, i) => (
                    <li key={i}>- {r}</li>
                  ))}
                </ul>
              </div>
            )}
            {rich.grantmaking_profile.regions_served && rich.grantmaking_profile.regions_served.length > 0 && (
              <div className={`mt-2 pt-2 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <div className="flex flex-wrap gap-1">
                  {rich.grantmaking_profile.regions_served.slice(0, 4).map((region, i) => (
                    <span key={i} className={`px-1.5 py-0.5 rounded text-xs ${isDark ? 'bg-slate-700 text-slate-300' : 'bg-slate-200 text-slate-600'}`}>
                      {region}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </SectionCard>
        ) : (
          <ContentPreview title="Grantmaking" description="grantmaking profile and distribution data" />
        )
      )}

    </div>
  );

  // ==========================================================================
  // MAIN RENDER
  // ==========================================================================
  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950' : 'bg-slate-100'}`}>
      {/* ═══════════════════════════════════════════════════════════════════════
          HERO SECTION (always visible, above tabs)
          ═══════════════════════════════════════════════════════════════════════ */}
      <div className={`border-b ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
        <div className="max-w-5xl mx-auto px-6 pt-4 pb-0">
          {/* Back link */}
          <Link
            to="/browse"
            aria-label="Back to browse"
            className={`inline-flex items-center gap-1 text-xs mb-3 ${
              isDark ? 'text-slate-500 hover:text-white' : 'text-slate-400 hover:text-slate-900'
            }`}
          >
            <ArrowLeft className="w-3 h-3" />
            Browse
          </Link>

          {/* Name — dominant element */}
          <h1 className={`text-2xl font-bold leading-tight ${isDark ? 'text-white' : 'text-slate-900'}`}>
            {charity.name}
          </h1>

          {/* Subtitle: address · cause area */}
          <div className={`flex items-center gap-1.5 mt-1 text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
            {getCharityAddress(charity) && (
              <span>{getCharityAddress(charity)}</span>
            )}
            {getCharityAddress(charity) && charity.causeArea && (
              <span className={isDark ? 'text-slate-700' : 'text-slate-300'}>·</span>
            )}
            {charity.causeArea && (
              <span className={isDark ? 'text-slate-400' : 'text-slate-600'}>{formatCauseArea(charity.causeArea)}</span>
            )}
          </div>

          {/* Single row: signals + tags (left) — actions (right) */}
          <div className="flex items-center justify-between mt-3 gap-4">
            {/* Left: signal badges */}
            <div className="flex flex-wrap items-center gap-1.5">
              <span
                className={`px-2 py-0.5 rounded text-[11px] font-semibold ${isDark ? 'bg-slate-800 text-slate-400' : 'bg-slate-100 text-slate-500'}`}
                title={getArchetypeDescription(uiSignals.archetype_code || charity.archetype)}
              >
                {uiSignals.archetype_label}
              </span>
              <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${getEvidenceStageClasses(uiSignals.evidence_stage, isDark)}`}>
                {getEvidenceStageLabel(uiSignals.evidence_stage)}
              </span>
              <RecommendationCue cue={uiSignals.recommendation_cue} rationale={null} isDark={isDark} compact />
              {isZakatEligible && (() => {
                const rawUrl = charity.zakatClaimEvidence?.[0] ? extractZakatPolicyUrl(charity.zakatClaimEvidence[0]) : undefined;
                // Only link if URL has a real path (not just homepage)
                const isDeepLink = rawUrl ? new URL(rawUrl).pathname.replace(/\/$/, '') !== '' : false;
                const policyUrl = isDeepLink ? rawUrl : undefined;
                const badgeClass = `inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold ${
                  isDark ? 'bg-emerald-900/40 text-emerald-400' : 'bg-emerald-100 text-emerald-700'
                }`;
                return policyUrl ? (
                  <a href={policyUrl} target="_blank" rel="noopener noreferrer" className={`${badgeClass} hover:opacity-80`}>
                    <Shield className="w-3 h-3" />
                    Accepts Zakat <ExternalLink className="w-2.5 h-2.5 opacity-60" />
                  </a>
                ) : (
                  <span className={badgeClass}>
                    <Shield className="w-3 h-3" />
                    Accepts Zakat
                  </span>
                );
              })()}
              {!!charity.trustSignals?.isConflictZone && (
                <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                  isDark ? 'bg-orange-900/50 text-orange-400' : 'bg-orange-100 text-orange-700'
                }`}>
                  Conflict Zone
                </span>
              )}
              {charity.categoryMetadata?.neglectedness === 'HIGH' && (
                <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                  isDark ? 'bg-violet-900/50 text-violet-400' : 'bg-violet-100 text-violet-700'
                }`}>
                  Neglected
                </span>
              )}
              {charity.evaluationTrack === 'NEW_ORG' && (
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold ${
                  isDark ? 'bg-amber-900/50 text-amber-300' : 'bg-amber-100 text-amber-700'
                }`}>
                  Emerging
                </span>
              )}
              {charity.evaluationTrack === 'RESEARCH_POLICY' && (
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold ${
                  isDark ? 'bg-indigo-900/50 text-indigo-300' : 'bg-indigo-100 text-indigo-700'
                }`}>
                  Research & Policy
                </span>
              )}
              {getDifferentiatorTags(charity, isDark).map((tag, i) => (
                <span key={i} className={`px-2 py-0.5 rounded text-[11px] font-semibold ${tag.colorClass}`}>
                  {tag.label}
                </span>
              ))}
            </div>

            {/* Right: inline actions */}
            <div className="flex items-center gap-1 flex-shrink-0">
              {isSignedIn ? (
                <>
                  <button
                    data-tour="action-log-donation"
                    onClick={() => setShowDonationModal(true)}
                    className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                      isDark ? 'text-slate-400 hover:text-white hover:bg-slate-800' : 'text-slate-500 hover:text-slate-900 hover:bg-slate-100'
                    }`}
                  >
                    <Plus className="w-3 h-3" />
                    Log
                  </button>
                  <CompareButton charityEin={charity.ein!} charityName={charity.name} size="sm" />
                  <span data-tour="action-save">
                    <BookmarkButton charityEin={charity.ein || charity.id || ''} charityName={charity.name} causeTags={charity.causeTags || undefined} showLabel size="sm" />
                  </span>
                  <ShareButton charityId={charity.ein!} charityName={charity.name} isDark={isDark} />
                </>
              ) : (
                <>
                  <SignInButton variant="custom" isDark={isDark}>
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium cursor-pointer transition-colors ${
                      isDark ? 'text-emerald-400 hover:text-emerald-300 hover:bg-slate-800' : 'text-emerald-600 hover:text-emerald-700 hover:bg-slate-100'
                    }`}>
                      <LogIn className="w-3 h-3" />
                      Sign in
                    </span>
                  </SignInButton>
                  <ShareButton charityId={charity.ein!} charityName={charity.name} isDark={isDark} />
                </>
              )}
              {donateUrl && (
                <a
                  data-tour="action-donate"
                  href={donateUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={handleDonateClick}
                  className={`inline-flex items-center gap-1 px-3 py-1 rounded text-xs font-semibold transition-colors ${
                    isDark ? 'bg-emerald-600 hover:bg-emerald-500 text-white' : 'bg-emerald-600 hover:bg-emerald-700 text-white'
                  }`}
                >
                  Donate <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          </div>

          {/* Tab bar — flush against bottom */}
          <div className="flex gap-0 mt-3 -mb-px">
            {tabs.map(tab => {
              const isActive = activeTab === tab.id;
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => {
                    handleTabChange(tab.id);
                    trackTabClick(charity.id ?? charity.ein ?? '', tab.id);
                  }}
                  className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                    isActive
                      ? isDark
                        ? 'border-emerald-400 text-emerald-400'
                        : 'border-emerald-600 text-emerald-700'
                      : isDark
                        ? 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-600'
                        : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════
          TAB CONTENT
          ═══════════════════════════════════════════════════════════════════════ */}
      <div className="max-w-5xl mx-auto px-6 py-6">
        {/* Sign-in banner for anonymous users */}
        {!isSignedIn && (
          <div className={`mb-6 rounded-xl p-5 border-2 ${
            isDark
              ? 'bg-gradient-to-br from-emerald-900/30 to-slate-900 border-emerald-700/50'
              : 'bg-gradient-to-br from-emerald-50 to-white border-emerald-300'
          }`}>
            <div className="flex items-center gap-2 mb-2">
              <Lock className={`w-4 h-4 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
              <h3 className={`text-base font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                Sign in to unlock the full evaluation
              </h3>
            </div>
            <p className={`text-sm mb-3 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              Leadership profiles, 3-year financials, impact evidence, donor fit analysis
            </p>
            <SignInButton
              variant="button"
              className={`inline-flex items-center justify-center px-5 py-2.5 rounded-full text-sm font-bold transition-colors ${
                isDark ? 'bg-emerald-600 hover:bg-emerald-500 text-white' : 'bg-emerald-600 hover:bg-emerald-700 text-white'
              }`}
            />
          </div>
        )}

        {activeTab === 'overview' && renderOverviewTab()}
        {activeTab === 'impact' && renderImpactTab()}
        {activeTab === 'giving' && renderGivingTab()}
        {activeTab === 'financials' && renderFinancialsTab()}
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════
          FOOTER (always visible, below tabs)
          ═══════════════════════════════════════════════════════════════════════ */}
      <div className={`border-t mt-4 pt-6 pb-8 ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
        <div className={`max-w-5xl mx-auto px-6 flex items-center justify-center gap-2 text-xs flex-wrap ${
          isDark ? 'text-slate-500' : 'text-slate-400'
        }`}>
          <span>EIN: {charity.ein}</span>
          {amal?.evaluation_date && (
            <>
              <span>--</span>
              <span>Last evaluated {new Date(amal.evaluation_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
            </>
          )}
          <span>--</span>
          <ShareButton charityId={charity.ein || charity.id || ''} charityName={charity.name} variant="text" isDark={isDark} />
          <span>--</span>
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
      <div className="max-w-5xl mx-auto px-6 pb-4">
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

export default TabbedView;

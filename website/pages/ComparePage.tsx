/**
 * ComparePage - Side-by-side charity comparison (max 3)
 * Shows scores, narratives, financials, confidence, tags, and more
 */

import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, X, ExternalLink, Lock, ChevronDown, ChevronUp, Award, AlertCircle, TrendingUp } from 'lucide-react';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { useCompareState } from '../src/contexts/UserFeaturesContext';
import { useCommunityMember } from '../src/auth';
import { BookmarkButton } from '../src/components/BookmarkButton';
import { getWalletType, formatWalletTag } from '../src/utils/walletUtils';
import { formatShortRevenue, formatPercent } from '../src/utils/formatters';
import { deriveUISignalsFromCharity, formatEvidenceForDonors, formatComponentName, stripCitations } from '../src/utils/scoreUtils';
import { getEvidenceStageLabel } from '../src/utils/scoreConstants';
import type { CharityProfile, ScoreComponentDetail, ImpactDetails, AlignmentDetails } from '../types';
import { RecommendationCue } from '../src/components/RecommendationCue';
import { SignalConstellation } from '../src/components/SignalConstellation';
import { HarveyBall, ratioToHarveyLevel, levelToLabel } from '../src/components/ScoreBreakdown';

// Category labels for human-readable display
const CATEGORY_LABELS: Record<string, string> = {
  'HUMANITARIAN': 'Humanitarian',
  'MEDICAL_HEALTH': 'Medical & Health',
  'SOCIAL_SERVICES': 'Social Services',
  'EDUCATION': 'Education',
  'RELIGIOUS_OUTREACH': 'Religious Outreach',
  'CIVIL_RIGHTS_LEGAL': 'Civil Rights & Legal',
  'ENVIRONMENT_CLIMATE': 'Environment & Climate',
  'INTERNATIONAL_DEVELOPMENT': 'International Development',
  'RESEARCH_POLICY': 'Research & Policy',
  'COMMUNITY_DEVELOPMENT': 'Community Development',
};

// Impact tier labels
const IMPACT_TIER_LABELS: Record<string, string> = {
  'HIGH': 'High',
  'ABOVE_AVERAGE': 'Above Average',
  'AVERAGE': 'Average',
  'BELOW_AVERAGE': 'Below Average',
  'LOW': 'Low',
};

// Tag categorization for color coding
const GEOGRAPHIC_TAGS = new Set([
  'usa', 'pakistan', 'palestine', 'syria', 'yemen', 'bangladesh', 'india', 'africa',
  'asia', 'middle-east', 'somalia', 'afghanistan', 'iraq', 'jordan', 'lebanon',
  'turkey', 'egypt', 'morocco', 'indonesia', 'malaysia', 'global', 'international',
  'domestic', 'local', 'regional'
]);

const ZAKAT_ASNAF_TAGS = new Set([
  'fuqara', 'masakin', 'fisabilillah', 'muallaf', 'gharimin', 'ibn-sabil',
  'zakat-eligible', 'zakat'
]);

const PROGRAM_TAGS = new Set([
  'medical', 'educational', 'food', 'shelter', 'clothing', 'legal-aid', 'water',
  'emergency-response', 'disaster-relief', 'refugees', 'orphans', 'widows',
  'direct-relief', 'capacity-building', 'advocacy', 'research'
]);

type TagCategory = 'geo' | 'zakat' | 'program' | 'other';

function getTagCategory(tag: string): TagCategory {
  const normalized = tag.toLowerCase();
  if (GEOGRAPHIC_TAGS.has(normalized)) return 'geo';
  if (ZAKAT_ASNAF_TAGS.has(normalized)) return 'zakat';
  if (PROGRAM_TAGS.has(normalized)) return 'program';
  return 'other';
}

// Extract geographic tags from causeTags
function extractGeographicTags(causeTags: string[] | null | undefined, location?: { state?: string | null } | null): string[] {
  const geoTags: string[] = [];

  if (causeTags) {
    for (const tag of causeTags) {
      if (GEOGRAPHIC_TAGS.has(tag.toLowerCase())) {
        geoTags.push(tag);
      }
    }
  }

  // Add HQ state if available and no other geo tags
  if (geoTags.length === 0 && location?.state) {
    geoTags.push(`HQ: ${location.state}`);
  }

  return geoTags;
}

function formatCategory(category: string | null | undefined): string | null {
  if (!category) return null;
  return CATEGORY_LABELS[category] || category.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatImpactTier(tier: string | null | undefined): string | null {
  if (!tier) return null;
  return IMPACT_TIER_LABELS[tier] || tier.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// Comparison row component
interface CompareRowProps {
  label: string;
  values: (string | number | React.ReactNode | null | undefined)[];
  isDark: boolean;
  highlight?: boolean;
}

function CompareRow({ label, values, isDark, highlight = false }: CompareRowProps) {
  return (
    <div className={`
      grid gap-3 py-2.5 border-b
      ${isDark ? 'border-slate-800' : 'border-slate-100'}
      ${highlight ? (isDark ? 'bg-emerald-900/10' : 'bg-emerald-50/50') : ''}
    `}
    style={{ gridTemplateColumns: `120px repeat(${values.length}, minmax(0, 1fr))` }}
    >
      <div className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
        {label}
      </div>
      {values.map((value, i) => (
        <div key={i} className={`text-sm min-w-0 overflow-hidden ${isDark ? 'text-white' : 'text-slate-900'}`}>
          {value ?? <span className={isDark ? 'text-slate-600' : 'text-slate-300'}>—</span>}
        </div>
      ))}
    </div>
  );
}

// Section header
function SectionHeader({ title, isDark }: { title: string; isDark: boolean }) {
  return (
    <div className={`px-4 py-2 ${isDark ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
      <h3 className={`text-xs font-bold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
        {title}
      </h3>
    </div>
  );
}

// Score badge component - Harvey ball + label for overall score (0-100)
function ScoreBadge({ score, isDark }: { score: number | null | undefined; isDark: boolean; size?: 'sm' | 'md' }) {
  if (score === null || score === undefined) {
    return <span className={isDark ? 'text-slate-500' : 'text-slate-400'}>—</span>;
  }

  const level = ratioToHarveyLevel(score / 100);
  const label = levelToLabel(level);

  return (
    <div className="flex items-center gap-2">
      <HarveyBall level={level} isDark={isDark} size="md" />
      <div>
        <span className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>{score}</span>
        <span className={`text-[10px] ml-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{label}</span>
      </div>
    </div>
  );
}

// Dimension score with Harvey ball (for 0-50 scale)
function DimensionScore({ score, max, isDark }: { score: number | null | undefined; max: number; isDark: boolean }) {
  if (score === null || score === undefined) {
    return <span className={isDark ? 'text-slate-500' : 'text-slate-400'}>—</span>;
  }

  const ratio = max > 0 ? score / max : 0;
  const level = ratioToHarveyLevel(ratio);
  const label = levelToLabel(level);

  return (
    <div className="flex items-center gap-2">
      <HarveyBall level={level} isDark={isDark} size="sm" />
      <span className={`text-xs font-medium ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{label}</span>
    </div>
  );
}

// Confidence indicator
function ConfidenceIndicator({ level, isDark }: { level: string | undefined | null; isDark: boolean }) {
  if (!level) return <span className={isDark ? 'text-slate-600' : 'text-slate-300'}>—</span>;

  const levelLower = level.toLowerCase();
  const color = levelLower === 'high' ? 'emerald' : levelLower === 'medium' ? 'amber' : 'slate';
  const colorClasses = {
    emerald: isDark ? 'text-emerald-400' : 'text-emerald-600',
    amber: isDark ? 'text-amber-400' : 'text-amber-600',
    slate: isDark ? 'text-slate-400' : 'text-slate-500',
  };

  return (
    <span className={`text-xs font-medium ${colorClasses[color]}`}>
      {level}
    </span>
  );
}

// Color-coded tag component
function ColoredTag({ tag, isDark }: { tag: string; isDark: boolean }) {
  const category = getTagCategory(tag);

  const colorClasses: Record<TagCategory, string> = {
    geo: isDark ? 'bg-blue-800/60 text-blue-200 border-blue-600' : 'bg-blue-100 text-blue-800 border-blue-300',
    zakat: isDark ? 'bg-emerald-800/60 text-emerald-200 border-emerald-600' : 'bg-emerald-100 text-emerald-800 border-emerald-300',
    program: isDark ? 'bg-violet-800/60 text-violet-200 border-violet-600' : 'bg-violet-100 text-violet-800 border-violet-300',
    other: isDark ? 'bg-slate-700/50 text-slate-300 border-slate-600' : 'bg-slate-50 text-slate-600 border-slate-300',
  };

  return (
    <span className={`px-1.5 py-0.5 rounded text-xs border ${colorClasses[category]}`}>
      {tag.replace(/-/g, ' ')}
    </span>
  );
}

// Tag list component with color coding
function TagList({ tags, isDark, max = 4 }: { tags: string[] | null | undefined; isDark: boolean; max?: number }) {
  if (!tags || tags.length === 0) return <span className={isDark ? 'text-slate-600' : 'text-slate-300'}>—</span>;

  return (
    <div className="flex flex-wrap gap-1">
      {tags.slice(0, max).map(tag => (
        <ColoredTag key={tag} tag={tag} isDark={isDark} />
      ))}
      {tags.length > max && (
        <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
          +{tags.length - max}
        </span>
      )}
    </div>
  );
}

// Plain text list for free-form items (Programs, Populations)
function TextList({ items, isDark, max = 3 }: { items: string[] | null | undefined; isDark: boolean; max?: number }) {
  if (!items || items.length === 0) return <span className={isDark ? 'text-slate-600' : 'text-slate-300'}>—</span>;

  const displayed = items.slice(0, max);
  const remaining = items.length - max;

  return (
    <span className={`text-xs leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
      {displayed.join(', ')}
      {remaining > 0 && <span className={isDark ? 'text-slate-500' : 'text-slate-400'}> +{remaining}</span>}
    </span>
  );
}


// ─── Score Analysis & Improvement Helpers ────────────────────────────────────

type DimensionKey = 'impact' | 'alignment';

function getDimensionDetails(charity: CharityProfile, dimension: DimensionKey): ImpactDetails | AlignmentDetails | null {
  const sd = charity.amalEvaluation?.score_details;
  if (!sd) return null;
  const details = sd[dimension];
  if (!details || !('components' in details)) return null;
  return details as ImpactDetails | AlignmentDetails;
}

function getUnionComponentNames(charities: CharityProfile[], dimension: DimensionKey): string[] {
  const nameSet = new Set<string>();
  for (const c of charities) {
    const details = getDimensionDetails(c, dimension);
    if (details) {
      for (const comp of details.components) {
        nameSet.add(comp.name);
      }
    }
  }
  return Array.from(nameSet);
}

function findComponent(charity: CharityProfile, dimension: DimensionKey, componentName: string): ScoreComponentDetail | null {
  const details = getDimensionDetails(charity, dimension);
  if (!details) return null;
  return details.components.find(c => c.name === componentName) || null;
}

function getImprovableComponentNames(charities: CharityProfile[]): string[] {
  const nameSet = new Set<string>();
  for (const dim of ['impact', 'alignment'] as DimensionKey[]) {
    for (const c of charities) {
      const details = getDimensionDetails(c, dim);
      if (details) {
        for (const comp of details.components) {
          if (comp.improvement_value > 0) {
            nameSet.add(comp.name);
          }
        }
      }
    }
  }
  return Array.from(nameSet);
}

function getTotalRecoverable(charity: CharityProfile): number {
  let total = 0;
  for (const dim of ['impact', 'alignment'] as DimensionKey[]) {
    const details = getDimensionDetails(charity, dim);
    if (details) {
      for (const comp of details.components) {
        total += comp.improvement_value;
      }
    }
  }
  return total;
}

function findImprovableComponent(charity: CharityProfile, componentName: string): ScoreComponentDetail | null {
  for (const dim of ['impact', 'alignment'] as DimensionKey[]) {
    const comp = findComponent(charity, dim, componentName);
    if (comp && comp.improvement_value > 0) return comp;
  }
  return null;
}

// Single component cell in the Score Analysis grid
function ComponentCell({ component, isMember, isDark }: { component: ScoreComponentDetail | null; isMember: boolean; isDark: boolean }) {
  if (!component) {
    return <span className={isDark ? 'text-slate-600' : 'text-slate-300'}>—</span>;
  }

  const noData = component.scored === 0 && !!component.evidence &&
    /not (yet )?available|unknown|insufficient data/i.test(component.evidence);

  const ratio = component.possible > 0 ? component.scored / component.possible : 0;
  const level = noData ? 0 as const : ratioToHarveyLevel(ratio);
  const label = noData ? 'No Data' : levelToLabel(level);

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5">
        <HarveyBall level={level} isDark={isDark} size="sm" tone={noData ? 'neutral' : undefined} />
        <span className={`text-[11px] font-medium ${
          noData
            ? (isDark ? 'text-slate-500' : 'text-slate-400')
            : (isDark ? 'text-slate-300' : 'text-slate-600')
        }`}>
          {label}
        </span>
      </div>
      {isMember && component.evidence && !noData && (
        <p className={`text-[11px] leading-relaxed ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
          {stripCitations(formatEvidenceForDonors(component.evidence))}
        </p>
      )}
    </div>
  );
}

// Dimension sub-header row showing dimension name + per-charity harvey balls
function DimensionSubHeader({ label, charities, dimension, isDark, numCharities }: {
  label: string;
  charities: CharityProfile[];
  dimension: DimensionKey;
  isDark: boolean;
  numCharities: number;
}) {
  return (
    <div
      className={`grid gap-3 py-2 border-b ${isDark ? 'border-slate-700 bg-slate-800/30' : 'border-slate-150 bg-slate-50/50'}`}
      style={{ gridTemplateColumns: `120px repeat(${numCharities}, minmax(0, 1fr))` }}
    >
      <div className={`text-xs font-semibold ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
        {label}
      </div>
      {charities.map(c => {
        const details = getDimensionDetails(c, dimension);
        const max = 50;
        if (!details) return (
          <div key={c.ein} className={isDark ? 'text-slate-600' : 'text-slate-300'}>—</div>
        );
        const level = ratioToHarveyLevel(details.score / max);
        return (
          <div key={c.ein} className="flex items-center gap-1.5">
            <HarveyBall level={level} isDark={isDark} size="sm" />
            <span className={`text-xs font-medium ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{levelToLabel(level)}</span>
          </div>
        );
      })}
    </div>
  );
}

// Improvement cell for the Opportunities section
function ImprovementCell({ component, isMember, isDark }: { component: ScoreComponentDetail | null; isMember: boolean; isDark: boolean }) {
  if (!component || component.improvement_value <= 0) {
    return <span className={isDark ? 'text-slate-600' : 'text-slate-300'}>—</span>;
  }

  return (
    <div className="space-y-1">
      <span className={`inline-flex items-center text-xs font-semibold px-1.5 py-0.5 rounded ${isDark ? 'bg-amber-900/40 text-amber-400' : 'bg-amber-100 text-amber-700'}`}>
        +{component.improvement_value}
      </span>
      {isMember && component.improvement_suggestion && (
        <p className={`text-[11px] leading-relaxed ${isDark ? 'text-amber-400/70' : 'text-amber-600'}`}>
          {component.improvement_suggestion}
        </p>
      )}
    </div>
  );
}

// Total recoverable badge
function TotalRecoverableBadge({ total, isDark }: { total: number; isDark: boolean }) {
  if (total <= 0) {
    return <span className={isDark ? 'text-slate-600' : 'text-slate-300'}>—</span>;
  }
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-1 rounded ${isDark ? 'bg-amber-900/30 text-amber-400' : 'bg-amber-100 text-amber-700'}`}>
      <TrendingUp className="w-3 h-3" />
      +{total} pts possible
    </span>
  );
}

// Collapsible section
function CollapsibleSection({ title, isDark, defaultOpen = false, children }: {
  title: string;
  isDark: boolean;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full px-4 py-2 flex items-center justify-between ${isDark ? 'bg-slate-800/50 hover:bg-slate-800' : 'bg-slate-50 hover:bg-slate-100'}`}
      >
        <h3 className={`text-xs font-bold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          {title}
        </h3>
        {isOpen ? <ChevronUp className="w-4 h-4" aria-hidden="true" /> : <ChevronDown className="w-4 h-4" aria-hidden="true" />}
      </button>
      {isOpen && children}
    </div>
  );
}

export function ComparePage() {
  const { isDark } = useLandingTheme();
  const navigate = useNavigate();
  const { compareList, removeFromCompare, clearCompare } = useCompareState();
  const isMember = useCommunityMember();
  const [charities, setCharities] = useState<CharityProfile[]>([]);
  const [loading, setLoading] = useState(true);

  // Load full charity data for each EIN
  useEffect(() => {
    async function loadCharities() {
      if (compareList.length === 0) {
        setCharities([]);
        setLoading(false);
        return;
      }

      setLoading(true);
      const loaded: CharityProfile[] = [];

      const results = await Promise.all(
        compareList.map(async ein => {
          try {
            const response = await fetch(`/data/charities/charity-${ein}.json`);
            if (response.ok) return response.json();
          } catch (err) {
            console.error(`Failed to load charity ${ein}:`, err);
          }
          return null;
        })
      );
      for (const data of results) {
        if (data) loaded.push(data);
      }

      setCharities(loaded);
      setLoading(false);
    }

    loadCharities();
  }, [compareList]);

  const numCharities = charities.length;

  // Redirect if less than 2 charities
  if (!loading && numCharities < 2) {
    return (
      <div className={`min-h-screen ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <div className="max-w-4xl mx-auto px-4 py-16 text-center">
          <h1 className={`text-2xl font-semibold mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>
            Select Charities to Compare
          </h1>
          <p className={`text-lg mb-8 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            You need at least 2 charities to compare. Browse charities and click "Compare" to add them.
          </p>
          <Link
            to="/browse"
            className="inline-flex items-center gap-2 px-6 py-3 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 transition-colors"
          >
            Browse Charities
          </Link>
        </div>
      </div>
    );
  }

  // Helper to extract data
  const getDataQuality = (c: CharityProfile) => (c.amalEvaluation?.score_details as any)?.data_confidence?.data_quality_label || null;
  const getVerificationTier = (c: CharityProfile) => (c.amalEvaluation?.score_details as any)?.data_confidence?.verification_tier || null;
  const getTransparency = (c: CharityProfile) => (c.amalEvaluation?.score_details as any)?.data_confidence?.transparency_label || null;

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Link
              to="/browse"
              aria-label="Back to browse"
              className={`p-2 rounded-lg transition-colors ${isDark ? 'hover:bg-slate-800 text-slate-400' : 'hover:bg-slate-100 text-slate-600'}`}
            >
              <ArrowLeft className="w-5 h-5" aria-hidden="true" />
            </Link>
            <div>
              <h1 className={`text-xl font-semibold [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>
                Compare Charities
              </h1>
              <p className={`text-xs mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                {numCharities} charities selected
              </p>
            </div>
          </div>
          <button
            onClick={() => { clearCompare(); navigate('/browse'); }}
            className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${isDark ? 'text-slate-400 hover:text-white hover:bg-slate-800' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'}`}
          >
            Clear All
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className={`animate-spin w-8 h-8 border-2 border-t-transparent rounded-full ${isDark ? 'border-slate-600' : 'border-slate-300'}`} />
          </div>
        ) : (
          <div className={`rounded-xl border ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
            <div className="overflow-x-auto">
            {/* Charity Headers (sticky) */}
            <div
              className={`grid min-w-[720px] gap-3 p-4 border-b rounded-t-xl sticky top-[65px] z-30 ${isDark ? 'border-slate-800 bg-slate-900' : 'border-slate-100 bg-white'}`}
              style={{ gridTemplateColumns: `120px repeat(${numCharities}, minmax(0, 1fr))` }}
            >
              <div />
              {charities.map(charity => (
                <div key={charity.ein} className="relative pr-6">
                  <button
                    onClick={() => removeFromCompare(charity.ein!)}
                    className={`absolute -top-1 right-0 p-1 rounded-full transition-colors ${isDark ? 'bg-slate-700 hover:bg-slate-600 text-slate-400' : 'bg-slate-200 hover:bg-slate-300 text-slate-600'}`}
                    aria-label={`Remove ${charity.name}`}
                  >
                    <X className="w-3 h-3" aria-hidden="true" />
                  </button>
                  <Link
                    to={`/charity/${charity.ein}`}
                    className={`block font-semibold text-sm hover:underline ${isDark ? 'text-white' : 'text-slate-900'}`}
                  >
                    {charity.name}
                  </Link>
                  <div className="flex items-center gap-2 mt-1.5">
                    <BookmarkButton charityEin={charity.ein!} charityName={charity.name} size="sm" />
                    <a
                      href={charity.website || '#'}
                      target="_blank"
                      rel="noreferrer"
                      aria-label={`Visit ${charity.name} website (opens in new tab)`}
                      className={`text-xs flex items-center gap-1 ${isDark ? 'text-slate-400 hover:text-slate-200' : 'text-slate-500 hover:text-slate-700'}`}
                    >
                      <ExternalLink className="w-3 h-3" aria-hidden="true" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
            <div className="min-w-[720px]">

            {/* Evaluation Signals Section */}
            <SectionHeader title="Evaluation Signals" isDark={isDark} />
            <div className="px-4">
              <CompareRow
                label="Archetype"
                values={charities.map(c => (c.ui_signals_v1 || deriveUISignalsFromCharity(c)).archetype_label)}
                isDark={isDark}
                highlight
              />
              <CompareRow
                label="Evidence Stage"
                values={charities.map(c => getEvidenceStageLabel((c.ui_signals_v1 || deriveUISignalsFromCharity(c)).evidence_stage))}
                isDark={isDark}
              />
              <CompareRow
                label="Recommendation"
                values={charities.map(c => {
                  const ui = c.ui_signals_v1 || deriveUISignalsFromCharity(c);
                  return <RecommendationCue cue={ui.recommendation_cue} rationale={null} isDark={isDark} compact />;
                })}
                isDark={isDark}
              />
              <CompareRow
                label="Signals"
                values={charities.map(c => {
                  const ui = c.ui_signals_v1 || deriveUISignalsFromCharity(c);
                  return <SignalConstellation signals={ui.signal_states} isDark={isDark} compact showLabels={false} />;
                })}
                isDark={isDark}
              />
            </div>

            {/* Detailed Assessment Section */}
            <CollapsibleSection title="Detailed Assessment" isDark={isDark} defaultOpen={false}>
              <div className="px-4">
                <CompareRow
                  label="GMG Score"
                  values={charities.map(c => <ScoreBadge score={c.amalEvaluation?.amal_score} isDark={isDark} />)}
                  isDark={isDark}
                />
                <CompareRow
                  label="Impact"
                  values={charities.map(c => <DimensionScore score={c.amalEvaluation?.confidence_scores?.impact} max={50} isDark={isDark} />)}
                  isDark={isDark}
                />
                <CompareRow
                  label="Alignment"
                  values={charities.map(c => <DimensionScore score={c.amalEvaluation?.confidence_scores?.alignment} max={50} isDark={isDark} />)}
                  isDark={isDark}
                />
              </div>
              <div className="px-4">
                {(['impact', 'alignment'] as DimensionKey[]).map(dimension => {
                  const componentNames = getUnionComponentNames(charities, dimension);
                  if (componentNames.length === 0) return null;
                  return (
                    <React.Fragment key={dimension}>
                      <DimensionSubHeader
                        label={dimension === 'impact' ? 'Impact' : 'Alignment'}
                        charities={charities}
                        dimension={dimension}
                        isDark={isDark}
                        numCharities={numCharities}
                      />
                      {componentNames.map(name => (
                        <CompareRow
                          key={`${dimension}-${name}`}
                          label={formatComponentName(name)}
                          values={charities.map(c => (
                            <ComponentCell
                              component={findComponent(c, dimension, name)}
                              isMember={isMember}
                              isDark={isDark}
                            />
                          ))}
                          isDark={isDark}
                        />
                      ))}
                    </React.Fragment>
                  );
                })}
                {!isMember && (
                  <div className={`py-2.5 text-center ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    <p className="text-xs">Sign in to see scoring evidence</p>
                  </div>
                )}
              </div>
            </CollapsibleSection>

            {/* Tags & Focus Areas */}
            <CollapsibleSection title="Tags & Focus" isDark={isDark} defaultOpen>
              <div className="px-4">
                <CompareRow
                  label="Category"
                  values={charities.map(c => formatCategory(c.primaryCategory || c.category))}
                  isDark={isDark}
                />
                <CompareRow
                  label="Geography"
                  values={charities.map(c => <TagList tags={extractGeographicTags(c.causeTags, c.location)} isDark={isDark} max={4} />)}
                  isDark={isDark}
                />
                <CompareRow
                  label="Who They Serve"
                  values={charities.map(c => <TextList items={(c as any).targeting?.populationsServed} isDark={isDark} max={4} />)}
                  isDark={isDark}
                />
                <CompareRow
                  label="Programs"
                  values={charities.map(c => <TextList items={c.programs} isDark={isDark} max={3} />)}
                  isDark={isDark}
                />
                <CompareRow
                  label="Cause Tags"
                  values={charities.map(c => <TagList tags={c.causeTags} isDark={isDark} max={5} />)}
                  isDark={isDark}
                />
              </div>
            </CollapsibleSection>

            {/* Opportunities to Improve */}
            {(() => {
              const improvableNames = getImprovableComponentNames(charities);
              const hasAnyImprovable = improvableNames.length > 0 || charities.some(c => getTotalRecoverable(c) > 0);
              if (!hasAnyImprovable) return null;

              const richImprovements = charities.map(c => {
                const rich = c.amalEvaluation?.rich_narrative?.areas_for_improvement;
                if (!rich || rich.length === 0) return null;
                return rich;
              });
              const hasRichImprovements = richImprovements.some(r => r !== null);

              return (
                <CollapsibleSection title="Opportunities to Improve" isDark={isDark} defaultOpen>
                  <div className="px-4">
                    <CompareRow
                      label="Growth Potential"
                      values={charities.map(c => <TotalRecoverableBadge total={getTotalRecoverable(c)} isDark={isDark} />)}
                      isDark={isDark}
                      highlight
                    />
                    {improvableNames.map(name => (
                      <CompareRow
                        key={`improve-${name}`}
                        label={formatComponentName(name)}
                        values={charities.map(c => (
                          <ImprovementCell
                            component={findImprovableComponent(c, name)}
                            isMember={isMember}
                            isDark={isDark}
                          />
                        ))}
                        isDark={isDark}
                      />
                    ))}
                    {isMember && hasRichImprovements && (
                      <CompareRow
                        label="Detailed Analysis"
                        values={richImprovements.map((areas, i) => {
                          if (!areas || areas.length === 0) {
                            return <span className={isDark ? 'text-slate-600' : 'text-slate-300'}>—</span>;
                          }
                          return (
                            <ul className="space-y-1.5" key={i}>
                              {areas.slice(0, 3).map((a, j) => {
                                const area = typeof a === 'string' ? a : a.area;
                                const context = typeof a === 'string' ? null : a.context;
                                return (
                                  <li key={j} className="flex gap-1.5 text-xs leading-relaxed">
                                    <AlertCircle className="w-3 h-3 text-amber-500 flex-shrink-0 mt-0.5" />
                                    <span className={isDark ? 'text-slate-300' : 'text-slate-600'}>
                                      <strong>{area}</strong>
                                      {context && <span className={isDark ? 'text-slate-500' : 'text-slate-400'}> — {stripCitations(context)}</span>}
                                    </span>
                                  </li>
                                );
                              })}
                            </ul>
                          );
                        })}
                        isDark={isDark}
                      />
                    )}
                    {!isMember && (
                      <div className={`py-2.5 text-center ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                        <p className="text-xs">Sign in to see improvement details</p>
                      </div>
                    )}
                  </div>
                </CollapsibleSection>
              );
            })()}

            {/* Classification Section */}
            <SectionHeader title="Classification" isDark={isDark} />
            <div className="px-4">
              <CompareRow
                label="Wallet Tag"
                values={charities.map(c => {
                  const walletType = getWalletType(c.amalEvaluation?.wallet_tag || '');
                  const isZakat = walletType === 'zakat';
                  return (
                    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium ${isZakat ? (isDark ? 'bg-emerald-900/30 text-emerald-400' : 'bg-emerald-100 text-emerald-700') : (isDark ? 'bg-slate-700 text-slate-300' : 'bg-slate-100 text-slate-600')}`}>
                      {isZakat && <Lock className="w-3 h-3" aria-hidden="true" />}
                      {formatWalletTag(c.amalEvaluation?.wallet_tag || '')}
                    </span>
                  );
                })}
                isDark={isDark}
                highlight
              />
              <CompareRow
                label="Impact Tier"
                values={charities.map(c => formatImpactTier(
                  c.amalEvaluation?.impact_tier ||
                  (c.amalEvaluation?.baseline_narrative as any)?.amal_scores?.impact_tier ||
                  c.amalEvaluation?.rich_narrative?.amal_scores?.impact_tier ||
                  c.impactTier
                ))}
                isDark={isDark}
              />
              <CompareRow
                label="Founded"
                values={charities.map(c => c.foundedYear)}
                isDark={isDark}
              />
            </div>

            {/* Financials Section */}
            <CollapsibleSection title="Financials" isDark={isDark} defaultOpen>
              <div className="px-4">
                <CompareRow
                  label="Revenue"
                  values={charities.map(c => formatShortRevenue(c.financials?.totalRevenue))}
                  isDark={isDark}
                />
                <CompareRow
                  label="Expenses"
                  values={charities.map(c => formatShortRevenue(c.financials?.totalExpenses))}
                  isDark={isDark}
                />
                <CompareRow
                  label="Program %"
                  values={charities.map(c => {
                    const ratio = c.financials?.programExpenseRatio;
                    if (!ratio) return null;
                    const num = typeof ratio === 'string' ? parseFloat(ratio) : ratio;
                    return formatPercent(num > 1 ? num / 100 : num);
                  })}
                  isDark={isDark}
                  highlight
                />
                <CompareRow
                  label="Assets"
                  values={charities.map(c => formatShortRevenue(c.financials?.totalAssets))}
                  isDark={isDark}
                />
                <CompareRow
                  label="Liabilities"
                  values={charities.map(c => formatShortRevenue(c.financials?.totalLiabilities))}
                  isDark={isDark}
                />
                <CompareRow
                  label="Net Assets"
                  values={charities.map(c => formatShortRevenue(c.financials?.netAssets))}
                  isDark={isDark}
                />
                <CompareRow
                  label="Working Capital"
                  values={charities.map(c => {
                    const months = c.financials?.workingCapitalMonths;
                    return months != null ? `${parseFloat(String(months)).toFixed(1)} mo` : null;
                  })}
                  isDark={isDark}
                />
                <CompareRow
                  label="Beneficiaries"
                  values={charities.map(c => {
                    const b = c.beneficiariesServedAnnually;
                    return b != null && b > 0 ? b.toLocaleString() : null;
                  })}
                  isDark={isDark}
                />
              </div>
            </CollapsibleSection>

            {/* Awards & Ratings */}
            <CollapsibleSection title="Awards & Ratings" isDark={isDark} defaultOpen>
              <div className="px-4">
                <CompareRow
                  label="CN Score"
                  values={charities.map(c => c.scores?.overall ? (
                    <span className="flex items-center gap-1">
                      <Award className="w-3 h-3 text-amber-500" aria-hidden="true" />
                      {Math.round(Number(c.scores.overall))}
                    </span>
                  ) : null)}
                  isDark={isDark}
                />
                <CompareRow
                  label="Candid Seal"
                  values={charities.map(c => c.awards?.candidSeal ? (
                    <span className={`text-xs font-medium ${c.awards.candidSeal === 'Platinum' ? 'text-slate-400' : 'text-amber-500'}`}>
                      {c.awards.candidSeal}
                    </span>
                  ) : null)}
                  isDark={isDark}
                />
                <CompareRow
                  label="BBB Status"
                  values={charities.map(c => c.awards?.bbbStatus)}
                  isDark={isDark}
                />
              </div>
            </CollapsibleSection>

            {/* Data Confidence Section - at bottom */}
            <CollapsibleSection title="Data Confidence" isDark={isDark} defaultOpen>
              <div className="px-4">
                <CompareRow
                  label="Data Quality"
                  values={charities.map(c => <ConfidenceIndicator level={getDataQuality(c)} isDark={isDark} />)}
                  isDark={isDark}
                />
                <CompareRow
                  label="Verification"
                  values={charities.map(c => <ConfidenceIndicator level={getVerificationTier(c)} isDark={isDark} />)}
                  isDark={isDark}
                />
                <CompareRow
                  label="Transparency"
                  values={charities.map(c => <ConfidenceIndicator level={getTransparency(c)} isDark={isDark} />)}
                  isDark={isDark}
                />
              </div>
            </CollapsibleSection>

            {/* Action Row */}
            <div className={`grid gap-3 p-4 border-t ${isDark ? 'border-slate-800 bg-slate-800/50' : 'border-slate-100 bg-slate-50'}`}
              style={{ gridTemplateColumns: `120px repeat(${numCharities}, minmax(0, 1fr))` }}
            >
              <div />
              {charities.map(charity => (
                <div key={charity.ein}>
                  <Link
                    to={`/charity/${charity.ein}`}
                    className="inline-flex items-center gap-1 px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-medium hover:bg-emerald-700 transition-colors"
                  >
                    Full Evaluation
                  </Link>
                </div>
              ))}
            </div>
            </div>{/* end min-width compare content */}
            </div>{/* end overflow-x-auto */}
          </div>
        )}
      </div>
    </div>
  );
}

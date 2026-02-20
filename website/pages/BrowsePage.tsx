import React, { useState, useMemo, useEffect } from 'react';
import { m } from 'motion/react';
import { CharityProfile } from '../types';
import { CharityCard } from '../src/components/CharityCard';
import { isPubliclyVisible } from '../src/utils/tierUtils';
import { THEMES } from '../src/themes';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { Search, X, LayoutGrid, ChevronDown, ChevronUp, SlidersHorizontal, Heart, BookOpen, Zap, Compass, ArrowRight } from 'lucide-react';
import { useCharities } from '../src/hooks/useCharities';
import { trackSearch, trackFilterApply, trackViewToggle } from '../src/utils/analytics';
import { useAuth } from '../src/auth/useAuth';
import { SignInButton } from '../src/auth/SignInButton';
import { useSearchParams } from 'react-router-dom';
import { deriveUISignalsFromCharity, getEvidenceStageRank } from '../src/utils/scoreUtils';
import { FeedbackButton } from '../src/components/FeedbackButton';

// Theme indices: soft-noor (light) = 4, warm-atmosphere (dark) = 2
const LIGHT_THEME_INDEX = 4;
const DARK_THEME_INDEX = 2;

// Preset filters - organized by impact theory: HOW (featured), then What/Who/Where
interface PresetFilter {
  id: string;
  label: string;
  tags?: string[];           // OR match on causeTags
  programFocusTags?: string[]; // OR match on programFocusTags (what they actually DO)
  minScore?: number;         // Override default SCORE_THRESHOLD_UNDER_REVIEW
  minEfficiency?: number;    // Min program expense ratio
  walletTag?: string;        // Match wallet tag
  zakatEligible?: boolean;   // Match charities with zakat classification
  established?: boolean;     // 25+ years of operation
  strongEvidence?: boolean;  // Evidence pillar score >= 24
  recommendationCues?: string[]; // Match qualitative recommendation cues
  evidenceStages?: string[]; // Match evidence stages
  group: 'how' | 'what' | 'who' | 'where' | 'focus' | 'quality';
  description?: string;      // Educational text shown in context banner
  insight?: string;          // Short insight for the "how" filters
}

const PRESET_FILTERS: PresetFilter[] = [
  // 🎯 HOW do they create change? (The key question - Layer 3)
  { id: 'systemic', label: 'Systemic Change', tags: ['systemic-change'], group: 'how',
    description: 'Working on policy, research, and institutional change. A single policy win can protect millions.',
    insight: 'One policy change can help more people than a lifetime of direct aid' },
  { id: 'root-causes', label: 'Long-Term Development', tags: ['long-term-development'], group: 'how',
    description: 'Building infrastructure, institutions, and capacity that outlast the program. Reducing future need for aid.',
    insight: 'Investing in systems that make charity unnecessary' },
  { id: 'education', label: 'Education & Skills', tags: ['educational'], group: 'how',
    description: 'Building human capital through education and training. Creating pathways out of poverty.',
    insight: 'Every educated child can lift a family out of poverty' },
  { id: 'direct-relief', label: 'Direct Relief', tags: ['emergency-response'], group: 'how',
    description: 'Immediate assistance to people in crisis. Food, medicine, shelter, and emergency aid.',
    insight: 'Critical when lives are on the line right now' },

  // 👥 WHO do they serve?
  { id: 'refugees', label: 'Refugees', tags: ['refugees'], group: 'who' },
  { id: 'orphans', label: 'Orphans', tags: ['orphans'], group: 'who' },
  { id: 'women', label: 'Women & Girls', tags: ['women'], group: 'who' },
  { id: 'youth', label: 'Youth', tags: ['youth'], group: 'who' },
  { id: 'converts', label: 'New Muslims', tags: ['muallaf', 'converts'], group: 'who' },
  { id: 'medical', label: 'Medical/Health', tags: ['medical'], group: 'who' },

  // 🌍 WHERE do they work?
  { id: 'palestine', label: 'Palestine', tags: ['palestine'], group: 'where' },
  { id: 'syria', label: 'Syria', tags: ['syria'], group: 'where' },
  { id: 'yemen', label: 'Yemen', tags: ['yemen'], group: 'where' },
  { id: 'afghanistan', label: 'Afghanistan', tags: ['afghanistan'], group: 'where' },
  { id: 'east-africa', label: 'East Africa', tags: ['somalia', 'sudan', 'ethiopia'], group: 'where' },
  { id: 'sudan', label: 'Sudan', tags: ['sudan'], group: 'where' },
  { id: 'pakistan', label: 'Pakistan', tags: ['pakistan'], group: 'where' },
  { id: 'bangladesh', label: 'Bangladesh', tags: ['bangladesh'], group: 'where' },
  { id: 'india', label: 'India', tags: ['india'], group: 'where' },
  { id: 'usa', label: 'USA', tags: ['usa'], group: 'where' },

  // ⭐ Quality Filters
  { id: 'strong-match', label: 'Maximum Alignment', recommendationCues: ['Strong Match'], group: 'quality',
    description: 'Profiles with strong mission match, lower observed risk, and higher evidence confidence.' },
  { id: 'zakat', label: 'Zakat Eligible', zakatEligible: true, group: 'quality',
    description: 'Verified to serve zakat-eligible beneficiaries (fuqara, masakin, refugees) with proper fund segregation.' },
  { id: 'cost-effective', label: '85%+ to Programs', minEfficiency: 0.85, group: 'quality',
    description: 'Charities spending 85%+ of funds on programs. More of your donation reaches beneficiaries directly.' },
  { id: 'established', label: 'Established (25+ yrs)', established: true, group: 'quality',
    description: 'Organizations with 25+ years of operation demonstrating long-term sustainability and track record.' },
  { id: 'grantmakers', label: 'Grantmakers', tags: ['grantmaking'], group: 'quality',
    description: 'Organizations that fund other charities rather than running programs directly.' },
  { id: 'emergency', label: 'Emergency Response', tags: ['emergency-response'], group: 'quality',
    description: 'Organizations active in disaster relief and emergency humanitarian response.' },
  { id: 'strong-evidence', label: 'Strong Evidence', strongEvidence: true, group: 'quality',
    description: 'Top-tier evidence of impact through rigorous outcome tracking and third-party evaluation.' },

  // 🎨 FOCUS - What do they actually DO? (Program focus tags)
  { id: 'focus-arts', label: 'Arts & Media', programFocusTags: ['arts-culture-media'], group: 'focus',
    description: 'Arts, storytelling, cultural representation, film, and media production.' },
  { id: 'focus-advocacy', label: 'Advocacy & Legal', programFocusTags: ['advocacy-legal'], group: 'focus',
    description: 'Civil rights, legal aid, policy advocacy, and litigation.' },
  { id: 'focus-humanitarian', label: 'Humanitarian', programFocusTags: ['humanitarian-relief'], group: 'focus',
    description: 'Emergency relief, food aid, and disaster response.' },
  { id: 'focus-water', label: 'Water & Sanitation', programFocusTags: ['water-sanitation'], group: 'focus',
    description: 'Clean water, infrastructure, and sanitation projects.' },
  { id: 'focus-education-k12', label: 'K-12 Education', programFocusTags: ['education-k12'], group: 'focus',
    description: 'Schools, youth education, and K-12 programs.' },
  { id: 'focus-education-higher', label: 'Higher Education', programFocusTags: ['education-higher'], group: 'focus',
    description: 'Universities, scholarships, and fellowship programs.' },
  { id: 'focus-healthcare', label: 'Healthcare', programFocusTags: ['healthcare-direct'], group: 'focus',
    description: 'Clinics, medical services, and health programs.' },
  { id: 'focus-economic', label: 'Economic Empowerment', programFocusTags: ['economic-empowerment'], group: 'focus',
    description: 'Job training, microfinance, and livelihood programs.' },
  { id: 'focus-community', label: 'Community Services', programFocusTags: ['community-services'], group: 'focus',
    description: 'Family services, social support, and local community programs.' },
  { id: 'focus-research', label: 'Research & Policy', programFocusTags: ['research-policy'], group: 'focus',
    description: 'Think tanks, research, and policy development.' },
  { id: 'focus-orphan', label: 'Orphan Care', programFocusTags: ['orphan-care'], group: 'focus',
    description: 'Orphan sponsorship, child welfare, and vulnerable children.' },
  { id: 'focus-refugee', label: 'Refugee Services', programFocusTags: ['refugee-services'], group: 'focus',
    description: 'Refugee support, resettlement, and displaced persons.' },
];

// Group labels
const GROUP_LABELS: Record<string, string> = {
  how: 'How do they create change?',
  focus: 'What do they do?',
  who: 'Who do they serve?',
  where: 'Where?',
  quality: 'More filters',
};

// Guided entry paths - intent-based navigation for first-time visitors
interface GuidedPath {
  id: string;
  label: string;
  description: string;
  icon: 'heart' | 'book' | 'zap' | 'compass';
  presets?: string[];           // Preset IDs to activate
  showCauseFilters?: boolean;   // For "What do they do?" path
  targetMode: 'simple' | 'power';  // Which view mode to enter
}

const GUIDED_PATHS: GuidedPath[] = [
  {
    id: 'zakat',
    label: 'Pay My Zakat',
    description: 'Verified zakat-eligible charities',
    icon: 'heart',
    presets: ['zakat'],
    targetMode: 'simple',
  },
  {
    id: 'cause',
    label: 'What do they do?',
    description: 'Program areas and interventions',
    icon: 'book',
    showCauseFilters: true,
    targetMode: 'simple',
  },
  {
    id: 'impact',
    label: 'Maximum Leverage',
    description: 'Mission-aligned charities with stronger signals',
    icon: 'zap',
    presets: ['strong-match'],
    targetMode: 'simple',
  },
  {
    id: 'browse',
    label: 'Browse All',
    description: 'See all evaluated charities',
    icon: 'compass',
    targetMode: 'power',
  },
];

interface DonorIntent {
  id: string;
  label: string;
  description: string;
  presets: string[];
}

const DONOR_INTENTS: DonorIntent[] = [
  {
    id: 'immediate-relief',
    label: 'Immediate Relief',
    description: 'Urgent aid for people in crisis right now.',
    presets: ['direct-relief', 'focus-humanitarian', 'emergency'],
  },
  {
    id: 'long-term-uplift',
    label: 'Long-Term Uplift',
    description: 'Education and development that reduce future dependency.',
    presets: ['root-causes', 'education', 'focus-education-k12', 'focus-education-higher', 'focus-economic'],
  },
  {
    id: 'maximum-leverage',
    label: 'Maximum Leverage',
    description: 'Policy, research, and scalable models that compound impact.',
    presets: ['systemic', 'focus-research', 'focus-advocacy', 'strong-evidence'],
  },
  {
    id: 'community-institutions',
    label: 'Community Institutions',
    description: 'Durable local infrastructure and ecosystem builders.',
    presets: ['focus-community', 'grantmakers', 'established'],
  },
];

// localStorage key for persisting browse preference
const BROWSE_STYLE_KEY = 'gmg-browse-style';

// Get AMAL score for a charity
const getScore = (charity: CharityProfile): number => {
  return charity.amalEvaluation?.amal_score || 0;
};

const getRecommendationRank = (cue: string | null | undefined): number => {
  if (cue === 'Strong Match') return 4;
  if (cue === 'Good Match') return 3;
  if (cue === 'Mixed Signals') return 2;
  if (cue === 'Limited Match') return 1;
  return 0;
};

export const BrowsePage: React.FC = () => {
  const { isDark } = useLandingTheme();
  const theme = THEMES[isDark ? DARK_THEME_INDEX : LIGHT_THEME_INDEX];
  const { isSignedIn } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  // Load charities from exported JSON
  const { charities: allCharities, loading, error } = useCharities();

  // Search and filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [activePresets, setActivePresets] = useState<Set<string>>(() => {
    const presetsParam = searchParams.get('presets');
    if (presetsParam) {
      const ids = presetsParam.split(',').filter(id => PRESET_FILTERS.some(p => p.id === id));
      return new Set(ids);
    }
    return new Set();
  });
  const [viewMode, setViewMode] = useState<'browse' | 'search'>('browse');
  const [selectedIntentId, setSelectedIntentId] = useState<string | null>(() => {
    const intentParam = searchParams.get('intent');
    return DONOR_INTENTS.some(i => i.id === intentParam) ? intentParam : null;
  });
  // Browse style: 'guided' (entry), 'simple' (results with minimal UI), 'power' (full filters)
  const [browseStyle, setBrowseStyle] = useState<'guided' | 'simple' | 'power'>(() => {
    const modeParam = searchParams.get('mode');
    if (modeParam === 'power' || modeParam === 'simple') return modeParam;
    // If presets are in URL, start in power mode
    if (searchParams.get('presets')) return 'power';
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(BROWSE_STYLE_KEY);
      if (saved === 'power') return 'power';
    }
    return 'guided';
  });
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const [showCauseFilters, setShowCauseFilters] = useState(false);
  const [selectedPathId, setSelectedPathId] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'score' | 'relevance' | 'name' | 'revenue' | 'program' | 'evidence'>('score');
  const [showSuggestCharity, setShowSuggestCharity] = useState(false);

  // Set page title
  useEffect(() => {
    document.title = 'Browse Charities | Good Measure Giving';
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  // Sync filter state to URL params
  useEffect(() => {
    const params = new URLSearchParams();
    if (activePresets.size > 0) {
      params.set('presets', Array.from(activePresets).join(','));
    }
    if (browseStyle !== 'guided') {
      params.set('mode', browseStyle);
    }
    if (selectedIntentId) {
      params.set('intent', selectedIntentId);
    }
    const newSearch = params.toString();
    const currentSearch = searchParams.toString();
    if (newSearch !== currentSearch) {
      setSearchParams(params, { replace: true });
    }
  }, [activePresets, browseStyle, selectedIntentId, setSearchParams]);

  // Get public charities (rich + baseline tiers, excludes hidden)
  const publicCharities = useMemo(() =>
    allCharities.filter(isPubliclyVisible),
    [allCharities]
  );

  const evaluatedCharities = useMemo(() =>
    publicCharities.filter(
      c => c.amalEvaluation?.wallet_tag && c.amalEvaluation.wallet_tag !== 'INSUFFICIENT-DATA'
    ),
    [publicCharities]
  );

  // Count of default browseable set (excludes hidden/curated-hidden)
  const defaultViewCount = useMemo(() =>
    evaluatedCharities.filter(c => !c.hideFromCurated).length,
    [evaluatedCharities]
  );

  // Current year for established calculation
  const currentYear = new Date().getFullYear();

  const getConfidenceBadge = (charity: CharityProfile): 'HIGH' | 'MEDIUM' | 'LOW' => {
    const raw = ((charity.amalEvaluation?.score_details as any)?.data_confidence?.badge
      || charity.amalEvaluation?.confidence_tier
      || 'LOW') as string;
    const normalized = raw.toUpperCase();
    if (normalized === 'HIGH') return 'HIGH';
    if (normalized === 'MEDIUM' || normalized === 'MODERATE') return 'MEDIUM';
    return 'LOW';
  };

  const matchesPreset = (
    charity: CharityProfile & {
      causeTags?: string[] | null;
      programFocusTags?: string[] | null;
      zakatClassification?: string | null;
      foundedYear?: number | null;
    },
    preset: PresetFilter
  ): boolean => {
    const uiSignals = charity.ui_signals_v1 || deriveUISignalsFromCharity(charity);
    const score = getScore(charity);

    if ((preset.minScore ?? 0) > 0 && score < (preset.minScore ?? 0)) return false;
    if (preset.minEfficiency && (charity.financials?.programExpenseRatio || 0) < preset.minEfficiency) return false;
    if (preset.walletTag && charity.amalEvaluation?.wallet_tag !== preset.walletTag) return false;
    if (preset.zakatEligible && !(charity.zakatClassification || charity.amalEvaluation?.wallet_tag === 'ZAKAT-ELIGIBLE')) return false;
    if (preset.established) {
      const yearsOperating = charity.foundedYear ? currentYear - charity.foundedYear : 0;
      if (yearsOperating < 25) return false;
    }
    if (preset.strongEvidence) {
      const evidenceScore = charity.amalEvaluation?.confidence_scores?.evidence || 0;
      if (evidenceScore < 24) return false;
    }
    if (preset.recommendationCues?.length && !preset.recommendationCues.includes(uiSignals.recommendation_cue)) return false;
    if (preset.evidenceStages?.length && !preset.evidenceStages.includes(uiSignals.evidence_stage)) return false;
    if (preset.tags?.length) {
      const charityTags = charity.causeTags || [];
      if (!preset.tags.some(tag => charityTags.includes(tag))) return false;
    }
    if (preset.programFocusTags?.length) {
      const charityFocusTags = charity.programFocusTags || [];
      if (!preset.programFocusTags.some(tag => charityFocusTags.includes(tag))) return false;
    }
    return true;
  };

  // Apply filtering logic:
  // - Default view: all browseable evaluated charities
  // - Search: finds ALL charities
  // - Stacked presets: AND all active filters together
  const filteredCharities = useMemo(() => {
    const extendedCharities = evaluatedCharities as (CharityProfile & {
      causeTags?: string[] | null;
      programFocusTags?: string[] | null;
      primaryCategory?: string | null;
      zakatClassification?: string | null;
      foundedYear?: number | null;
      amalEvaluation?: CharityProfile['amalEvaluation'] & {
        confidence_scores?: { evidence?: number };
      };
    })[];

    // If searching, search ALL charities (no score filter)
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      return extendedCharities.filter(c =>
        c.name.toLowerCase().includes(query) ||
        c.rawData?.mission?.toLowerCase().includes(query) ||
        c.ein?.includes(query)
      );
    }

    // Get all active presets
    const presets = Array.from(activePresets).map(id => PRESET_FILTERS.find(p => p.id === id)).filter(Boolean) as PresetFilter[];

    // Determine minimum score (only when preset explicitly requires it)
    const minScore = presets.length > 0
      ? Math.max(0, ...presets.map(p => p.minScore ?? 0))
      : 0;

    // Start with baseline set
    let results = extendedCharities.filter(c => getScore(c) >= minScore);

    // Always hide charities marked hideFromCurated - only searchable, never browsable
    results = results.filter(c => !c.hideFromCurated);

    // Apply each preset's filters (AND logic - charity must match ALL active presets)
    for (const preset of presets) {
      results = results.filter(c => matchesPreset(c, preset));
    }

    return results;
  }, [evaluatedCharities, searchQuery, activePresets, currentYear]);

  const getRelevanceScore = (charity: CharityProfile): number => {
    const uiSignals = charity.ui_signals_v1 || deriveUISignalsFromCharity(charity);
    const confidence = getConfidenceBadge(charity);

    const selectedIntent = selectedIntentId ? DONOR_INTENTS.find(i => i.id === selectedIntentId) : null;
    // Relevance is only meaningful after path or donor intent is selected.
    if (!selectedPathId && !selectedIntent) return 0;

    let intentScore = 0;
    if (selectedPathId === 'zakat') {
      intentScore = charity.amalEvaluation?.wallet_tag === 'ZAKAT-ELIGIBLE' ? 70 : 0;
    } else if (selectedPathId === 'cause') {
      const causeMatches = Array.from(activePresets)
        .map(id => PRESET_FILTERS.find(p => p.id === id))
        .filter((p): p is PresetFilter => !!p && (p.group === 'focus' || p.group === 'how'))
        .filter(p => matchesPreset(charity as any, p)).length;
      intentScore = causeMatches > 0 ? Math.min(70, 50 + (causeMatches - 1) * 20) : 0;
    } else if (selectedPathId === 'impact') {
      intentScore = 0
        + (uiSignals.recommendation_cue === 'Strong Match' ? 40 : 0)
        + ((uiSignals.evidence_stage === 'Verified' || uiSignals.evidence_stage === 'Established') ? 20 : 0)
        + (uiSignals.signal_states.risk === 'Strong' ? 10 : 0);
    }

    if (selectedIntent) {
      const intentPresetMatches = selectedIntent.presets
        .map(id => PRESET_FILTERS.find(p => p.id === id))
        .filter((p): p is PresetFilter => !!p)
        .filter(p => matchesPreset(charity as any, p)).length;
      if (intentPresetMatches > 0) {
        intentScore += Math.min(35, 20 + (intentPresetMatches - 1) * 7);
      }
    }

    const filterMatches = Array.from(activePresets)
      .map(id => PRESET_FILTERS.find(p => p.id === id))
      .filter((p): p is PresetFilter => !!p)
      .filter(p => matchesPreset(charity as any, p)).length;
    const filterScore = Math.min(20, filterMatches * 5);
    const confidenceBonus = confidence === 'HIGH' ? 8 : confidence === 'MEDIUM' ? 4 : 0;
    const cueBonus = uiSignals.recommendation_cue === 'Strong Match' ? 2 : uiSignals.recommendation_cue === 'Good Match' ? 1 : 0;

    return intentScore + filterScore + confidenceBonus + cueBonus;
  };

  // Sort charities by selected sort option
  const sortedCharities = useMemo(() => {
    const sorted = [...filteredCharities];
    switch (sortBy) {
      case 'score':
        sorted.sort((a, b) => {
          const scoreDiff = getScore(b) - getScore(a);
          if (scoreDiff !== 0) return scoreDiff;
          const aUi = a.ui_signals_v1 || deriveUISignalsFromCharity(a);
          const bUi = b.ui_signals_v1 || deriveUISignalsFromCharity(b);
          const aRank = getEvidenceStageRank(aUi.evidence_stage);
          const bRank = getEvidenceStageRank(bUi.evidence_stage);
          if (bRank !== aRank) return bRank - aRank;
          return a.name.localeCompare(b.name);
        });
        break;
      case 'relevance':
        sorted.sort((a, b) => {
          const aRel = getRelevanceScore(a);
          const bRel = getRelevanceScore(b);
          if (bRel !== aRel) return bRel - aRel;
          const scoreDiff = getScore(b) - getScore(a);
          if (scoreDiff !== 0) return scoreDiff;
          const byName = a.name.localeCompare(b.name);
          if (byName !== 0) return byName;
          return (a.ein || '').localeCompare(b.ein || '');
        });
        break;
      case 'name':
        sorted.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case 'revenue':
        sorted.sort((a, b) => (b.financials?.totalRevenue || 0) - (a.financials?.totalRevenue || 0));
        break;
      case 'program':
        sorted.sort((a, b) => (b.financials?.programExpenseRatio || 0) - (a.financials?.programExpenseRatio || 0));
        break;
      case 'evidence':
      default:
        sorted.sort((a, b) => {
          const aUi = a.ui_signals_v1 || deriveUISignalsFromCharity(a);
          const bUi = b.ui_signals_v1 || deriveUISignalsFromCharity(b);
          const aRank = getEvidenceStageRank(aUi.evidence_stage);
          const bRank = getEvidenceStageRank(bUi.evidence_stage);
          if (bRank !== aRank) return bRank - aRank;
          const aCue = getRecommendationRank(aUi.recommendation_cue);
          const bCue = getRecommendationRank(bUi.recommendation_cue);
          if (bCue !== aCue) return bCue - aCue;
          return a.name.localeCompare(b.name);
        });
        break;
    }
    return sorted;
  }, [filteredCharities, sortBy, selectedPathId, activePresets, selectedIntentId]);

  // Track search queries (debounced to avoid tracking every keystroke)
  useEffect(() => {
    if (!searchQuery.trim()) return;
    const timeoutId = setTimeout(() => {
      trackSearch(searchQuery, sortedCharities.length);
    }, 500);
    return () => clearTimeout(timeoutId);
  }, [searchQuery, sortedCharities.length]);

  // Count charities per preset (contextual - considers active filters)
  // Shows: "If I toggle this filter, how many results would I have?"
  const presetCounts = useMemo(() => {
    const counts = new Map<string, number>();
    const extendedCharities = evaluatedCharities as (CharityProfile & {
      causeTags?: string[] | null;
      programFocusTags?: string[] | null;
      zakatClassification?: string | null;
      foundedYear?: number | null;
      amalEvaluation?: CharityProfile['amalEvaluation'] & {
        confidence_scores?: { evidence?: number };
      };
    })[];

    // Helper to apply a single preset's filters to a set of charities
    const applyPresetFilter = (charities: typeof extendedCharities, preset: PresetFilter) => {
      return charities.filter(c => matchesPreset(c, preset));
    };

    // Base set: all browseable charities
    const baseCharities = extendedCharities.filter(c =>
      !c.hideFromCurated
    );

    // Get all active preset objects
    const activePresetObjects = Array.from(activePresets)
      .map(id => PRESET_FILTERS.find(p => p.id === id))
      .filter(Boolean) as PresetFilter[];

    for (const preset of PRESET_FILTERS) {
      // Build the set of presets that would be active if this one is toggled
      const isCurrentlyActive = activePresets.has(preset.id);
      const presetsToApply = isCurrentlyActive
        ? activePresetObjects.filter(p => p.id !== preset.id)  // Remove this one (simulating toggle off)
        : [...activePresetObjects, preset];  // Add this one (simulating toggle on)

      // Apply all presets in sequence
      let results = baseCharities;
      for (const p of presetsToApply) {
        results = applyPresetFilter(results, p);
      }

      counts.set(preset.id, results.length);
    }
    return counts;
  }, [evaluatedCharities, activePresets, currentYear]);

  // Group presets for UI
  const groupedPresets = useMemo(() => {
    const groups: Record<string, PresetFilter[]> = { how: [], focus: [], who: [], where: [], quality: [] };
    for (const preset of PRESET_FILTERS) {
      if (groups[preset.group]) {
        groups[preset.group].push(preset);
      }
    }
    return groups;
  }, []);

  // Toggle a preset filter (add/remove from set)
  const togglePreset = (presetId: string) => {
    const wasActive = activePresets.has(presetId);
    const preset = PRESET_FILTERS.find(p => p.id === presetId);
    setActivePresets(prev => {
      const next = new Set(prev);
      if (next.has(presetId)) {
        next.delete(presetId);
      } else {
        next.add(presetId);
      }
      return next;
    });
    setSearchQuery('');
    if (preset) {
      trackFilterApply(presetId, preset.group, presetCounts.get(presetId) || 0);
    }
  };

  // Clear filters
  const clearFilters = () => {
    setSearchQuery('');
    setActivePresets(new Set());
    setSelectedIntentId(null);
  };

  // Handle guided path selection
  const selectGuidedPath = (path: GuidedPath) => {
    trackViewToggle('', browseStyle, path.targetMode);
    if (path.presets && path.presets.length > 0) {
      setActivePresets(new Set(path.presets));
    } else {
      setActivePresets(new Set());
    }
    setSelectedIntentId(null);
    setShowCauseFilters(path.showCauseFilters || false);
    setSelectedPathId(path.id);
    setBrowseStyle(path.targetMode);
    setSortBy('score');

    // Persist power mode preference
    if (path.targetMode === 'power') {
      localStorage.setItem(BROWSE_STYLE_KEY, 'power');
    }
  };

  // Switch to power mode (full filters)
  const switchToPowerMode = () => {
    trackViewToggle('', browseStyle, 'power');
    setBrowseStyle('power');
    if (!selectedPathId) setSortBy('score');
    localStorage.setItem(BROWSE_STYLE_KEY, 'power');
  };

  // Return to guided view
  const returnToGuided = () => {
    trackViewToggle('', browseStyle, 'guided');
    setBrowseStyle('guided');
    setActivePresets(new Set());
    setSelectedIntentId(null);
    setShowCauseFilters(false);
    setSelectedPathId(null);
    setSortBy('score');
    // Clear power mode preference when explicitly returning to guided
    localStorage.removeItem(BROWSE_STYLE_KEY);
  };

  const hasActiveFilters = searchQuery || activePresets.size > 0 || selectedIntentId;

  if (loading) {
    return (
      <div className={`min-h-screen py-12 ${theme.bgPage}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="animate-pulse">
            <div className={`h-12 w-64 rounded-lg mb-4 ${isDark ? 'bg-slate-800' : 'bg-slate-200'}`} />
            <div className={`h-6 w-96 rounded mb-8 ${isDark ? 'bg-slate-800' : 'bg-slate-200'}`} />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3, 4, 5, 6].map(i => (
                <div key={i} className={`h-48 rounded-xl ${isDark ? 'bg-slate-800' : 'bg-slate-200'}`} />
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`min-h-screen py-12 ${theme.bgPage}`}>
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p className={`text-lg ${isDark ? 'text-red-400' : 'text-red-600'}`}>
            Failed to load charities: {error}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={`relative min-h-screen py-3 sm:py-6 ${theme.bgPage}`}>

      {/* Background Elements from Theme */}
      <div className="absolute inset-0 z-0 overflow-hidden">{theme.backgroundElements}</div>

      <div className="relative max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">

        {/* Header Section - hidden on mobile for density, shown on desktop */}
        <div className="hidden sm:flex mb-2 sm:mb-4 flex-wrap items-center justify-between gap-2">
          <h1 className={`text-xl sm:text-2xl md:text-3xl font-bold font-merriweather transition-colors [text-wrap:balance] ${theme.textMain}`}>
            Explore Muslim Charities
          </h1>
          <div className={`flex items-center gap-2 text-sm font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            {searchQuery ? (
              <span className={`px-3 py-1 rounded-full ${isDark ? 'bg-blue-900/30 text-blue-300' : 'bg-blue-100 text-blue-700'}`}>
                {sortedCharities.length} result{sortedCharities.length !== 1 ? 's' : ''} for "{searchQuery}"
              </span>
            ) : activePresets.size > 0 ? (
              <span className={`px-3 py-1 rounded-full ${isDark ? 'bg-emerald-900/30 text-emerald-300' : 'bg-emerald-100 text-emerald-700'}`}>
                {sortedCharities.length} matching
              </span>
            ) : (
              <span className={`px-3 py-1 rounded-full ${isDark ? 'bg-slate-800' : 'bg-slate-100'}`}>
                {defaultViewCount} charities evaluated
              </span>
            )}
          </div>
        </div>

        {/* Tab Toggle: Browse vs Search + Lens Toggle */}
        <div className="mb-2 sm:mb-4 flex flex-wrap items-center gap-3">
          <div className={`inline-flex p-1 rounded-xl ${isDark ? 'bg-slate-800' : 'bg-slate-100'}`}>
            <button
              onClick={() => { trackViewToggle('', viewMode, 'browse'); setViewMode('browse'); setSearchQuery(''); }}
              className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-5 py-2 sm:py-2.5 rounded-lg text-sm font-medium transition-all ${
                viewMode === 'browse'
                  ? isDark
                    ? 'bg-slate-700 text-white shadow-sm'
                    : 'bg-white text-slate-900 shadow-sm'
                  : isDark
                    ? 'text-slate-400 hover:text-white'
                    : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              <LayoutGrid className="w-4 h-4" aria-hidden="true" />
              Browse
            </button>
            <button
              onClick={() => { trackViewToggle('', viewMode, 'search'); setViewMode('search'); setActivePresets(new Set()); }}
              className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-5 py-2 sm:py-2.5 rounded-lg text-sm font-medium transition-all ${
                viewMode === 'search'
                  ? isDark
                    ? 'bg-slate-700 text-white shadow-sm'
                    : 'bg-white text-slate-900 shadow-sm'
                  : isDark
                    ? 'text-slate-400 hover:text-white'
                    : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              <Search className="w-4 h-4" aria-hidden="true" />
              Search
            </button>
          </div>
        </div>

        {/* Search Input (only shown in search mode) */}
        {viewMode === 'search' && (
          <div className="relative mb-6">
            <Search className={`absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} aria-hidden="true" />
            <input
              type="text"
              autoFocus
              aria-label="Search charities"
              placeholder={`Search ${evaluatedCharities.length} charities by name, mission, or EIN...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={`w-full pl-12 pr-12 py-4 rounded-2xl border-2 transition-all ${
                isDark
                  ? 'bg-slate-900 border-slate-800 text-white placeholder-slate-500 focus:border-emerald-500 focus:bg-slate-800'
                  : 'bg-white border-slate-100 text-slate-900 placeholder-slate-400 focus:border-emerald-500 shadow-sm'
              } focus:outline-none focus:ring-4 focus:ring-emerald-500/10`}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className={`absolute right-4 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
                  isDark
                    ? 'bg-slate-700 hover:bg-slate-600 text-slate-300'
                    : 'bg-slate-200 hover:bg-slate-300 text-slate-600'
                }`}
                aria-label="Clear search"
              >
                <X className="w-4 h-4" aria-hidden="true" />
              </button>
            )}
          </div>
        )}

        {/* Donor Intent Chips - statement-of-purpose matching */}
        {viewMode === 'browse' && browseStyle !== 'guided' && (
          <div className={`mb-4 rounded-xl p-3 sm:p-4 ${isDark ? 'bg-slate-900/70 border border-slate-800' : 'bg-white border border-slate-200'}`}>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <h3 className={`text-sm font-semibold ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>
                Match my purpose
              </h3>
              {selectedIntentId && (
                <button
                  onClick={() => { setSelectedIntentId(null); if (!selectedPathId) setSortBy('score'); }}
                  className={`text-xs underline underline-offset-2 ${isDark ? 'text-slate-400 hover:text-slate-200' : 'text-slate-500 hover:text-slate-700'}`}
                >
                  Clear purpose
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {DONOR_INTENTS.map((intent) => {
                const isActive = selectedIntentId === intent.id;
                return (
                  <button
                    key={intent.id}
                    onClick={() => {
                      setSelectedIntentId(prev => prev === intent.id ? null : intent.id);
                      setSortBy('relevance');
                    }}
                    title={intent.description}
                    className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-600/25'
                        : isDark
                          ? 'bg-slate-800 border border-slate-700 text-slate-300 hover:border-emerald-600/50'
                          : 'bg-slate-50 border border-slate-200 text-slate-700 hover:border-emerald-400'
                    }`}
                  >
                    {intent.label}
                  </button>
                );
              })}
            </div>
            {selectedIntentId && (
              <p className={`mt-2 text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                {DONOR_INTENTS.find(i => i.id === selectedIntentId)?.description}
              </p>
            )}
          </div>
        )}

        {/* Guided Entry - shown in browse mode when browseStyle is 'guided' */}
        {viewMode === 'browse' && browseStyle === 'guided' && (
          <div className="mb-6">
            <h2 className={`text-lg sm:text-xl font-semibold mb-4 ${isDark ? 'text-white' : 'text-slate-800'}`}>
              What brings you here?
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {GUIDED_PATHS.map((path) => {
                const IconComponent = {
                  heart: Heart,
                  book: BookOpen,
                  zap: Zap,
                  compass: Compass,
                }[path.icon];

                return (
                  <button
                    key={path.id}
                    onClick={() => selectGuidedPath(path)}
                    className={`group text-left p-4 sm:p-5 rounded-xl border transition-all duration-200 ${
                      isDark
                        ? 'bg-slate-800 border-l-4 border-l-emerald-500 border-t-slate-700 border-r-slate-700 border-b-slate-700 hover:bg-slate-750 hover:border-l-emerald-400'
                        : 'bg-white border-l-4 border-l-emerald-500 border-t-slate-200 border-r-slate-200 border-b-slate-200 shadow-sm hover:shadow-md hover:border-l-emerald-600'
                    }`}
                  >
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-3 transition-colors ${
                      isDark
                        ? 'bg-emerald-900/50 text-emerald-400 group-hover:bg-emerald-800'
                        : 'bg-emerald-50 text-emerald-600 group-hover:bg-emerald-100'
                    }`}>
                      <IconComponent className="w-5 h-5" aria-hidden="true" />
                    </div>
                    <h3 className={`font-semibold text-sm sm:text-base mb-1 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                      {path.label}
                    </h3>
                    <p className={`text-xs sm:text-sm ${isDark ? 'text-slate-300' : 'text-slate-500'}`}>
                      {path.description}
                    </p>
                  </button>
                );
              })}
            </div>
            <button
              onClick={switchToPowerMode}
              className={`mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                isDark
                  ? 'border-slate-700 text-slate-300 hover:border-emerald-600/50 hover:text-emerald-400'
                  : 'border-slate-300 text-slate-600 hover:border-emerald-500 hover:text-emerald-600'
              }`}
            >
              <SlidersHorizontal className="w-4 h-4" aria-hidden="true" />
              Explore All Filters
            </button>
          </div>
        )}

        {/* Simple View - shown after selecting Zakat/Cause/Impact paths */}
        {viewMode === 'browse' && browseStyle === 'simple' && (
          <div className="mb-4">
            {/* Back to guided + current selection indicator */}
            <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
              <button
                onClick={returnToGuided}
                className={`inline-flex items-center gap-1.5 text-sm font-medium transition-colors ${
                  isDark ? 'text-slate-400 hover:text-emerald-400' : 'text-slate-500 hover:text-emerald-600'
                }`}
              >
                <ArrowRight className="w-4 h-4 rotate-180" />
                Back
              </button>
              <button
                onClick={switchToPowerMode}
                className={`inline-flex items-center gap-1.5 text-sm font-medium transition-colors ${
                  isDark ? 'text-slate-400 hover:text-emerald-400' : 'text-slate-500 hover:text-emerald-600'
                }`}
              >
                More filters
                <SlidersHorizontal className="w-4 h-4" aria-hidden="true" />
              </button>
            </div>

            {/* Cause filter chips - only shown for "What do they do?" path */}
            {showCauseFilters && (
              <div className={`rounded-xl p-3 sm:p-4 ${isDark ? 'bg-gradient-to-br from-emerald-900/30 to-slate-900 border border-emerald-800/30' : 'bg-gradient-to-br from-emerald-50 to-white border border-emerald-200'}`}>
                <h3 className={`text-sm font-bold mb-3 ${isDark ? 'text-emerald-400' : 'text-emerald-800'}`}>
                  What do they do?
                </h3>
                <div className="flex flex-wrap gap-2">
                  {groupedPresets['focus'].map((preset) => {
                    const isActive = activePresets.has(preset.id);
                    return (
                      <button
                        key={preset.id}
                        onClick={() => togglePreset(preset.id)}
                        className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                          isActive
                            ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-600/25'
                            : isDark
                              ? 'bg-slate-800 border border-slate-700 text-slate-300 hover:border-emerald-600/50'
                              : 'bg-white border border-slate-200 text-slate-700 hover:border-emerald-400'
                        }`}
                      >
                        {preset.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Active filter indicator + quick access to donor-signal filters for non-cause paths */}
            {!showCauseFilters && (
              <div className="flex flex-wrap items-center gap-2">
                {activePresets.size > 0 && (
                  <>
                    <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Showing:</span>
                    {Array.from(activePresets).map(presetId => {
                      const preset = PRESET_FILTERS.find(p => p.id === presetId);
                      return preset ? (
                        <button
                          key={presetId}
                          type="button"
                          onClick={() => togglePreset(presetId)}
                          title={`Remove ${preset.label}`}
                          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium ${
                            isDark
                              ? 'bg-emerald-900/50 text-emerald-300 border border-emerald-800/50 hover:bg-emerald-900/70'
                              : 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100'
                          }`}
                        >
                          {preset.label}
                          <X className="w-3 h-3" aria-hidden="true" />
                        </button>
                      ) : null;
                    })}
                  </>
                )}
                <button
                  type="button"
                  onClick={switchToPowerMode}
                  title="Open donor-signal filters"
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                    isDark
                      ? 'bg-slate-800 text-slate-300 border border-slate-700 hover:border-emerald-700/60 hover:text-emerald-300'
                      : 'bg-slate-100 text-slate-600 border border-slate-200 hover:border-emerald-400 hover:text-emerald-700'
                  }`}
                >
                  Donor Signals
                  <SlidersHorizontal className="w-3.5 h-3.5" aria-hidden="true" />
                </button>
              </div>
            )}
          </div>
        )}

        {/* Power Mode (Full Filters) - only shown in browse mode with power style */}
        {viewMode === 'browse' && browseStyle === 'power' && (
        <nav className="mb-2 sm:mb-4">
          {/* Back to guided view link */}
          <button
            onClick={returnToGuided}
            className={`mb-3 inline-flex items-center gap-1.5 text-sm font-medium transition-colors ${
              isDark ? 'text-slate-400 hover:text-emerald-400' : 'text-slate-500 hover:text-emerald-600'
            }`}
          >
            <ArrowRight className="w-4 h-4 rotate-180" />
            Back to guided view
          </button>

          {/* Cause filter bar - shown when coming from "What do they do?" path */}
          {showCauseFilters && (
            <div className={`rounded-xl p-3 sm:p-4 mb-2 sm:mb-3 ${isDark ? 'bg-gradient-to-br from-emerald-900/30 to-slate-900 border border-emerald-800/30' : 'bg-gradient-to-br from-emerald-50 to-white border border-emerald-200'}`}>
              <h3 className={`text-sm font-bold mb-2 sm:mb-3 ${isDark ? 'text-emerald-400' : 'text-emerald-800'}`}>
                What do they do?
              </h3>
              <div className="flex flex-wrap gap-2">
                {groupedPresets['focus'].map((preset) => {
                  const isActive = activePresets.has(preset.id);
                  return (
                    <button
                      key={preset.id}
                      onClick={() => togglePreset(preset.id)}
                      className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                        isActive
                          ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-600/25'
                          : isDark
                            ? 'bg-slate-800 border border-slate-700 text-slate-300 hover:border-emerald-600/50'
                            : 'bg-white border border-slate-200 text-slate-700 hover:border-emerald-400'
                      }`}
                    >
                      <span>{preset.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Featured Section: HOW do they create change? - hidden when cause filters shown */}
          {!showCauseFilters && (
          <div className={`rounded-xl p-3 sm:p-4 mb-2 sm:mb-3 ${isDark ? 'bg-gradient-to-br from-emerald-900/30 to-slate-900 border border-emerald-800/30' : 'bg-gradient-to-br from-emerald-50 to-white border border-emerald-200'}`}>
            <h3 className={`text-sm font-bold mb-2 sm:mb-3 ${isDark ? 'text-emerald-400' : 'text-emerald-800'}`}>
              How do they create change?
            </h3>
            {/* Mobile: Horizontal scroll chips */}
            <div className="flex sm:hidden overflow-x-auto scrollbar-hide gap-2 -mx-3 px-3 pb-1">
              {groupedPresets['how'].map((preset) => {
                const count = presetCounts.get(preset.id) || 0;
                const isActive = activePresets.has(preset.id);
                return (
                  <button
                    key={preset.id}
                    onClick={() => togglePreset(preset.id)}
                    className={`flex-shrink-0 inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-emerald-600 text-white'
                        : isDark
                          ? 'bg-slate-800 border border-slate-700 text-slate-300'
                          : 'bg-white border border-slate-200 text-slate-700'
                    }`}
                  >
                    <span>{preset.label}</span>
                    {/* Count only shown on inactive filters - active filters don't need count */}
                  </button>
                );
              })}
            </div>
            {/* Desktop: Rich card grid */}
            <div className="hidden sm:grid grid-cols-2 md:grid-cols-4 gap-3">
              {groupedPresets['how'].map((preset) => {
                const count = presetCounts.get(preset.id) || 0;
                const isActive = activePresets.has(preset.id);
                return (
                  <button
                    key={preset.id}
                    onClick={() => togglePreset(preset.id)}
                    className={`group text-left p-4 rounded-xl border-2 transition-all duration-200 ${
                      isActive
                        ? 'bg-emerald-600 border-emerald-600 text-white shadow-lg shadow-emerald-600/25'
                        : isDark
                          ? 'bg-slate-800/50 border-slate-700 hover:border-emerald-600/50 hover:bg-slate-800'
                          : 'bg-white border-slate-200 hover:border-emerald-400 shadow-sm hover:shadow'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className={`font-bold ${isActive ? 'text-white' : isDark ? 'text-white' : 'text-slate-900'}`}>
                        {preset.label}
                      </span>
                      {/* Count only shown on inactive filters (on hover) - active filters don't need count */}
                      {!isActive && (
                        <span className={`text-xs tabular-nums px-2 py-0.5 rounded-full ${isDark ? 'bg-slate-700 text-slate-400' : 'bg-slate-100 text-slate-500'}`}>
                          {count}
                        </span>
                      )}
                    </div>
                    {preset.insight && (
                      <p className={`text-xs leading-relaxed ${
                        isActive ? 'text-emerald-100' : isDark ? 'text-slate-500' : 'text-slate-500'
                      }`}>
                        {preset.insight}
                      </p>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
          )}

          {/* Secondary Filters: Focus, Who, Where, Quality - always shown in power mode */}
          <div className={`rounded-lg sm:rounded-xl p-3 sm:p-4 ${isDark ? 'bg-slate-900/80' : 'bg-slate-50 border border-slate-100'}`}>
            <div className="space-y-3">
              {(['focus', 'who', 'where', 'quality'] as const).map((groupKey, groupIndex) => (
                <div key={groupKey}>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                    <span className={`text-xs font-medium uppercase tracking-wider w-32 flex-shrink-0 ${
                      isDark ? 'text-slate-500' : 'text-slate-400'
                    }`}>
                      {GROUP_LABELS[groupKey]}
                    </span>
                    <div className="flex flex-wrap items-center gap-1.5">
                      {groupedPresets[groupKey].map((preset) => {
                        const count = presetCounts.get(preset.id) || 0;
                        const isActive = activePresets.has(preset.id);
                        return (
                          <button
                            key={preset.id}
                            onClick={() => togglePreset(preset.id)}
                            className={`group/chip inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all duration-200 ${
                              isActive
                                ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-600/25'
                                : isDark
                                  ? 'bg-slate-800/50 hover:bg-slate-800 text-slate-300 hover:text-white'
                                  : 'bg-white hover:bg-slate-50 border text-slate-600 border-slate-200 hover:border-slate-300 shadow-sm hover:shadow'
                            }`}
                          >
                            <span>{preset.label}</span>
                            {/* Count only shown on inactive filters (on hover) */}
                            {!isActive && (
                              <span className={`text-[11px] tabular-nums ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                                {count}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  {groupIndex < 3 && (
                    <div className={`mt-3 border-b ${isDark ? 'border-slate-800' : 'border-slate-200/50'}`} />
                  )}
                </div>
              ))}
            </div>
          </div>

          {hasActiveFilters && (
            <div className={`mt-3 sm:mt-5 pt-2 sm:pt-4 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
              <button
                onClick={clearFilters}
                className={`inline-flex items-center gap-2 text-sm font-medium transition-colors ${
                  isDark ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                <span className="w-5 h-5 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-xs">✕</span>
                Clear filter
              </button>
            </div>
          )}
        </nav>
        )}

        {/* Sort + Results Summary */}
        {sortedCharities.length > 0 && (
          <div className={`flex items-center justify-between mb-3 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            <div className="flex items-center gap-2">
              <span className="text-sm">
                {sortedCharities.length} {sortedCharities.length === 1 ? 'charity' : 'charities'}
              </span>
              {selectedIntentId && (
                <span className={`text-[11px] px-2 py-0.5 rounded-full ${
                  isDark ? 'bg-emerald-900/40 text-emerald-300' : 'bg-emerald-100 text-emerald-700'
                }`}>
                  Purpose: {DONOR_INTENTS.find(i => i.id === selectedIntentId)?.label}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Sort by</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
                className={`text-sm font-medium rounded-lg px-2 py-1 border cursor-pointer ${
                  isDark
                    ? 'bg-slate-800 border-slate-700 text-slate-300'
                    : 'bg-white border-slate-200 text-slate-700'
                }`}
              >
                <option value="score">Overall</option>
                <option value="relevance">Purpose Match</option>
                <option value="evidence">Evidence Stage</option>
                <option value="name">Name A-Z</option>
                <option value="revenue">Revenue</option>
                <option value="program">Program %</option>
              </select>
            </div>
          </div>
        )}

        {/* Charity Grid */}
        <section>
          {sortedCharities.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2 sm:gap-4">
              {sortedCharities.map((charity, index) => (
                <m.div
                  key={charity.id}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, delay: Math.min(index * 0.03, 0.6) }}
                >
                  <CharityCard charity={charity} compact position={index} />
                </m.div>
              ))}
            </div>
          ) : (
            <div className={`text-center py-24 rounded-xl border border-dashed ${isDark ? 'bg-slate-800/20 border-slate-700' : 'bg-white border-slate-200'}`}>
              <div className={`text-6xl mb-4`}>🔍</div>
              <h3 className={`text-xl font-bold mb-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                No matches found
              </h3>
              <p className={`mb-6 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                Try removing some filters or searching for a different term.
              </p>
              {hasActiveFilters && (
                <button
                  onClick={clearFilters}
                  className={`px-6 py-3 rounded-lg font-medium transition-colors ${
                    isDark ? 'bg-emerald-600 text-white hover:bg-emerald-500' : 'bg-emerald-600 text-white hover:bg-emerald-700'
                  }`}
                >
                  Browse all evaluated charities
                </button>
              )}
            </div>
          )}
        </section>

        {/* Suggest a Charity CTA */}
        {sortedCharities.length > 0 && (
          <div className="mt-6 text-center">
            <button
              onClick={() => setShowSuggestCharity(true)}
              className={`text-sm transition-colors ${
                isDark ? 'text-slate-500 hover:text-emerald-400' : 'text-slate-400 hover:text-emerald-600'
              }`}
            >
              Don{'\u2019'}t see your charity?{' '}
              <span className="underline underline-offset-2">Suggest one.</span>
            </button>
          </div>
        )}

        {/* Suggest a Charity modal */}
        {showSuggestCharity && (
          <FeedbackButton
            defaultOpen
            initialFeedbackType="suggest_charity"
            onClose={() => setShowSuggestCharity(false)}
          />
        )}

        {/* Sign-in CTA for unauthenticated users */}
        {!isSignedIn && sortedCharities.length > 0 && (
          <section className={`mt-8 rounded-xl border p-6 sm:p-8 text-center ${
            isDark
              ? 'bg-slate-900/50 border-slate-800'
              : 'bg-white border-slate-200'
          }`}>
            <h3 className={`text-lg font-bold font-merriweather mb-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
              See the full evaluation
            </h3>
            <p className={`text-sm mb-4 max-w-lg mx-auto ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              Sign in to unlock leadership details, financial deep dives, impact evidence, and donor fit analysis for every charity — free, no strings.
            </p>
            <SignInButton variant="button" className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium transition-colors ${
              isDark
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                : 'bg-emerald-600 hover:bg-emerald-700 text-white'
            }`} />
          </section>
        )}
      </div>
    </div>
  );
};

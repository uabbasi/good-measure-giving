/**
 * useCharities hook - Load charities from exported JSON files
 *
 * Loads from:
 * - /data/charities.json (summary list for browse/search)
 * - /data/charities/charity-{ein}.json (full details on demand)
 *
 * Uses TanStack Query for caching, deduplication, and devtools visibility.
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { CharityProfile, UISignalsV1 } from '../../types';
import { normalizeCauseArea, type CauseCategory } from '../utils/categoryUtils';
import { deriveUISignalsFromSummary, deriveUISignalsFromCharity } from '../utils/scoreUtils';

// Summary charity from charities.json (lighter weight for listing)
export interface CharitySummary {
  id: string;
  ein: string;
  name: string;
  tier: 'rich' | 'baseline' | 'hidden';
  mission: string | null;
  /** Headline from baseline/rich narrative - fallback when mission is null */
  headline?: string | null;
  category: string | null;
  website: string;
  amalScore: number;
  walletTag: string;
  confidenceTier: string;
  impactTier: string;
  zakatClassification: string | null;
  isMuslimCharity: boolean;
  programExpenseRatio: number | null;
  totalRevenue: number | null;
  lastUpdated: string;
  /** Raw cause area from rich_narrative (e.g., "HUMANITARIAN", "EDUCATION") */
  causeArea?: string | null;
  /** MECE primary category (e.g., "HUMANITARIAN", "CIVIL_RIGHTS_LEGAL") */
  primaryCategory?: string | null;
  /** Cause tags for filtering/display (e.g., ["domestic-us", "faith-based"]) */
  causeTags?: string[] | null;
  /** Program focus tags for similarity matching (e.g., ["arts-culture-media", "education-higher"]) */
  programFocusTags?: string[] | null;
  /** Pillar scores for methodology visualization (impact/50, alignment/50, dataConfidence 0-1) */
  pillarScores?: {
    impact: number;
    alignment: number;
    dataConfidence?: number;
  } | null;
  /** Evaluation track for alternative scoring rubrics */
  evaluationTrack?: string | null;
  /** Year the organization was founded */
  foundedYear?: number | null;
  /** Hide from default browse view (still searchable via direct URL) */
  hideFromCurated?: boolean;
  /** Plain-English score summary sentence */
  scoreSummary?: string | null;
  /** Zakat asnaf categories served */
  asnafServed?: string[] | null;
  /** Rubric archetype from score details */
  rubricArchetype?: string | null;
  /** Donor-facing qualitative signals */
  ui_signals_v1?: UISignalsV1 | null;
}

interface CharitiesIndex {
  charities: CharitySummary[];
}

// Convert summary to minimal CharityProfile for listing
// Note: This creates a lightweight profile for browse/search - full details are loaded separately
function summaryToProfile(summary: CharitySummary): CharityProfile {
  return {
    id: summary.id,
    ein: summary.ein,
    name: summary.name,
    tier: summary.tier,
    category: summary.category || 'General',
    website: summary.website,
    programs: [],
    populationsServed: [],
    geographicCoverage: [],
    scores: {
      overall: null,
      financial: null,
      accountability: null,
      transparency: null,
      effectiveness: null,
    },
    financials: {
      totalRevenue: summary.totalRevenue || 0,
      totalExpenses: 0,
      programExpenses: 0,
      adminExpenses: 0,
      fundraisingExpenses: 0,
      programExpenseRatio: summary.programExpenseRatio || 0,
    },
    rawData: {
      name: summary.name,
      description: summary.headline || '',
      mission: summary.mission || summary.headline || '',
      program_expense_ratio: summary.programExpenseRatio || 0,
      admin_fundraising_ratio: 0,
      beneficiaries_annual: 0,
      geographic_reach: [],
      board_members_count: 0,
      independent_board_members: 0,
      audit_performed: false,
      zakat_policy: '',
      transparency_level: '',
      red_flags: [],
      outcomes_evidence: '',
    },
    amalEvaluation: {
      charity_ein: summary.ein,
      charity_name: summary.name,
      amal_score: summary.amalScore,
      wallet_tag: summary.walletTag,
      confidence_tier: summary.confidenceTier,
      impact_tier: summary.impactTier,
      zakat_classification: summary.zakatClassification,
      confidence_scores: summary.pillarScores ? {
        impact: summary.pillarScores.impact,
        alignment: summary.pillarScores.alignment,
        dataConfidence: summary.pillarScores.dataConfidence,
      } : undefined,
      evaluation_date: summary.lastUpdated,
    },
    // Store raw causeArea for filtering
    causeArea: summary.causeArea || null,
    // MECE primary category and cause tags
    primaryCategory: summary.primaryCategory || null,
    causeTags: summary.causeTags || null,
    // Program focus tags (LLM-extracted for similarity matching)
    programFocusTags: summary.programFocusTags || null,
    // Evaluation track (for alternative scoring rubrics)
    evaluationTrack: summary.evaluationTrack || null,
    foundedYear: summary.foundedYear || null,
    // Hide from curated browse view (accessible via search/direct URL)
    hideFromCurated: summary.hideFromCurated,
    // Score summary sentence (deterministic, not LLM-generated)
    scoreSummary: summary.scoreSummary || null,
    // Asnaf categories for browse page filtering
    asnafServed: summary.asnafServed || null,
    rubricArchetype: summary.rubricArchetype || null,
    ui_signals_v1: summary.ui_signals_v1 || deriveUISignalsFromSummary(summary),
  } as CharityProfile;
}

// Fetch function shared by the query
async function fetchCharitiesIndex(): Promise<{ summaries: CharitySummary[]; charities: CharityProfile[] }> {
  const response = await fetch('/data/charities.json');
  if (!response.ok) {
    throw new Error(`Failed to load charities: ${response.status}`);
  }
  const data: CharitiesIndex = await response.json();
  return {
    summaries: data.charities,
    charities: data.charities.map(summaryToProfile),
  };
}

/**
 * Hook to load all charities from exported JSON.
 * Uses TanStack Query — data is fetched once and cached for the session.
 */
export function useCharities() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['charities'],
    queryFn: fetchCharitiesIndex,
  });

  return {
    charities: data?.charities ?? [],
    summaries: data?.summaries ?? [],
    loading: isLoading,
    error: error ? (error instanceof Error ? error.message : 'Failed to load charities') : null,
  };
}

/**
 * Hook to load a single charity's full details.
 * Cached per EIN so navigating between detail pages doesn't re-fetch.
 */
export function useCharity(ein: string) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['charity', ein],
    queryFn: async () => {
      const response = await fetch(`/data/charities/charity-${ein}.json`);
      if (!response.ok) {
        throw new Error(`Charity not found: ${ein}`);
      }
      const charity = (await response.json()) as CharityProfile;
      if (!charity.ui_signals_v1) {
        charity.ui_signals_v1 = deriveUISignalsFromCharity(charity);
      }
      return charity;
    },
    enabled: !!ein,
  });

  return {
    charity: data ?? null,
    loading: isLoading,
    error: error ? (error instanceof Error ? error.message : 'Failed to load charity') : null,
  };
}

/**
 * Search and filter charities
 */
/** Available program focus tags for filtering */
export const PROGRAM_FOCUS_TAG_LABELS: Record<string, string> = {
  'arts-culture-media': 'Arts, Culture & Media',
  'advocacy-legal': 'Advocacy & Legal',
  'humanitarian-relief': 'Humanitarian Relief',
  'water-sanitation': 'Water & Sanitation',
  'education-k12': 'K-12 Education',
  'education-higher': 'Higher Education',
  'healthcare-direct': 'Healthcare',
  'economic-empowerment': 'Economic Empowerment',
  'community-services': 'Community Services',
  'research-policy': 'Research & Policy',
  'religious-services': 'Religious Services',
  'orphan-care': 'Orphan Care',
  'refugee-services': 'Refugee Services',
};

export function useCharitySearch(
  charities: CharityProfile[],
  searchQuery: string,
  filters?: {
    walletTag?: string;
    minScore?: number;
    tier?: string;
    /** Filter by normalized cause categories (multi-select) */
    causeCategories?: CauseCategory[];
    /** Filter by program focus tags (multi-select) */
    programFocusTags?: string[];
  }
) {
  return useMemo(() => {
    let results = [...charities];

    // Text search
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      results = results.filter(c =>
        c.name.toLowerCase().includes(query) ||
        c.rawData?.mission?.toLowerCase().includes(query) ||
        c.category?.toLowerCase().includes(query) ||
        c.ein?.includes(query)
      );
    }

    // Wallet tag filter
    if (filters?.walletTag) {
      results = results.filter(c =>
        c.amalEvaluation?.wallet_tag?.includes(filters.walletTag!)
      );
    }

    // Minimum score filter
    if (filters?.minScore) {
      results = results.filter(c =>
        (c.amalEvaluation?.amal_score || 0) >= filters.minScore!
      );
    }

    // Tier filter
    if (filters?.tier) {
      results = results.filter(c => c.tier === filters.tier);
    }

    // Cause category filter (multi-select)
    if (filters?.causeCategories && filters.causeCategories.length > 0) {
      const selectedCategories = new Set(filters.causeCategories);
      results = results.filter(c => {
        // Get raw causeArea from charity and normalize it
        const rawCause = (c as CharityProfile & { causeArea?: string | null }).causeArea;
        const normalized = normalizeCauseArea(rawCause);
        // Include if charity's normalized cause matches any selected category
        return normalized && selectedCategories.has(normalized);
      });
    }

    // Program focus tag filter (multi-select)
    if (filters?.programFocusTags && filters.programFocusTags.length > 0) {
      const selectedTags = new Set(filters.programFocusTags);
      results = results.filter(c => {
        const charityTags = (c as CharityProfile & { programFocusTags?: string[] | null }).programFocusTags;
        // Include if charity has any of the selected program focus tags
        return charityTags && charityTags.some(tag => selectedTags.has(tag));
      });
    }

    return results;
  }, [charities, searchQuery, filters]);
}

export default useCharities;

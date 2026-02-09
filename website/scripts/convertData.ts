/**
 * Data Conversion Script
 * Converts charity data from pipeline format to React app format
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { CharityProfile, RatingColor, ImpactAssessment, ConfidenceAssessment, DimensionEvaluation, CharityRawData, AmalEvaluation } from '../types';

// ES Module workaround for __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Paths
const DATA_DIR = path.join(__dirname, '../data');
const CHARITIES_JSON = path.join(DATA_DIR, 'charities.json');
const CHARITY_FILES_DIR = path.join(DATA_DIR, 'charities');
const OUTPUT_FILE = path.join(__dirname, '../src/data/charities.ts');
const TOP_CHARITY_FILE = path.join(__dirname, '../src/data/topCharity.ts');

// Type definitions for source data
interface SourceDimension {
  name: string;
  scoreColor: 'GREEN' | 'YELLOW' | 'RED' | 'UNKNOWN';
  rationale: string;
  citedMetrics: string[];
  scoreValue?: number | null;
  weight: number;
  dataAvailable: boolean;
}

interface SourceNarrative {
  text: string;
  citedSources: string[];
  keyStrengths: string[];
  growthOpportunities: string[];
  llmModel?: string;
}

interface SourceEvaluation {
  impactTier: 'HIGH' | 'MODERATE' | 'LOW';
  confidenceTier: 'HIGH' | 'MODERATE' | 'LOW' | 'INSUFFICIENT_DATA';
  dimensions?: {
    impact: SourceDimension[];
    confidence: SourceDimension[];
  };
  narratives?: {
    impact: SourceNarrative;
    confidence: SourceNarrative;
  };
}

interface SourceAmalDimensionScore {
  score: number;
  level: string;
  rationale: string;
  evidence?: string[];
}

interface SourceAmalEvaluation {
  charity_ein: string;
  charity_name: string;
  amal_score: number;
  wallet_tag: string;
  tier_1_score: number;
  tier_2_score: number;
  evaluation_date: string;
  methodology_version: string;
  tier_1_strategic_fit?: {
    subtotal: number;
    systemic_leverage: SourceAmalDimensionScore;
    ummah_gap: SourceAmalDimensionScore;
  };
  tier_2_execution?: {
    subtotal: number;
    absorptive_capacity: SourceAmalDimensionScore;
    evidence_of_impact: SourceAmalDimensionScore;
  };
  wallet_routing?: {
    tag: string;
    matching_categories: string[];
    rationale: string;
    advisory: string;
    disclaimer: string;
    donor_guidance?: string;
    donor_growth_message?: string;
  };
  summary?: {
    headline: string;
    narrative: string;
    strengths: string[];
    improvement_areas: string[];
    donor_guidance: string;
  };
  data_confidence?: {
    level: string;
    gaps: string[];
    sources_used: string[];
  };
}

interface SourceCharity {
  id: string;
  ein: string;
  name: string;
  tier?: 'rich' | 'baseline' | 'hidden';  // T001: Charity tier
  mission?: string;
  category?: string | null;
  website?: string;
  zakatEligible?: string;
  status?: string;
  scores?: {
    overall?: number;
    financial?: number;
    accountability?: number;
    transparency?: number;
    effectiveness?: number;
  };
  financials?: {
    totalRevenue?: number;
    programExpenses?: number;
    adminExpenses?: number;
    fundraisingExpenses?: number;
    programExpenseRatio?: number;
    fiscalYear?: number;
  };
  sourceAttribution?: any;  // T058 - Source attribution metadata
  evaluation?: SourceEvaluation;
  amalEvaluation?: SourceAmalEvaluation;  // Amal Impact Matrix evaluation
  sources?: any;
  programs?: string[];
  populationsServed?: string[];
  geographicCoverage?: string[];
  hideFromCurated?: boolean;  // Hide from default browse view
}

/**
 * Convert ALL CAPS names to Title Case.
 * Preserves known acronyms (CAIR, ISF, ISNA, etc.) and small words (of, the, for, etc.)
 */
function toDisplayName(name: string): string {
  // Only transform if the name is mostly uppercase (>60% caps letters)
  const letters = name.replace(/[^a-zA-Z]/g, '');
  const upperCount = (name.match(/[A-Z]/g) || []).length;
  if (letters.length === 0 || upperCount / letters.length < 0.6) return name;

  const acronyms = new Set([
    'CAIR', 'USA', 'US', 'ISF', 'ISNA', 'ICNA', 'IRUSA', 'SAMS', 'MSA',
    'MAS', 'HHRD', 'IDRF', 'UKIM', 'INC', 'LLC', 'NFP', 'II', 'III', 'IV',
    'UNICEF', 'CARE', 'MCA', 'ING', 'SIUT', 'SAPA', 'ICNAB', 'BASMAH',
    'PCRF', 'ACLU', 'MCC', 'AMSSF', 'ISPU',
  ]);
  const smallWords = new Set(['of', 'the', 'for', 'and', 'in', 'on', 'a', 'an', 'to']);

  return name
    .split(/\s+/)
    .map((word, index) => {
      const upper = word.toUpperCase();
      if (acronyms.has(upper)) return upper;
      if (index > 0 && smallWords.has(word.toLowerCase())) return word.toLowerCase();
      // Title case: first letter upper, rest lower
      // Handle hyphenated words (e.g., "AMERICAN-ISLAMIC" → "American-Islamic")
      if (word.includes('-')) {
        return word.split('-').map(part => {
          const partUpper = part.toUpperCase();
          if (acronyms.has(partUpper)) return partUpper;
          return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
        }).join('-');
      }
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(' ');
}

/**
 * Round long decimal numbers in narrative text strings.
 * Matches patterns like "96.33333333333333" and rounds to integer.
 */
function roundScoresInText(text: string): string {
  // Match numbers with 3+ decimal places (e.g., 96.333333, 0.982699)
  return text.replace(/\b(\d+)\.(\d{3,})\b/g, (_match, intPart, decPart) => {
    const num = parseFloat(`${intPart}.${decPart}`);
    // For numbers that look like scores (>1), round to integer
    if (num >= 1) return Math.round(num).toString();
    // For ratios (0.xxx), round to 2 decimal places
    return num.toFixed(2);
  });
}

/**
 * Recursively walk an object and round decimal scores in all string values.
 */
function cleanTextFields(obj: any): any {
  if (typeof obj === 'string') return roundScoresInText(obj);
  if (Array.isArray(obj)) return obj.map(cleanTextFields);
  if (obj && typeof obj === 'object') {
    const result: any = {};
    for (const [key, value] of Object.entries(obj)) {
      result[key] = cleanTextFields(value);
    }
    return result;
  }
  return obj;
}

/**
 * Map tier to rating color
 */
function tierToRatingColor(tier: 'HIGH' | 'MODERATE' | 'LOW' | undefined): RatingColor {
  if (!tier) return RatingColor.UNKNOWN;
  const mapping: Record<string, RatingColor> = {
    'HIGH': RatingColor.GREEN,
    'MODERATE': RatingColor.YELLOW,
    'LOW': RatingColor.RED
  };
  return mapping[tier] || RatingColor.UNKNOWN;
}

/**
 * Map source dimension to target dimension evaluation
 */
function mapDimension(dim: SourceDimension): DimensionEvaluation {
  const colorMap: Record<string, RatingColor> = {
    'GREEN': RatingColor.GREEN,
    'YELLOW': RatingColor.YELLOW,
    'RED': RatingColor.RED,
    'UNKNOWN': RatingColor.UNKNOWN
  };
  return {
    rating: colorMap[dim.scoreColor] || RatingColor.UNKNOWN,
    rationale: dim.rationale || 'No rationale provided'
  };
}

/**
 * Map impact dimensions from source to target structure
 */
function mapImpactDimensions(dimensions: SourceDimension[] | undefined) {
  const dimMap: Record<string, string> = {
    'cost_effectiveness': 'cost_effectiveness',
    'evidence_of_effectiveness': 'intervention_strength',
    'problem_importance_tractability': 'problem_importance',
    'scale_of_reach': 'scale_of_reach',
    'sustainability_depth': 'long_term_benefit'
  };

  const result: any = {
    problem_importance: { rating: RatingColor.UNKNOWN, rationale: 'Data not available' },
    intervention_strength: { rating: RatingColor.UNKNOWN, rationale: 'Data not available' },
    scale_of_reach: { rating: RatingColor.UNKNOWN, rationale: 'Data not available' },
    cost_effectiveness: { rating: RatingColor.UNKNOWN, rationale: 'Data not available' },
    long_term_benefit: { rating: RatingColor.UNKNOWN, rationale: 'Data not available' }
  };

  if (!dimensions) return result;

  dimensions.forEach(dim => {
    const targetKey = dimMap[dim.name];
    if (targetKey) {
      result[targetKey] = mapDimension(dim);
    }
  });

  return result;
}

/**
 * Map confidence dimensions from source to target structure
 */
function mapConfidenceDimensions(dimensions: SourceDimension[] | undefined) {
  const dimMap: Record<string, string> = {
    'transparency': 'transparency',
    'accountability_governance': 'governance',
    'use_of_funds': 'financial_controls',
    'third_party_verification': 'third_party_verification',
    'reporting_quality': 'reporting_quality'
  };

  const result: any = {
    transparency: RatingColor.UNKNOWN,
    governance: RatingColor.UNKNOWN,
    financial_controls: RatingColor.UNKNOWN,
    third_party_verification: RatingColor.UNKNOWN,
    reporting_quality: RatingColor.UNKNOWN
  };

  if (!dimensions) return result;

  dimensions.forEach(dim => {
    const targetKey = dimMap[dim.name];
    if (targetKey) {
      // Map string to RatingColor enum
      const colorMap: Record<string, RatingColor> = {
        'GREEN': RatingColor.GREEN,
        'YELLOW': RatingColor.YELLOW,
        'RED': RatingColor.RED,
        'UNKNOWN': RatingColor.UNKNOWN
      };
      result[targetKey] = colorMap[dim.scoreColor] || RatingColor.UNKNOWN;
    }
  });

  return result;
}

/**
 * Extract beneficiaries count from sources
 */
function extractBeneficiaries(charity: SourceCharity): number {
  // Try to find from metrics if available
  if (charity.sources?.candid?.data?.candid_profile?.metrics) {
    const metrics = charity.sources.candid.data.candid_profile.metrics;
    if (metrics.length > 0 && metrics[0].year_data?.length > 0) {
      const latestValue = metrics[0].year_data[0][1];
      if (latestValue) return parseInt(latestValue);
    }
  }
  // Default estimate based on revenue
  const revenue = charity.financials?.totalRevenue || 0;
  if (revenue > 20000000) return 50000;
  if (revenue > 10000000) return 25000;
  if (revenue > 5000000) return 10000;
  if (revenue > 1000000) return 5000;
  return 1000;
}

/**
 * Extract geographic reach
 */
function extractGeographicReach(charity: SourceCharity): string[] {
  const sources = charity.sources;
  if (sources?.candid?.data?.candid_profile?.areas_served) {
    return sources.candid.data.candid_profile.areas_served;
  }
  if (sources?.reconciled?.data?.reconciled_profile?.geographic_coverage) {
    return sources.reconciled.data.reconciled_profile.geographic_coverage;
  }
  // Default based on name patterns
  if (charity.name.toLowerCase().includes('global') || charity.name.toLowerCase().includes('international')) {
    return ['Multiple Countries'];
  }
  return ['United States'];
}

/**
 * Extract board info
 */
function extractBoardInfo(charity: SourceCharity) {
  const cnData = charity.sources?.charity_navigator?.data?.cn_profile;
  const candidData = charity.sources?.candid?.data?.candid_profile;

  const boardSize = cnData?.board_size || candidData?.board_size || 5;
  const independentPct = cnData?.independent_board_percentage || 0;
  const independentCount = Math.round((independentPct / 100) * boardSize);

  return {
    board_members_count: boardSize,
    independent_board_members: independentCount
  };
}

/**
 * Convert a single charity from source to target format
 */
function convertCharity(sourceCharity: SourceCharity, index: number): CharityProfile {
  const evaluation = sourceCharity.evaluation;
  const boardInfo = extractBoardInfo(sourceCharity);

  // Build rawData
  const rawData: CharityRawData = {
    name: toDisplayName(sourceCharity.name),
    description: sourceCharity.mission?.substring(0, 200) || 'No description available',
    mission: sourceCharity.mission || 'Mission statement not available',
    program_expense_ratio: Math.round((sourceCharity.financials?.programExpenseRatio || 0.75) * 100),
    admin_fundraising_ratio: 100 - Math.round((sourceCharity.financials?.programExpenseRatio || 0.75) * 100),
    beneficiaries_annual: extractBeneficiaries(sourceCharity),
    geographic_reach: extractGeographicReach(sourceCharity),
    board_members_count: boardInfo.board_members_count,
    independent_board_members: boardInfo.independent_board_members,
    audit_performed: (sourceCharity.scores?.accountability || 0) > 80,
    zakat_policy: sourceCharity.zakatEligible === 'yes'
      ? 'Zakat-eligible organization with proper fund separation'
      : sourceCharity.zakatEligible === 'unclear'
      ? 'Zakat eligibility unclear. Scholar consultation recommended.'
      : 'Not specifically designated for Zakat',
    transparency_level: sourceCharity.sources?.candid?.data?.transparency_seal?.toUpperCase() || 'None',
    red_flags: boardInfo.independent_board_members === 0 ? ['No independent board members'] : [],
    outcomes_evidence: evaluation?.narratives?.impact?.text?.substring(0, 300) || 'Limited outcome data available'
  };

  // Build Impact Assessment
  const impactNarrative = evaluation?.narratives?.impact;
  const impactAssessment: ImpactAssessment = {
    overall_rating: tierToRatingColor(evaluation?.impactTier),
    dimension_ratings: mapImpactDimensions(evaluation?.dimensions?.impact),
    narrative: impactNarrative?.text || `${toDisplayName(sourceCharity.name)} works in ${sourceCharity.category || 'charitable activities'} with a program expense ratio of ${rawData.program_expense_ratio}%.`,
    cited_sources: impactNarrative?.citedSources || ['IRS 990', 'Charity Navigator'],
    key_strengths: impactNarrative?.keyStrengths || ['Financial data available'],
    growth_opportunities: impactNarrative?.growthOpportunities || ['Increase transparency reporting'],
    confidence_level: evaluation?.confidenceTier === 'HIGH' ? 'high' :
                      evaluation?.confidenceTier === 'MODERATE' ? 'medium' : 'low'
  };

  // Build Confidence Assessment
  const confidenceNarrative = evaluation?.narratives?.confidence;
  const confidenceAssessment: ConfidenceAssessment = {
    confidence_tier: evaluation?.confidenceTier || 'INSUFFICIENT_DATA',
    dimension_ratings: mapConfidenceDimensions(evaluation?.dimensions?.confidence),
    narrative: confidenceNarrative?.text || `This organization has a ${evaluation?.confidenceTier || 'MODERATE'} confidence rating based on available data.`
  };

  // Build the charity profile
  const profile: CharityProfile = {
    id: sourceCharity.id,
    name: toDisplayName(sourceCharity.name),
    tier: sourceCharity.tier,  // T001: Include tier field
    category: sourceCharity.category || 'General',
    ein: sourceCharity.ein,
    website: sourceCharity.website,
    programs: sourceCharity.programs || [],
    populationsServed: sourceCharity.populationsServed || [],
    geographicCoverage: sourceCharity.geographicCoverage || [],
    scores: {
      overall: sourceCharity.scores?.overall || null,
      financial: sourceCharity.scores?.financial || null,
      accountability: sourceCharity.scores?.accountability || null,
      transparency: sourceCharity.scores?.transparency || null,
      effectiveness: sourceCharity.scores?.effectiveness || null
    },
    financials: sourceCharity.financials ? {
      totalRevenue: sourceCharity.financials.totalRevenue,
      totalExpenses: (sourceCharity.financials.programExpenses || 0) +
                     (sourceCharity.financials.adminExpenses || 0) +
                     (sourceCharity.financials.fundraisingExpenses || 0),
      programExpenses: sourceCharity.financials.programExpenses,
      adminExpenses: sourceCharity.financials.adminExpenses,
      fundraisingExpenses: sourceCharity.financials.fundraisingExpenses,
      programExpenseRatio: sourceCharity.financials.programExpenseRatio,
      fiscalYear: sourceCharity.financials.fiscalYear
    } : undefined,
    sourceAttribution: sourceCharity.sourceAttribution || {},  // T058 - Include source attribution
    rawData,
    impactAssessment,
    confidenceAssessment,
    hideFromCurated: sourceCharity.hideFromCurated || false,
    // Extended fields for card differentiators
    primaryCategory: (sourceCharity as any).primaryCategory || null,
    causeTags: (sourceCharity as any).causeTags || [],
    impactTier: (sourceCharity as any).evaluation?.impactTier || null,
    categoryMetadata: (sourceCharity as any).categoryMetadata || null,
    headline: (sourceCharity as any).headline || null,
    totalRevenue: sourceCharity.financials?.totalRevenue || null,
    // Emerging org detection
    foundedYear: (sourceCharity as any).foundedYear || null,
    evaluationTrack: (sourceCharity as any).evaluationTrack || null,
  };

  // Add Amal evaluation if available
  if (sourceCharity.amalEvaluation) {
    const amalEval = sourceCharity.amalEvaluation;

    // Clean up wallet_tag - remove brackets if present
    let walletTag = amalEval.wallet_tag;
    if (walletTag.startsWith('[') && walletTag.endsWith(']')) {
      walletTag = walletTag.slice(1, -1);
    }

    // Clean up wallet_routing.tag if present
    let walletRouting = amalEval.wallet_routing;
    if (walletRouting) {
      let routingTag = walletRouting.tag;
      if (routingTag.startsWith('[') && routingTag.endsWith(']')) {
        routingTag = routingTag.slice(1, -1);
      }
      walletRouting = {
        ...walletRouting,
        tag: routingTag as any,
        donor_guidance: walletRouting.donor_guidance || amalEval.summary?.donor_guidance || '',
        donor_growth_message: walletRouting.donor_growth_message || ''
      };
    }

    profile.amalEvaluation = {
      ...amalEval,
      charity_name: toDisplayName(amalEval.charity_name),
      wallet_tag: walletTag as any,
      wallet_routing: walletRouting
    } as AmalEvaluation;
  }

  // Clean decimal scores from all narrative text fields
  if (profile.impactAssessment) {
    profile.impactAssessment.narrative = roundScoresInText(profile.impactAssessment.narrative);
  }
  if (profile.confidenceAssessment) {
    profile.confidenceAssessment.narrative = roundScoresInText(profile.confidenceAssessment.narrative);
  }
  if (profile.rawData) {
    profile.rawData.outcomes_evidence = roundScoresInText(profile.rawData.outcomes_evidence);
    profile.rawData.zakat_policy = roundScoresInText(profile.rawData.zakat_policy);
  }
  if (profile.amalEvaluation) {
    profile.amalEvaluation = cleanTextFields(profile.amalEvaluation);
  }

  return profile;
}

/**
 * Build a summary entry for charities.json from a detail file.
 * Extracts the lightweight fields needed for browse/search pages.
 */
function buildSummaryFromDetail(detail: any): any {
  const amal = detail.amalEvaluation || {};

  // Extract pillar scores from confidence_scores
  const cs = amal.confidence_scores;
  // New 2-dimension format (impact/50, alignment/50, dataConfidence 0-1)
  const pillarScores = cs && cs.impact != null
    ? { impact: cs.impact, alignment: cs.alignment, dataConfidence: cs.dataConfidence ?? null }
    // Legacy 4-dimension format (trust/evidence/effectiveness/fit)
    : cs && cs.trust != null
      ? { impact: (cs.effectiveness ?? 0) + (cs.evidence ?? 0), alignment: cs.fit ?? 0, dataConfidence: null }
      : null;

  // Extract headline from rich or baseline narrative
  const headline = amal.rich_narrative?.headline
    || amal.baseline_narrative?.headline
    || null;

  // Derive impactTier from amal_score
  const score = amal.amal_score;
  let impactTier: string | null = null;
  if (score != null) {
    if (score >= 80) impactTier = 'HIGH';
    else if (score >= 65) impactTier = 'ABOVE_AVERAGE';
    else if (score >= 50) impactTier = 'AVERAGE';
    else impactTier = 'BELOW_AVERAGE';
  }

  // Derive confidenceTier from dataConfidence (0-1 float) or legacy trust score
  const dataConf = cs?.dataConfidence;
  const trustScore = cs?.trust;
  let confidenceTier: string | null = null;
  if (dataConf != null) {
    if (dataConf >= 0.7) confidenceTier = 'HIGH';
    else if (dataConf >= 0.4) confidenceTier = 'MODERATE';
    else confidenceTier = 'LOW';
  } else if (trustScore != null) {
    if (trustScore >= 20) confidenceTier = 'HIGH';
    else if (trustScore >= 15) confidenceTier = 'MODERATE';
    else if (trustScore >= 10) confidenceTier = 'BASIC';
    else confidenceTier = 'NONE';
  }

  return {
    id: detail.ein,
    ein: detail.ein,
    name: toDisplayName(detail.name || detail.ein),
    tier: detail.tier || 'baseline',
    mission: detail.mission || null,
    headline,
    category: detail.category || null,
    website: detail.website || null,
    overallScore: detail.scores?.overall || null,
    financialScore: detail.scores?.financial || null,
    accountabilityScore: detail.scores?.accountability || null,
    programExpenseRatio: detail.financials?.programExpenseRatio || null,
    totalRevenue: detail.financials?.totalRevenue || null,
    isMuslimCharity: detail.isMuslimCharity || false,
    lastUpdated: detail.lastUpdated || null,
    status: detail.status || null,
    impactTier,
    confidenceTier,
    zakatClassification: detail.zakatClassification || null,
    amalScore: amal.amal_score || null,
    walletTag: amal.wallet_tag || null,
    pillarScores,
    causeArea: amal.rich_narrative?.donor_fit_matrix?.cause_area || null,
    primaryCategory: detail.primaryCategory || null,
    categoryMetadata: detail.categoryMetadata || null,
    causeTags: detail.causeTags || null,
    programFocusTags: detail.programFocusTags || null,
    hideFromCurated: detail.hideFromCurated || null,
    evaluationTrack: detail.evaluationTrack || null,
    foundedYear: detail.foundedYear || null,
    scoreSummary: amal.score_details?.score_summary || null,
  };
}

/**
 * Main conversion function
 */
async function convertAllCharities() {
  console.log('🔄 Starting charity data conversion...\n');

  // Step 1: Build charities.json index from individual charity files
  // This ensures the index is always in sync with whatever files exist on disk.
  const charityFiles = fs.readdirSync(CHARITY_FILES_DIR)
    .filter(f => f.startsWith('charity-') && f.endsWith('.json'));

  console.log(`📂 Found ${charityFiles.length} charity files in ${CHARITY_FILES_DIR}`);

  const summaries: any[] = [];
  for (const file of charityFiles) {
    try {
      const detail = JSON.parse(fs.readFileSync(path.join(CHARITY_FILES_DIR, file), 'utf-8'));
      summaries.push(buildSummaryFromDetail(detail));
    } catch (error) {
      console.error(`⚠️  Skipping ${file}: ${error instanceof Error ? error.message : error}`);
    }
  }

  // Write rebuilt charities.json
  const indexData = { source: 'build', charities: summaries };
  fs.writeFileSync(CHARITIES_JSON, JSON.stringify(indexData, null, 2), 'utf-8');
  console.log(`📋 Rebuilt charities.json: ${summaries.length} charities from ${charityFiles.length} files\n`);

  // Step 2: Convert each charity to React app format
  const convertedCharities: CharityProfile[] = [];
  let successCount = 0;
  let errorCount = 0;

  for (let i = 0; i < charityFiles.length; i++) {
    const file = charityFiles[i];
    const filePath = path.join(CHARITY_FILES_DIR, file);

    try {
      const charityData: SourceCharity = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      const converted = convertCharity(charityData, i);
      convertedCharities.push(converted);
      successCount++;

      if (successCount % 10 === 0) {
        console.log(`✅ Converted ${successCount} charities...`);
      }
    } catch (error) {
      console.error(`❌ Error converting ${file}:`, error instanceof Error ? error.message : error);
      errorCount++;
    }
  }

  console.log(`\n✨ Conversion complete!`);
  console.log(`   ✅ Success: ${successCount}`);
  console.log(`   ❌ Errors: ${errorCount}`);

  // Find the top-scoring charity for the landing page sample audit
  const topCharity = convertedCharities
    .filter(c => c.amalEvaluation?.amal_score && c.amalEvaluation.amal_score >= 70)
    .sort((a, b) => (b.amalEvaluation?.amal_score || 0) - (a.amalEvaluation?.amal_score || 0))[0];

  const topCharityData = topCharity ? {
    name: toDisplayName(topCharity.name),
    ein: topCharity.id,
    headline: topCharity.amalEvaluation?.baseline_narrative?.headline ||
              topCharity.amalEvaluation?.summary?.headline ||
              topCharity.rawData?.mission?.substring(0, 100) || 'Leading nonprofit organization',
    amalEvaluation: {
      amal_score: topCharity.amalEvaluation?.amal_score || 0,
      confidence_scores: {
        impact: topCharity.amalEvaluation?.confidence_scores?.impact || 0,
        alignment: topCharity.amalEvaluation?.confidence_scores?.alignment || 0,
        dataConfidence: topCharity.amalEvaluation?.confidence_scores?.dataConfidence || 0,
      },
      // Legacy fields for backward compat
      trust: { score: topCharity.amalEvaluation?.trust?.score || topCharity.amalEvaluation?.confidence_scores?.trust || 0 },
      evidence: { score: topCharity.amalEvaluation?.evidence?.score || topCharity.amalEvaluation?.confidence_scores?.evidence || 0 },
      effectiveness: { score: topCharity.amalEvaluation?.effectiveness?.score || topCharity.amalEvaluation?.confidence_scores?.effectiveness || 0 },
      fit: { score: topCharity.amalEvaluation?.fit?.score || topCharity.amalEvaluation?.confidence_scores?.fit || 0 },
      // Include score_details for "How This Score Was Calculated" breakdown
      score_details: topCharity.amalEvaluation?.score_details || undefined,
    },
    // Include a highlight stat if available from strengths or headline
    impactHighlight: topCharity.amalEvaluation?.rich_narrative?.key_strengths?.[0] ||
                     topCharity.amalEvaluation?.summary?.strengths?.[0] ||
                     topCharity.amalEvaluation?.baseline_narrative?.headline ||
                     topCharity.amalEvaluation?.summary?.headline ||
                     topCharity.rawData?.mission?.substring(0, 150) ||
                     'Highly-rated organization with strong impact metrics'
  } : null;

  console.log(`\n🏆 Top charity for landing page: ${topCharityData?.name} (Score: ${topCharityData?.amalEvaluation.amal_score})`);

  // Generate main charities file
  const outputContent = `import type { CharityProfile, RatingColor } from '../../types';

/**
 * Charity data converted from pipeline
 * Generated on: ${new Date().toISOString()}
 * Total charities: ${convertedCharities.length}
 */

export const CHARITIES: CharityProfile[] = ${JSON.stringify(convertedCharities, null, 2)};

// Return undefined when not found so callers can surface a proper 404 state.
// Note: Uses ein as the identifier since id may not be present in generated data
export const getCharityById = (id: string) => CHARITIES.find(c => c.ein === id || c.id === id);
`;

  // Generate separate top charity file (keeps large CHARITIES array out of landing page bundle)
  const topCharityContent = `/**
 * Top-scoring charity for landing page sample audit
 * Auto-generated at build time - always shows the current highest-rated charity
 *
 * NOTE: This is intentionally in a separate file from charities.ts to ensure
 * the large CHARITIES array (4+ MB) is not pulled into the main bundle.
 */
import type { CharityProfile, AmalDimensionScore, ScoreDetails } from '../../types';

// Extended type for landing page with pillar scores as objects
interface FeaturedCharityData extends CharityProfile {
  amalEvaluation?: CharityProfile['amalEvaluation'] & {
    trust?: AmalDimensionScore;
    evidence?: AmalDimensionScore;
    effectiveness?: AmalDimensionScore;
    fit?: AmalDimensionScore;
    score_details?: ScoreDetails;
  };
}

export const TOP_CHARITY_FOR_LANDING: FeaturedCharityData | null = ${JSON.stringify(topCharityData, null, 2)};
`;

  // Write output files
  const outputDir = path.dirname(OUTPUT_FILE);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  fs.writeFileSync(OUTPUT_FILE, outputContent, 'utf-8');
  console.log(`\n📝 Written to: ${OUTPUT_FILE}`);
  console.log(`   File size: ${(fs.statSync(OUTPUT_FILE).size / 1024).toFixed(2)} KB`);

  fs.writeFileSync(TOP_CHARITY_FILE, topCharityContent, 'utf-8');
  console.log(`📝 Written to: ${TOP_CHARITY_FILE}`);

  // Copy data/ into public/data/ so Vite includes it in dist/
  // (replaces the symlink which doesn't work reliably on CI)
  const PUBLIC_DATA_DIR = path.join(__dirname, '../public/data');
  const PUBLIC_CHARITIES_DIR = path.join(PUBLIC_DATA_DIR, 'charities');

  if (fs.existsSync(PUBLIC_DATA_DIR)) {
    fs.rmSync(PUBLIC_DATA_DIR, { recursive: true });
  }
  fs.mkdirSync(PUBLIC_CHARITIES_DIR, { recursive: true });

  // Copy charities.json index
  fs.copyFileSync(CHARITIES_JSON, path.join(PUBLIC_DATA_DIR, 'charities.json'));

  // Copy individual charity files
  for (const file of charityFiles) {
    fs.copyFileSync(
      path.join(CHARITY_FILES_DIR, file),
      path.join(PUBLIC_CHARITIES_DIR, file),
    );
  }

  // Copy prompts directory if it exists
  const PROMPTS_DIR = path.join(DATA_DIR, 'prompts');
  if (fs.existsSync(PROMPTS_DIR)) {
    const PUBLIC_PROMPTS_DIR = path.join(PUBLIC_DATA_DIR, 'prompts');
    fs.mkdirSync(PUBLIC_PROMPTS_DIR, { recursive: true });
    for (const file of fs.readdirSync(PROMPTS_DIR)) {
      fs.copyFileSync(
        path.join(PROMPTS_DIR, file),
        path.join(PUBLIC_PROMPTS_DIR, file),
      );
    }
  }

  console.log(`📂 Copied data/ → public/data/ (${charityFiles.length} charity files)`);
}

// Run conversion
convertAllCharities().catch(console.error);

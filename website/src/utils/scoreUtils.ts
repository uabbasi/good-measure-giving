/**
 * Shared score analysis utilities
 * Extracted from TerminalView for reuse across ScoreBreakdown, ImprovementGuide, etc.
 */

import { cleanNarrativeText } from './cleanNarrativeText';
import type { CharityProfile, UISignalsV1, UISignalState } from '../../types';
import { uiSignalsConfig, UI_SIGNALS_CONFIG_HASH, UI_SIGNALS_CONFIG_VERSION } from '../generated/uiSignalsConfig';

/**
 * Numeric score → human-readable rating label
 */
export const getScoreRating = (score: number): string => {
  if (score >= 75) return 'Exceptional';
  if (score >= 60) return 'Good';
  if (score >= 45) return 'Average';
  if (score >= 30) return 'Below Average';
  return 'Needs Improvement';
};

/**
 * Strip citation markers from text for non-authenticated users.
 * Removes <cite id="N">...</cite> tags (keeping inner text) and [N] markers.
 */
export const stripCitations = (text: string): string => {
  if (!text) return '';
  const cleaned = text
    // Closed cite tags: keep inner text
    .replace(/<cite id=["']?\d+["']?>(.*?)<\/cite>/g, '$1')
    // Unclosed cite tags (LLM artifact): keep text after the tag
    .replace(/<cite\s+id=["']?\[?\d+\]?["']?>/g, '')
    .replace(/\[\d+\]/g, '');
  return cleanNarrativeText(cleaned);
};

/**
 * Map improvement text to a scoring dimension based on keywords.
 */
export const mapImprovementToDimension = (
  improvement: string | { area: string; context: string }
): string | null => {
  const text = typeof improvement === 'string'
    ? improvement.toLowerCase()
    : `${improvement.area} ${improvement.context}`.toLowerCase();

  // Impact indicators
  if (
    text.includes('expense ratio') || text.includes('program ratio') ||
    text.includes('cost') || text.includes('efficiency') || text.includes('fundraising') ||
    text.includes('overhead') || text.includes('financial efficiency') ||
    text.includes('impact') || text.includes('beneficiar') ||
    text.includes('transparency') || text.includes('governance') || text.includes('board') ||
    text.includes('audit') || text.includes('disclosure') || text.includes('accountability') ||
    text.includes('outcome') || text.includes('measurement') || text.includes('evidence') ||
    text.includes('evaluation') || text.includes('metrics') || text.includes('tracking') ||
    text.includes('data')
  ) {
    return 'impact';
  }
  // Alignment indicators
  if (
    text.includes('mission') || text.includes('focus') || text.includes('alignment') ||
    text.includes('cause') || text.includes('zakat') || text.includes('strategic')
  ) {
    return 'alignment';
  }
  return null;
};

/**
 * Generate fallback improvement suggestion when the narrative lacks one for a dimension.
 */
/** Map pipeline component names to donor-friendly labels */
export function formatComponentName(name: string): string {
  const nameMap: Record<string, string> = {
    'Underserved Space': 'Room for More Donors',
    'Funding Gap': 'Room for More Donors',
    'Funding Gap Opportunity': 'Room for More Donors',
    'Directness': 'Service Delivery',
    'Program Ratio': 'Program Spending',
    'Cause Urgency': 'Problem Severity',
    'Governance': 'Board & Oversight',
  };
  return nameMap[name] || name;
}

/** Convert pipeline shorthand evidence to donor-friendly text */
export function formatEvidenceForDonors(evidence: string): string {
  const removeScoringArtifacts = (text: string): string =>
    text
      // Remove point-style score annotations: (+4), (-2), (+1.5)
      .replace(/\s*\(\s*[+-]\d+(?:\.\d+)?\s*\)/g, '')
      // Remove ratio score annotations: (4/13), (3/5 funding gap), etc.
      .replace(/\s*\(\s*\d+(?:\.\d+)?\s*\/\s*\d+(?:\.\d+)?[^)]*\)/g, '')
      // Normalize separators/spacing after removals
      .replace(/\s*;\s*/g, '; ')
      .replace(/\s{2,}/g, ' ')
      .replace(/;\s*$/g, '')
      .trim();

  // Theory of change: LEVEL
  const tocMatch = evidence.match(/^Theory of change:\s*(\w+)(?:\s*\(.*\))?$/i);
  if (tocMatch) {
    const level = tocMatch[1].toUpperCase();
    const map: Record<string, string> = {
      STRONG: 'Has a well-articulated path from activities to impact',
      CLEAR: 'Clear connection between activities and intended outcomes',
      DEVELOPING: 'Emerging logic connecting programs to outcomes',
      BASIC: 'Basic framework linking activities to goals',
      ABSENT: 'No documented path from activities to impact',
    };
    return map[level] || evidence;
  }

  // Board governance: LEVEL (N members)
  const boardMatch = evidence.match(/^Board governance:\s*(\w+)\s*\((\d+|unknown)\s*members(?:,\s*(.+))?\)$/i);
  if (boardMatch) {
    const level = boardMatch[1].toUpperCase();
    const members = boardMatch[2];
    const suffix = boardMatch[3] ? ` (${boardMatch[3].trim()})` : '';
    const adjective: Record<string, string> = {
      STRONG: 'Strong', ADEQUATE: 'Adequate', MINIMAL: 'Minimal',
      WEAK: 'Limited', BASELINE: 'Baseline',
    };
    const adj = adjective[level] || level.charAt(0) + level.slice(1).toLowerCase();
    return members === 'unknown'
      ? `${adj} board oversight${suffix}`
      : `${adj} board oversight with ${members} members${suffix}`;
  }

  // Program expense ratio: N%
  const progMatch = evidence.match(/^Program expense ratio:\s*(\d+)%$/i);
  if (progMatch) {
    return `${progMatch[1]}% of spending goes directly to programs`;
  }
  if (/^Program expense ratio:\s*unknown$/i.test(evidence)) {
    return 'Program expense ratio not yet available';
  }

  // Working capital: N months (STATUS)
  const wcMatch = evidence.match(/^Working capital:\s*([\d.]+)\s*months?\s*\((\w+)\)$/i);
  if (wcMatch) {
    const months = wcMatch[1];
    const status = wcMatch[2].toLowerCase();
    return `${months} months of operating reserves (${status})`;
  }
  if (/^Working capital:\s*unknown/i.test(evidence)) {
    return 'Operating reserves data not available';
  }

  // Evidence & outcomes: LEVEL
  const evidenceMatch = evidence.match(/^Evidence & outcomes:\s*(\w+)(?:\s*\(.*\))?$/i);
  if (evidenceMatch) {
    const level = evidenceMatch[1].toUpperCase();
    const map: Record<string, string> = {
      VERIFIED: 'Tracks and verifies program outcomes',
      MEASURED: 'Measures program outcomes systematically',
      TRACKED: 'Tracks basic program outputs',
      UNVERIFIED: 'Outcome tracking not yet verified',
    };
    return map[level] || evidence;
  }

  // Delivery model: TYPE
  const deliveryMatch = evidence.match(/^Delivery model:\s*(.+)$/i);
  if (deliveryMatch) {
    const model = deliveryMatch[1].trim();
    const map: Record<string, string> = {
      'Direct Provision': 'Delivers services directly to beneficiaries',
      'Direct Service': 'Provides direct services to those in need',
      'Capacity Building': 'Builds local capacity for sustained impact',
      'Indirect': 'Works through partner organizations',
      'Systemic Change': 'Pursues systemic change for broad impact',
    };
    return map[model] || `Delivers through ${model.toLowerCase()} model`;
  }

  // Cost per beneficiary: $X/beneficiary (rating for CAUSE)
  const cpbMatch = evidence.match(/^\$([\d,.]+)\/beneficiary\s*\((\w+)\s+for\s+(.+)\)$/i);
  if (cpbMatch) {
    const cost = cpbMatch[1];
    const rating = cpbMatch[2].toLowerCase();
    return `Reaches each beneficiary at $${cost} (${rating})`;
  }

  // Cause area: NAME (X/Y)
  const causeMatch = evidence.match(/^Cause area:\s*(.+)\s*\((\d+)\/(\d+)\)$/i);
  if (causeMatch) {
    const cause = causeMatch[1].trim().replace(/_/g, ' ');
    const numerator = Number.parseFloat(causeMatch[2]);
    const denominator = Number.parseFloat(causeMatch[3]);
    const ratio = denominator > 0 ? (numerator / denominator) : 0;
    const qualifier =
      ratio >= 0.66 ? 'a comparatively stronger evidence base'
      : ratio >= 0.4 ? 'a mixed evidence base'
      : 'a more limited evidence base';
    return `Works in ${cause} — ${qualifier}`;
  }

  // Founded YEAR (N years — X/Y)
  const foundedMatch = evidence.match(/^Founded\s+(\d{4})\s*\((\d+)\s*years?\s*—\s*(\d+)\/(\d+)\)$/i);
  if (foundedMatch) {
    return `Established ${foundedMatch[1]} (${foundedMatch[2]} years of track record)`;
  }

  // Revenue: $X (Y/5 funding gap)
  const revMatch = evidence.match(/^Revenue:\s*\$([\d,.]+[KMB]?)\s*\((\d+)\/5\s+funding gap\)$/i);
  if (revMatch) {
    const gapScore = parseInt(revMatch[2]);
    const gapLabel = gapScore >= 4 ? 'high potential for additional donor impact' : 'large organization with established funding';
    return `Annual revenue of $${revMatch[1]} — ${gapLabel}`;
  }
  if (/^Revenue:\s*unknown/i.test(evidence)) {
    return 'Revenue data not yet available';
  }

  // Pass through anything we don't recognize
  return removeScoringArtifacts(evidence);
}

export const generateFallbackImprovement = (
  dimension: string,
  scoreDetails: any
): string | null => {
  if (!scoreDetails) return null;

  const details = scoreDetails[dimension];
  if (!details) return null;

  if (details.rationale) {
    const rationale = details.rationale;

    switch (dimension) {
      case 'impact':
        if (rationale.includes('Program ratio') || rationale.includes('program ratio')) {
          return 'Increase the proportion of funds directed to program services to improve operational efficiency.';
        }
        if (rationale.includes('Working capital') || rationale.includes('working capital')) {
          return 'Build financial reserves to ensure organizational sustainability and operational stability.';
        }
        if (rationale.includes('Data quality') && rationale.includes('low')) {
          return 'Improve public disclosure of financial and operational data to build donor confidence.';
        }
        if (rationale.includes('basic outcome') || rationale.includes('BASIC')) {
          return 'Develop comprehensive outcome tracking systems to demonstrate measurable impact.';
        }
        return 'Focus on improving cost efficiency and maximizing program impact per dollar spent.';

      case 'alignment':
        if (rationale.includes('Counterfactual') && rationale.includes('low')) {
          return 'Clarify unique value proposition and how the organization addresses gaps others cannot fill.';
        }
        return 'Strengthen alignment between stated mission and demonstrated activities.';
    }
  }

  return null;
};

type SummaryLike = {
  ein?: string;
  id?: string;
  archetype?: string | null;
  rubricArchetype?: string | null;
  foundedYear?: number | null;
  evaluationTrack?: string | null;
  amalScore?: number | null;
  amalEvaluation?: CharityProfile['amalEvaluation'];
  ui_signals_v1?: UISignalsV1 | null;
  evidenceQuality?: CharityProfile['evidenceQuality'] | null;
};

const SIGNAL_ORDER: Record<UISignalState, number> = {
  Strong: 3,
  Moderate: 2,
  Limited: 1,
};

const EVIDENCE_STAGE_ORDER: Record<string, number> = {
  Verified: 4,
  Established: 3,
  Building: 2,
  Early: 1,
};

const normalizeConfidenceBadge = (raw: string | null | undefined): 'HIGH' | 'MEDIUM' | 'LOW' => {
  const value = (raw || '').toUpperCase();
  if (value === 'HIGH') return 'HIGH';
  if (value === 'MEDIUM' || value === 'MODERATE') return 'MEDIUM';
  return 'LOW';
};

const getComponentRatio = (
  scoreDetails: CharityProfile['amalEvaluation'] extends { score_details?: infer T } ? T : any,
  dimension: 'impact' | 'alignment' | 'credibility',
  name: string
): number | null => {
  const details: any = (scoreDetails as any)?.[dimension];
  const components: any[] = details?.components || [];
  const comp = components.find(c => typeof c?.name === 'string' && c.name.toLowerCase() === name.toLowerCase());
  if (!comp || typeof comp.scored !== 'number' || typeof comp.possible !== 'number' || comp.possible <= 0) return null;
  return Math.max(0, Math.min(1, comp.scored / comp.possible));
};

export const getArchetypeLabel = (archetypeCode: string | null | undefined): string => {
  if (!archetypeCode) return 'General Profile';
  const key = archetypeCode.toUpperCase();
  const mapped = (uiSignalsConfig.archetype_labels as Record<string, string | undefined>)[key];
  if (mapped) return mapped;
  return key.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
};

export const getArchetypeDescription = (archetypeCode: string | null | undefined): string => {
  if (!archetypeCode) {
    return 'General profile used when there is not enough information to assign a specific archetype.';
  }
  const key = archetypeCode.toUpperCase();
  const mapped = (uiSignalsConfig as any).archetype_descriptions?.[key] as string | undefined;
  if (mapped) return mapped;
  return `Archetype: ${getArchetypeLabel(key)}`;
};

const deriveSignalStates = (charity: SummaryLike): UISignalsV1['signal_states'] => {
  const scoreDetails: any = charity.amalEvaluation?.score_details || {};
  const evidenceRatio = getComponentRatio(scoreDetails, 'impact', 'Evidence & Outcomes') ?? 0;
  const financialRatio = getComponentRatio(scoreDetails, 'impact', 'Financial Health') ?? 0;
  const programRatio = getComponentRatio(scoreDetails, 'impact', 'Program Ratio') ?? 0;
  const governanceRatio = getComponentRatio(scoreDetails, 'impact', 'Governance');

  const donorFitLevel = ((scoreDetails?.alignment?.muslim_donor_fit_level as string | undefined) || 'LOW').toUpperCase();
  const alignmentScore = (scoreDetails?.alignment?.score as number | undefined)
    ?? (charity.amalEvaluation?.confidence_scores?.alignment as number | undefined)
    ?? 0;
  const riskDeduction = (scoreDetails?.risk_deduction as number | undefined)
    ?? (scoreDetails?.risks?.total_deduction as number | undefined)
    ?? 0;

  const evidenceCfg = uiSignalsConfig.signals.evidence;
  const evidence: UISignalState =
    evidenceRatio >= evidenceCfg.strong_ratio
      ? 'Strong'
      : evidenceRatio >= evidenceCfg.moderate_ratio_min
        ? 'Moderate'
        : 'Limited';

  const financialCfg = uiSignalsConfig.signals.financial_health;
  const financial_health: UISignalState =
    financialRatio >= financialCfg.strong_min && programRatio >= financialCfg.strong_min
      ? 'Strong'
      : financialRatio < financialCfg.moderate_min || programRatio < financialCfg.moderate_min
        ? 'Limited'
        : 'Moderate';

  const donorFitCfg = uiSignalsConfig.signals.donor_fit;
  const donor_fit: UISignalState =
    donorFitLevel === 'HIGH' && alignmentScore >= donorFitCfg.strong_alignment_min
      ? 'Strong'
      : donorFitLevel === 'MODERATE' || alignmentScore >= donorFitCfg.moderate_alignment_min
        ? 'Moderate'
        : 'Limited';

  const riskCfg = uiSignalsConfig.signals.risk;
  const risk: UISignalState =
    riskDeduction === 0 && governanceRatio != null && governanceRatio >= riskCfg.governance_strong_min
      ? 'Strong'
      : riskDeduction <= riskCfg.deduction_limited_max || (governanceRatio != null && governanceRatio < riskCfg.governance_moderate_min)
        ? 'Limited'
        : 'Moderate';

  return { evidence, financial_health, donor_fit, risk };
};

const deriveEvidenceStage = (
  confidence: 'HIGH' | 'MEDIUM' | 'LOW',
  foundedYear: number | null | undefined,
  evaluationTrack: string | null | undefined,
  thirdPartyEvaluated: boolean,
  evidenceSignal: UISignalState
): UISignalsV1['evidence_stage'] => {
  const currentYear = new Date().getFullYear();
  const yearsOperating = foundedYear ? currentYear - foundedYear : null;
  if (confidence === 'HIGH' && !!yearsOperating && yearsOperating >= 10 && thirdPartyEvaluated) return 'Verified';
  if (confidence === 'HIGH' || (confidence === 'MEDIUM' && evidenceSignal === 'Strong')) return 'Established';
  if (confidence === 'MEDIUM') return 'Building';
  if (confidence === 'LOW' || evaluationTrack === 'NEW_ORG') return 'Early';
  return 'Early';
};

const deriveCue = (
  score: number,
  confidence: 'HIGH' | 'MEDIUM' | 'LOW',
  riskSignal: UISignalState
): UISignalsV1['recommendation_cue'] => {
  const riskLevel = riskSignal === 'Strong' ? 'LOW' : riskSignal === 'Moderate' ? 'MODERATE' : 'HIGH';
  if (score < uiSignalsConfig.recommendation_cue.limited_match.score_max_exclusive || (confidence === 'LOW' && riskLevel === 'HIGH')) return 'Limited Match';
  if (score >= uiSignalsConfig.recommendation_cue.strong_match.score_min && confidence === 'HIGH' && riskLevel === 'LOW') return 'Strong Match';
  if (score >= uiSignalsConfig.recommendation_cue.good_match.score_min && (confidence === 'HIGH' || confidence === 'MEDIUM') && (riskLevel === 'LOW' || riskLevel === 'MODERATE')) {
    return 'Good Match';
  }
  return 'Mixed Signals';
};

const deriveAssessmentLabel = (
  cue: UISignalsV1['recommendation_cue'],
  stage: UISignalsV1['evidence_stage']
): UISignalsV1['assessment_label'] => {
  if (cue === 'Limited Match' && (stage === 'Verified' || stage === 'Established')) return 'Well Documented Low Score';
  if (cue === 'Strong Match' && (stage === 'Verified' || stage === 'Established')) return 'High Conviction';
  if (cue === 'Good Match' && (stage === 'Verified' || stage === 'Established' || stage === 'Building')) return 'Promising';
  if (cue === 'Mixed Signals') return 'Context Dependent';
  return 'Limited Basis';
};

const buildCueRationale = (cue: UISignalsV1['recommendation_cue']): string => {
  if (cue === 'Strong Match') return 'Strong donor fit, low risk profile, and credible supporting evidence for outcomes.';
  if (cue === 'Good Match') return 'Good donor alignment with manageable risk. Evidence quality is solid but still evolving in places.';
  if (cue === 'Limited Match') return 'Limited match due to weaker results and/or higher uncertainty; review methodology details before deciding.';
  return 'Context dependent profile. Consider cause fit, risk profile, and evidence maturity before deciding.';
};

export const deriveUISignalsFromSummary = (charity: SummaryLike): UISignalsV1 => {
  const scoreDetails: any = charity.amalEvaluation?.score_details || {};
  const confidence = normalizeConfidenceBadge(
    scoreDetails?.data_confidence?.badge || charity.amalEvaluation?.confidence_tier || null
  );
  const signals = deriveSignalStates(charity);
  const thirdPartyEvaluated = Boolean(charity.evidenceQuality?.thirdPartyEvaluated);
  const stage = deriveEvidenceStage(
    confidence,
    charity.foundedYear,
    charity.evaluationTrack,
    thirdPartyEvaluated,
    signals.evidence
  );
  const score = charity.amalScore ?? charity.amalEvaluation?.amal_score ?? 0;
  const cue = deriveCue(score, confidence, signals.risk);
  const archetypeCode = charity.archetype || charity.rubricArchetype || null;

  return {
    schema_version: uiSignalsConfig.schema_version,
    config_version: UI_SIGNALS_CONFIG_VERSION,
    config_hash: UI_SIGNALS_CONFIG_HASH,
    assessment_label: deriveAssessmentLabel(cue, stage),
    archetype_code: archetypeCode,
    archetype_label: getArchetypeLabel(archetypeCode),
    evidence_stage: stage,
    signal_states: signals,
    recommendation_cue: cue,
    recommendation_rationale: buildCueRationale(cue),
    used_fallback: true,
    fallback_reasons: ['missing_ui_signals_v1'],
  };
};

export const deriveUISignalsFromCharity = (charity: CharityProfile): UISignalsV1 => {
  if (charity.ui_signals_v1) return charity.ui_signals_v1;
  return deriveUISignalsFromSummary({
    id: charity.id,
    ein: charity.ein,
    archetype: charity.archetype,
    foundedYear: charity.foundedYear,
    evaluationTrack: charity.evaluationTrack,
    amalEvaluation: charity.amalEvaluation,
    amalScore: charity.amalEvaluation?.amal_score ?? 0,
    evidenceQuality: charity.evidenceQuality,
  });
};

export const getEvidenceStageRank = (stage: string | null | undefined): number => {
  if (!stage) return 0;
  return EVIDENCE_STAGE_ORDER[stage] || 0;
};

export const getSignalStrengthScore = (signals: UISignalsV1['signal_states']): number => {
  return (
    SIGNAL_ORDER[signals.evidence] +
    SIGNAL_ORDER[signals.financial_health] +
    SIGNAL_ORDER[signals.donor_fit] +
    SIGNAL_ORDER[signals.risk]
  );
};

export const getRecommendationCue = (charity: CharityProfile): UISignalsV1['recommendation_cue'] => {
  return deriveUISignalsFromCharity(charity).recommendation_cue;
};

export const getEvidenceStage = (charity: CharityProfile): UISignalsV1['evidence_stage'] => {
  return deriveUISignalsFromCharity(charity).evidence_stage;
};

export const getSignalStates = (charity: CharityProfile): UISignalsV1['signal_states'] => {
  return deriveUISignalsFromCharity(charity).signal_states;
};

export const getAssessmentLabel = (charity: CharityProfile): UISignalsV1['assessment_label'] => {
  return deriveUISignalsFromCharity(charity).assessment_label;
};

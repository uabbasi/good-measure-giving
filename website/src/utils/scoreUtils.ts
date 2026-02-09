/**
 * Shared score analysis utilities
 * Extracted from TerminalView for reuse across ScoreBreakdown, ImprovementGuide, etc.
 */

import { cleanNarrativeText } from './cleanNarrativeText';

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
    'Underserved Space': 'Funding Gap Opportunity',
    'Funding Gap': 'Funding Gap',
  };
  return nameMap[name] || name;
}

/** Convert pipeline shorthand evidence to donor-friendly text */
export function formatEvidenceForDonors(evidence: string): string {
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
    return `Works in ${cause} — a well-studied cause area (${causeMatch[2]}/${causeMatch[3]} evidence rating)`;
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
  return evidence;
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

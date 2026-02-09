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

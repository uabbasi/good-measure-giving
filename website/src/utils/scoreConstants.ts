/**
 * Score threshold constants and helpers
 * Centralizes score-related logic for consistency across components
 */

// Score thresholds
export const SCORE_THRESHOLD_INSUFFICIENT_DATA = 30; // Below this: truly data-deficient
export const SCORE_THRESHOLD_MODERATE = 60;          // Below this: developing/amber
export const SCORE_THRESHOLD_TOP_RATED = 75;         // Above this: top-tier/emerald

// Legacy alias — kept to avoid mass rename across codebase
export const SCORE_THRESHOLD_UNDER_REVIEW = SCORE_THRESHOLD_INSUFFICIENT_DATA;

/**
 * Check if a charity has insufficient data (score below publication threshold).
 * Only truly data-deficient charities (<30) are hidden.
 */
export const isInsufficientData = (score: number | undefined): boolean => {
  return (score ?? 0) < SCORE_THRESHOLD_INSUFFICIENT_DATA;
};

/** Legacy alias for isInsufficientData */
export const isUnderReview = isInsufficientData;

/**
 * Get styling for the "Insufficient Data" badge
 */
export const getUnderReviewStyles = (isDark: boolean) => ({
  bg: isDark ? 'bg-amber-900/30' : 'bg-amber-50',
  text: isDark ? 'text-amber-400' : 'text-amber-700',
  border: isDark ? 'border-amber-800' : 'border-amber-200',
});

/**
 * Get color class for numeric score display.
 * 4-tier system: emerald (75+), blue (60-74), amber (30-59), rose (<30)
 */
export const getScoreColorClass = (score: number, isDark: boolean): string => {
  if (score >= SCORE_THRESHOLD_TOP_RATED) {
    return isDark ? 'text-emerald-400' : 'text-emerald-500';
  }
  if (score >= SCORE_THRESHOLD_MODERATE) {
    return isDark ? 'text-blue-400' : 'text-blue-500';
  }
  if (score >= SCORE_THRESHOLD_INSUFFICIENT_DATA) {
    return isDark ? 'text-amber-400' : 'text-amber-500';
  }
  return isDark ? 'text-rose-400' : 'text-rose-500';
};

/**
 * Get background color class for score progress bars.
 * Same tier system as text colors.
 */
export const getScoreBarColorClass = (score: number, max: number): string => {
  const pct = max > 0 ? (score / max) * 100 : 0;
  if (pct >= 75) return 'bg-emerald-500';
  if (pct >= 60) return 'bg-blue-500';
  if (pct >= 40) return 'bg-amber-500';
  return 'bg-rose-400';
};

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

// Qualitative signal labels
export const EVIDENCE_STAGES = ['Verified', 'Established', 'Building', 'Early'] as const;
export const SIGNAL_STATES = ['Strong', 'Moderate', 'Limited'] as const;
export const RECOMMENDATION_CUES = ['Strong Match', 'Good Match', 'Mixed Signals', 'Limited Match'] as const;

export const getEvidenceStageLabel = (stage: string): string => {
  if (stage === 'Early') return 'Limited Evidence';
  return stage;
};

/**
 * Color classes for evidence-stage badges.
 * Designed for scanability:
 * - evidence chips are lower-ink (white/neutral background + colored border)
 * - high contrast text for readability on light cards
 */
export const getEvidenceStageClasses = (stage: string, isDark: boolean): string => {
  if (stage === 'Verified') return isDark ? 'bg-slate-900/30 text-cyan-300 border-cyan-700/60' : 'bg-white text-cyan-800 border-cyan-300';
  if (stage === 'Established') return isDark ? 'bg-slate-900/30 text-indigo-300 border-indigo-700/60' : 'bg-white text-indigo-800 border-indigo-300';
  if (stage === 'Building') return isDark ? 'bg-slate-900/30 text-amber-300 border-amber-700/60' : 'bg-white text-amber-800 border-amber-300';
  return isDark ? 'bg-slate-900/30 text-slate-300 border-slate-600' : 'bg-white text-slate-700 border-slate-300';
};

type WalletType = 'zakat' | 'sadaqah';
type CauseCategoryTone = 'population' | 'intervention' | 'geography' | 'approach';

const TAG_PALETTES = {
  giving: {
    zakat: {
      dark: 'bg-emerald-900/45 text-emerald-200 border-emerald-700/70',
      light: 'bg-emerald-100 text-emerald-800 border-emerald-300',
    },
    sadaqah: {
      dark: 'bg-teal-900/45 text-teal-200 border-teal-700/70',
      light: 'bg-teal-100 text-teal-800 border-teal-300',
    },
  },
  how: {
    emergency: {
      dark: 'bg-rose-900/45 text-rose-200 border-rose-700/70',
      light: 'bg-rose-100 text-rose-800 border-rose-300',
    },
    policy: {
      dark: 'bg-violet-900/45 text-violet-200 border-violet-700/70',
      light: 'bg-violet-100 text-violet-800 border-violet-300',
    },
    research: {
      dark: 'bg-fuchsia-900/45 text-fuchsia-200 border-fuchsia-700/70',
      light: 'bg-fuchsia-100 text-fuchsia-800 border-fuchsia-300',
    },
    education: {
      dark: 'bg-indigo-900/45 text-indigo-200 border-indigo-700/70',
      light: 'bg-indigo-100 text-indigo-800 border-indigo-300',
    },
    grantmaking: {
      dark: 'bg-purple-900/45 text-purple-200 border-purple-700/70',
      light: 'bg-purple-100 text-purple-800 border-purple-300',
    },
    directServices: {
      dark: 'bg-violet-900/40 text-violet-200 border-violet-700/70',
      light: 'bg-violet-100 text-violet-800 border-violet-300',
    },
    community: {
      dark: 'bg-indigo-900/40 text-indigo-200 border-indigo-700/70',
      light: 'bg-indigo-100 text-indigo-800 border-indigo-300',
    },
  },
  detailCategories: {
    population: {
      dark: 'bg-fuchsia-900/35 text-fuchsia-300 border-fuchsia-700/50',
      light: 'bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200',
    },
    intervention: {
      dark: 'bg-orange-900/35 text-orange-300 border-orange-700/50',
      light: 'bg-orange-50 text-orange-700 border-orange-200',
    },
    geography: {
      dark: 'bg-sky-900/35 text-sky-300 border-sky-700/50',
      light: 'bg-sky-50 text-sky-700 border-sky-200',
    },
    approach: {
      dark: 'bg-violet-900/35 text-violet-300 border-violet-700/50',
      light: 'bg-violet-50 text-violet-700 border-violet-200',
    },
  },
} as const;

const getPaletteClasses = (palette: { dark: string; light: string }, isDark: boolean): string => {
  return isDark ? palette.dark : palette.light;
};

export const getGivingTagClasses = (walletType: WalletType, isDark: boolean): string => {
  return getPaletteClasses(TAG_PALETTES.giving[walletType], isDark);
};

export const getHowTagClasses = (label: string, isDark: boolean): string => {
  if (label === 'Emergency Relief') return getPaletteClasses(TAG_PALETTES.how.emergency, isDark);
  if (label === 'Advocacy & Policy') return getPaletteClasses(TAG_PALETTES.how.policy, isDark);
  if (label === 'Research & Policy') return getPaletteClasses(TAG_PALETTES.how.research, isDark);
  if (label === 'Education') return getPaletteClasses(TAG_PALETTES.how.education, isDark);
  if (label === 'Grantmaking') return getPaletteClasses(TAG_PALETTES.how.grantmaking, isDark);
  if (label === 'Direct Services') return getPaletteClasses(TAG_PALETTES.how.directServices, isDark);
  return getPaletteClasses(TAG_PALETTES.how.community, isDark);
};

export const getCauseCategoryTagClasses = (category: CauseCategoryTone, isDark: boolean): string => {
  return getPaletteClasses(TAG_PALETTES.detailCategories[category], isDark);
};

/**
 * Color classes for recommendation cue badges.
 */
export const getRecommendationCueClasses = (cue: string, isDark: boolean): string => {
  if (cue === 'Strong Match') return isDark ? 'bg-emerald-900/40 text-emerald-300 border-emerald-800/60' : 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (cue === 'Good Match') return isDark ? 'bg-blue-900/40 text-blue-300 border-blue-800/60' : 'bg-blue-50 text-blue-700 border-blue-200';
  if (cue === 'Mixed Signals') return isDark ? 'bg-amber-900/40 text-amber-300 border-amber-800/60' : 'bg-amber-50 text-amber-700 border-amber-200';
  return isDark ? 'bg-slate-800 text-slate-300 border-slate-700' : 'bg-slate-100 text-slate-600 border-slate-200';
};

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

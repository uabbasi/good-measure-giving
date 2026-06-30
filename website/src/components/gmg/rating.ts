// Maps numeric GMG scores onto the Consumer-Reports-style Harvey-ball rating
// scale. The number stays the source of truth underneath; the ball is the
// primary visual, the number the secondary detail.

import type { GmgPalette } from './tokens';

export type Rating = 'Strong' | 'Good' | 'Moderate' | 'Fair' | 'Weak';

export const RATING_SCALE: Record<Rating, { fill: number; tone: keyof GmgPalette }> = {
  Strong: { fill: 1.0, tone: 'pos' },
  Good: { fill: 0.75, tone: 'pos' },
  Moderate: { fill: 0.5, tone: 'caution' },
  Fair: { fill: 0.25, tone: 'caution' },
  Weak: { fill: 0.0, tone: 'neg' },
};

// Risk level → semantic tone (lower risk is positive).
export const riskTone = (level: string): keyof GmgPalette => {
  const l = (level || '').toUpperCase();
  if (l.startsWith('LOW')) return 'pos';
  if (l.startsWith('HIGH')) return 'neg';
  return 'caution';
};

// Thresholds are expressed as a fraction of the maximum (tunable).
export const ratingFromFraction = (frac: number): Rating => {
  if (frac >= 0.8) return 'Strong';
  if (frac >= 0.64) return 'Good';
  if (frac >= 0.48) return 'Moderate';
  if (frac >= 0.32) return 'Fair';
  return 'Weak';
};

// Each evaluation dimension (Impact, Alignment) is scored 0–50.
export const ratingFromDimension = (score: number, max = 50): Rating =>
  ratingFromFraction(max > 0 ? score / max : 0);

// A single rubric criterion carries its own `scored` / `possible`.
export const ratingFromCriterion = (scored: number, possible: number): Rating =>
  ratingFromFraction(possible > 0 ? scored / possible : 0);

// The overall GMG score (0–100) as a Harvey band. Thresholds are tuned to the
// real score distribution (which clusters ~40–70), so the bands are meaningful
// and well-spread rather than bunched: Strong ~11% · Good ~19% · Moderate ~43% ·
// Fair ~23% · Weak ~5%. Shown as a band, not a precise rank.
export const ratingFromGmgScore = (score: number): Rating => {
  if (score >= 78) return 'Strong';
  if (score >= 67) return 'Good';
  if (score >= 54) return 'Moderate';
  if (score >= 42) return 'Fair';
  return 'Weak';
};

export const ratingColor = (rating: Rating, p: GmgPalette): string => {
  const tone = RATING_SCALE[rating].tone;
  return p[tone] as string;
};

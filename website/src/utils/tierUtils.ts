/**
 * T004: Tier utility functions for charity classification
 *
 * Provides helpers for working with the three-tier charity system:
 * - rich: Prominently featured charities with comprehensive narratives
 * - baseline: Standard charities searchable on browse page
 * - hidden: Not publicly listed, accessible only via direct URL
 */

import type { CharityTier, CharityProfile } from '../../types';

/**
 * Check if a charity is in the rich tier (prominently featured)
 */
export function isRichTier(charity: CharityProfile): boolean {
  return charity.tier === 'rich';
}

/**
 * Check if a charity is in the baseline tier (standard listing)
 */
export function isBaselineTier(charity: CharityProfile): boolean {
  return charity.tier === 'baseline';
}

/**
 * Check if a charity is in the hidden tier (direct URL access only)
 */
export function isHiddenTier(charity: CharityProfile): boolean {
  return charity.tier === 'hidden';
}

/**
 * Check if a charity should be publicly visible (not hidden)
 */
export function isPubliclyVisible(charity: CharityProfile): boolean {
  return charity.tier !== 'hidden';
}

/**
 * Filter charities by tier
 */
export function filterByTier(charities: CharityProfile[], tier: CharityTier): CharityProfile[] {
  return charities.filter(c => c.tier === tier);
}

/**
 * Get rich tier charities from a list
 */
export function getRichCharities(charities: CharityProfile[]): CharityProfile[] {
  return filterByTier(charities, 'rich');
}

/**
 * Get baseline tier charities from a list
 */
export function getBaselineCharities(charities: CharityProfile[]): CharityProfile[] {
  return filterByTier(charities, 'baseline');
}

/**
 * Get publicly visible charities (rich + baseline, excludes hidden)
 */
export function getPublicCharities(charities: CharityProfile[]): CharityProfile[] {
  return charities.filter(isPubliclyVisible);
}

/**
 * Get tier display label for UI
 */
export function getTierLabel(tier: CharityTier): string {
  switch (tier) {
    case 'rich':
      return 'Featured';
    case 'baseline':
      return 'Evaluated';
    case 'hidden':
      return 'Not Publicly Listed';
    default:
      return 'Unknown';
  }
}

/**
 * Get tier badge color class for styling
 */
export function getTierBadgeClass(tier: CharityTier): string {
  switch (tier) {
    case 'rich':
      return 'bg-amber-100 text-amber-800 border-amber-200';
    case 'baseline':
      return 'bg-gray-100 text-gray-700 border-gray-200';
    case 'hidden':
      return 'bg-red-50 text-red-600 border-red-200';
    default:
      return 'bg-gray-100 text-gray-600 border-gray-200';
  }
}

/**
 * Formatting utilities for display
 */

import type { CharityProfile } from '../../types';

/**
 * Get formatted address from charity location data.
 * Returns full address like "100 N Central Expy, Richardson, TX 75080"
 * or falls back to "City, State" if street address isn't available.
 */
export function getCharityAddress(charity: CharityProfile): string | null {
  const loc = charity.location;
  const city = loc?.city || charity.city;
  const state = loc?.state || charity.state;
  if (!city && !state) return null;

  const parts: string[] = [];
  if (loc?.address) parts.push(titleCase(loc.address));
  if (city) parts.push(city);
  // Combine state + zip as one unit
  const stateZip = [state, loc?.zip?.split('-')[0]].filter(Boolean).join(' ');
  if (stateZip) parts.push(stateZip);

  return parts.join(', ');
}

/**
 * Title-case a string (e.g., "100 N CENTRAL EXPY" → "100 N Central Expy")
 */
function titleCase(s: string): string {
  return s.replace(/\w\S*/g, (w) =>
    w.length <= 2 ? w : w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()
  );
}

/**
 * Format revenue for compact display: $18M, $1.2M, $450K
 */
export function formatShortRevenue(revenue: number | null | undefined): string | null {
  if (!revenue || revenue <= 0) return null;
  if (revenue >= 1_000_000_000) return `$${(revenue / 1_000_000_000).toFixed(1)}B`;
  if (revenue >= 1_000_000) return `$${(revenue / 1_000_000).toFixed(1)}M`;
  if (revenue >= 1_000) return `$${Math.round(revenue / 1_000)}K`;
  return `$${revenue}`;
}

/**
 * Format currency with full precision: $1,234,567
 */
export function formatCurrency(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

/**
 * Format currency with decimals: $1,234.56
 */
export function formatCurrencyWithCents(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

/**
 * Format percentage: 85.5%
 */
export function formatPercent(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined) return '-';
  // Handle both 0-1 ratios and 0-100 percentages
  const pct = value > 1 ? value : value * 100;
  return `${pct.toFixed(decimals)}%`;
}

/**
 * Format date for display: Jan 15, 2024
 */
export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '-';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/**
 * Format date as relative time: "2 days ago", "3 months ago"
 */
export function formatRelativeDate(dateString: string | null | undefined): string {
  if (!dateString) return '-';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
  return `${Math.floor(diffDays / 365)} years ago`;
}

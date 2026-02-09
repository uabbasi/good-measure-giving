/**
 * Shared wallet tag utilities
 * Centralizes wallet tag formatting and styling to ensure consistency
 *
 * Binary classification system:
 * - ZAKAT-ELIGIBLE: Charity claims zakat eligibility on their website
 * - SADAQAH-ELIGIBLE: All other charities (default)
 */

export type WalletTagType = 'zakat' | 'sadaqah' | 'insufficient';

/**
 * Determine the wallet tag type from a raw tag string
 */
export const getWalletType = (tag: string | undefined): WalletTagType => {
  if (!tag) return 'sadaqah';

  if (tag.includes('ZAKAT')) {
    return 'zakat';
  }
  if (tag.includes('INSUFFICIENT-DATA')) {
    return 'insufficient';
  }
  return 'sadaqah';
};

/**
 * Get human-readable label for wallet tag
 */
export const formatWalletTag = (tag: string | undefined): string => {
  const type = getWalletType(tag);
  switch (type) {
    case 'zakat': return 'Zakat Eligible';
    case 'insufficient': return 'Insufficient Data';
    default: return 'Sadaqah';
  }
};

/**
 * Get Tailwind background color class for wallet tag
 */
export const getWalletBgColor = (tag: string | undefined): string => {
  const type = getWalletType(tag);
  switch (type) {
    case 'zakat': return 'bg-emerald-500';
    default: return 'bg-slate-400';
  }
};

/**
 * Get full styling object for wallet tag badge
 */
export const getWalletStyles = (tag: string | undefined, isDark: boolean) => {
  const type = getWalletType(tag);

  switch (type) {
    case 'zakat':
      return {
        bg: isDark ? 'bg-emerald-900/30' : 'bg-emerald-50',
        text: isDark ? 'text-emerald-400' : 'text-emerald-700',
        border: isDark ? 'border-emerald-800' : 'border-emerald-200',
      };
    case 'insufficient':
      return {
        bg: isDark ? 'bg-slate-800' : 'bg-slate-100',
        text: isDark ? 'text-slate-400' : 'text-slate-600',
        border: isDark ? 'border-slate-700' : 'border-slate-200',
      };
    default: // sadaqah
      return {
        bg: isDark ? 'bg-slate-800' : 'bg-slate-100',
        text: isDark ? 'text-slate-400' : 'text-slate-600',
        border: isDark ? 'border-slate-700' : 'border-slate-200',
      };
  }
};

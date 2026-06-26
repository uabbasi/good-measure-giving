import type { ZakatAssets, ZakatLiabilities } from '../../types';

/**
 * Fallback nisab in USD — 85g gold valued as of June 26, 2026
 * (gold spot ~$4,073/oz → $11,130 per 85g, rounded down conservatively).
 *
 * The public zakat calculator pages refresh nisab live via useNisab()
 * from gold-api.com. This constant is the last-resort fallback used when
 * (a) the API is unreachable, (b) the response is malformed, or
 * (c) the ZakatEstimator modal renders before a live value is fetched.
 *
 * It is also the value baked into the prerendered (SSR) gold & silver chart,
 * so keep it close to current spot — stale values get indexed by Google.
 *
 * When updating: bump to current 85g-of-gold value in USD, rounded down
 * slightly for conservatism (better to under-estimate nisab than over-).
 */
export const NISAB_USD = 11_100;

/**
 * Fallback silver price in USD per gram — consistent with the NISAB_USD epoch
 * (silver spot ~$59/oz on June 26, 2026 → ~$1.90/g).
 *
 * Used as the last-resort fallback and the server-render value for the
 * gold & silver zakat chart, which refreshes live via useSilverPricePerGram()
 * from gold-api.com (XAG). When updating: bump to current silver spot per gram.
 */
export const SILVER_USD_PER_GRAM = 1.9;

export const ZAKAT_RATE = 0.025;

export interface ZakatEstimate {
  totalAssets: number;
  totalLiabilities: number;
  netZakatable: number;
  zakatAmount: number;
  isAboveNisab: boolean;
}

/**
 * Calculate zakat owed on given assets and liabilities.
 * Returns 0 if net zakatable wealth is below nisab.
 *
 * @param nisabUsd Optional override of the nisab threshold. Defaults to the
 *   hardcoded NISAB_USD constant. Pass a live value (e.g. from useNisab())
 *   when you want the threshold to track current gold spot price.
 */
export function calculateZakat(
  assets: ZakatAssets,
  liabilities: ZakatLiabilities = {},
  nisabUsd: number = NISAB_USD,
): ZakatEstimate {
  const totalAssets =
    (assets.cash ?? 0) +
    (assets.gold ?? 0) +
    (assets.silver ?? 0) +
    (assets.stocks ?? 0) +
    (assets.businessInventory ?? 0) +
    (assets.receivables ?? 0) +
    (assets.rentalIncome ?? 0) +
    (assets.other ?? 0);

  const totalLiabilities =
    (liabilities.debts ?? 0) +
    (liabilities.loans ?? 0) +
    (liabilities.creditCards ?? 0) +
    (liabilities.other ?? 0);

  const netZakatable = Math.max(0, totalAssets - totalLiabilities);
  const isAboveNisab = netZakatable >= nisabUsd;
  const zakatAmount = isAboveNisab ? Math.round(netZakatable * ZAKAT_RATE) : 0;

  return { totalAssets, totalLiabilities, netZakatable, zakatAmount, isAboveNisab };
}

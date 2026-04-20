import type { ZakatAssets, ZakatLiabilities } from '../../types';

/** Approximate nisab in USD — 85g gold at ~$82/g (April 2026). */
export const NISAB_USD = 6_970;

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

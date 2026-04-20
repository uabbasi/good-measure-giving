/**
 * SEO helpers for charity detail pages.
 * Title/meta/FAQ templates driven by charity data fields.
 * Pure functions only — no I/O, no mutation.
 */

export type ZakatStatus = 'ZAKAT_ELIGIBLE' | 'SADAQAH_ONLY' | 'UNCLEAR' | 'NEW_ORG';

export interface ZakatStatusInput {
  walletTag: string | null;
  zakatClassification: string | null;
}

export function classifyZakatStatus(input: ZakatStatusInput): ZakatStatus {
  const tag = (input.walletTag ?? '').toUpperCase();
  if (tag.includes('ZAKAT-ELIGIBLE')) return 'ZAKAT_ELIGIBLE';
  if (tag === 'SADAQAH-ELIGIBLE') return 'SADAQAH_ONLY';
  return 'UNCLEAR';
}

export interface CharityTitleInput {
  name: string;
  score: number | null;
  zakatStatus: ZakatStatus;
}

export function buildCharityTitle(input: CharityTitleInput): string {
  if (input.zakatStatus === 'NEW_ORG') {
    return `${input.name} Review: Early-Stage Muslim Charity | GMG`;
  }
  const scorePart = input.score != null ? `${input.score}/100 Rating` : 'Evaluated';
  if (input.zakatStatus === 'ZAKAT_ELIGIBLE' && input.score != null) {
    return `Is ${input.name} Zakat Eligible? ${input.score}/100 Rating & Review | GMG`;
  }
  if (input.score != null) {
    return `${input.name} Review: ${scorePart} & Zakat Status | GMG`;
  }
  return `${input.name} Review: ${scorePart} | GMG`;
}

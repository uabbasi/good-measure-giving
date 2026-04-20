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

export interface CharityDescriptionInput {
  name: string;
  score: number | null;
  zakatStatus: ZakatStatus;
  missionFragment: string;
}

function truncate(text: string, max: number): string {
  return text.length <= max ? text : text.slice(0, max - 1) + '\u2026';
}

export function buildCharityDescription(input: CharityDescriptionInput): string {
  let lead: string;
  switch (input.zakatStatus) {
    case 'ZAKAT_ELIGIBLE':
      lead = `${input.name} is classified as Zakat Eligible by Good Measure Giving.`;
      break;
    case 'SADAQAH_ONLY':
      lead = `${input.name} is sadaqah-eligible but not zakat-eligible per Good Measure Giving.`;
      break;
    case 'NEW_ORG':
      lead = `${input.name} is an early-stage Muslim charity, too new to rate numerically.`;
      break;
    default:
      lead = `${input.name} evaluated by Good Measure Giving.`;
  }
  const scorePart = input.score != null ? ` Rated ${input.score}/100 on impact and transparency.` : '';
  const raw = `${lead}${scorePart} ${input.missionFragment}`.trim();
  return truncate(raw, 160);
}

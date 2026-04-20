/**
 * SEO helpers for charity detail pages.
 * Title/meta/FAQ templates driven by charity data fields.
 * Pure functions only — no I/O, no mutation.
 */

import type { FaqPair } from './schema';

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
      lead = `${input.name} publicly claims to accept zakat.`;
      break;
    case 'SADAQAH_ONLY':
      lead = `${input.name} does not publicly claim zakat acceptance (sadaqah-eligible).`;
      break;
    case 'NEW_ORG':
      lead = `${input.name} is an early-stage Muslim charity, too new to rate numerically.`;
      break;
    default:
      lead = `${input.name} evaluated by Good Measure Giving.`;
  }
  const scorePart = input.score != null ? ` Good Measure Giving score: ${input.score}/100 (Impact + Alignment).` : '';
  const raw = `${lead}${scorePart} ${input.missionFragment}`.trim();
  return truncate(raw, 160);
}

export interface CharityFaqInput {
  name: string;
  score: number | null;
  zakatStatus: ZakatStatus;
  mission: string;
  city: string | null;
  state: string | null;
}

export function buildCharityFaqPairs(input: CharityFaqInput): FaqPair[] {
  const zakatQ = `Does ${input.name} accept zakat?`;
  let zakatA: string;
  switch (input.zakatStatus) {
    case 'ZAKAT_ELIGIBLE':
      zakatA = `${input.name} publicly claims to accept zakat donations (via a dedicated zakat page, calculator, or fund). Good Measure Giving passes this designation along but does not render a fiqh verdict — the determination of whether their programs meet zakat-eligibility criteria is yours, guided by your scholar.`;
      break;
    case 'SADAQAH_ONLY':
      zakatA = `${input.name} does not publicly claim to accept zakat, so Good Measure Giving tags it Sadaqah-Eligible. That doesn't necessarily mean your scholar would disagree — it means the organization itself hasn't stated a zakat position. Sadaqah is always appropriate for any charitable purpose.`;
      break;
    case 'NEW_ORG':
      zakatA = `${input.name} is an early-stage organization. Good Measure Giving has not yet assessed a zakat-acceptance claim. Check their website directly for the most current zakat policy.`;
      break;
    default:
      zakatA = `${input.name}'s zakat-acceptance stance is unclear in public sources. Good Measure Giving surfaces the charity's own claim when stated; when it's not clearly stated, we flag it as unclear rather than guess.`;
  }

  const ratingQ = `What is ${input.name}'s Good Measure Giving score?`;
  const ratingA = input.score != null
    ? `Good Measure Giving scores ${input.name} ${input.score}/100. The score combines Impact (how effectively the charity is set up to deliver results — cost efficiency, evidence practices, financial health, governance) and Alignment (fit for Muslim donors — cause urgency, donor fit, funding gap, track record), with up to 10 points deducted for red flags.`
    : `${input.name} is evaluated by Good Measure Giving but does not yet have a numeric score.`;

  const locationQ = `Where is ${input.name} based and what do they do?`;
  const locationParts: string[] = [];
  if (input.city && input.state) {
    locationParts.push(`${input.name} is based in ${input.city}, ${input.state}.`);
  } else {
    locationParts.push(`${input.name} operates as an independent Muslim charity.`);
  }
  if (input.mission) {
    locationParts.push(input.mission);
  }
  const locationA = locationParts.join(' ');

  return [
    { question: zakatQ, answer: zakatA },
    { question: ratingQ, answer: ratingA },
    { question: locationQ, answer: locationA },
  ];
}

export interface SimilarCharityCandidate {
  ein: string;
  name: string;
  category: string;
  amalScore: number | null;
  zakatStatus: ZakatStatus;
}

export interface SimilarSelectorInput {
  currentEin: string;
  category: string;
  zakatStatus: ZakatStatus;
  pool: SimilarCharityCandidate[];
  limit: number;
}

export function selectSimilarCharities(input: SimilarSelectorInput): SimilarCharityCandidate[] {
  return input.pool
    .filter((c) => c.ein !== input.currentEin)
    .filter((c) => c.category === input.category)
    .filter((c) => c.zakatStatus === input.zakatStatus)
    .sort((a, b) => (b.amalScore ?? 0) - (a.amalScore ?? 0))
    .slice(0, input.limit);
}

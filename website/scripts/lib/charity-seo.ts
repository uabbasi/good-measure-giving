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

export interface CharityFaqInput {
  name: string;
  score: number | null;
  zakatStatus: ZakatStatus;
  mission: string;
  city: string | null;
  state: string | null;
}

export function buildCharityFaqPairs(input: CharityFaqInput): FaqPair[] {
  const zakatQ = `Is ${input.name} zakat eligible?`;
  let zakatA: string;
  switch (input.zakatStatus) {
    case 'ZAKAT_ELIGIBLE':
      zakatA = `Yes — ${input.name} is classified as Zakat Eligible by Good Measure Giving based on its programs and beneficiary alignment with the 8 zakat categories.`;
      break;
    case 'SADAQAH_ONLY':
      zakatA = `No — ${input.name} is sadaqah-eligible but does not meet the criteria for zakat eligibility in Good Measure Giving's evaluation.`;
      break;
    case 'NEW_ORG':
      zakatA = `${input.name} is an early-stage organization; zakat eligibility has not yet been determined.`;
      break;
    default:
      zakatA = `${input.name}'s zakat eligibility is currently unclear in Good Measure Giving's evaluation.`;
  }

  const ratingQ = `What is ${input.name}'s impact rating?`;
  const ratingA = input.score != null
    ? `Good Measure Giving rates ${input.name} ${input.score}/100 on impact, alignment, and financial transparency.`
    : `${input.name} is evaluated by Good Measure Giving but does not yet have a numeric rating.`;

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

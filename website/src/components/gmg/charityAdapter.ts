// Adapts a real CharityProfile (exported JSON shape) into the fields the GMG
// "Modern" detail page renders. Tolerant of missing data — every field has a
// sensible fallback so the proof surface renders for any charity/tier.

import { Rating, ratingFromDimension, ratingFromCriterion } from './rating';

export interface GmgRow {
  ein: string;
  name: string;
  cause: string;
  region: string;
  wallet: string;
  walletIsZakat: boolean;
  impact: Rating;
  alignment: Rating;
  amalScore: number;
  risk: string;
  verification: string;
  programPct: number | null;
}

const stripTags = (s: unknown): string =>
  typeof s === 'string'
    ? s
        .replace(/<cite[^>]*>(.*?)<\/cite>/gis, '$1')
        .replace(/<[^>]+>/g, '')
        .replace(/\s+/g, ' ')
        .trim()
    : '';

// Coerce numbers OR numeric strings (the exported JSON stores some financial
// figures as strings, e.g. workingCapitalMonths: "18.00").
const num = (v: unknown, d = 0): number => {
  const n = typeof v === 'number' ? v : typeof v === 'string' ? parseFloat(v) : NaN;
  return Number.isFinite(n) ? n : d;
};
const numOrNull = (v: unknown): number | null => {
  const n = num(v, NaN);
  return Number.isFinite(n) ? n : null;
};

export interface GmgCriterion {
  name: string;
  rating: Rating;
  scored: number;
  possible: number;
  note: string;
  improvement?: string;
  improvementValue: number;
}

export interface GmgDimension {
  overall: Rating;
  score: number;
  max: number;
  criteria: GmgCriterion[];
  flag?: string;
}

// `overallScore` comes from confidence_scores (authoritative, present on every
// record, and what the index uses); criteria come from score_details.components.
const buildDimension = (raw: any, overallScore: unknown, max = 50): GmgDimension => {
  const score = overallScore != null ? num(overallScore) : num(raw?.score);
  const components: any[] = Array.isArray(raw?.components) ? raw.components : [];
  const criteria: GmgCriterion[] = components.map((c) => ({
    name: c?.name ?? 'Criterion',
    rating: ratingFromCriterion(num(c?.scored), num(c?.possible, 1)),
    scored: num(c?.scored),
    possible: num(c?.possible),
    note: stripTags(c?.evidence) || '—',
    improvement: c?.improvement_suggestion ? stripTags(c.improvement_suggestion) : undefined,
    improvementValue: num(c?.improvement_value),
  }));
  // Pick the most valuable improvement opportunity as the dimension's flag.
  const flagCrit = criteria
    .filter((c) => c.improvement)
    .sort((a, b) => b.improvementValue - a.improvementValue)[0];
  return {
    overall: ratingFromDimension(score, max),
    score,
    max,
    criteria,
    flag: flagCrit?.improvement,
  };
};

const titleCase = (s: string): string =>
  s.replace(/[_-]+/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());

const walletLabel = (tag: string | undefined): string => {
  const t = (tag || '').toUpperCase();
  if (t.includes('ZAKAT')) return 'Accepts Zakat';
  if (t.includes('SADAQAH')) return 'Sadaqah';
  return 'Sadaqah';
};

export interface GmgCharity {
  name: string;
  ein: string;
  address: string;
  founded: number | null;
  trackRecordYears: number | null;
  category: string;
  region: string;
  wallet: string;
  donateUrl: string | null;

  amalScore: number;
  rubricVersion: string;
  evaluatedOn: string;
  riskLevel: string;

  impact: GmgDimension;
  alignment: GmgDimension;

  // stat strip
  costPerBeneficiary: number | null;
  programRatioPct: number | null;
  reserveMonths: number | null;
  totalRevenue: number | null;
  fiscalYear: number | null;

  // financials
  programExpenses: number | null;
  adminExpenses: number | null;
  fundraisingExpenses: number | null;
  totalAssets: number | null;
  netAssets: number | null;

  // narrative
  headline: string;
  summary: string;
  strengths: { point: string; detail: string }[];
  growthAreas: string[];
  bestForSummary: string;
  idealFor: string[];
  considerations: string[];
  caseAgainst: string;

  // facts / signals
  programs: string[];
  populations: string[];
  geography: string[];
  assessmentLabel: string | null;
  archetypeLabel: string | null;
  evidenceStage: string | null;
  recommendationCue: string | null;

  // zakat
  asnaf: string | null;
  claimsZakat: boolean;
  zakatEvidence: string | null;

  awards: { cn: string | null; candid: string | null; bbb: string | null };
}

// Lightweight per-row projection for the index table.
export const adaptRow = (c: any): GmgRow => {
  const ae = c?.amalEvaluation ?? {};
  const cs = ae?.confidence_scores ?? {};
  const sd = ae?.score_details ?? {};
  const fin = c?.financials ?? {};
  const sig = c?.ui_signals_v1 ?? {};
  const dc = num(cs?.data_confidence);
  const pr = numOrNull(fin?.programExpenseRatio ?? c?.rawData?.program_expense_ratio);
  return {
    ein: c?.ein ?? '',
    name: c?.name ?? 'Charity',
    cause: c?.category ?? c?.primaryCategory ?? '—',
    region:
      (Array.isArray(c?.geographicCoverage) && c.geographicCoverage[0]) ||
      c?.targeting?.primary_region ||
      'Multi',
    wallet: walletLabel(ae?.wallet_tag),
    walletIsZakat: (ae?.wallet_tag ?? '').toUpperCase().includes('ZAKAT'),
    impact: ratingFromDimension(num(cs?.impact), 50),
    alignment: ratingFromDimension(num(cs?.alignment), 50),
    amalScore: num(ae?.amal_score),
    risk: sd?.risks?.overall_risk_level ?? 'LOW',
    verification: sig?.evidence_stage ?? (dc >= 0.7 ? 'Verified' : dc >= 0.4 ? 'Building' : 'Early'),
    programPct: pr == null ? null : Math.round(pr <= 1 ? pr * 100 : pr),
  };
};

export const adaptCharity = (c: any): GmgCharity => {
  const ae = c?.amalEvaluation ?? {};
  const cs = ae?.confidence_scores ?? {};
  const sd = ae?.score_details ?? {};
  const fin = c?.financials ?? {};
  const rn = ae?.rich_narrative ?? {};
  const bn = ae?.baseline_narrative ?? {};
  const narrative = Object.keys(rn).length ? rn : bn;
  const sig = c?.ui_signals_v1 ?? {};
  const loc = c?.location ?? {};
  const awards = c?.awards ?? {};

  const founded = typeof c?.foundedYear === 'number' ? c.foundedYear : null;

  const idp = rn?.ideal_donor_profile ?? {};
  const strengthsRaw: any[] = Array.isArray(narrative?.strengths) ? narrative.strengths : [];
  const improvementsRaw: any[] = Array.isArray(narrative?.areas_for_improvement)
    ? narrative.areas_for_improvement
    : [];
  const asAreaText = (x: any): string =>
    typeof x === 'string' ? stripTags(x) : stripTags(x?.area || x?.point || x?.context || '');

  const addr = [loc?.address, loc?.city, loc?.state].filter(Boolean).join(', ');

  return {
    name: c?.name ?? 'Charity',
    ein: c?.ein ?? '',
    address: addr || (loc?.state ?? ''),
    founded,
    trackRecordYears: founded ? 2026 - founded : null,
    category: c?.category ?? c?.primaryCategory ?? '',
    region:
      (Array.isArray(c?.geographicCoverage) && c.geographicCoverage[0]) ||
      c?.targeting?.primary_region ||
      'Multi',
    wallet: walletLabel(ae?.wallet_tag ?? c?.walletTag),
    donateUrl: c?.donationUrl || c?.website || null,

    amalScore: num(ae?.amal_score),
    rubricVersion: ae?.rubric_version ?? '',
    evaluatedOn: (ae?.evaluation_date ?? '').slice(0, 10),
    riskLevel: sd?.risks?.overall_risk_level ?? 'LOW',

    impact: buildDimension(sd?.impact, cs?.impact, 50),
    alignment: buildDimension(sd?.alignment, cs?.alignment, 50),

    costPerBeneficiary: numOrNull(
      sd?.impact?.cost_per_beneficiary ?? rn?.financial_deep_dive?.cost_per_beneficiary,
    ),
    programRatioPct: (() => {
      const r = numOrNull(fin?.programExpenseRatio ?? c?.rawData?.program_expense_ratio);
      if (r == null) return null;
      // Source stores either a fraction (0.80) or a percent (80.3).
      return Math.round(r <= 1 ? r * 100 : r);
    })(),
    reserveMonths: (() => {
      const r = numOrNull(fin?.workingCapitalMonths ?? rn?.financial_deep_dive?.reserves_months);
      return r == null ? null : Math.round(r * 10) / 10;
    })(),
    totalRevenue: numOrNull(fin?.totalRevenue ?? rn?.financial_deep_dive?.annual_revenue),
    fiscalYear: numOrNull(fin?.fiscalYear),

    programExpenses: numOrNull(fin?.programExpenses),
    adminExpenses: numOrNull(fin?.adminExpenses),
    fundraisingExpenses: numOrNull(fin?.fundraisingExpenses),
    totalAssets: numOrNull(fin?.totalAssets),
    netAssets: numOrNull(fin?.netAssets),

    headline: stripTags(narrative?.headline) || c?.scoreSummary || c?.mission || c?.name || '',
    summary: stripTags(narrative?.summary) || stripTags(c?.mission),
    strengths: strengthsRaw.slice(0, 3).map((s) => ({
      point: stripTags(s?.point || s?.area || ''),
      detail: stripTags(s?.detail || s?.context || ''),
    })),
    growthAreas: improvementsRaw.map(asAreaText).filter(Boolean).slice(0, 4),
    bestForSummary: stripTags(idp?.best_for_summary) || '',
    idealFor: (Array.isArray(idp?.donor_motivations) ? idp.donor_motivations : [])
      .map(stripTags)
      .filter(Boolean)
      .slice(0, 4),
    considerations: (Array.isArray(idp?.giving_considerations) ? idp.giving_considerations : [])
      .map(stripTags)
      .filter(Boolean)
      .slice(0, 4),
    caseAgainst: stripTags(rn?.case_against?.summary) || '',

    programs: (Array.isArray(c?.programs) ? c.programs : [])
      .map((p: any) => (typeof p === 'string' ? p : p?.name))
      .filter(Boolean)
      .slice(0, 6),
    populations: (Array.isArray(c?.populationsServed) ? c.populationsServed : [])
      .map(titleCase)
      .slice(0, 6),
    geography: (Array.isArray(c?.geographicCoverage) ? c.geographicCoverage : []).slice(0, 6),
    assessmentLabel: sig?.assessment_label ?? null,
    archetypeLabel: sig?.archetype_label ?? null,
    evidenceStage: sig?.evidence_stage ?? null,
    recommendationCue: sig?.recommendation_cue ?? null,

    asnaf: sd?.zakat?.asnaf_category ? titleCase(sd.zakat.asnaf_category) : null,
    claimsZakat: !!sd?.zakat?.charity_claims_zakat,
    zakatEvidence: stripTags(sd?.zakat?.claim_evidence) || null,

    awards: {
      cn: Array.isArray(awards?.cnBeacons) && awards.cnBeacons.length ? awards.cnBeacons[0] : null,
      candid: awards?.candidSeal ?? null,
      bbb: awards?.bbbStatus ?? null,
    },
  };
};

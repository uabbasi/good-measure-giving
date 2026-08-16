// Adapts a real CharityProfile (exported JSON shape) into the fields the GMG
// "Modern" detail page renders. Tolerant of missing data — every field has a
// sensible fallback so the proof surface renders for any charity/tier.

import { Rating, ratingFromDimension, ratingFromCriterion, ratingFromGmgScore } from './rating';
import {
  regionsFromCauseTags, regionLabel, regionKeysFromCauseTags, asnafKeysFromCauseTags,
} from './adapters/regions';
import {
  buildCitationIndex, anchorConcerns, aggregateGrants, buildFinancialSeries,
  parseCitedText,
  type CitationIndex, type AnchoredConcerns, type GrantFlows, type FinancialYear,
  type CitedSegment,
} from './adapters';

export type SizeBand = 'lt1m' | '1to10m' | '10to100m' | 'gte100m';

const toSizeBand = (revenue: number | null): SizeBand | null => {
  if (revenue == null) return null;
  if (revenue < 1e6) return 'lt1m';
  if (revenue < 1e7) return '1to10m';
  if (revenue < 1e8) return '10to100m';
  return 'gte100m';
};

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
  /** Overall GMG score as a Harvey band — null when the charity isn't scored yet. */
  overall: Rating | null;
  verification: string;
  programPct: number | null;
  // Qualitative signal ratings (ui_signals_v1.signal_states), shown as Harvey
  // balls on the index. All point the same way: Strong = good.
  financialHealth: Rating;
  risk: Rating; // Strong = low risk / strong risk-management
  donorFit: Rating;
  revenue: number | null; // annual revenue — the "Size" column
  /** Enum key behind `cause` — the facet key. `cause` stays the display label. */
  causeKey: string;
  /** Region keys from causeTags; empty for the 69 charities with no region tag. */
  regionTags: string[];
  /** Asnaf keys from causeTags; empty for the 65 with none. */
  asnafTags: string[];
  isMuslimLed: boolean;
  /** null for the 7 charities with no revenue figure. */
  sizeBand: SizeBand | null;
}

const stripTags = (s: unknown): string =>
  typeof s === 'string'
    ? s
        .replace(/<cite[^>]*>(.*?)<\/cite>/gis, '$1')
        .replace(/<[^>]+>/g, '')
        .replace(/\s+/g, ' ')
        .trim()
    : '';

// Pipeline evidence strings sometimes restate a criterion's own scored/possible
// fraction in prose — "Cause area: Humanitarian (13/13)", "Revenue: $58.0M
// (3/5 funding gap)", "Founded 1933 (93 years — 6/6)". That's the exact number
// the dedicated scored/possible display already renders (member-only), so
// leaving it in the note text republished it in public prose regardless of
// who's signed in. Strips only the fraction that matches THIS criterion's own
// scored/possible — not any other digits the note happens to contain — and
// drops a parenthetical entirely if the fraction was the only thing in it.
export const stripScoreFraction = (note: string, scored: number, possible: number): string =>
  note
    .replace(/\(([^)]*)\)/g, (full: string, inner: string) => {
      const fraction = new RegExp(`\\b${scored}\\s*/\\s*${possible}\\b`);
      if (!fraction.test(inner)) return full;
      const cleaned = inner
        .replace(fraction, '')
        .replace(/^\s*[—-]\s*/, '')
        .replace(/\s*[—-]\s*$/, '')
        .replace(/\s{2,}/g, ' ')
        .trim();
      return cleaned ? `(${cleaned})` : '';
    })
    .replace(/\s{2,}/g, ' ')
    .trim();

// score_details.zakat.claim_evidence is meant to be a quoted source for the
// charity's zakat claim, rendered verbatim in italics as if it were a real
// citation (see RightForYou.tsx). For 11 of 135 published charities — found
// via manual QA on Al-Barr Foundation, also present on Doctors Without
// Borders — the pipeline's zakat-corroboration step writes its own internal
// audit-trail failure message into that same field instead of a citation:
// "CORROBORATION FAILED: Discovered via search (confidence=0.50)". That
// reads as the charity's own words on a public page. Treat it as absent
// rather than fixing it up — there's no legitimate quote to salvage once the
// corroboration step failed.
const isPipelineInternalText = (s: string): boolean => /CORROBORATION FAILED/i.test(s);

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

const boolOrNull = (v: unknown): boolean | null => {
  if (typeof v === 'boolean') return v;
  if (v === 1 || v === 0) return v === 1;
  return null;
};

const strList = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string').map(stripTags).filter(Boolean) : [];

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
    note: stripScoreFraction(stripTags(c?.evidence) || '—', num(c?.scored), num(c?.possible)),
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

// ui_signals_v1.signal_states use a 3-level scale (Strong/Moderate/Limited);
// map onto the 5-level Harvey scale as full / half / empty.
const signalToRating = (s: unknown): Rating => {
  switch (String(s || '').toLowerCase()) {
    case 'strong':
      return 'Strong';
    case 'moderate':
      return 'Moderate';
    case 'limited':
      return 'Weak';
    default:
      return 'Moderate';
  }
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
  /** A dedicated donation page (pipeline's `donationUrl`). Null when the pipeline hasn't found one distinct from the homepage — see `website`. */
  donateUrl: string | null;
  /** General charity homepage. Used as the CTA's "Visit website" fallback when `donateUrl` is null, instead of silently mislabeling a homepage link as "Donate". */
  website: string | null;

  amalScore: number;
  /** amalEvaluation.evaluation_date — when the rubric last scored this charity. Not shown on the page: it goes stale whenever the pipeline re-exports without re-scoring. See `updatedOn`. */
  evaluatedOn: string;
  /** lastUpdated — when this record was last exported. This, not `evaluatedOn`, is what the page's utility row displays. */
  updatedOn: string;
  riskLevel: string;

  impact: GmgDimension;
  alignment: GmgDimension;

  // stat strip
  costPerBeneficiary: number | null;
  programRatioPct: number | null;
  reserveMonths: number | null;
  totalRevenue: number | null;
  fiscalYear: number | null;
  // Published data-vintage age (score_details.data_confidence.data_age_years).
  // Computed once by the pipeline at evaluation time — the badge must use
  // this, not `new Date()`, or every prerendered page recomputes a
  // different age at hydration than the one baked into the SSR.
  dataAgeYears: number | null;
  // score_details.data_confidence.data_quality_{label,value} — computed by the
  // pipeline but, until now, never rendered anywhere in the website UI.
  dataQualityLabel: string | null;
  dataQualityValue: number | null;
  // Form 990 filing is not required for churches/mosques; the scorer already
  // exempts these orgs from filing-currency penalties (see
  // `_check_filing_currency` in the pipeline). Exported as integer 0/1.
  form990Exempt: boolean;

  // financials
  programExpenses: number | null;
  adminExpenses: number | null;
  fundraisingExpenses: number | null;
  totalAssets: number | null;
  netAssets: number | null;
  /** Gift-in-kind and burn-rate signals. Sparse: 71/166 charities have at least one. */
  noncashRatio: number | null;
  cashAdjustedProgramRatio: number | null;
  domesticBurnRate: number | null;

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
  // Browse-consistent signal ratings (Harvey balls). `overall` is the GMG band
  // (null when unscored); the rest come from ui_signals_v1.signal_states.
  overall: Rating | null;
  financialHealth: Rating;
  risk: Rating;
  donorFit: Rating;
  assessmentLabel: string | null;
  archetypeLabel: string | null;
  evidenceStage: string | null;
  recommendationCue: string | null;

  // zakat
  asnaf: string | null;
  claimsZakat: boolean;
  zakatEvidence: string | null;

  awards: {
    cn: string | null; candid: string | null; bbb: string | null;
    cnUrl: string | null; candidUrl: string | null; bbbUrl: string | null;
  };

  /** Resolved citation index; narrative text is parsed against this. */
  citations: CitationIndex;
  /**
   * The same narrative content as the plain-text fields above, but parsed into
   * renderable segments so inline <cite> markers can be shown. Both forms exist
   * deliberately: the plain strings feed meta descriptions and the compare page,
   * where markup would be wrong; these feed the detail page, where the citation
   * is the point. Parsed here rather than at each render site so section
   * components stay dumb.
   */
  cited: {
    summary: CitedSegment[];
    caseAgainstSummary: CitedSegment[];
    peerDifferentiator: CitedSegment[];
    dimensionExplanations: {
      impact: CitedSegment[];
      alignment: CitedSegment[];
      credibility: CitedSegment[];
    };
    strengths: { point: string; detail: CitedSegment[] }[];
    growthAreas: { point: string; detail: CitedSegment[] }[];
    strengthsDeepDive: CitedSegment[][];
  };
  /** keyConcerns grouped by the page section they caveat. */
  concerns: AnchoredConcerns;
  /** Most-recent-year grant aggregation; null when the charity makes no grants. */
  grantFlows: GrantFlows | null;
  /** Multi-year revenue/expense series, zeros normalized to null. */
  financialSeries: FinancialYear[];

  evidence: {
    grade: string | null;
    gradeExplanation: string;
    /** impact_evidence.theory_of_change — a status enum (DOCUMENTED/IMPLICIT/PUBLISHED/DEVELOPING/ABSENT/STRONG), not prose. Render as a badge, not an explanation; see `theoryOfChangeSummary` for the actual prose. */
    theoryOfChange: string;
    /** impact_evidence.theory_of_change_summary (166/166) — one or two sentences of actual prose explaining the theory of change. */
    theoryOfChangeSummary: string;
    whyEvidenceMatters: string;
    externalEvaluations: string[];
    outcomeTrackingYears: number | null;
  };
  capacity: {
    ceoName: string | null;
    ceoCompensation: number | null;
    ceoCompensationPctRevenue: number | null;
    boardSize: number | null;
    independentBoardPct: number | null;
    hasConflictPolicy: boolean | null;
    hasFinancialAudit: boolean | null;
    employeesCount: number | null;
    volunteersCount: number | null;
    programsCount: number | null;
    geographicReach: string;
  };
  peers: {
    peerGroup: string;
    differentiator: string;
    peerCount: number | null;
    programRatioMedian: number | null;
    industryProgramRatio: number | null;
    cnOverallScore: number | null;
    transparencyScore: number | null;
    similarOrganizations: { name: string; differentiator: string }[];
  };
  bbb: {
    summary: string;
    auditType: string | null;
    effectivenessStatus: string | null;
    financesStatus: string | null;
    governanceStatus: string | null;
    standardsMet: number | null;
    reviewUrl: string | null;
  };
  outlook: {
    maturityStage: string;
    roomForFunding: string;
    roomForFundingExplanation: string;
    strategicPriorities: string[];
    yearsOperating: number | null;
    revenueGrowth3yr: number | null;
  };
  // Named `donorFitMatrix`, not `donorFit` — that name is already taken by the
  // browse-consistent Harvey-ball signal rating above (ui_signals_v1). This is
  // a different shape (rich_narrative.donor_fit_matrix) and a same-named
  // property here would be a duplicate-identifier error against a different type.
  donorFitMatrix: {
    causeArea: string;
    givingStyle: string;
    evidenceRigor: string;
    geographicFocus: string;
    zakatStatus: string;
    zakatAsnafServed: string[];
  };
  /** score_details risks. The export's `mitigation` is null in all 206 rows, so it is not mapped. */
  risks: { category: string; description: string; severity: string; dataSource: string }[];
  /** Per-field provenance. `sourceUrl` is null for entries the export never gave a URL. */
  provenance: { field: string; sourceName: string; sourceUrl: string | null; fiscalYear: number | null }[];
  notIdealFor: string[];
  caseAgainstFactors: string[];
  caseAgainstMitigation: string;
  /** Root-level theoryOfChange (116/166) — NOT evidence.theoryOfChange, which is a different field. */
  theoryOfChange: string | null;
}

// Lightweight per-row projection for the index table.
export const adaptRow = (c: any): GmgRow => {
  const ae = c?.amalEvaluation ?? {};
  const cs = ae?.confidence_scores ?? {};
  const fin = c?.financials ?? {};
  const sig = c?.ui_signals_v1 ?? {};
  // The index summary carries dataConfidence (camelCase); full files use
  // data_confidence (snake). Accept either so Verif. isn't stuck on "Early".
  const dc = num(cs?.dataConfidence ?? cs?.data_confidence);
  const pr = numOrNull(fin?.programExpenseRatio ?? c?.rawData?.program_expense_ratio);
  const states = sig?.signal_states ?? {};
  const scoreVal = numOrNull(ae?.amal_score);
  const revenue = numOrNull(c?.totalRevenue ?? fin?.totalRevenue);
  return {
    ein: c?.ein ?? '',
    name: c?.name ?? 'Charity',
    cause: c?.category ?? c?.primaryCategory ?? '—',
    region: regionLabel(regionsFromCauseTags(c?.causeTags)),
    wallet: walletLabel(ae?.wallet_tag),
    walletIsZakat: (ae?.wallet_tag ?? '').toUpperCase().includes('ZAKAT'),
    impact: ratingFromDimension(num(cs?.impact), 50),
    alignment: ratingFromDimension(num(cs?.alignment), 50),
    amalScore: num(ae?.amal_score),
    overall: scoreVal == null ? null : ratingFromGmgScore(scoreVal),
    verification: sig?.evidence_stage ?? (dc >= 0.7 ? 'Verified' : dc >= 0.4 ? 'Building' : 'Early'),
    programPct: pr == null ? null : Math.round(pr <= 1 ? pr * 100 : pr),
    financialHealth: signalToRating(states?.financial_health),
    risk: signalToRating(states?.risk),
    donorFit: signalToRating(states?.donor_fit),
    revenue,
    causeKey: c?.primaryCategory ?? '',
    regionTags: regionKeysFromCauseTags(c?.causeTags),
    asnafTags: asnafKeysFromCauseTags(c?.causeTags),
    isMuslimLed: c?.isMuslimCharity === true,
    sizeBand: toSizeBand(revenue),
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
  const deepDiveRaw: any[] = Array.isArray(rn?.strengths_deep_dive) ? rn.strengths_deep_dive : [];
  const asAreaText = (x: any): string =>
    typeof x === 'string' ? stripTags(x) : stripTags(x?.area || x?.point || x?.context || '');

  const addr = [loc?.address, loc?.city, loc?.state].filter(Boolean).join(', ');

  const citationIndex = buildCitationIndex(rn?.all_citations, c);
  const cite = (text: unknown): CitedSegment[] => parseCitedText(text, citationIndex);
  // `dimension_explanations` reads from `narrative` (rich-or-baseline), not `rn`
  // alone — baseline narratives carry this field too, just as plain strings
  // rather than `{ explanation }` objects, and a rich-only read would silently
  // go empty for any charity that hasn't been promoted to a rich narrative yet.
  const de = narrative?.dimension_explanations ?? {};
  const deText = (k: string): unknown => {
    const entry = (de as Record<string, unknown>)[k];
    if (entry && typeof entry === 'object' && !Array.isArray(entry)) {
      return (entry as Record<string, unknown>).explanation;
    }
    return entry;
  };

  return {
    name: c?.name ?? 'Charity',
    ein: c?.ein ?? '',
    address: addr || (loc?.state ?? ''),
    founded,
    trackRecordYears: founded ? 2026 - founded : null,
    category: c?.category ?? c?.primaryCategory ?? '',
    // `region` must be the same canonical label the browse index shows
    // (adaptRow, below) — Phase 3 builds a region facet on that vocabulary,
    // and a detail page disagreeing with its own index row would be a bug a
    // donor could actually see. So the canonical cause-tag vocabulary always
    // wins; free-text `targeting.geographicCoverage` is only a fallback for
    // charities with no region cause-tag. Don't invert this precedence —
    // `geography` (below) is the place for the fuller free-text list.
    region: (() => {
      const canonical = regionsFromCauseTags(c?.causeTags);
      if (canonical.length > 0) return regionLabel(canonical);
      const fromTargeting = Array.isArray(c?.targeting?.geographicCoverage)
        ? c.targeting.geographicCoverage.filter((g: unknown): g is string => typeof g === 'string')
        : [];
      return regionLabel(fromTargeting);
    })(),
    wallet: walletLabel(ae?.wallet_tag ?? c?.walletTag),
    donateUrl: c?.donationUrl || null,
    website: c?.website || null,

    amalScore: num(ae?.amal_score),
    evaluatedOn: (ae?.evaluation_date ?? '').slice(0, 10),
    updatedOn: (c?.lastUpdated ?? '').slice(0, 10),
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
    dataAgeYears: numOrNull(sd?.data_confidence?.data_age_years),
    dataQualityLabel: sd?.data_confidence?.data_quality_label ?? null,
    dataQualityValue: numOrNull(sd?.data_confidence?.data_quality_value),
    form990Exempt: !!c?.form990Exempt,

    programExpenses: numOrNull(fin?.programExpenses),
    adminExpenses: numOrNull(fin?.adminExpenses),
    fundraisingExpenses: numOrNull(fin?.fundraisingExpenses),
    totalAssets: numOrNull(fin?.totalAssets),
    netAssets: numOrNull(fin?.netAssets),
    noncashRatio: numOrNull(fin?.noncashRatio),
    cashAdjustedProgramRatio: numOrNull(fin?.cashAdjustedProgramRatio),
    domesticBurnRate: numOrNull(fin?.domesticBurnRate),

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
    populations: (Array.isArray(c?.targeting?.populationsServed) ? c.targeting.populationsServed : [])
      .filter((p: unknown): p is string => typeof p === 'string')
      .map(titleCase)
      .slice(0, 6),
    geography: (Array.isArray(c?.targeting?.geographicCoverage) ? c.targeting.geographicCoverage : [])
      .filter((g: unknown): g is string => typeof g === 'string')
      .slice(0, 6),
    overall: (() => {
      const sv = numOrNull(ae?.amal_score);
      return sv == null ? null : ratingFromGmgScore(sv);
    })(),
    financialHealth: signalToRating(sig?.signal_states?.financial_health),
    risk: signalToRating(sig?.signal_states?.risk),
    donorFit: signalToRating(sig?.signal_states?.donor_fit),
    assessmentLabel: sig?.assessment_label ?? null,
    archetypeLabel: sig?.archetype_label ?? null,
    evidenceStage: sig?.evidence_stage ?? null,
    recommendationCue: sig?.recommendation_cue ?? null,

    asnaf: sd?.zakat?.asnaf_category ? titleCase(sd.zakat.asnaf_category) : null,
    claimsZakat: !!sd?.zakat?.charity_claims_zakat,
    zakatEvidence: (() => {
      const cleaned = stripTags(sd?.zakat?.claim_evidence);
      return cleaned && !isPipelineInternalText(cleaned) ? cleaned : null;
    })(),

    awards: {
      cn: Array.isArray(awards?.cnBeacons) && awards.cnBeacons.length ? awards.cnBeacons[0] : null,
      candid: awards?.candidSeal ?? null,
      bbb: awards?.bbbStatus ?? null,
      cnUrl: awards?.cnUrl ?? null,
      candidUrl: awards?.candidUrl ?? null,
      bbbUrl: awards?.bbbReviewUrl ?? null,
    },

    citations: citationIndex,
    cited: {
      summary: cite(narrative?.summary),
      caseAgainstSummary: cite(rn?.case_against?.summary),
      peerDifferentiator: cite(rn?.peer_comparison?.differentiator),
      dimensionExplanations: {
        impact: cite(deText('impact')),
        alignment: cite(deText('alignment')),
        credibility: cite(deText('credibility')),
      },
      strengths: strengthsRaw.slice(0, 3).map((s) => ({
        point: stripTags(s?.point || s?.area || ''),
        detail: cite(s?.detail || s?.context || ''),
      })),
      // Mirrors `cited.strengths`: the label and its cited prose travel
      // together as a pair, so a consumer can never assume the two carry the
      // same content. `point` matches the plain `growthAreas` label above;
      // `detail` is the cited `context`, where the pipeline actually attaches
      // citations (measured fleet-wide at 321 references).
      growthAreas: improvementsRaw
        .map((x) => ({
          point: asAreaText(x),
          detail: typeof x === 'string' ? cite(x) : cite(x?.context || ''),
        }))
        .filter((g) => g.detail.length > 0)
        .slice(0, 4),
      strengthsDeepDive: deepDiveRaw.filter((s): s is string => typeof s === 'string').map(cite),
    },
    concerns: anchorConcerns(c?.keyConcerns),
    grantFlows: aggregateGrants(c?.grantsData),
    financialSeries: buildFinancialSeries(rn?.financial_deep_dive?.yearly_financials),

    evidence: {
      grade: rn?.impact_evidence?.evidence_grade ?? null,
      gradeExplanation: stripTags(rn?.impact_evidence?.evidence_grade_explanation),
      theoryOfChange: stripTags(rn?.impact_evidence?.theory_of_change),
      theoryOfChangeSummary: stripTags(rn?.impact_evidence?.theory_of_change_summary),
      whyEvidenceMatters: stripTags(rn?.impact_evidence?.why_evidence_matters),
      externalEvaluations: strList(rn?.impact_evidence?.external_evaluations),
      outcomeTrackingYears: numOrNull(rn?.impact_evidence?.outcome_tracking_years),
    },
    capacity: {
      ceoName: rn?.organizational_capacity?.ceo_name ?? null,
      ceoCompensation: numOrNull(rn?.organizational_capacity?.ceo_compensation),
      ceoCompensationPctRevenue: numOrNull(rn?.organizational_capacity?.ceo_compensation_pct_revenue),
      boardSize: numOrNull(rn?.organizational_capacity?.board_size),
      independentBoardPct: numOrNull(rn?.organizational_capacity?.independent_board_pct),
      hasConflictPolicy: boolOrNull(rn?.organizational_capacity?.has_conflict_policy),
      hasFinancialAudit: boolOrNull(rn?.organizational_capacity?.has_financial_audit),
      employeesCount: numOrNull(rn?.organizational_capacity?.employees_count),
      volunteersCount: numOrNull(rn?.organizational_capacity?.volunteers_count),
      programsCount: numOrNull(rn?.organizational_capacity?.programs_count),
      geographicReach: stripTags(rn?.organizational_capacity?.geographic_reach),
    },
    peers: {
      peerGroup: stripTags(rn?.peer_comparison?.peer_group),
      differentiator: stripTags(rn?.peer_comparison?.differentiator),
      peerCount: numOrNull(rn?.financial_deep_dive?.peer_count),
      programRatioMedian: numOrNull(rn?.financial_deep_dive?.peer_program_ratio_median),
      industryProgramRatio: numOrNull(rn?.financial_deep_dive?.industry_program_ratio),
      cnOverallScore: numOrNull(rn?.financial_deep_dive?.cn_overall_score),
      transparencyScore: numOrNull(rn?.financial_deep_dive?.transparency_score),
      similarOrganizations: (Array.isArray(rn?.similar_organizations) ? rn.similar_organizations : [])
        .filter((s: unknown): s is Record<string, unknown> => !!s && typeof s === 'object')
        .map((s: Record<string, unknown>) => ({
          name: stripTags(s.name),
          differentiator: stripTags(s.differentiator),
        }))
        .filter((s: { name: string }) => s.name !== ''),
    },
    bbb: {
      summary: stripTags(rn?.bbb_assessment?.summary),
      auditType: rn?.bbb_assessment?.audit_type ?? null,
      effectivenessStatus: rn?.bbb_assessment?.effectiveness_status ?? null,
      financesStatus: rn?.bbb_assessment?.finances_status ?? null,
      governanceStatus: rn?.bbb_assessment?.governance_status ?? null,
      standardsMet: numOrNull(rn?.bbb_assessment?.standards_met),
      reviewUrl: rn?.bbb_assessment?.review_url ?? null,
    },
    outlook: {
      maturityStage: stripTags(rn?.long_term_outlook?.maturity_stage),
      roomForFunding: stripTags(rn?.long_term_outlook?.room_for_funding),
      roomForFundingExplanation: stripTags(rn?.long_term_outlook?.room_for_funding_explanation),
      strategicPriorities: strList(rn?.long_term_outlook?.strategic_priorities),
      yearsOperating: numOrNull(rn?.long_term_outlook?.years_operating),
      revenueGrowth3yr: numOrNull(rn?.long_term_outlook?.revenue_growth_3yr),
    },
    donorFitMatrix: {
      causeArea: stripTags(rn?.donor_fit_matrix?.cause_area),
      givingStyle: stripTags(rn?.donor_fit_matrix?.giving_style),
      evidenceRigor: stripTags(rn?.donor_fit_matrix?.evidence_rigor),
      geographicFocus: stripTags(rn?.donor_fit_matrix?.geographic_focus),
      zakatStatus: stripTags(rn?.donor_fit_matrix?.zakat_status),
      zakatAsnafServed: strList(rn?.donor_fit_matrix?.zakat_asnaf_served),
    },
    risks: (Array.isArray(sd?.risks?.risks) ? sd.risks.risks : [])
      .filter((r: unknown): r is Record<string, unknown> => !!r && typeof r === 'object')
      .map((r: Record<string, unknown>) => ({
        category: stripTags(r.category),
        description: stripTags(r.description),
        severity: String(r.severity ?? ''),
        dataSource: stripTags(r.data_source),
      }))
      .filter((r: { description: string }) => r.description !== ''),
    provenance: Object.entries((c?.sourceAttribution ?? {}) as Record<string, unknown>)
      .filter(([, v]) => !!v && typeof v === 'object' && !Array.isArray(v))
      .map(([field, v]) => {
        const rec = v as Record<string, unknown>;
        return {
          field,
          sourceName: stripTags(rec.source_name),
          sourceUrl: typeof rec.source_url === 'string' && rec.source_url !== '' ? rec.source_url : null,
          fiscalYear: numOrNull(rec.fiscal_year),
        };
      })
      .filter((p) => p.sourceName !== ''),
    // `not_ideal_for` is exported as a single prose string, not a list (confirmed
    // fleet-wide: 166/166 occurrences are strings, never arrays) — strList()
    // would silently discard it every time. Wrap the non-empty string instead.
    notIdealFor: (() => {
      const s = stripTags(idp?.not_ideal_for);
      return s ? [s] : [];
    })(),
    caseAgainstFactors: strList(rn?.case_against?.risk_factors),
    caseAgainstMitigation: stripTags(rn?.case_against?.mitigation_notes),
    // Root-level theoryOfChange (116/166) — NOT evidence.theoryOfChange, which is a different field.
    theoryOfChange: typeof c?.theoryOfChange === 'string' && c.theoryOfChange !== ''
      ? stripTags(c.theoryOfChange)
      : null,
  };
};

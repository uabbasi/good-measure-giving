// Pure faceted-filtering logic for /browse. No React, no DOM — everything
// here is a plain function over GmgRow[] so it can be unit-tested against the
// real corpus and reused by both the URL layer and the UI (Task 3).

import type { GmgRow, SizeBand } from './charityAdapter';
import { REGION_TAGS, ASNAF_TAGS } from './adapters/regions';

export type FacetKey = 'cause' | 'asnaf' | 'region' | 'size' | 'evidence';
export type Scope = 'all' | 'muslim';
export type WalletFilter = 'all' | 'zakat' | 'sadaqah';

export interface FacetState {
  query: string;
  wallet: WalletFilter;
  scope: Scope;
  cause: string[];
  asnaf: string[];
  region: string[];
  size: SizeBand[];
  evidence: string[];
}

export type FacetAction =
  | { type: 'query'; value: string }
  | { type: 'wallet'; value: WalletFilter }
  | { type: 'scope'; value: Scope }
  | { type: 'toggle'; facet: FacetKey; value: string }
  | { type: 'clearFacet'; facet: FacetKey }
  | { type: 'clearAll' };

// The 16 MECE primary-category enum keys measured across the corpus. Kept
// here (rather than derived from rows at runtime) so URL parsing can
// validate without needing a corpus in scope; the test suite asserts this
// list can't silently drift from the data.
export const CAUSE_KEYS = [
  'HUMANITARIAN',
  'RELIGIOUS_CONGREGATION',
  'CIVIL_RIGHTS_LEGAL',
  'MEDICAL_HEALTH',
  'PHILANTHROPY_GRANTMAKING',
  'EDUCATION_INTERNATIONAL',
  'BASIC_NEEDS',
  'RELIGIOUS_OUTREACH',
  'EDUCATION_HIGHER_RELIGIOUS',
  'EDUCATION_K12_RELIGIOUS',
  'ENVIRONMENT_CLIMATE',
  'RESEARCH_POLICY',
  'SOCIAL_SERVICES',
  'WOMENS_SERVICES',
  'ADVOCACY_CIVIC',
  'MEDIA_JOURNALISM',
] as const;

const SIZE_BANDS: readonly SizeBand[] = ['lt1m', '1to10m', '10to100m', 'gte100m'];

// The four ui_signals_v1.evidence_stage (row.verification) values found
// across the corpus. Exported so the test suite can assert this list can't
// silently drift from the data, the same way CAUSE_KEYS is guarded above.
export const EVIDENCE_VALUES = ['Verified', 'Established', 'Early', 'Building'] as const;

export const INITIAL_FACET_STATE: FacetState = {
  query: '',
  wallet: 'all',
  scope: 'all',
  cause: [],
  asnaf: [],
  region: [],
  size: [],
  evidence: [],
};

const toggleValue = <T,>(arr: T[], value: T): T[] =>
  arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value];

export const facetReducer = (state: FacetState, action: FacetAction): FacetState => {
  switch (action.type) {
    case 'query':
      return { ...state, query: action.value };
    case 'wallet':
      return { ...state, wallet: action.value };
    case 'scope':
      return { ...state, scope: action.value };
    case 'toggle': {
      const { facet, value } = action;
      return { ...state, [facet]: toggleValue(state[facet] as string[], value) };
    }
    case 'clearFacet':
      return { ...state, [action.facet]: [] };
    case 'clearAll':
      return INITIAL_FACET_STATE;
  }
};

// `query` is a search, not a facet — it must not trigger noindex (Task 4).
export const isFacetActive = (state: FacetState): boolean =>
  state.wallet !== 'all' ||
  state.scope !== 'all' ||
  state.cause.length > 0 ||
  state.asnaf.length > 0 ||
  state.region.length > 0 ||
  state.size.length > 0 ||
  state.evidence.length > 0;

const matchesQuery = (row: GmgRow, query: string): boolean => {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return `${row.name} ${row.ein} ${row.cause}`.toLowerCase().includes(q);
};

const matchesWallet = (row: GmgRow, wallet: WalletFilter): boolean => {
  if (wallet === 'zakat') return row.walletIsZakat;
  if (wallet === 'sadaqah') return !row.walletIsZakat;
  return true;
};

const matchesScope = (row: GmgRow, scope: Scope): boolean => (scope === 'muslim' ? row.isMuslimLed : true);

// A single-valued row field (e.g. causeKey) matches an OR'd selection.
const matchesOneOf = (selected: string[], value: string): boolean =>
  selected.length === 0 || selected.includes(value);

// A multi-valued row field (e.g. regionTags) matches if it intersects the OR'd selection.
const intersects = (selected: string[], present: string[]): boolean =>
  selected.length === 0 || selected.some((v) => present.includes(v));

export const applyFacets = (rows: GmgRow[], state: FacetState): GmgRow[] =>
  rows.filter((row) => {
    if (!matchesQuery(row, state.query)) return false;
    if (!matchesWallet(row, state.wallet)) return false;
    if (!matchesScope(row, state.scope)) return false;
    if (!matchesOneOf(state.cause, row.causeKey)) return false;
    if (!intersects(state.asnaf, row.asnafTags)) return false;
    if (!intersects(state.region, row.regionTags)) return false;
    if (state.size.length > 0 && (row.sizeBand === null || !state.size.includes(row.sizeBand))) return false;
    if (!matchesOneOf(state.evidence, row.verification)) return false;
    return true;
  });

// For each value of `facet`, how many rows match with that facet's own
// constraint removed (every other constraint still applies): apply `query`
// plus every constraint EXCEPT this facet's own, then tally. This is what
// keeps a pill's count honest (non-zero for values not yet selected) as the
// user narrows — it is not "if this value were added to the current
// selection", which for a second-or-later pick would be the larger OR'd
// union instead.
//
// Keyed by FacetKey (rather than a switch) so a sixth facet fails to compile
// here, the same way `toggle` above can't silently misroute one.
const FACET_VALUES: Record<FacetKey, (row: GmgRow) => string[]> = {
  cause: (row) => [row.causeKey],
  asnaf: (row) => row.asnafTags,
  region: (row) => row.regionTags,
  size: (row) => (row.sizeBand !== null ? [row.sizeBand] : []),
  evidence: (row) => [row.verification],
};

export const facetCounts = (rows: GmgRow[], state: FacetState, facet: FacetKey): Record<string, number> => {
  const candidates = applyFacets(rows, { ...state, [facet]: [] });
  const counts: Record<string, number> = {};
  const bump = (key: string) => {
    if (!key) return;
    counts[key] = (counts[key] ?? 0) + 1;
  };
  const values = FACET_VALUES[facet];
  for (const row of candidates) {
    values(row).forEach(bump);
  }
  return counts;
};

const csv = (params: URLSearchParams, key: string): string[] => {
  const raw = params.get(key);
  return raw ? raw.split(',').filter(Boolean) : [];
};

export const facetStateToSearch = (state: FacetState): string => {
  const params = new URLSearchParams();
  if (state.query) params.set('q', state.query);
  if (state.wallet !== 'all') params.set('wallet', state.wallet);
  if (state.scope !== 'all') params.set('scope', state.scope);
  if (state.cause.length) params.set('cause', state.cause.join(','));
  if (state.asnaf.length) params.set('asnaf', state.asnaf.join(','));
  if (state.region.length) params.set('region', state.region.join(','));
  if (state.size.length) params.set('size', state.size.join(','));
  if (state.evidence.length) params.set('evidence', state.evidence.join(','));
  const s = params.toString();
  return s ? `?${s}` : '';
};

export const facetStateFromSearch = (search: string): FacetState => {
  const params = new URLSearchParams(search);
  const wallet = params.get('wallet');
  const scope = params.get('scope');
  return {
    query: params.get('q') ?? '',
    wallet: wallet === 'zakat' || wallet === 'sadaqah' ? wallet : 'all',
    scope: scope === 'muslim' ? 'muslim' : 'all',
    cause: csv(params, 'cause').filter((v) => (CAUSE_KEYS as readonly string[]).includes(v)),
    asnaf: csv(params, 'asnaf').filter((v) => v in ASNAF_TAGS),
    region: csv(params, 'region').filter((v) => v in REGION_TAGS),
    size: csv(params, 'size').filter((v): v is SizeBand => SIZE_BANDS.includes(v as SizeBand)),
    evidence: csv(params, 'evidence').filter((v) => (EVIDENCE_VALUES as readonly string[]).includes(v)),
  };
};

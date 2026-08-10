// Places each keyConcern next to the thing it caveats. Only 168 of 343
// concerns in the corpus carry a data_points.field, so anchoring falls back
// to the concern's own type — which covers the remaining 175 exactly.

export type ConcernSeverity = 'high' | 'medium' | 'low';

export type ConcernAnchor =
  | 'reserves'
  | 'money'
  | 'risks'
  | 'zakat'
  | 'governance'
  | 'whatTheyDo'
  | 'trust';

export interface Concern {
  type: string;
  severity: ConcernSeverity;
  headline: string;
  detail: string;
  dataPoints: Record<string, string | number | boolean>;
  anchor: ConcernAnchor;
}

export interface AnchoredConcerns {
  all: Concern[];
  byAnchor: Record<ConcernAnchor, Concern[]>;
  highest: ConcernSeverity | null;
}

const FIELD_ANCHORS: Record<string, ConcernAnchor> = {
  working_capital_months: 'reserves',
  income_statement: 'money',
  total_revenue: 'money',
  total_expenses: 'money',
};

const TYPE_ANCHORS: Record<string, ConcernAnchor> = {
  risk_deduction: 'risks',
  zakat_hoarding: 'zakat',
  ceo_comp_excessive: 'governance',
  gik_inflation: 'money',
  revenue_expense_mismatch: 'money',
  implausible_cpb: 'money',
  high_fundraising_ratio: 'money',
  domestic_burn: 'money',
  geographic_mismatch: 'whatTheyDo',
  data_quality: 'trust',
};

const ANCHORS: ConcernAnchor[] = [
  'reserves', 'money', 'risks', 'zakat', 'governance', 'whatTheyDo', 'trust',
];

const SEVERITY_RANK: Record<ConcernSeverity, number> = { high: 0, medium: 1, low: 2 };

const toSeverity = (v: unknown): ConcernSeverity => {
  const s = String(v ?? '').toLowerCase();
  if (s === 'high' || s === 'medium' || s === 'low') return s;
  // Fail toward visibility, not away from it. 'high' would falsely trip the
  // header's high-severity indicator; 'low' would bury a malformed value or
  // a future severity (e.g. 'critical') under 215 legitimate low concerns.
  // 'medium' surfaces it without overstating it.
  return 'medium';
};

const toDataPoints = (v: unknown): Record<string, string | number | boolean> => {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return {};
  const out: Record<string, string | number | boolean> = {};
  for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
    if (typeof val === 'string' || typeof val === 'number' || typeof val === 'boolean') out[k] = val;
  }
  return out;
};

const emptyByAnchor = (): Record<ConcernAnchor, Concern[]> => ({
  reserves: [], money: [], risks: [], zakat: [], governance: [], whatTheyDo: [], trust: [],
});

export const anchorConcerns = (raw: unknown): AnchoredConcerns => {
  const byAnchor = emptyByAnchor();
  if (!Array.isArray(raw)) return { all: [], byAnchor, highest: null };

  const all: Concern[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
    const rec = item as Record<string, unknown>;
    const dataPoints = toDataPoints(rec.data_points);
    const field = typeof dataPoints.field === 'string' ? dataPoints.field : '';
    const type = String(rec.type ?? '');
    const anchor = FIELD_ANCHORS[field] ?? TYPE_ANCHORS[type] ?? 'trust';
    all.push({
      type,
      severity: toSeverity(rec.severity),
      headline: String(rec.headline ?? ''),
      detail: String(rec.detail ?? ''),
      dataPoints,
      anchor,
    });
  }

  const bySeverity = (a: Concern, b: Concern): number =>
    SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity];

  all.sort(bySeverity);
  for (const anchor of ANCHORS) {
    byAnchor[anchor] = all.filter((c) => c.anchor === anchor).sort(bySeverity);
  }

  return { all, byAnchor, highest: all.length > 0 ? all[0].severity : null };
};

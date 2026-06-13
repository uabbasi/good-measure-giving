import type { CdpData } from './useCdpData';

export interface SectionDef {
  id: string;
  label: string;
  applies: (d: CdpData) => boolean;
}

export const SECTIONS: SectionDef[] = [
  { id: 'about',              label: 'About',                applies: () => true },
  { id: 'why-this-score',     label: 'Why this score',       applies: (d) => d.amalScore != null },
  { id: 'strengths-concerns', label: 'Strengths & concerns', applies: () => true },
  { id: 'evidence',           label: 'Evidence',             applies: (d) => !!d.rich?.impact_evidence || !d.canViewRich },
  { id: 'donor-fit',          label: 'Donor fit',            applies: (d) => !!d.rich?.ideal_donor_profile || !d.canViewRich },
  { id: 'financials',         label: 'Financials',           applies: (d) => !!d.revenue || !!d.financials },
  { id: 'leadership',         label: 'Leadership',           applies: (d) => !!d.rich?.organizational_capacity || !!d.charity.baselineGovernance || !d.canViewRich },
  { id: 'trust-awards',       label: 'Trust & awards',       applies: (d) => !!d.charity.awards || !!d.rich?.bbb_assessment || !d.canViewRich },
  {
    id: 'zakat',
    label: 'Zakat',
    applies: (d) =>
      !!d.charity.amalEvaluation?.zakat_classification ||
      d.charity.amalEvaluation?.wallet_tag === 'ZAKAT-ELIGIBLE',
  },
  { id: 'similar-orgs',       label: 'Similar orgs',         applies: (d) => !!d.rich?.similar_organizations?.length || !d.canViewRich },
];

export function visibleSections(d: CdpData): SectionDef[] {
  return SECTIONS.filter(s => s.applies(d));
}

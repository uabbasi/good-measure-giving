import { useMemo } from 'react';
import type {
  CharityProfile,
  AmalEvaluation,
  BaselineNarrative,
  RichNarrative,
  UISignalsV1,
  CharityFinancials,
} from '../../../types';
import { resolveCitationUrls, type CitationLike } from '../../utils/citationUrls';
import { deriveUISignalsFromCharity } from '../../utils/scoreUtils';
import { getTheoryOfChangeCitations, type TocCitation } from './sections/_primitives';

export interface CdpData {
  charity: CharityProfile;
  canViewRich: boolean;
  amal: AmalEvaluation | undefined;
  baseline: BaselineNarrative | undefined;
  rich: RichNarrative | undefined;
  hasRich: boolean;
  amalScore: number | null;
  impact: number | undefined;
  alignment: number | undefined;
  riskDeduction: number | undefined;
  signals: UISignalsV1;
  financials: CharityFinancials | undefined;
  revenue: number | undefined;
  headline: string;
  aboutSummary: string;
  citations: CitationLike[];
  theoryOfChangeCitations: TocCitation[];
}

export function buildCdpData(charity: CharityProfile, canViewRich: boolean): CdpData {
  const amal = charity.amalEvaluation;
  const baseline = amal?.baseline_narrative;
  const rich = amal?.rich_narrative;
  const scores = amal?.confidence_scores;
  const financials = charity.financials ?? charity.rawData?.financials;
  const rawCitations = (
    canViewRich
      ? (rich?.all_citations || baseline?.all_citations || [])
      : (baseline?.all_citations || [])
  ) as CitationLike[];
  const citations = resolveCitationUrls(rawCitations, charity);

  return {
    charity,
    canViewRich,
    amal,
    baseline,
    rich,
    hasRich: !!amal?.rich_narrative,
    amalScore: amal?.amal_score ?? null,
    impact: scores?.impact,
    alignment: scores?.alignment,
    riskDeduction: amal?.score_details?.risk_deduction,
    signals: deriveUISignalsFromCharity(charity),
    financials,
    revenue: financials?.totalRevenue || charity.rawData?.total_revenue,
    headline: canViewRich
      ? (rich?.headline || baseline?.headline || '')
      : (baseline?.headline || ''),
    aboutSummary: canViewRich
      ? (rich?.summary || baseline?.summary || '')
      : (baseline?.summary || ''),
    citations,
    theoryOfChangeCitations: getTheoryOfChangeCitations(citations as TocCitation[]),
  };
}

export function useCdpData(charity: CharityProfile, canViewRich: boolean): CdpData {
  return useMemo(() => buildCdpData(charity, canViewRich), [charity, canViewRich]);
}

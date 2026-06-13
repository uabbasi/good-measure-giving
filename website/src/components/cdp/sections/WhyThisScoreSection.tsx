/**
 * WhyThisScoreSection (CDP single-scroll): id="why-this-score".
 * Lifted verbatim from TabbedView's renderImpactTab "Methodology Details" block:
 * NEW_ORG charities get a non-numeric message; everyone else gets the rich-gated
 * <ScoreBreakdown /> (confidence scores, rationale, dimension explanations,
 * strengths, areas for improvement, theory of change summary).
 */
import React from 'react';
import { BarChart3 } from 'lucide-react';
import { useLandingTheme } from '../../../../contexts/LandingThemeContext';
import { ScoreBreakdown } from '../../ScoreBreakdown';
import type { RichCitation } from '../../../../types';
import type { CdpData } from '../useCdpData';
import { SectionCard, SectionHeader } from './_primitives';

export const WhyThisScoreSection: React.FC<{ data: CdpData }> = ({ data }) => {
  const { isDark } = useLandingTheme();
  const { charity, canViewRich, amal, baseline, rich, amalScore } = data;
  const scores = amal?.confidence_scores;

  const areasForImprovement = (
    canViewRich ? rich?.areas_for_improvement : baseline?.areas_for_improvement
  ) as Array<string | { area: string; context: string; citation_ids: string[] }> | undefined;

  if (!amal?.score_details) return null;

  return (
    <section id="why-this-score" className="space-y-5">
      {charity.evaluationTrack === 'NEW_ORG' ? (
        <SectionCard isDark={isDark}>
          <SectionHeader icon={BarChart3} title="Methodology" isDark={isDark} />
          <p className={`text-sm leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            This organization is too early to rate numerically.
            We show qualitative context and early indicators while it builds a longer public track record.
          </p>
        </SectionCard>
      ) : (
        <SectionCard isDark={isDark}>
          <SectionHeader icon={BarChart3} title="Methodology Details" isDark={isDark} />
          <ScoreBreakdown
            scoreDetails={amal.score_details}
            confidenceScores={scores}
            amalScore={amalScore ?? 0}
            citations={data.citations as RichCitation[]}
            isSignedIn={canViewRich}
            isDark={isDark}
            dimensionExplanations={rich?.dimension_explanations || baseline?.dimension_explanations}
            amalScoreRationale={canViewRich ? rich?.amal_score_rationale : undefined}
            scoreSummary={charity.scoreSummary}
            strengths={canViewRich ? rich?.strengths : baseline?.strengths}
            areasForImprovement={areasForImprovement}
            theoryOfChangeSummary={rich?.impact_evidence?.theory_of_change_summary || charity.theoryOfChange}
          />
        </SectionCard>
      )}
    </section>
  );
};

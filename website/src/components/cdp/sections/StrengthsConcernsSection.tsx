/**
 * StrengthsConcernsSection (CDP single-scroll): id="strengths-concerns".
 * Lifted verbatim from TabbedView's renderGivingTab "Balanced View" block:
 * case_against summary (rich) or score summary (baseline fallback), Strengths
 * (green + source links), Key Concerns (red/amber alerts with data points),
 * Growth Areas (amber), Considerations (rich risk factors), mitigation notes, and
 * the UI signal-state fallback pills + recommendation rationale. The whole section
 * renders only when there is content; the inner card is shown when
 * `canViewRich || !rich?.case_against`, otherwise an anonymous ContentPreview.
 */
import React from 'react';
import { Scale, AlertTriangle } from 'lucide-react';
import { useLandingTheme } from '../../../../contexts/LandingThemeContext';
import { GLOSSARY } from '../../../data/glossary';
import { SourceLinkedText } from '../../SourceLinkedText';
import { ContentPreview } from '../../ContentPreview';
import type { KeyConcern } from '../../../../types';
import type { CdpData } from '../useCdpData';
import { SectionCard, SectionHeader } from './_primitives';

export const StrengthsConcernsSection: React.FC<{ data: CdpData }> = ({ data }) => {
  const { isDark } = useLandingTheme();
  const { charity, canViewRich, amal, baseline, rich, citations, keyConcerns, uiSignals } = data;

  const strengths = (canViewRich ? (rich?.strengths || baseline?.strengths) : baseline?.strengths) || [];
  const areasForImprovement = (
    canViewRich ? rich?.areas_for_improvement : baseline?.areas_for_improvement
  ) as Array<string | { area: string; context: string; citation_ids: string[] }> | undefined;

  // Key Concerns render helper (verbatim from TabbedView)
  const renderKeyConcerns = (concerns: KeyConcern[]) => {
    if (!concerns.length) return null;
    return (
      <div className="space-y-2">
        {concerns.map((concern, i) => {
          const isHigh = concern.severity === 'high';
          const borderColor = isHigh
            ? (isDark ? 'border-red-500/60' : 'border-red-400')
            : (isDark ? 'border-amber-500/50' : 'border-amber-400');
          const bgColor = isHigh
            ? (isDark ? 'bg-red-950/30' : 'bg-red-50')
            : (isDark ? 'bg-amber-950/20' : 'bg-amber-50');
          const iconColor = isHigh
            ? (isDark ? 'text-red-400' : 'text-red-600')
            : (isDark ? 'text-amber-400' : 'text-amber-600');
          const headlineColor = isHigh
            ? (isDark ? 'text-red-300' : 'text-red-800')
            : (isDark ? 'text-amber-300' : 'text-amber-800');

          return (
            <div key={i} className={`rounded-lg border-2 ${borderColor} ${bgColor} p-3`}>
              <div className="flex items-start gap-2">
                <AlertTriangle className={`w-4 h-4 mt-0.5 flex-shrink-0 ${iconColor}`} />
                <div className="flex-1 min-w-0">
                  <div className={`text-sm font-semibold ${headlineColor}`}>
                    {concern.headline}
                  </div>
                  <div className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {concern.detail}
                  </div>
                  {concern.data_points && Object.keys(concern.data_points).length > 0 && (
                    <div className={`flex flex-wrap gap-3 mt-2 text-xs font-mono ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                      {concern.type === 'gik_inflation' && concern.data_points.noncash_ratio != null && (
                        <span>Noncash: {(concern.data_points.noncash_ratio * 100).toFixed(0)}%</span>
                      )}
                      {concern.type === 'gik_inflation' && concern.data_points.cash_adjusted_program_ratio != null && (
                        <span>Cash-adj program ratio: {(concern.data_points.cash_adjusted_program_ratio * 100).toFixed(0)}%</span>
                      )}
                      {concern.type === 'domestic_burn' && concern.data_points.domestic_burn_rate != null && (
                        <span>Domestic spend: {(concern.data_points.domestic_burn_rate * 100).toFixed(0)}%</span>
                      )}
                      {concern.type === 'zakat_hoarding' && concern.data_points.reserves_months != null && (
                        <span>Reserves: {concern.data_points.reserves_months.toFixed(0)} months</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  if (!(strengths.length > 0 || keyConcerns.length > 0 || (areasForImprovement && areasForImprovement.length > 0) || rich?.case_against)) {
    return null;
  }

  return (
    <section id="strengths-concerns">
      {canViewRich || !rich?.case_against ? (
        <SectionCard isDark={isDark}>
          <SectionHeader icon={Scale} title="Balanced View" isDark={isDark} infoTip={GLOSSARY['Things to Know']} />
          {rich?.case_against?.summary && canViewRich && (
            <p className={`text-sm mb-4 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              <SourceLinkedText text={rich.case_against.summary} citations={citations} isDark={isDark} />
            </p>
          )}
          {(charity.scoreSummary || amal?.score_details?.score_summary) && !rich?.case_against && (
            <p className={`text-sm mb-4 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              {charity.scoreSummary || amal?.score_details?.score_summary}
            </p>
          )}
          {strengths.length > 0 && (
            <div className="mb-4">
              <div className={`text-xs font-semibold mb-2 ${isDark ? 'text-emerald-400' : 'text-emerald-700'}`}>
                Strengths
              </div>
              <ul className={`space-y-1.5 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                {strengths.map((s, i) => {
                  const text = typeof s === 'object' ? s.point : s;
                  return (
                    <li key={i} className="flex items-start gap-2">
                      <span className={isDark ? 'text-emerald-400' : 'text-emerald-600'}>+</span>
                      <SourceLinkedText text={text} citations={citations} isDark={isDark} subtle />
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
          {keyConcerns.length > 0 && (
            <div className="mb-4">
              <div className={`text-xs font-semibold mb-2 ${isDark ? 'text-red-400' : 'text-red-700'}`}>
                Key Concerns
              </div>
              {renderKeyConcerns(keyConcerns)}
            </div>
          )}
          {areasForImprovement && areasForImprovement.length > 0 && (
            <div className={keyConcerns.length > 0 || strengths.length > 0 ? '' : 'mb-4'}>
              <div className={`text-xs font-semibold mb-2 ${isDark ? 'text-amber-400' : 'text-amber-700'}`}>
                Growth Areas
              </div>
              <ul className={`space-y-1.5 text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                {areasForImprovement.slice(0, 4).map((a, i) => {
                  const text = typeof a === 'object' ? a.area : a;
                  return (
                    <li key={i} className="flex items-start gap-2">
                      <span className={isDark ? 'text-amber-400' : 'text-amber-600'}>-</span>
                      <SourceLinkedText text={text} citations={citations} isDark={isDark} subtle />
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
          {rich?.case_against?.risk_factors && rich.case_against.risk_factors.length > 0 && canViewRich && (
            <div className={`mt-4 pt-3 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
              <div className={`text-xs font-semibold mb-2 flex items-center gap-1 ${isDark ? 'text-violet-400' : 'text-violet-600'}`}>
                <Scale className="w-3 h-3" />
                Considerations
              </div>
              <ul className={`text-xs space-y-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                {rich.case_against.risk_factors.map((risk, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-violet-500 mt-0.5">-</span>
                    <SourceLinkedText text={risk} citations={citations} isDark={isDark} />
                  </li>
                ))}
              </ul>
            </div>
          )}
          {rich?.case_against?.mitigation_notes && canViewRich && (
            <div className={`mt-3 pt-2 border-t text-xs ${isDark ? 'border-slate-700 text-slate-500' : 'border-slate-200 text-slate-500'}`}>
              <span className="font-semibold">Mitigation:</span> {rich.case_against.mitigation_notes}
            </div>
          )}
          {!rich?.case_against && uiSignals?.signal_states && (
            <div className={`mt-4 pt-3 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
              <div className="flex flex-wrap gap-2 mb-2">
                {(Object.entries(uiSignals.signal_states) as [string, string][]).map(([key, state]) => {
                  const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                  const pillClasses = state === 'Strong'
                    ? (isDark ? 'bg-emerald-900/40 text-emerald-400 border-emerald-700' : 'bg-emerald-50 text-emerald-700 border-emerald-300')
                    : state === 'Moderate'
                    ? (isDark ? 'bg-amber-900/30 text-amber-400 border-amber-700' : 'bg-amber-50 text-amber-700 border-amber-300')
                    : (isDark ? 'bg-slate-700/50 text-slate-400 border-slate-600' : 'bg-slate-100 text-slate-500 border-slate-300');
                  return (
                    <span key={key} className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border ${pillClasses}`}>
                      {label}: {state}
                    </span>
                  );
                })}
              </div>
              {uiSignals?.recommendation_rationale && (
                <p className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  {uiSignals.recommendation_rationale}
                </p>
              )}
            </div>
          )}
        </SectionCard>
      ) : (
        <ContentPreview title="Balanced View" description="strengths, concerns, and important context" valueProps={['Risk factors and mitigation notes', 'Case against giving analysis', 'Important context for donors']} />
      )}
    </section>
  );
};

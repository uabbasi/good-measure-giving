/**
 * EvidenceSection (CDP single-scroll): id="evidence".
 * Lifted verbatim from TabbedView's renderImpactTab "Evidence" block:
 * evidence grade + explanation, RCT availability, theory of change + summary +
 * linked sources, external evaluations, evidence-quality checklist, citation
 * stats (total/unique/strong/by-type), and Form 990 tax year. Rich-gated with an
 * anonymous ContentPreview fallback.
 */
import React from 'react';
import { Shield, ExternalLink, CheckCircle2, AlertCircle } from 'lucide-react';
import { useLandingTheme } from '../../../../contexts/LandingThemeContext';
import { InfoTip } from '../../InfoTip';
import { GLOSSARY } from '../../../data/glossary';
import { SourceLinkedText } from '../../SourceLinkedText';
import { ContentPreview } from '../../ContentPreview';
import type { CdpData } from '../useCdpData';
import { SectionCard, SectionHeader } from './_primitives';

export const EvidenceSection: React.FC<{ data: CdpData }> = ({ data }) => {
  const { isDark } = useLandingTheme();
  const { charity, canViewRich, rich, citations, theoryOfChangeCitations } = data;

  if (!(rich?.impact_evidence || charity.evidenceQuality || rich?.citation_stats)) {
    return null;
  }

  if (!(canViewRich || charity.evidenceQuality)) {
    return (
      <section id="evidence">
        <ContentPreview title="Evidence" description="evidence quality and evaluation details" valueProps={['Theory of change assessment', 'Evidence grade and methodology', 'External evaluations and citations']} />
      </section>
    );
  }

  return (
    <section id="evidence">
      <SectionCard isDark={isDark}>
        <SectionHeader icon={Shield} title="Evidence" isDark={isDark} infoTip={GLOSSARY['Impact Evidence']} />
        {/* Impact Evidence grade + details (signed-in with rich) */}
        {rich?.impact_evidence && canViewRich && (
          <>
            {charity.evaluationTrack === 'NEW_ORG' && (
              <div className={`mb-3 p-2 rounded text-xs ${
                isDark ? 'bg-sky-900/30 text-sky-300 border border-sky-800/50' : 'bg-sky-50 text-sky-700 border border-sky-200'
              }`}>
                <strong>Emerging org evaluation:</strong> As a newer organization{charity.foundedYear ? ` (est. ${charity.foundedYear})` : ''},
                evidence is assessed on theory of change and early indicators rather than years of outcome data.
              </div>
            )}
            <div className="flex items-start gap-2 mb-3">
              <span className={`px-2 py-1 rounded font-mono font-bold text-sm flex-shrink-0 ${
                rich.impact_evidence.evidence_grade === 'A' || rich.impact_evidence.evidence_grade === 'B'
                  ? isDark ? 'bg-emerald-900/50 text-emerald-400' : 'bg-emerald-100 text-emerald-700'
                  : rich.impact_evidence.evidence_grade === 'C' || rich.impact_evidence.evidence_grade === 'D'
                  ? isDark ? 'bg-amber-900/50 text-amber-400' : 'bg-amber-100 text-amber-700'
                  : isDark ? 'bg-red-900/50 text-red-400' : 'bg-red-100 text-red-700'
              }`}>
                {rich.impact_evidence.evidence_grade}
              </span>
              <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                <SourceLinkedText text={rich.impact_evidence.evidence_grade_explanation || ''} citations={citations} isDark={isDark} />
              </span>
            </div>
            <div className={`space-y-1.5 text-xs ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              <div className="flex justify-between">
                <span>RCT Available</span>
                <span className={`font-mono ${rich.impact_evidence.rct_available ? isDark ? 'text-emerald-400' : 'text-emerald-600' : isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  {rich.impact_evidence.rct_available ? 'YES' : 'NO'}
                </span>
              </div>
              {rich.impact_evidence.theory_of_change && (
                <div className="flex justify-between">
                  <span className="flex items-center gap-1">Theory of Change <InfoTip text={GLOSSARY['Theory of Change']} isDark={isDark} /></span>
                  <span className="font-mono">{rich.impact_evidence.theory_of_change.toUpperCase()}</span>
                </div>
              )}
            </div>
            {rich.impact_evidence.theory_of_change_summary && (
              <div className={`mt-3 pt-3 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <div className={`text-xs font-semibold mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Theory of Change Summary
                </div>
                <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  <SourceLinkedText text={rich.impact_evidence.theory_of_change_summary} citations={citations} isDark={isDark} />
                </p>
                {theoryOfChangeCitations.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {theoryOfChangeCitations.map((c, i) => (
                      <a
                        key={`${c.id || 'toc'}-${i}`}
                        href={c.source_url || undefined}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] border ${
                          isDark ? 'border-emerald-800/60 text-emerald-400 hover:bg-emerald-900/20' : 'border-emerald-200 text-emerald-700 hover:bg-emerald-50'
                        }`}
                        title={c.source_name || 'Source'}
                      >
                        {(c.source_name || `Source ${i + 1}`).replace(/^Charity Website\s*-\s*/i, '')}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    ))}
                  </div>
                )}
              </div>
            )}
            {rich.impact_evidence.external_evaluations && rich.impact_evidence.external_evaluations.length > 0 && (
              <div className={`mt-2 pt-2 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>External Evaluations</div>
                <div className={`text-xs mt-1 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                  {rich.impact_evidence.external_evaluations.slice(0, 2).join(', ')}
                </div>
              </div>
            )}
          </>
        )}
        {/* Evidence quality checklist */}
        {charity.evidenceQuality && (
          <div className={`${rich?.impact_evidence && canViewRich ? `mt-4 pt-4 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}` : ''}`}>
            <div className="space-y-2">
              {[
                { key: 'hasOutcomeMethodology', label: 'Outcome methodology documented' },
                { key: 'hasMultiYearMetrics', label: 'Multi-year metrics tracked' },
                { key: 'thirdPartyEvaluated', label: 'Third-party evaluated' },
                { key: 'receivesFoundationGrants', label: 'Receives foundation grants' },
              ].map(({ key, label }) => {
                const val = (charity.evidenceQuality as Record<string, unknown>)?.[key];
                if (val === null || val === undefined) return null;
                return (
                  <div key={key} className="flex items-center gap-2 text-sm">
                    {val ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                    ) : (
                      <AlertCircle className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-slate-600' : 'text-slate-400'}`} />
                    )}
                    <span className={val ? (isDark ? 'text-slate-300' : 'text-slate-700') : (isDark ? 'text-slate-500' : 'text-slate-400')}>
                      {label}
                    </span>
                  </div>
                );
              })}
              {charity.evidenceQuality.evaluationSources && charity.evidenceQuality.evaluationSources.length > 0 && (
                <div className={`mt-2 pt-2 border-t text-xs ${isDark ? 'border-slate-800 text-slate-500' : 'border-slate-200 text-slate-400'}`}>
                  Sources: {charity.evidenceQuality.evaluationSources.join(', ')}
                </div>
              )}
            </div>
          </div>
        )}
        {/* Citation stats (signed-in only) */}
        {rich?.citation_stats && canViewRich && (
          <div className={`mt-4 pt-4 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
            <div className={`space-y-1.5 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              <div className="flex justify-between">
                <span>Total Citations</span>
                <span className="font-mono">{rich.citation_stats.total_count}</span>
              </div>
              <div className="flex justify-between">
                <span>Unique Sources</span>
                <span className="font-mono">{rich.citation_stats.unique_sources}</span>
              </div>
              <div className="flex justify-between">
                <span>Strong Sources</span>
                <span className={`font-mono ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                  {rich.citation_stats.high_confidence_count}
                </span>
              </div>
            </div>
            {rich.citation_stats.by_source_type && (
              <div className={`mt-2 pt-2 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <div className="flex flex-wrap gap-1">
                  {Object.entries(rich.citation_stats.by_source_type).map(([type, count]) => (
                    <span key={type} className={`px-1.5 py-0.5 rounded text-xs ${isDark ? 'bg-slate-700 text-slate-300' : 'bg-slate-200 text-slate-600'}`}>
                      {type}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {rich?.data_confidence?.form_990_tax_year && (
              <div className={`mt-2 pt-2 border-t text-xs ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <div className="flex justify-between">
                  <span className={isDark ? 'text-slate-500' : 'text-slate-400'}>990 Tax Year</span>
                  <span className={`font-mono ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{rich.data_confidence.form_990_tax_year}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </SectionCard>
    </section>
  );
};

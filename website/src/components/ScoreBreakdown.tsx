/**
 * ScoreBreakdown: Qualitative "Methodology Signals" section.
 * Uses Harvey balls and narrative evidence, intentionally hiding numeric scores.
 */

import React from 'react';
import { CheckCircle2, TrendingUp, AlertTriangle } from 'lucide-react';
import { InfoTip } from './InfoTip';
import { GLOSSARY } from '../data/glossary';
import {
  ScoreDetails,
  ConfidenceScores,
  RichCitation,
  ImpactDetails,
  AlignmentDetails,
  ScoreComponentDetail,
} from '../../types';
import { SourceLinkedText } from './SourceLinkedText';
import { stripCitations, formatComponentName, formatEvidenceForDonors, getArchetypeLabel } from '../utils/scoreUtils';

interface DimensionConfig {
  key: 'impact' | 'alignment';
  label: string;
  max: number;
}

const DIMENSIONS: DimensionConfig[] = [
  { key: 'impact', label: 'Impact', max: 50 },
  { key: 'alignment', label: 'Alignment', max: 50 },
];

interface ScoreBreakdownProps {
  scoreDetails: ScoreDetails;
  confidenceScores?: ConfidenceScores;
  amalScore: number;
  citations: RichCitation[];
  isSignedIn: boolean;
  isDark: boolean;
  dimensionExplanations?: {
    impact?: string | { explanation: string; improvement?: string; citation_ids: string[] };
    alignment?: string | { explanation: string; improvement?: string; citation_ids: string[] };
    [key: string]: unknown;
  };
  amalScoreRationale?: string;
  scoreSummary?: string | null;
  strengths?: Array<string | { point: string; detail: string; citation_ids: string[] }>;
  areasForImprovement?: Array<string | { area: string; context: string; citation_ids: string[] }>;
}

export type HarveyLevel = 0 | 1 | 2 | 3 | 4;
export type HarveyTone = 'good' | 'mixed' | 'caution' | 'neutral';

const HARVEY_DEGREES: Record<HarveyLevel, number> = {
  0: 0,
  1: 90,
  2: 180,
  3: 270,
  4: 360,
};

const isDataUnavailable = (component: ScoreComponentDetail): boolean =>
  component.scored === 0 && !!component.evidence &&
  /not (yet )?available|unknown|insufficient data/i.test(component.evidence);

const isFinancialHealthComponent = (component: ScoreComponentDetail): boolean => {
  const n = component.name.toLowerCase();
  return n.includes('financial health') || n.includes('financial_health');
};

const extractWorkingCapitalMonths = (evidence: string): number | null => {
  const match = evidence.match(/working capital:\s*(-?\d+(?:\.\d+)?)\s*months/i);
  if (!match) return null;
  const months = Number.parseFloat(match[1]);
  return Number.isFinite(months) ? months : null;
};

const getFinancialHealthContext = (component: ScoreComponentDetail): {
  benchmark: string;
  current: string;
  replacementSuggestion: string;
} => {
  const benchmark = 'What good looks like: reserve policy matched to mission risk. Typical range is 3-12 months for most nonprofits (often higher for volatile emergency response or designated endowment models).';
  const months = extractWorkingCapitalMonths(component.evidence || '');

  if (months === null) {
    return {
      benchmark,
      current: 'Current reserves are not reported.',
      replacementSuggestion: 'Publish reserve levels and define a board-approved operating reserve policy (typically 3-12 months for most organizations).',
    };
  }

  const monthLabel = `${months.toFixed(1)} months`;
  if (months < 1) {
    return {
      benchmark,
      current: `Current reserves: ${monthLabel} (critical liquidity risk).`,
      replacementSuggestion: 'Urgently increase operating reserves to improve continuity; aim for at least 3 months unless a different policy is explicitly justified.',
    };
  }
  if (months < 3) {
    return {
      benchmark,
      current: `Current reserves: ${monthLabel} (lean buffer).`,
      replacementSuggestion: 'Strengthen the liquidity buffer toward a resilient operating range (commonly 3-12 months), based on revenue volatility.',
    };
  }
  if (months <= 12) {
    return {
      benchmark,
      current: `Current reserves: ${monthLabel} (healthy range).`,
      replacementSuggestion: 'Maintain current reserve discipline and document clear deployment triggers.',
    };
  }
  if (months <= 24) {
    return {
      benchmark,
      current: `Current reserves: ${monthLabel} (high but potentially reasonable).`,
      replacementSuggestion: 'Ensure reserves are intentional: document what portion is designated, restricted, or planned for staged deployment.',
    };
  }

  return {
    benchmark,
    current: `Current reserves: ${monthLabel} (very high).`,
    replacementSuggestion: 'Publish a time-bound plan to deploy excess unrestricted reserves into mission delivery, while keeping a clear operating reserve floor.',
  };
};

const normalizeImprovementSuggestion = (component: ScoreComponentDetail): string | null => {
  const suggestion = component.improvement_suggestion?.trim();
  if (!suggestion) return null;

  if (
    isFinancialHealthComponent(component) &&
    (
      /build working capital reserves to 1-3 months/i.test(suggestion) ||
      /build working capital reserves down to 1-3 months/i.test(suggestion) ||
      /reduce(?:ing)? .*working capital.*1-3 months/i.test(suggestion)
    )
  ) {
    return getFinancialHealthContext(component).replacementSuggestion;
  }

  if (
    isFinancialHealthComponent(component) &&
    /capital deployment plan.*excess reserves.*operating reserve target/i.test(suggestion)
  ) {
    return getFinancialHealthContext(component).replacementSuggestion;
  }

  return suggestion;
};

export const ratioToHarveyLevel = (ratio: number): HarveyLevel => {
  if (ratio >= 0.8) return 4;
  if (ratio >= 0.6) return 3;
  if (ratio >= 0.4) return 2;
  if (ratio >= 0.2) return 1;
  return 0;
};

export const levelToTone = (level: HarveyLevel): HarveyTone => {
  if (level >= 3) return 'good';
  if (level === 2) return 'mixed';
  if (level <= 1) return 'caution';
  return 'neutral';
};

export const levelToLabel = (level: HarveyLevel): string => {
  if (level === 4) return 'Strong';
  if (level === 3) return 'Good';
  if (level === 2) return 'Moderate';
  if (level === 1) return 'Weak';
  return 'Insufficient';
};

const getHarveyPalette = (tone: HarveyTone, isDark: boolean): {
  fill: string;
  empty: string;
  border: string;
  text: string;
} => {
  if (tone === 'good') {
    return isDark
      ? { fill: '#34d399', empty: '#334155', border: 'border-emerald-700/70', text: 'text-emerald-300' }
      : { fill: '#059669', empty: '#e2e8f0', border: 'border-emerald-300', text: 'text-emerald-700' };
  }
  if (tone === 'mixed') {
    return isDark
      ? { fill: '#f59e0b', empty: '#334155', border: 'border-amber-700/70', text: 'text-amber-300' }
      : { fill: '#d97706', empty: '#e2e8f0', border: 'border-amber-300', text: 'text-amber-700' };
  }
  if (tone === 'caution') {
    return isDark
      ? { fill: '#fb7185', empty: '#334155', border: 'border-rose-700/70', text: 'text-rose-300' }
      : { fill: '#e11d48', empty: '#e2e8f0', border: 'border-rose-300', text: 'text-rose-700' };
  }
  return isDark
    ? { fill: '#94a3b8', empty: '#334155', border: 'border-slate-600', text: 'text-slate-300' }
    : { fill: '#64748b', empty: '#e2e8f0', border: 'border-slate-300', text: 'text-slate-700' };
};

export const HarveyBall: React.FC<{
  level: HarveyLevel;
  tone?: HarveyTone;
  isDark: boolean;
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}> = ({ level, tone, isDark, size = 'md', label }) => {
  const resolvedTone = tone || levelToTone(level);
  const palette = getHarveyPalette(resolvedTone, isDark);
  const deg = HARVEY_DEGREES[level];
  const sizeClass = size === 'sm' ? 'w-6 h-6' : size === 'lg' ? 'w-9 h-9' : 'w-7 h-7';

  return (
    <span
      aria-label={label || levelToLabel(level)}
      title={label || levelToLabel(level)}
      className={`block shrink-0 translate-y-px rounded-full border ${sizeClass} ${palette.border}`}
      style={{ background: `conic-gradient(${palette.fill} ${deg}deg, ${palette.empty} ${deg}deg)` }}
    />
  );
};

const ComponentRow: React.FC<{
  component: ScoreComponentDetail;
  citations: RichCitation[];
  isSignedIn: boolean;
  isDark: boolean;
}> = ({ component, citations, isSignedIn, isDark }) => {
  const noData = isDataUnavailable(component);
  const isFinancialHealth = isFinancialHealthComponent(component);
  const financialHealthContext = isFinancialHealth ? getFinancialHealthContext(component) : null;
  const improvementSuggestion = normalizeImprovementSuggestion(component);
  const ratio = component.possible > 0 ? component.scored / component.possible : 0;
  const level = noData ? 0 : ratioToHarveyLevel(ratio);
  const tone = noData ? 'neutral' : levelToTone(level);
  const palette = getHarveyPalette(tone, isDark);

  return (
    <div className="py-3">
      <div className="flex items-center gap-3">
        <HarveyBall level={level} tone={tone} isDark={isDark} size="sm" />
        <span className={`flex-1 text-sm ${noData ? (isDark ? 'text-slate-500' : 'text-slate-400') : (isDark ? 'text-slate-200' : 'text-slate-700')}`}>
          {formatComponentName(component.name)}
        </span>
        <span className={`text-xs font-semibold ${palette.text}`}>
          {noData ? 'No Data' : levelToLabel(level)}
        </span>
      </div>

      {financialHealthContext && (
        <div className={`mt-1 ml-10 text-[11px] leading-relaxed ${
          isDark ? 'text-slate-400' : 'text-slate-600'
        }`}>
          <p><strong>{financialHealthContext.benchmark}</strong></p>
          <p className={isDark ? 'text-slate-500' : 'text-slate-500'}>{financialHealthContext.current}</p>
        </div>
      )}

      {component.evidence && !noData && (
        <p className={`mt-1 ml-10 text-xs leading-relaxed ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
          {(() => {
            const formatted = formatEvidenceForDonors(component.evidence);
            return isSignedIn ? (
              <SourceLinkedText text={formatted} citations={citations} isDark={isDark} />
            ) : (
              stripCitations(formatted)
            );
          })()}
        </p>
      )}

      {improvementSuggestion && (
        <p className={`mt-1 ml-10 text-xs leading-relaxed ${isDark ? 'text-amber-300/80' : 'text-amber-700'}`}>
          {improvementSuggestion}
        </p>
      )}
    </div>
  );
};


const DimensionSection: React.FC<{
  config: DimensionConfig;
  details: ImpactDetails | AlignmentDetails;
  explanation?: string | { explanation: string; improvement?: string; citation_ids: string[] };
  citations: RichCitation[];
  isSignedIn: boolean;
  isDark: boolean;
}> = ({ config, details, explanation, citations, isSignedIn, isDark }) => {
  const ratio = config.max > 0 ? details.score / config.max : 0;
  const level = ratioToHarveyLevel(ratio);
  const tone = levelToTone(level);
  const palette = getHarveyPalette(tone, isDark);

  const explanationText = typeof explanation === 'object' ? explanation.explanation : explanation;
  const improvementText = typeof explanation === 'object' ? explanation.improvement : undefined;
  const hasCitations = typeof explanation === 'object';
  const rubricArchetype = 'rubric_archetype' in details ? (details as ImpactDetails).rubric_archetype : undefined;

  return (
    <div className={`rounded-lg pb-1 ${isDark ? 'bg-slate-800/60' : 'bg-slate-50'}`}>
      <div className="p-4 pb-2">
        <div className="flex items-center justify-between mb-2 gap-3">
          <span className="flex items-center gap-2">
            <span className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
              {config.label}
            </span>
            {GLOSSARY[config.label] && <InfoTip text={GLOSSARY[config.label]} isDark={isDark} />}
            {rubricArchetype && (
              <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                isDark ? 'bg-indigo-900/40 text-indigo-300' : 'bg-indigo-50 text-indigo-700'
              }`}>
                {getArchetypeLabel(rubricArchetype)}
              </span>
            )}
          </span>
          <span className="inline-flex items-center gap-2">
            <HarveyBall level={level} tone={tone} isDark={isDark} size="md" label={`${config.label}: ${levelToLabel(level)}`} />
            <span className={`text-sm font-bold ${palette.text}`}>{levelToLabel(level)}</span>
          </span>
        </div>
      </div>

      {explanationText && (
        <div className="px-4 pb-2">
          <p className={`text-sm leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            {isSignedIn && hasCitations ? (
              <SourceLinkedText text={explanationText} citations={citations} isDark={isDark} />
            ) : (
              stripCitations(explanationText || '')
            )}
          </p>
        </div>
      )}

      {isSignedIn ? (
        <div className={`px-4 pb-3 divide-y ${isDark ? 'divide-slate-700/40' : 'divide-slate-200/80'}`}>
          {details.components.map((comp) => (
            <ComponentRow
              key={comp.name}
              component={comp}
              citations={citations}
              isSignedIn={isSignedIn}
              isDark={isDark}
            />
          ))}
        </div>
      ) : (
        <div className={`mx-4 mb-3 px-3 py-2.5 rounded-lg text-center ${
          isDark ? 'bg-slate-700/40' : 'bg-slate-100'
        }`}>
          <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            Sign in to see the full component-level assessment
          </p>
        </div>
      )}

      {isSignedIn && improvementText && (
        <div className={`mx-4 mt-2 mb-5 px-3 py-2.5 rounded-lg flex items-start gap-2 ${
          isDark ? 'bg-amber-900/15' : 'bg-amber-50'
        }`}>
          <TrendingUp className={`w-3.5 h-3.5 shrink-0 mt-0.5 ${
            isDark ? 'text-amber-400' : 'text-amber-600'
          }`} />
          <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
            <SourceLinkedText text={improvementText} citations={citations} isDark={isDark} />
          </p>
        </div>
      )}
    </div>
  );
};

const getRiskSignal = (riskDeduction: number): { label: string; level: HarveyLevel; tone: HarveyTone } => {
  if (riskDeduction <= -4) return { label: 'High Organizational Risk', level: 1, tone: 'caution' };
  if (riskDeduction <= -1) return { label: 'Moderate Organizational Risk', level: 2, tone: 'mixed' };
  return { label: 'Low Organizational Risk', level: 4, tone: 'good' };
};

export const ScoreBreakdown: React.FC<ScoreBreakdownProps> = ({
  scoreDetails,
  citations,
  isSignedIn,
  isDark,
  dimensionExplanations,
  amalScoreRationale,
  scoreSummary,
  strengths,
  areasForImprovement,
}) => {
  const dataConfidence = scoreDetails.data_confidence;
  const riskSignal = getRiskSignal(scoreDetails.risk_deduction || 0);
  const hasStrengths = strengths && strengths.length > 0;
  const hasImprovements = areasForImprovement && areasForImprovement.length > 0;

  return (
    <div className={`rounded-lg border p-4 md:p-6 mb-6 ${
      isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
    }`}>
      <div className={`text-xs uppercase tracking-widest font-semibold mb-3 ${
        isDark ? 'text-slate-500' : 'text-slate-500'
      }`}>
        How We Evaluate
      </div>

      {amalScoreRationale && (
        <p className={`text-sm leading-relaxed mb-4 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
          {isSignedIn ? (
            <SourceLinkedText text={amalScoreRationale} citations={citations} isDark={isDark} />
          ) : (
            stripCitations(amalScoreRationale)
          )}
        </p>
      )}
      {!amalScoreRationale && scoreSummary && (
        <p className={`text-sm leading-relaxed mb-4 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
          {scoreSummary}
        </p>
      )}

      {hasStrengths && (
        <div className="mb-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          {strengths!.map((strength, i) => {
            const isRichFormat = typeof strength === 'object';
            const displayText = isSignedIn
              ? (isRichFormat ? `${strength.point}: ${strength.detail}` : strength)
              : (isRichFormat ? strength.point : stripCitations(strength as string));
            return (
              <div key={i} className={`px-3 py-2 rounded-lg flex items-start gap-2 ${
                isDark ? 'bg-emerald-900/20' : 'bg-emerald-50'
              }`}>
                <CheckCircle2 className={`w-3.5 h-3.5 shrink-0 mt-0.5 ${
                  isDark ? 'text-emerald-400' : 'text-emerald-600'
                }`} />
                <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  {isSignedIn && isRichFormat
                    ? <SourceLinkedText text={displayText as string} citations={citations} isDark={isDark} />
                    : displayText}
                </p>
              </div>
            );
          })}
        </div>
      )}

      <p className={`text-xs leading-relaxed mb-4 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
        <strong className={isDark ? 'text-slate-300' : 'text-slate-700'}>Impact</strong> assesses organizational indicators associated with effective programs.
        {' '}
        <strong className={isDark ? 'text-slate-300' : 'text-slate-700'}>Alignment</strong> reflects fit with Muslim donor priorities.
      </p>

      <div className="space-y-5">
        {DIMENSIONS.map((dim) => {
          const details = scoreDetails[dim.key];
          if (!details || !('components' in details)) return null;
          const explanation = dimensionExplanations?.[dim.key];
          return (
            <DimensionSection
              key={dim.key}
              config={dim}
              details={details as ImpactDetails | AlignmentDetails}
              explanation={explanation as string | { explanation: string; improvement?: string; citation_ids: string[] } | undefined}
              citations={citations}
              isSignedIn={isSignedIn}
              isDark={isDark}
            />
          );
        })}
      </div>

      {isSignedIn && hasImprovements && (
        <div className={`mt-4 pt-3 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
          <div className={`text-xs uppercase tracking-widest font-semibold mb-3 flex items-center gap-1.5 ${
            isDark ? 'text-amber-400/80' : 'text-amber-700'
          }`}>
            <TrendingUp className="w-3 h-3" />
            Room to Grow
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {areasForImprovement!.map((area, i) => {
              const isRichFormat = typeof area === 'object';
              const text = isRichFormat ? `${area.area}: ${area.context}` : (area as string);
              return (
                <div key={i} className={`px-3 py-2 rounded-lg flex items-start gap-2 ${
                  isDark ? 'bg-amber-900/15' : 'bg-amber-50'
                }`}>
                  <TrendingUp className={`w-3.5 h-3.5 shrink-0 mt-0.5 ${
                    isDark ? 'text-amber-400' : 'text-amber-600'
                  }`} />
                  <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    {isSignedIn && isRichFormat
                      ? <SourceLinkedText text={text} citations={citations} isDark={isDark} />
                      : stripCitations(text)}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className={`mt-4 pt-3 border-t flex flex-wrap items-center gap-x-6 gap-y-2 text-xs ${
        isDark ? 'border-slate-700 text-slate-400' : 'border-slate-200 text-slate-600'
      }`}>
        <span className="inline-flex items-center gap-2">
          <AlertTriangle className="w-3 h-3" />
          <HarveyBall level={riskSignal.level} tone={riskSignal.tone} isDark={isDark} size="sm" label={riskSignal.label} />
          <span>{riskSignal.label}</span>
          <InfoTip text={GLOSSARY['Organizational Risk']} isDark={isDark} />
        </span>
        {dataConfidence && (
          <span className="inline-flex items-center gap-1.5">
            How Much We Know: <strong className={isDark ? 'text-slate-200' : 'text-slate-700'}>{dataConfidence.badge}</strong>
            <InfoTip text={GLOSSARY['How Much We Know']} isDark={isDark} />
          </span>
        )}
      </div>
    </div>
  );
};

export default ScoreBreakdown;

/**
 * ScoreBreakdown: Unified "Score Analysis" section.
 * Combines score rationale, dimension breakdowns with inline evidence,
 * strengths, and improvement opportunities into one cohesive block.
 */

import React from 'react';
import { CheckCircle2, TrendingUp, AlertTriangle } from 'lucide-react';
import {
  ScoreDetails,
  ConfidenceScores,
  RichCitation,
  ImpactDetails,
  AlignmentDetails,
  ScoreComponentDetail,
} from '../../types';
import { SourceLinkedText } from './SourceLinkedText';
import { stripCitations } from '../utils/scoreUtils';
import { getScoreBarColorClass } from '../utils/scoreConstants';

/** Map pipeline component names to donor-friendly labels */
function formatComponentName(name: string): string {
  const nameMap: Record<string, string> = {
    'Underserved Space': 'Funding Gap Opportunity',
    'Funding Gap': 'Funding Gap',
  };
  return nameMap[name] || name;
}

// ─── Types ───────────────────────────────────────────────────────────────────

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

// ─── Evidence Formatting ─────────────────────────────────────────────────────

/** Convert pipeline shorthand evidence to donor-friendly text */
function formatEvidenceForDonors(evidence: string): string {
  // Theory of change: LEVEL
  const tocMatch = evidence.match(/^Theory of change:\s*(\w+)(?:\s*\(.*\))?$/i);
  if (tocMatch) {
    const level = tocMatch[1].toUpperCase();
    const map: Record<string, string> = {
      STRONG: 'Has a well-articulated path from activities to impact',
      CLEAR: 'Clear connection between activities and intended outcomes',
      DEVELOPING: 'Emerging logic connecting programs to outcomes',
      BASIC: 'Basic framework linking activities to goals',
      ABSENT: 'No documented path from activities to impact',
    };
    return map[level] || evidence;
  }

  // Board governance: LEVEL (N members)
  const boardMatch = evidence.match(/^Board governance:\s*(\w+)\s*\((\d+|unknown)\s*members(?:,\s*(.+))?\)$/i);
  if (boardMatch) {
    const level = boardMatch[1].toUpperCase();
    const members = boardMatch[2];
    const suffix = boardMatch[3] ? ` (${boardMatch[3].trim()})` : '';
    const adjective: Record<string, string> = {
      STRONG: 'Strong', ADEQUATE: 'Adequate', MINIMAL: 'Minimal',
      WEAK: 'Limited', BASELINE: 'Baseline',
    };
    const adj = adjective[level] || level.charAt(0) + level.slice(1).toLowerCase();
    return members === 'unknown'
      ? `${adj} board oversight${suffix}`
      : `${adj} board oversight with ${members} members${suffix}`;
  }

  // Program expense ratio: N%
  const progMatch = evidence.match(/^Program expense ratio:\s*(\d+)%$/i);
  if (progMatch) {
    return `${progMatch[1]}% of spending goes directly to programs`;
  }
  if (/^Program expense ratio:\s*unknown$/i.test(evidence)) {
    return 'Program expense ratio not yet available';
  }

  // Working capital: N months (STATUS)
  const wcMatch = evidence.match(/^Working capital:\s*([\d.]+)\s*months?\s*\((\w+)\)$/i);
  if (wcMatch) {
    const months = wcMatch[1];
    const status = wcMatch[2].toLowerCase();
    return `${months} months of operating reserves (${status})`;
  }
  if (/^Working capital:\s*unknown/i.test(evidence)) {
    return 'Operating reserves data not available';
  }

  // Evidence & outcomes: LEVEL
  const evidenceMatch = evidence.match(/^Evidence & outcomes:\s*(\w+)(?:\s*\(.*\))?$/i);
  if (evidenceMatch) {
    const level = evidenceMatch[1].toUpperCase();
    const map: Record<string, string> = {
      VERIFIED: 'Tracks and verifies program outcomes',
      MEASURED: 'Measures program outcomes systematically',
      TRACKED: 'Tracks basic program outputs',
      UNVERIFIED: 'Outcome tracking not yet verified',
    };
    return map[level] || evidence;
  }

  // Delivery model: TYPE
  const deliveryMatch = evidence.match(/^Delivery model:\s*(.+)$/i);
  if (deliveryMatch) {
    const model = deliveryMatch[1].trim();
    const map: Record<string, string> = {
      'Direct Provision': 'Delivers services directly to beneficiaries',
      'Direct Service': 'Provides direct services to those in need',
      'Capacity Building': 'Builds local capacity for sustained impact',
      'Indirect': 'Works through partner organizations',
      'Systemic Change': 'Pursues systemic change for broad impact',
    };
    return map[model] || `Delivers through ${model.toLowerCase()} model`;
  }

  // Cost per beneficiary: $X/beneficiary (rating for CAUSE)
  const cpbMatch = evidence.match(/^\$([\d,.]+)\/beneficiary\s*\((\w+)\s+for\s+(.+)\)$/i);
  if (cpbMatch) {
    const cost = cpbMatch[1];
    const rating = cpbMatch[2].toLowerCase();
    return `Reaches each beneficiary at $${cost} (${rating})`;
  }

  // Cause area: NAME (X/Y)
  const causeMatch = evidence.match(/^Cause area:\s*(.+)\s*\((\d+)\/(\d+)\)$/i);
  if (causeMatch) {
    const cause = causeMatch[1].trim().replace(/_/g, ' ');
    return `Works in ${cause} — a well-studied cause area (${causeMatch[2]}/${causeMatch[3]} evidence rating)`;
  }

  // Founded YEAR (N years — X/Y)
  const foundedMatch = evidence.match(/^Founded\s+(\d{4})\s*\((\d+)\s*years?\s*—\s*(\d+)\/(\d+)\)$/i);
  if (foundedMatch) {
    return `Established ${foundedMatch[1]} (${foundedMatch[2]} years of track record)`;
  }

  // Revenue: $X (Y/5 funding gap)
  const revMatch = evidence.match(/^Revenue:\s*\$([\d,.]+[KMB]?)\s*\((\d+)\/5\s+funding gap\)$/i);
  if (revMatch) {
    const gapScore = parseInt(revMatch[2]);
    const gapLabel = gapScore >= 4 ? 'high potential for additional donor impact' : 'large organization with established funding';
    return `Annual revenue of $${revMatch[1]} — ${gapLabel}`;
  }
  if (/^Revenue:\s*unknown/i.test(evidence)) {
    return 'Revenue data not yet available';
  }

  // Pass through anything we don't recognize
  return evidence;
}

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Check if a component's evidence indicates data is entirely missing */
const isDataUnavailable = (component: ScoreComponentDetail): boolean =>
  component.scored === 0 && !!component.evidence &&
  /not (yet )?available|unknown|insufficient data/i.test(component.evidence);

/** Status dot: green for full, amber for partial, grey for no data, red for missing */
const StatusDot: React.FC<{ status: ScoreComponentDetail['status']; noData?: boolean }> = ({ status, noData }) => {
  const color = noData ? 'bg-slate-500' :
    status === 'full' ? 'bg-emerald-500' :
    status === 'partial' ? 'bg-amber-500' :
    'bg-rose-400';
  return <span className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${color}`} />;
};

/** Single component row — evidence always visible, no collapsible */
const ComponentRow: React.FC<{
  component: ScoreComponentDetail;
  citations: RichCitation[];
  isSignedIn: boolean;
  isDark: boolean;
}> = ({ component, citations, isSignedIn, isDark }) => {
  const noData = isDataUnavailable(component);

  return (
    <div className={`py-3`}>
      {/* Header: name + score + status + improvement badge */}
      <div className="flex items-center gap-2">
        <StatusDot status={component.status} noData={noData} />
        <span className={`flex-1 text-sm ${noData ? (isDark ? 'text-slate-500' : 'text-slate-400') : (isDark ? 'text-slate-300' : 'text-slate-700')}`}>
          {formatComponentName(component.name)}
        </span>
        {noData ? (
          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
            isDark ? 'bg-slate-700 text-slate-400' : 'bg-slate-100 text-slate-400'
          }`}>
            No Data
          </span>
        ) : (
          <span className={`text-sm font-mono tabular-nums ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            {component.scored}/{component.possible}
          </span>
        )}
        {component.improvement_value > 0 && !noData && (
          <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
            isDark ? 'bg-amber-900/40 text-amber-400' : 'bg-amber-100 text-amber-700'
          }`}>
            +{component.improvement_value}
          </span>
        )}
      </div>

      {/* Evidence — always visible, formatted for donors */}
      {component.evidence && !noData && (
        <p className={`mt-1 ml-4 text-xs leading-relaxed ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
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

      {/* Improvement suggestion — inline */}
      {component.improvement_value > 0 && component.improvement_suggestion && (
        <p className={`mt-1 ml-4 text-xs leading-relaxed ${isDark ? 'text-amber-400/70' : 'text-amber-600'}`}>
          → {component.improvement_suggestion}
        </p>
      )}
    </div>
  );
};

/** Dimension section (Impact or Alignment) — always open */
const DimensionSection: React.FC<{
  config: DimensionConfig;
  details: ImpactDetails | AlignmentDetails;
  explanation?: string | { explanation: string; improvement?: string; citation_ids: string[] };
  citations: RichCitation[];
  isSignedIn: boolean;
  isDark: boolean;
}> = ({ config, details, explanation, citations, isSignedIn, isDark }) => {
  const score = details.score;
  const pct = config.max > 0 ? (score / config.max) * 100 : 0;
  const barColor = getScoreBarColorClass(score, config.max);

  const explanationText = typeof explanation === 'object' ? explanation.explanation : explanation;
  const improvementText = typeof explanation === 'object' ? explanation.improvement : undefined;
  const hasCitations = typeof explanation === 'object';

  return (
    <div className={`rounded-lg pb-1 ${isDark ? 'bg-slate-800/60' : 'bg-slate-50'}`}>
      {/* Dimension header with score bar */}
      <div className="p-4 pb-2">
        <div className="flex items-center justify-between mb-2">
          <span className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
            {config.label}
          </span>
          <span className={`text-sm font-mono font-bold ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>
            {score}/{config.max}
          </span>
        </div>
        <div className={`h-1.5 rounded-full ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}>
          <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Dimension explanation */}
      {explanationText && (
        <div className={`px-4 pb-2`}>
          <p className={`text-sm leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            {isSignedIn && hasCitations ? (
              <SourceLinkedText text={explanationText} citations={citations} isDark={isDark} />
            ) : (
              stripCitations(explanationText || '')
            )}
          </p>
        </div>
      )}

      {/* Component rows */}
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

      {/* Per-dimension improvement path */}
      {improvementText && (
        <div className={`mx-4 mt-2 mb-5 px-3 py-2.5 rounded-lg flex items-start gap-2 ${
          isDark ? 'bg-amber-900/15' : 'bg-amber-50'
        }`}>
          <TrendingUp className={`w-3.5 h-3.5 shrink-0 mt-0.5 ${
            isDark ? 'text-amber-400' : 'text-amber-600'
          }`} />
          <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
            {isSignedIn && hasCitations ? (
              <SourceLinkedText text={improvementText} citations={citations} isDark={isDark} />
            ) : (
              stripCitations(improvementText)
            )}
          </p>
        </div>
      )}
    </div>
  );
};

// ─── Main Component ──────────────────────────────────────────────────────────

export const ScoreBreakdown: React.FC<ScoreBreakdownProps> = ({
  scoreDetails,
  amalScore,
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
  const riskDeduction = scoreDetails.risk_deduction || 0;
  const hasStrengths = strengths && strengths.length > 0;
  const hasImprovements = areasForImprovement && areasForImprovement.length > 0;

  return (
    <div className={`rounded-lg border p-4 md:p-6 mb-6 ${
      isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
    }`}>
      {/* Section header */}
      <div className={`text-xs uppercase tracking-widest font-semibold mb-3 ${
        isDark ? 'text-slate-500' : 'text-slate-400'
      }`}>
        Score Analysis
      </div>

      {/* Score rationale */}
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

      {/* Strengths — compact row above dimensions */}
      {hasStrengths && (
        <div className={`mb-4 grid grid-cols-1 md:grid-cols-2 gap-3`}>
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

      {/* Dimension explainer */}
      <p className={`text-xs leading-relaxed mb-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
        <strong className={isDark ? 'text-slate-400' : 'text-slate-500'}>Impact</strong> measures how effectively they use funds. <strong className={isDark ? 'text-slate-400' : 'text-slate-500'}>Alignment</strong> measures how well they match Muslim donor priorities.
      </p>

      {/* Dimension sections */}
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

      {/* Improvement opportunities — inline below dimensions */}
      {hasImprovements && (
        <div className={`mt-4 pt-3 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
          <div className={`text-xs uppercase tracking-widest font-semibold mb-3 flex items-center gap-1.5 ${
            isDark ? 'text-amber-400/80' : 'text-amber-600'
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

      {/* Footer: Risk deduction + Data Confidence */}
      <div className={`mt-4 pt-3 border-t flex flex-wrap items-center gap-x-6 gap-y-2 text-xs ${
        isDark ? 'border-slate-700 text-slate-500' : 'border-slate-200 text-slate-400'
      }`}>
        {riskDeduction !== 0 && (
          <span className="flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            Risk: {riskDeduction > 0 ? '-' : '+'}{Math.abs(riskDeduction)} pts
          </span>
        )}
        {dataConfidence && (
          <span>
            Data Confidence: {dataConfidence.badge}
          </span>
        )}
      </div>
    </div>
  );
};

export default ScoreBreakdown;

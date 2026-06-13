/**
 * VerdictHero: at-a-glance "verdict" panel that leads the single-scroll CDP.
 *
 * Presentational only. Renders strictly from real data fields on CdpData:
 * recommendation cue + rationale, the GMG score (or assessment label when the
 * org is pre-990 / NEW_ORG), Impact/Alignment/Risk score bars, the four signal
 * pills, and a badge row.
 */

import React from 'react';
import { Shield } from 'lucide-react';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import { RecommendationCue } from '../RecommendationCue';
import { SignalConstellation } from '../SignalConstellation';
import {
  getEvidenceStageClasses,
  getEvidenceStageLabel,
  getScoreColorClass,
  getScoreBarColorClass,
} from '../../utils/scoreConstants';
import type { CdpData } from './useCdpData';

interface ScoreBarProps {
  label: string;
  value: number;
  max: number;
  /** Render as a penalty (negative) bar rather than a positive achievement. */
  penalty?: boolean;
  isDark: boolean;
}

const ScoreBar: React.FC<ScoreBarProps> = ({ label, value, max, penalty = false, isDark }) => {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  const barColor = penalty ? 'bg-rose-500' : getScoreBarColorClass(value, max);
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          {label}
        </span>
        <span className={`text-xs font-semibold tabular-nums ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
          {penalty ? `−${value}` : value}
          <span className={isDark ? 'text-slate-600' : 'text-slate-400'}>/{max}</span>
        </span>
      </div>
      <div className={`h-1.5 rounded-full overflow-hidden ${isDark ? 'bg-slate-800' : 'bg-slate-100'}`}>
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
};

interface VerdictHeroProps {
  data: CdpData;
}

export const VerdictHero: React.FC<VerdictHeroProps> = ({ data }) => {
  const { isDark } = useLandingTheme();
  const { signals, amalScore, impact, alignment, riskDeduction } = data;

  const hasScore = amalScore != null;
  const isZakatEligible = data.charity.amalEvaluation?.wallet_tag === 'ZAKAT-ELIGIBLE';

  // Risk is stored as a positive penalty magnitude; cap the bar at a sane max.
  const riskValue = Math.abs(riskDeduction ?? 0);
  const RISK_MAX = 10;

  return (
    <div className={`rounded-xl border p-5 md:p-6 ${
      isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'
    }`}>
      {/* Recommendation cue + rationale */}
      <RecommendationCue
        cue={signals.recommendation_cue}
        rationale={signals.recommendation_rationale}
        isDark={isDark}
      />

      {/* Score block */}
      <div className="mt-4 flex items-end gap-3">
        {hasScore ? (
          <>
            <div className="flex items-baseline gap-1">
              <span className={`text-5xl font-bold leading-none tabular-nums ${getScoreColorClass(amalScore!, isDark)}`}>
                {amalScore}
              </span>
              <span className={`text-xl font-semibold ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
                /100
              </span>
            </div>
            <span className={`text-xs font-medium uppercase tracking-wide pb-1 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
              GMG score
            </span>
          </>
        ) : (
          <div className="flex flex-col gap-1">
            <span className={`text-2xl font-bold leading-tight ${isDark ? 'text-white' : 'text-slate-900'}`}>
              {signals.assessment_label}
            </span>
            <span className={`inline-flex items-center self-start px-2 py-0.5 rounded text-[11px] font-semibold border ${getEvidenceStageClasses(signals.evidence_stage, isDark)}`}>
              {getEvidenceStageLabel(signals.evidence_stage)}
            </span>
          </div>
        )}
      </div>

      {/* Dimension bars (only when a numeric score exists) */}
      {hasScore && (
        <div className="mt-4 space-y-2.5">
          {impact != null && <ScoreBar label="Impact" value={impact} max={50} isDark={isDark} />}
          {alignment != null && <ScoreBar label="Alignment" value={alignment} max={50} isDark={isDark} />}
          <ScoreBar label="Risk deduction" value={riskValue} max={RISK_MAX} penalty isDark={isDark} />
        </div>
      )}

      {/* Signal pills */}
      <div className="mt-5">
        <SignalConstellation signals={signals.signal_states} isDark={isDark} />
      </div>

      {/* Badge row. The evidence stage already leads the score block in the
          no-score case, so only repeat it here when a numeric score is shown. */}
      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        {hasScore && (
          <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${getEvidenceStageClasses(signals.evidence_stage, isDark)}`}>
            {getEvidenceStageLabel(signals.evidence_stage)}
          </span>
        )}
        <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${isDark ? 'bg-slate-800 text-slate-400' : 'bg-slate-100 text-slate-500'}`}>
          {signals.archetype_label}
        </span>
        {isZakatEligible && (
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold ${
            isDark ? 'bg-emerald-900/40 text-emerald-400' : 'bg-emerald-100 text-emerald-700'
          }`}>
            <Shield className="w-3 h-3" />
            Accepts Zakat
          </span>
        )}
      </div>
    </div>
  );
};

export default VerdictHero;

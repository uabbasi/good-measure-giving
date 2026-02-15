import React from 'react';
import { getRecommendationCueClasses } from '../utils/scoreConstants';
import type { UISignalsV1 } from '../../types';

interface RecommendationCueProps {
  cue: UISignalsV1['recommendation_cue'];
  rationale?: string | null;
  isDark: boolean;
  compact?: boolean;
}

const DISPLAY_LABELS: Record<UISignalsV1['recommendation_cue'], string> = {
  'Strong Match': 'High Confidence',
  'Good Match': 'Good Signals',
  'Mixed Signals': 'Mixed Signals',
  'Limited Match': 'Limited Signals',
};

export const RecommendationCue: React.FC<RecommendationCueProps> = ({
  cue,
  rationale,
  isDark,
  compact = false,
}) => {
  return (
    <div className="space-y-1">
      <span className={`inline-flex items-center border rounded font-semibold ${compact ? 'text-[11px] px-2 py-0.5' : 'text-xs px-2.5 py-1'} ${getRecommendationCueClasses(cue, isDark)}`}>
        {DISPLAY_LABELS[cue]}
      </span>
      {!compact && rationale && (
        <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          {rationale}
        </p>
      )}
    </div>
  );
};

export default RecommendationCue;

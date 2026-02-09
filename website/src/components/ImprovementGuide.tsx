/**
 * ImprovementGuide: "What This Charity Can Do to Improve"
 * Aggregates improvement suggestions from score components, grouped by dimension,
 * sorted by point value. Constructive, charity-directed tone.
 */

import React from 'react';
import { TrendingUp } from 'lucide-react';
import { ScoreDetails, ScoreComponentDetail } from '../../types';
import { mapImprovementToDimension } from '../utils/scoreUtils';

interface ImprovementGuideProps {
  scoreDetails: ScoreDetails;
  areasForImprovement?: Array<string | { area: string; context: string }>;
  isDark: boolean;
}

interface GroupedImprovement {
  name: string;
  suggestion: string;
  value: number;
}

const DIMENSION_LABELS: Record<string, string> = {
  impact: 'Impact',
  alignment: 'Alignment',
};

export const ImprovementGuide: React.FC<ImprovementGuideProps> = ({
  scoreDetails,
  areasForImprovement,
  isDark,
}) => {
  // Collect improvements from score components
  const grouped: Record<string, GroupedImprovement[]> = {};
  let totalRecoverable = 0;

  const addToGroup = (dimension: string, item: GroupedImprovement) => {
    if (!grouped[dimension]) grouped[dimension] = [];
    grouped[dimension].push(item);
    totalRecoverable += item.value;
  };

  // Primary source: score_details components with improvement_value > 0
  for (const dimKey of ['impact', 'alignment'] as const) {
    const details = scoreDetails[dimKey];
    if (!details || !('components' in details)) continue;

    for (const comp of (details as { components: ScoreComponentDetail[] }).components) {
      if (comp.improvement_value > 0 && comp.improvement_suggestion) {
        addToGroup(dimKey, {
          name: comp.name,
          suggestion: comp.improvement_suggestion,
          value: comp.improvement_value,
        });
      }
    }
  }

  // Merge narrative areas_for_improvement that aren't already covered
  if (areasForImprovement) {
    const coveredNames = new Set(
      Object.values(grouped).flatMap(arr => arr.map(g => g.name.toLowerCase()))
    );

    for (const imp of areasForImprovement) {
      const text = typeof imp === 'string' ? imp : `${imp.area}: ${imp.context}`;
      const dimension = mapImprovementToDimension(imp) || 'impact';

      // Skip if already covered by a score component
      const lowerText = text.toLowerCase();
      const alreadyCovered = Array.from(coveredNames).some(
        name => lowerText.includes(name) || name.includes(lowerText.slice(0, 20))
      );
      if (alreadyCovered) continue;

      addToGroup(dimension, {
        name: typeof imp === 'string' ? 'General' : imp.area,
        suggestion: text,
        value: 0, // narrative-only, no point value
      });
    }
  }

  // Nothing to show
  if (totalRecoverable === 0 && Object.keys(grouped).length === 0) return null;

  // Sort each group by improvement_value descending
  for (const key of Object.keys(grouped)) {
    grouped[key].sort((a, b) => b.value - a.value);
  }

  // Sort dimensions by total recoverable descending
  const dimensionOrder = Object.keys(grouped).sort((a, b) => {
    const sumA = grouped[a].reduce((s, g) => s + g.value, 0);
    const sumB = grouped[b].reduce((s, g) => s + g.value, 0);
    return sumB - sumA;
  });

  return (
    <div className={`rounded-lg border p-5 mb-6 ${
      isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
    }`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className={`text-xs uppercase tracking-widest font-semibold ${
          isDark ? 'text-slate-500' : 'text-slate-400'
        }`}>
          Paths to Improvement
        </div>
        {totalRecoverable > 0 && (
          <span className={`text-xs font-medium px-2 py-1 rounded ${
            isDark ? 'bg-amber-900/30 text-amber-400' : 'bg-amber-50 text-amber-700'
          }`}>
            {totalRecoverable} pts recoverable
          </span>
        )}
      </div>

      {/* Grouped improvements */}
      <div className="space-y-4">
        {dimensionOrder.map((dimKey) => {
          const items = grouped[dimKey];
          const dimTotal = items.reduce((s, g) => s + g.value, 0);

          return (
            <div key={dimKey}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`text-sm font-semibold ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>
                  {DIMENSION_LABELS[dimKey] || dimKey}
                </span>
                {dimTotal > 0 && (
                  <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    (+{dimTotal} possible)
                  </span>
                )}
              </div>
              <div className="space-y-2">
                {items.map((item, i) => (
                  <div key={`${dimKey}-${i}`} className="flex items-start gap-2">
                    <TrendingUp className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${
                      isDark ? 'text-amber-400' : 'text-amber-500'
                    }`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                          {item.name}
                        </span>
                        {item.value > 0 && (
                          <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                            isDark ? 'bg-amber-900/40 text-amber-400' : 'bg-amber-100 text-amber-700'
                          }`}>
                            +{item.value}
                          </span>
                        )}
                      </div>
                      <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                        {item.suggestion}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ImprovementGuide;

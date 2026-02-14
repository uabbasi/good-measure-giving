/**
 * CompareBar - Sticky bottom bar showing selected charities for comparison
 * Shows up to 3 charities, with ability to remove and navigate to compare page
 */

import React from 'react';
import { Link } from 'react-router-dom';
import { X, ArrowRight } from 'lucide-react';
import { useLandingTheme } from '../../contexts/LandingThemeContext';
import { useCompareState } from '../contexts/UserFeaturesContext';
import { useCharities } from '../hooks/useCharities';

export function CompareBar() {
  const { isDark } = useLandingTheme();
  const { compareList, removeFromCompare, clearCompare, compareCount } = useCompareState();
  const { summaries } = useCharities();

  // Don't render if no charities selected
  if (compareCount === 0) return null;

  // Get charity details for selected EINs
  const selectedCharities = compareList
    .map(ein => summaries?.find(c => c.ein === ein))
    .filter(Boolean);

  return (
    <div
      className={`
        fixed bottom-0 left-0 right-0 z-40
        border-t shadow-lg
        pb-[env(safe-area-inset-bottom)]
        ${isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}
      `}
    >
      <div className="max-w-5xl mx-auto px-4 py-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          {/* Selected charities */}
          <div className="flex-1 flex items-center gap-2 overflow-x-auto pb-1 sm:gap-3 sm:pb-0">
            <span className={`text-sm font-medium whitespace-nowrap ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              Compare ({compareCount}/3):
            </span>

            {selectedCharities.map(charity => (
              <div
                key={charity!.ein}
                className={`
                  flex items-center gap-2 px-3 py-1.5 rounded-lg
                  ${isDark ? 'bg-slate-800' : 'bg-slate-100'}
                `}
              >
                <span className={`text-sm font-medium truncate max-w-[150px] ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {charity!.name}
                </span>
                <button
                  onClick={() => removeFromCompare(charity!.ein)}
                  className={`
                    p-1 rounded transition-colors
                    ${isDark
                      ? 'hover:bg-slate-700 text-slate-400 hover:text-slate-200'
                      : 'hover:bg-slate-200 text-slate-500 hover:text-slate-700'
                    }
                  `}
                  aria-label={`Remove ${charity!.name} from comparison`}
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}

            {/* Empty slots */}
            {Array.from({ length: 3 - compareCount }).map((_, i) => (
              <div
                key={`empty-${i}`}
                className={`
                  px-3 py-1.5 rounded-lg border-2 border-dashed
                  ${isDark ? 'border-slate-700' : 'border-slate-200'}
                `}
              >
                <span className={`text-sm ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
                  + Add charity
                </span>
              </div>
            ))}
          </div>

          {/* Actions */}
          <div className="flex w-full items-center gap-2 sm:w-auto sm:flex-shrink-0">
            <button
              onClick={clearCompare}
              className={`
                flex-1 px-3 py-2 text-sm font-medium rounded-lg transition-colors sm:flex-none
                ${isDark
                  ? 'text-slate-400 hover:text-white hover:bg-slate-800'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }
              `}
            >
              Clear
            </button>
            <Link
              to="/compare"
              className={`
                inline-flex flex-1 items-center justify-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-colors sm:flex-none
                ${compareCount >= 2
                  ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                  : `cursor-not-allowed ${isDark ? 'bg-slate-700 text-slate-500' : 'bg-slate-200 text-slate-400'}`
                }
              `}
              onClick={(e) => compareCount < 2 && e.preventDefault()}
              aria-disabled={compareCount < 2}
            >
              Compare
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

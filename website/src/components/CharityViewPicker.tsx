/**
 * CharityViewPicker: Inline view toggle for charity detail pages.
 * Allows switching between Terminal and Grades views.
 * Terminal is the default view.
 */

import React from 'react';
import { useLandingTheme } from '../../contexts/LandingThemeContext';

export type ViewType = 'terminal' | 'niche' | 'compare';

interface InlineViewToggleProps {
  currentView: ViewType;
  onViewChange: (view: ViewType) => void;
}

/**
 * Inline view toggle rendered inside the bottom metadata bar of each view.
 * Replaces the old floating pill picker.
 */
export const InlineViewToggle: React.FC<InlineViewToggleProps> = ({
  currentView,
  onViewChange,
}) => {
  const { isDark } = useLandingTheme();

  const views: { key: 'terminal' | 'niche'; label: string }[] = [
    { key: 'terminal', label: 'Terminal' },
    { key: 'niche', label: 'Grades' },
  ];

  return (
    <span className="inline-flex items-center gap-1" role="tablist" aria-label="View selection">
      {views.map((view, i) => {
        const isActive = currentView === view.key;
        return (
          <React.Fragment key={view.key}>
            {i > 0 && <span className={isDark ? 'text-slate-600' : 'text-slate-300'}>|</span>}
            <button
              onClick={() => onViewChange(view.key)}
              role="tab"
              aria-selected={isActive}
              className={`text-xs transition-colors ${
                isActive
                  ? isDark ? 'text-white font-medium' : 'text-slate-900 font-medium'
                  : isDark ? 'text-slate-500 hover:text-slate-300' : 'text-slate-400 hover:text-slate-600'
              }`}
            >
              {view.label}
            </button>
          </React.Fragment>
        );
      })}
    </span>
  );
};

export default InlineViewToggle;

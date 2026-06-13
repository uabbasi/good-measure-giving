/**
 * MobileScoreBar: mobile-only sticky bar for the single-scroll CDP.
 *
 * Shows a compact GMG score (or the recommendation cue when the score is null)
 * plus the recommendation cue text, and a chevron button that toggles a
 * jump-to-section dropdown. Selecting a section closes the panel and
 * smooth-scrolls to it.
 */

import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import type { CdpData } from './useCdpData';
import type { SectionDef } from './sections.config';
import { scrollToSection } from './scrollToSection';
import { DISPLAY_LABELS } from '../RecommendationCue';

interface MobileScoreBarProps {
  data: CdpData;
  sections: SectionDef[];
}

export const MobileScoreBar: React.FC<MobileScoreBarProps> = ({ data, sections }) => {
  const { isDark } = useLandingTheme();
  const [open, setOpen] = useState(false);

  const cue = DISPLAY_LABELS[data.signals.recommendation_cue];
  const hasScore = data.amalScore != null;

  const handleSelect = (id: string) => {
    setOpen(false);
    scrollToSection(id);
  };

  return (
    <div
      className={`md:hidden sticky top-0 z-30 border-b ${
        isDark ? 'bg-slate-900/95 border-slate-700' : 'bg-white/95 border-slate-200'
      } backdrop-blur`}
    >
      <div className="flex items-center justify-between gap-2 px-4 py-2">
        <div className="flex items-baseline gap-2 min-w-0">
          {hasScore && (
            <span className={`text-base font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
              {data.amalScore}
              <span className={`text-xs font-normal ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                /100
              </span>
            </span>
          )}
          <span className={`text-xs font-medium truncate ${isDark ? 'text-emerald-400' : 'text-emerald-700'}`}>
            {cue}
          </span>
        </div>

        <button
          type="button"
          aria-label="Jump to section"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors cursor-pointer ${
            isDark
              ? 'text-slate-300 hover:bg-slate-800'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          Sections
          <ChevronDown className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {open && (
        <ul
          className={`border-t ${
            isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
          }`}
        >
          {sections.map((section) => (
            <li key={section.id}>
              <button
                type="button"
                onClick={() => handleSelect(section.id)}
                className={`block w-full text-left text-sm px-4 py-2 transition-colors cursor-pointer ${
                  isDark
                    ? 'text-slate-300 hover:bg-slate-800'
                    : 'text-slate-700 hover:bg-slate-100'
                }`}
              >
                {section.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

/**
 * SectionRail: desktop-only sticky navigation for the single-scroll CDP.
 *
 * Renders one clickable item per visible section. The item matching `activeId`
 * is highlighted (emerald left border + emerald text) and carries
 * aria-current="true"; clicking any item smooth-scrolls to that section.
 */

import React from 'react';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import type { SectionDef } from './sections.config';
import { scrollToSection } from './scrollToSection';

interface SectionRailProps {
  sections: SectionDef[];
  activeId: string;
}

export const SectionRail: React.FC<SectionRailProps> = ({ sections, activeId }) => {
  const { isDark } = useLandingTheme();

  return (
    <nav
      aria-label="Section navigation"
      className="hidden md:block sticky top-24 self-start"
    >
      <ul className="space-y-0.5 border-l border-transparent">
        {sections.map((section) => {
          const isActive = section.id === activeId;
          return (
            <li key={section.id}>
              <button
                type="button"
                aria-current={isActive ? 'true' : undefined}
                onClick={() => scrollToSection(section.id)}
                className={`block w-full text-left text-sm px-3 py-1.5 -ml-px border-l-2 transition-colors cursor-pointer ${
                  isActive
                    ? isDark
                      ? 'border-emerald-400 text-emerald-400 font-medium'
                      : 'border-emerald-600 text-emerald-700 font-medium'
                    : isDark
                      ? 'border-transparent text-slate-400 hover:text-slate-200'
                      : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                {section.label}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
};

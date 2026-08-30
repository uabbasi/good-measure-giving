// Scroll-spy rail on desktop, sticky jump menu on mobile. The page runs to
// ~14 sections after phase 2B and needs a way to reach one directly.
//
// IntersectionObserver is absent during SSR and not guaranteed in jsdom, so its
// construction is guarded — an exception here would be swallowed by
// prerender.ts's per-route try/catch and silently blank all 166 charity pages.

import React, { useEffect, useState } from 'react';
import { GmgPalette, FONT_MONO } from './tokens';

export interface RailSection {
  id: string;
  label: string;
}

// The mobile bar renders 40px tall; 8px more keeps the section heading clear
// of it rather than flush against it after a jump.
export const MOBILE_RAIL_OFFSET = 48;

export const SectionRail: React.FC<{
  sections: RailSection[];
  p: GmgPalette;
  isMobile: boolean;
}> = ({ sections, p, isMobile }) => {
  const [active, setActive] = useState<string | null>(null);
  const sectionIds = sections.map((s) => s.id).join('|');

  useEffect(() => {
    if (sections.length === 0) return;
    if (typeof IntersectionObserver === 'undefined') return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (visible) setActive((visible.target as HTMLElement).dataset.section ?? null);
      },
      { rootMargin: '-20% 0px -70% 0px' },
    );

    const els = sections
      .map((s) => document.querySelector<HTMLElement>(`[data-section="${s.id}"]`))
      .filter((el): el is HTMLElement => el !== null);
    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [sectionIds]);

  if (sections.length === 0) return null;

  const link = (s: RailSection): React.CSSProperties => ({
    display: 'block',
    fontFamily: FONT_MONO,
    fontSize: 10,
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    color: active === s.id ? p.fg : p.sub2,
    textDecoration: 'none',
    padding: isMobile ? '6px 10px' : '5px 0',
    borderLeft: isMobile ? 'none' : `2px solid ${active === s.id ? p.accent : 'transparent'}`,
    paddingLeft: 10,
    whiteSpace: 'nowrap',
  });

  if (isMobile) {
    return (
      <>
        {/* This bar is sticky at top:0, so a jump from it lands the target
            section underneath the bar itself — you arrive inside a section
            with its heading hidden, which reads as "the link went nowhere".
            scroll-margin-top pushes the landing down past the bar. It is
            declared here rather than on Section because the overlap only
            exists while this bar does: on desktop the rail sits in its own
            column and an offset would just leave dead headroom. */}
        <style>{`[data-section]{scroll-margin-top:${MOBILE_RAIL_OFFSET}px}`}</style>
        <nav
          aria-label="Page sections"
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 20,
            display: 'flex',
            gap: 4,
            overflowX: 'auto',
            background: p.bg2,
            borderBottom: `1px solid ${p.rule}`,
            padding: '6px 8px',
          }}
        >
          {sections.map((s) => (
            <a key={s.id} href={`#${s.id}`} style={link(s)}>
              {s.label}
            </a>
          ))}
        </nav>
      </>
    );
  }

  return (
    <nav
      aria-label="Page sections"
      style={{ position: 'sticky', top: 24, alignSelf: 'start', display: 'grid', gap: 2 }}
    >
      {sections.map((s) => (
        <a key={s.id} href={`#${s.id}`} style={link(s)}>
          {s.label}
        </a>
      ))}
    </nav>
  );
};

export default SectionRail;

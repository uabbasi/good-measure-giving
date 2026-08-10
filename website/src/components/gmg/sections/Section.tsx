// Shared shell for every donor-question section on the charity detail page.
// The `data-section` wrapper is ALWAYS mounted (never put behind a gate) —
// SectionRail queries `[data-section]` to drive the scroll-spy rail, and
// gated content mounts only after auth resolves post-hydration, so a wrapper
// nested inside a gate would silently never be observed.

import React from 'react';
import { GmgPalette } from '../tokens';
import { Kicker } from '../primitives';

export const Section: React.FC<{
  id: string;
  title: string;
  p: GmgPalette;
  padX: number;
  children: React.ReactNode;
}> = ({ id, title, p, padX, children }) => (
  <section data-section={id} id={id} style={{ padding: `20px ${padX}px`, borderBottom: `1px solid ${p.rule}` }}>
    <Kicker p={p}>{title}</Kicker>
    <div style={{ marginTop: 10 }}>{children}</div>
  </section>
);

export default Section;

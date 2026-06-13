import { describe, it, expect } from 'vitest';
import { SECTIONS, visibleSections } from './sections.config';
import type { CdpData } from './useCdpData';

const d = (over: Partial<CdpData>) => ({ canViewRich: true, rich: {}, charity: {}, ...over }) as unknown as CdpData;

describe('SECTIONS', () => {
  it('is ordered verdict-first reasoning order', () => {
    expect(SECTIONS.map(s => s.id).slice(0, 4))
      .toEqual(['about', 'why-this-score', 'strengths-concerns', 'evidence']);
  });

  it('every section has an applies predicate', () => {
    expect(SECTIONS.every(s => typeof s.applies === 'function')).toBe(true);
  });

  it('hides why-this-score when amalScore is null', () => {
    const ids = visibleSections(d({ amalScore: null })).map(s => s.id);
    expect(ids).not.toContain('why-this-score');
  });

  it('keeps why-this-score when amalScore is present', () => {
    const ids = visibleSections(d({ amalScore: 82 })).map(s => s.id);
    expect(ids).toContain('why-this-score');
  });
});

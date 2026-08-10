import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { CitedText, SourceList, collectCitations } from './CitedText';
import { gmgPalette } from './tokens';
import type { Citation, CitedSegment } from './adapters/citations';

const p = gmgPalette(false);
const cite = (n: number, name: string, url: string | null): Citation => ({
  n, id: String(n), sourceName: name, sourceUrl: url, sourceType: 'form990',
  claim: '', quote: '', accessDate: '2026-01-09', confidence: 0.9,
});
const c1 = cite(1, 'IRS Form 990', 'https://example.org/990');
const c2 = cite(2, 'Charity Navigator', null);

const segs: CitedSegment[] = [
  { kind: 'text', text: 'Managed ' },
  { kind: 'cited', text: '$1.5B in revenue', citation: c1 },
  { kind: 'text', text: ' across 40 countries.' },
];

describe('CitedText', () => {
  it('renders the prose with a superscript marker on the cited span', () => {
    const { container } = render(<CitedText segments={segs} p={p} />);
    expect(container.textContent).toContain('Managed $1.5B in revenue');
    expect(container.textContent).toContain('across 40 countries.');
    const sup = container.querySelector('sup');
    expect(sup?.textContent).toBe('1');
  });

  it('renders nothing at all for an empty segment list', () => {
    const { container } = render(<CitedText segments={[]} p={p} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders a marker for a cited segment whose span is empty', () => {
    // The pipeline emits a few <cite> tags with no enclosed text; the citation
    // still resolved, so the marker must survive even though the text is ''.
    const { container } = render(
      <CitedText segments={[{ kind: 'cited', text: '', citation: c1 }]} p={p} />,
    );
    expect(container.querySelector('sup')?.textContent).toBe('1');
  });

  it('gives each marker an accessible reference to its source', () => {
    const { container } = render(<CitedText segments={segs} p={p} />);
    const sup = container.querySelector('sup');
    expect(sup?.getAttribute('aria-label')).toContain('IRS Form 990');
  });

  it('separates the marker from the text it follows, so a digit before it does not read as an exponent', () => {
    // e.g. "Founded in 1933<sup>6</sup>" must not visually merge into "19336".
    const digitAdjacent: CitedSegment[] = [{ kind: 'cited', text: 'Founded in 1933', citation: c1 }];
    const { container } = render(<CitedText segments={digitAdjacent} p={p} />);
    const sup = container.querySelector('sup') as HTMLElement | null;
    expect(sup?.style.marginLeft).not.toBe('');
    expect(sup?.style.marginLeft).not.toBe('0px');
    expect(sup?.style.marginLeft).not.toBe('1px');
  });
});

describe('collectCitations', () => {
  it('dedupes across segment arrays and orders by citation number', () => {
    const a: CitedSegment[] = [{ kind: 'cited', text: 'x', citation: c2 }];
    const b: CitedSegment[] = [
      { kind: 'cited', text: 'y', citation: c1 },
      { kind: 'cited', text: 'z', citation: c2 },
    ];
    expect(collectCitations(a, b).map((c) => c.n)).toEqual([1, 2]);
  });

  it('returns nothing when no segment is cited', () => {
    expect(collectCitations([{ kind: 'text', text: 'plain' }])).toEqual([]);
  });
});

describe('SourceList', () => {
  it('links a source that has a URL and plain-texts one that does not', () => {
    const { container, getByText } = render(<SourceList citations={[c1, c2]} p={p} />);
    const link = container.querySelector('a');
    expect(link?.getAttribute('href')).toBe('https://example.org/990');
    expect(link?.getAttribute('rel')).toBe('noopener noreferrer');
    expect(getByText(/Charity Navigator/)).toBeInTheDocument();
    expect(container.querySelectorAll('a').length).toBe(1);
  });

  it('renders nothing for an empty list, so a section shows no empty Sources block', () => {
    const { container } = render(<SourceList citations={[]} p={p} />);
    expect(container.firstChild).toBeNull();
  });

  it('numbers each entry to match its marker', () => {
    const { container } = render(<SourceList citations={[c1, c2]} p={p} />);
    expect(container.textContent).toMatch(/1\.\s*IRS Form 990/);
    expect(container.textContent).toMatch(/2\.\s*Charity Navigator/);
  });
});

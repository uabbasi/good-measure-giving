import { describe, it, expect } from 'vitest';
import { parseText, buildCitationMap, Citation } from './SourceLinkedText';

describe('parseText', () => {
  it('parses bare digit cite tags: <cite id="1">', () => {
    const segments = parseText('Hello <cite id="1">world</cite> end');
    expect(segments).toEqual([
      { type: 'text', content: 'Hello ' },
      { type: 'cite', content: 'world', id: '1' },
      { type: 'text', content: ' end' },
    ]);
  });

  it('parses bracket cite tags: <cite id="[1]">', () => {
    const segments = parseText('Hello <cite id="[1]">world</cite> end');
    expect(segments).toEqual([
      { type: 'text', content: 'Hello ' },
      { type: 'cite', content: 'world', id: '1' },
      { type: 'text', content: ' end' },
    ]);
  });

  it('parses single-quoted bracket cite tags', () => {
    const segments = parseText("Hello <cite id='[2]'>text</cite> end");
    expect(segments).toEqual([
      { type: 'text', content: 'Hello ' },
      { type: 'cite', content: 'text', id: '2' },
      { type: 'text', content: ' end' },
    ]);
  });

  it('parses multiple bracket cite tags', () => {
    const segments = parseText(
      '<cite id="[1]">first</cite> middle <cite id="[4]">fourth</cite>'
    );
    expect(segments).toEqual([
      { type: 'cite', content: 'first', id: '1' },
      { type: 'text', content: ' middle ' },
      { type: 'cite', content: 'fourth', id: '4' },
    ]);
  });

  it('parses legacy [N] markers', () => {
    const segments = parseText('Some text [3] more');
    expect(segments).toEqual([
      { type: 'text', content: 'Some text ' },
      { type: 'legacy', content: '[3]', id: '3' },
      { type: 'text', content: ' more' },
    ]);
  });

  it('handles mixed cite and legacy formats', () => {
    const segments = parseText('<cite id="[1]">linked</cite> and [2] legacy');
    expect(segments).toEqual([
      { type: 'cite', content: 'linked', id: '1' },
      { type: 'text', content: ' and ' },
      { type: 'legacy', content: '[2]', id: '2' },
      { type: 'text', content: ' legacy' },
    ]);
  });

  it('returns plain text when no citations present', () => {
    const segments = parseText('Just plain text');
    expect(segments).toEqual([{ type: 'text', content: 'Just plain text' }]);
  });

  it('handles empty string', () => {
    expect(parseText('')).toEqual([]);
  });
});

describe('buildCitationMap', () => {
  const citations: Citation[] = [
    { id: '[1]', source_url: 'https://example.com/1', source_name: 'Source 1' },
    { id: '[2]', source_url: 'https://example.com/2', source_name: 'Source 2' },
    { id: '[3]', source_url: null, source_name: 'No URL' },
  ];

  it('maps numeric IDs from bracket-format citation IDs', () => {
    const map = buildCitationMap(citations);
    expect(map.get('1')).toEqual({ url: 'https://example.com/1', name: 'Source 1' });
    expect(map.get('2')).toEqual({ url: 'https://example.com/2', name: 'Source 2' });
  });

  it('also maps bracket-format IDs for legacy lookup', () => {
    const map = buildCitationMap(citations);
    expect(map.get('[1]')).toEqual({ url: 'https://example.com/1', name: 'Source 1' });
  });

  it('skips citations without URLs', () => {
    const map = buildCitationMap(citations);
    expect(map.has('3')).toBe(false);
    expect(map.has('[3]')).toBe(false);
  });

  it('blocks guidestar.org URLs', () => {
    const blocked: Citation[] = [
      { id: '[1]', source_url: 'https://www.guidestar.org/profile/123', source_name: 'GuideStar' },
    ];
    const map = buildCitationMap(blocked);
    expect(map.has('1')).toBe(false);
  });

  it('blocks ngo-monitor.org URLs', () => {
    const blocked: Citation[] = [
      { id: '[1]', source_url: 'https://ngo-monitor.org/something', source_name: 'NGO Monitor' },
    ];
    const map = buildCitationMap(blocked);
    expect(map.has('1')).toBe(false);
  });
});

describe('parseText + buildCitationMap integration', () => {
  it('bracket cite IDs in text match bracket citation IDs in data', () => {
    // This is the real-world scenario: data has id="[4]" in text and "[4]" in citations
    const text = '<cite id="[4]">Feeding, Water, Health</cite> are core sectors';
    const citations: Citation[] = [
      { id: '[4]', source_url: 'https://sadagaat-usa.org', source_name: 'SADAGAAT' },
    ];

    const segments = parseText(text);
    const map = buildCitationMap(citations);

    // parseText should extract id "4" (stripped brackets)
    expect(segments[0]).toEqual({ type: 'cite', content: 'Feeding, Water, Health', id: '4' });

    // buildCitationMap should have entry for "4"
    expect(map.get('4')).toEqual({ url: 'https://sadagaat-usa.org', name: 'SADAGAAT' });
  });
});

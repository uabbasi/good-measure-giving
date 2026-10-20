// JSON-LD page URLs must carry the trailing slash: Google crawls them, and each
// no-slash one 308-redirects into Search Console's "Page with redirect" report.

import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { buildCharityMeta, serializeJsonLd } from './prerender';

const detail = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../data/charities/charity-13-5660870.json'), 'utf8'));

describe('serializeJsonLd', () => {
  it('emits only trailing-slash page URLs for a real charity page', () => {
    const blocks = buildCharityMeta(detail).jsonLd as unknown[];
    const urls = blocks.flatMap((b) => serializeJsonLd(b).match(/https:\/\/goodmeasuregiving\.org\/[^"]*/g) ?? []);
    expect(urls).toContain('https://goodmeasuregiving.org/browse/');
    expect(urls.filter((u) => !u.endsWith('/') && !/\.\w+$/.test(u))).toEqual([]);
  });

  it('leaves file URLs, the bare origin, and external URLs alone', () => {
    const out = serializeJsonLd({ a: 'https://goodmeasuregiving.org/og-share.jpg', b: 'https://goodmeasuregiving.org', c: 'https://example.org/x' });
    expect(JSON.parse(out)).toEqual({ a: 'https://goodmeasuregiving.org/og-share.jpg', b: 'https://goodmeasuregiving.org', c: 'https://example.org/x' });
  });
});

// buildCharityMeta: the GMG numeric score is member-only site-wide (see
// charityAdapter's showScore/showScores and the peer-score fix in 64047f1),
// so nothing this function emits for anonymous crawlers — <title>, meta
// description, or JSON-LD — may carry the number. Real fixture data, not a
// hand-built object, so a future field rename can't silently stop exercising
// the actual shape charity-<ein>.json files carry.

import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { buildCharityMeta } from './prerender';

const dir = path.resolve(__dirname, '../data/charities');
const load = (ein: string) => JSON.parse(fs.readFileSync(path.join(dir, `charity-${ein}.json`), 'utf8'));

describe('buildCharityMeta — no numeric score reaches a public surface', () => {
  it('carries no ratingValue/Review block in JSON-LD, and no digit-score in title or description', () => {
    const detail = load('13-5660870'); // International Rescue Committee, amal_score 78
    const meta = buildCharityMeta(detail);

    const blocks = meta.jsonLd as Record<string, unknown>[];
    for (const block of blocks) {
      expect(block['@type']).not.toBe('Review');
      expect(JSON.stringify(block)).not.toContain('ratingValue');
      expect(JSON.stringify(block)).not.toContain('reviewRating');
    }

    // The title/description carry a qualitative band instead — proves this
    // isn't just an absent field but real replacement copy.
    expect(meta.title).toMatch(/Strong|Good|Moderate|Fair|Weak|Evaluated|Early-Stage/);
    expect(meta.title).not.toMatch(/\d+\/100/);
    expect(meta.description).not.toMatch(/\d+\/100/);
  });

  it('holds across the whole corpus, not just the one fixture', () => {
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
    expect(files.length).toBeGreaterThan(100);

    const leaks: string[] = [];
    for (const file of files) {
      const meta = buildCharityMeta(load(file.replace(/^charity-/, '').replace(/\.json$/, '')));
      const blocksText = JSON.stringify(meta.jsonLd);
      if (/ratingValue|reviewRating|"@type":"Review"/.test(blocksText)) leaks.push(`${file} :: jsonLd`);
      if (/\d+\/100/.test(meta.title)) leaks.push(`${file} :: title "${meta.title}"`);
      if (/\d+\/100/.test(meta.description)) leaks.push(`${file} :: description "${meta.description}"`);
    }
    expect(leaks).toEqual([]);
  });
});

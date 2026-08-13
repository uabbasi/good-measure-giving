// stripScoreFraction: pipeline evidence text restates a criterion's own
// scored/possible fraction in prose. The dedicated {scored}/{possible} display
// next to each criterion is member-only (GmgCharityDetail.tsx's showScore /
// showScores), so the same number sitting in the note text republished it to
// everyone regardless of sign-in. These three template shapes cover 100% of
// the fraction-bearing evidence strings found across the live corpus
// (data/charities/*.json, checked 2026-08-12): "Cause area: X (S/P)",
// "Revenue: $XM (S/P funding gap)", "Founded YYYY (N years — S/P)".

import { describe, it, expect } from 'vitest';
import { stripScoreFraction, adaptCharity } from './charityAdapter';
import fs from 'node:fs';
import path from 'node:path';

describe('stripScoreFraction', () => {
  it('drops a parenthetical whose only content is the fraction', () => {
    expect(stripScoreFraction('Cause area: Humanitarian (13/13)', 13, 13)).toBe('Cause area: Humanitarian');
  });

  it('keeps the surrounding words in the parenthetical, drops only the fraction', () => {
    expect(stripScoreFraction('Revenue: $4.0M (5/5 funding gap)', 5, 5)).toBe('Revenue: $4.0M (funding gap)');
  });

  it('cleans up a dangling em dash left by the fraction removal', () => {
    expect(stripScoreFraction('Founded 2001 (25 years — 6/6)', 6, 6)).toBe('Founded 2001 (25 years)');
  });

  it('leaves the note untouched when it does not contain this fraction', () => {
    const note = 'Board governance: STRONG (35 members)';
    expect(stripScoreFraction(note, 7, 8)).toBe(note);
  });

  it('leaves the note untouched when possible=0 and the note is dashless', () => {
    expect(stripScoreFraction('—', 0, 0)).toBe('—');
  });

  it('does not touch an unrelated number pair that is not this fraction', () => {
    // scored/possible is 3/5 for this criterion, but the note cites a
    // different figure entirely — must not be mistaken for the score.
    expect(stripScoreFraction('Peer median is 4/5 on this metric', 3, 5)).toBe('Peer median is 4/5 on this metric');
  });
});

describe('stripScoreFraction wired into adaptCharity — real corpus data', () => {
  const dir = path.resolve(__dirname, '../../../data/charities');

  it('produces no criterion note containing its own scored/possible fraction, across the whole corpus', () => {
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
    expect(files.length).toBeGreaterThan(100); // sanity: corpus actually loaded

    const leaks: string[] = [];
    for (const file of files) {
      const raw = JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8'));
      const c = adaptCharity(raw);
      for (const dim of [c.impact, c.alignment]) {
        for (const cr of dim.criteria) {
          const fraction = new RegExp(`\\b${cr.scored}\\s*/\\s*${cr.possible}\\b`);
          if (fraction.test(cr.note)) leaks.push(`${file} :: ${cr.name} :: "${cr.note}"`);
        }
      }
    }
    expect(leaks).toEqual([]);
  });

  it('still carries real, non-numeric evidence text for a criterion known to have a funding-gap note', () => {
    const raw = JSON.parse(fs.readFileSync(path.join(dir, 'charity-13-5660870.json'), 'utf8'));
    const c = adaptCharity(raw);
    const fundingGap = c.alignment.criteria.find((cr) => cr.name.toLowerCase().includes('funding gap'));
    expect(fundingGap).toBeDefined();
    expect(fundingGap!.note).toContain('funding gap');
    expect(fundingGap!.note).not.toMatch(/\d+\s*\/\s*\d+/);
  });
});

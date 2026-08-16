// zakatEvidence: score_details.zakat.claim_evidence is rendered verbatim in
// italics on the detail page as if it were a real quoted source (see
// RightForYou.tsx's "Zakat verification" block). For 11 of 135 published
// charities — found via manual QA on Al-Barr Foundation (85-3964369), also
// present on Doctors Without Borders (13-3433452) — the pipeline's
// corroboration step writes its own internal failure message into that same
// field instead of a citation: "CORROBORATION FAILED: Discovered via search
// (confidence=0.50)". adaptCharity must treat that as absent, not display it.

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { adaptCharity } from './charityAdapter';

const dir = path.resolve(__dirname, '../../../data/charities');
const load = (ein: string) => adaptCharity(JSON.parse(fs.readFileSync(path.join(dir, `charity-${ein}.json`), 'utf8')));

describe('zakatEvidence — pipeline-internal audit text never reaches the page', () => {
  it('is null for a charity whose corroboration check failed, not the raw failure message', () => {
    const c = load('85-3964369'); // Al-Barr Foundation
    expect(c.zakatEvidence).toBeNull();
  });

  it('holds for a second, unrelated charity with the same defect', () => {
    const c = load('13-3433452'); // Doctors Without Borders
    expect(c.zakatEvidence).toBeNull();
  });

  it('still passes through a real quoted claim untouched', () => {
    const c = load('13-5660870'); // International Rescue Committee — real dedicated zakat page cited
    expect(c.zakatEvidence).not.toBeNull();
    expect(c.zakatEvidence).not.toMatch(/CORROBORATION FAILED/i);
  });

  it('holds across the whole corpus, not just these two fixtures', () => {
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
    expect(files.length).toBeGreaterThan(100); // sanity: corpus actually loaded

    const leaks: string[] = [];
    for (const file of files) {
      const c = adaptCharity(JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8')));
      if (c.zakatEvidence && /CORROBORATION FAILED/i.test(c.zakatEvidence)) leaks.push(file);
    }
    expect(leaks).toEqual([]);
  });
});

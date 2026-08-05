/**
 * The published EDITION and the internal RUBRIC_VERSION are two version lines
 * for two audiences, and only one of them is public.
 *
 * They were previously one string, mirrored into this config by hand under a
 * comment asking the next person to keep it in step with
 * data-pipeline/src/scorers/v2_scorers.py. It drifted, and the drift was
 * visible on a single page: the site strip served "METHODOLOGY v5.2.0" while
 * every charity detail page underneath it read "RUBRIC v5.3.0", carried
 * straight out of the exported data.
 *
 * A comment is not a mechanism. These are the mechanism.
 */

import { readdirSync, readFileSync, statSync } from 'fs';
import { join } from 'path';
import { describe, expect, it } from 'vitest';

import { EDITION, EDITION_HISTORY } from './siteVersion';

const SRC = join(__dirname, '..');
const WEBSITE = join(__dirname, '..', '..');
const SKIP_DIRS = new Set(['node_modules', 'dist', 'build', 'coverage', '.vite', 'generated']);

/**
 * Every rendered surface, discovered rather than listed.
 *
 * A hand-maintained list is what let this bug survive the first sweep: the
 * grep covered website/src and missed website/pages/MethodologyPage.tsx —
 * a ROOT-level directory — which was stamping the internal semver into the
 * page's own citation string. Only the typechecker caught it. Walk the tree.
 */
function renderedSources(dir: string, found: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (SKIP_DIRS.has(name)) continue;
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      renderedSources(full, found);
    } else if (name.endsWith('.tsx') && !name.includes('.test.')) {
      found.push(full);
    }
  }
  return found;
}

// .tsx renders; the adapter is .ts but feeds every charity page.
const RENDERED_SOURCES = [
  ...renderedSources(WEBSITE),
  join(SRC, 'components/gmg/charityAdapter.ts'),
];

describe('the edition is what the public sees', () => {
  it('is a plain major.minor, not a semver patch line', () => {
    // A patch digit invites bumping the public number for a bug fix, which is
    // exactly the coupling this split exists to break.
    expect(EDITION).toMatch(/^\d+\.\d+$/);
  });

  it('is the newest entry in the published history', () => {
    expect(EDITION_HISTORY[0].edition).toBe(EDITION);
  });

  it('marks exactly one edition as current', () => {
    const live = EDITION_HISTORY.filter((e) => e.until === null);
    expect(live).toHaveLength(1);
    expect(live[0].edition).toBe(EDITION);
  });

  it('leaves no gap or overlap in the history', () => {
    for (let i = 1; i < EDITION_HISTORY.length; i += 1) {
      const older = EDITION_HISTORY[i];
      expect(older.until).not.toBeNull();
      expect(older.from <= (older.until as string)).toBe(true);
      expect((older.until as string) < EDITION_HISTORY[i - 1].from).toBe(true);
    }
  });
});

describe('the internal rubric version stays internal', () => {
  it('is not rendered on any public surface', () => {
    // The rubric version reaches the site only through the exported field
    // `rubric_version` / its camelCase alias. Reading it at all in something
    // that renders is how it got onto the page last time.
    const offenders = RENDERED_SOURCES.filter((file) =>
      /rubricVersion|rubric_version|RUBRIC_VERSION/.test(readFileSync(file, 'utf8')),
    ).map((file) => file.slice(WEBSITE.length + 1));

    expect(offenders, 'these render the internal rubric version').toEqual([]);
  });

  it('actually scanned the tree, including root-level pages', () => {
    // Guards the guard: if the walk silently returns nothing, the check above
    // passes vacuously forever.
    const rel = RENDERED_SOURCES.map((f) => f.slice(WEBSITE.length + 1));
    expect(rel.length).toBeGreaterThan(20);
    expect(rel).toContain('pages/MethodologyPage.tsx');
    expect(rel).toContain('src/components/gmg/GmgVersionStrip.tsx');
  });

  it('is not what the version strip prints', () => {
    const strip = readFileSync(join(SRC, 'components/gmg/GmgVersionStrip.tsx'), 'utf8');
    expect(strip).toMatch(/EDITION \$\{EDITION\}/);
    expect(strip).not.toMatch(/METHODOLOGY v/);
  });
});

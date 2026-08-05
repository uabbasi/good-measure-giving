// The PUBLISHED edition of Good Measure Giving's methodology.
//
// Two version lines run in parallel and must not be confused:
//
//   EDITION (this file)          the promise made to a donor. It answers
//                                "has the meaning of this score changed since
//                                I last trusted it?" It moves rarely and
//                                deliberately, and it is the ONLY version any
//                                visitor sees.
//
//   RUBRIC_VERSION               data lineage, in
//   (v2_scorers.py, semver)      data-pipeline/src/scorers/v2_scorers.py. It
//                                answers "which code produced this score?",
//                                stamps evaluations.rubric_version and the
//                                Dolt tags, and must bump on ANY scoring
//                                change — including bug fixes nobody would
//                                announce. It is an engineering artifact and
//                                is deliberately not rendered anywhere.
//
// These used to be the same string, mirrored by hand with a comment asking
// the next person to keep them in step. They drifted: the site strip served
// "METHODOLOGY v5.2.0" while every score behind it, and every charity detail
// page, said 5.3.0. Mirroring one number for two audiences guarantees this —
// the internal line has to move for reasons the external line must not.
//
// WHEN TO BUMP THE EDITION
//
//   2.0 -> 2.1   a reweighting or a new signal: scores a donor already saw
//                now read differently
//   2.0 -> 3.0   a structural change to what the score MEANS
//   no bump      bug fixes, new data sources, refactors, re-runs — however
//                large. Those move RUBRIC_VERSION alone.
//
// The test in siteVersion.test.ts holds the invariant that no internal semver
// leaks into a rendered surface; a comment asking nicely is what failed last
// time.
export const EDITION = '2.0';

export interface EditionRecord {
  edition: string;
  /** First month this edition was published, YYYY-MM. */
  from: string;
  /** Last month it was current, or null while it is the live edition. */
  until: string | null;
  /** What changed for a reader — not a changelog of the code. */
  summary: string;
}

// Public history, newest first. Feeds /changelog so an edition number can be
// traced to what it actually changed.
export const EDITION_HISTORY: EditionRecord[] = [
  {
    edition: '2.0',
    from: '2026-08',
    until: null,
    summary:
      'Program-expense ratios are recomputed from the figures published beside them, ' +
      'rather than carried over from a rating that pools three filing years. 91 charities ' +
      'changed; five now publish no ratio because the filings behind them cannot support one.',
  },
  {
    edition: '1.0',
    from: '2026-02',
    until: '2026-07',
    summary: 'First published index.',
  },
];

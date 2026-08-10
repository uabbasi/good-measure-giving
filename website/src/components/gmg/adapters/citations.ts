// Turns the pipeline's inline <cite id="N">…</cite> markup into renderable
// segments. The two structures disagree on id format — all_citations stores
// "[1]" while the markup emits id="1" — so every lookup normalizes first.

import { resolveCitationUrls, type CitationLike } from '../../../utils/citationUrls';

export interface Citation {
  /** 1-based display number, in all_citations order. */
  n: number;
  /** Normalized id, matching what inline markup carries (e.g. "1"). */
  id: string;
  sourceName: string;
  sourceUrl: string | null;
  sourceType: string | null;
  claim: string;
  quote: string;
  accessDate: string | null;
  confidence: number | null;
}

export interface CitationIndex {
  ordered: Citation[];
  byId: Map<string, Citation>;
}

export type CitedSegment =
  | { kind: 'text'; text: string }
  | { kind: 'cited'; text: string; citation: Citation };

const CITE_RE = /<cite\s+id="([^"]*)"\s*>(.*?)<\/cite>/gis;

export const normalizeCitationId = (raw: unknown): string =>
  String(raw ?? '')
    .trim()
    .replace(/^\[+/, '')
    .replace(/\]+$/, '')
    .trim();

const clean = (s: unknown): string =>
  typeof s === 'string' ? s.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim() : '';

// Like `clean`, but preserves leading/trailing whitespace: text segments sit
// next to a sibling <cite> span, and trimming would fuse "Founded in" against
// "1933" with no space between them.
const cleanSegment = (s: unknown): string =>
  typeof s === 'string' ? s.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ') : '';

const str = (v: unknown): string => (typeof v === 'string' ? v : '');
const strOrNull = (v: unknown): string | null =>
  typeof v === 'string' && v.trim() !== '' ? v : null;
const numOrNull = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) ? v : null;

export const buildCitationIndex = (raw: unknown, context?: unknown): CitationIndex => {
  const empty: CitationIndex = { ordered: [], byId: new Map() };
  if (!Array.isArray(raw) || raw.length === 0) return empty;

  const likes = raw.filter((c): c is Record<string, unknown> => !!c && typeof c === 'object');
  if (likes.length === 0) return empty;

  const resolved = resolveCitationUrls(likes as unknown as CitationLike[], context);

  const ordered: Citation[] = resolved.map((c, i) => {
    const rec = c as unknown as Record<string, unknown>;
    return {
      n: i + 1,
      id: normalizeCitationId(rec.id),
      sourceName: str(rec.source_name),
      sourceUrl: strOrNull(rec.source_url),
      sourceType: strOrNull(rec.source_type),
      claim: clean(rec.claim),
      quote: clean(rec.quote),
      accessDate: strOrNull(rec.access_date),
      confidence: numOrNull(rec.confidence),
    };
  });

  const byId = new Map<string, Citation>();
  for (const c of ordered) if (c.id && !byId.has(c.id)) byId.set(c.id, c);

  return { ordered, byId };
};

export const parseCitedText = (text: unknown, index: CitationIndex): CitedSegment[] => {
  if (typeof text !== 'string' || text.trim() === '') return [];

  const segments: CitedSegment[] = [];
  const push = (kind: 'text', raw: string): void => {
    const t = cleanSegment(raw);
    if (t !== '') segments.push({ kind, text: t });
  };

  let cursor = 0;
  CITE_RE.lastIndex = 0;
  let match = CITE_RE.exec(text);
  while (match !== null) {
    push('text', text.slice(cursor, match.index));
    const citation = index.byId.get(normalizeCitationId(match[1]));
    const inner = cleanSegment(match[2]);
    // A citation is "resolved" once its id matches, independent of whether the
    // pipeline left the tag's span empty (seen fleet-wide: a few <cite> tags
    // carry no enclosed text at all). Only an id with no match degrades to
    // plain text.
    if (citation) segments.push({ kind: 'cited', text: inner, citation });
    else push('text', match[2]);
    cursor = match.index + match[0].length;
    match = CITE_RE.exec(text);
  }
  push('text', text.slice(cursor));

  return segments;
};

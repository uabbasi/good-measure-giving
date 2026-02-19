/**
 * SourceLinkedText: Renders text with Wikipedia-style inline citations.
 *
 * Parses `<cite id="1">linked text</cite>` tags and renders them as
 * clickable links that open the source URL in a new tab.
 *
 * Also handles legacy `[1]` style markers for backwards compatibility.
 */

import React from 'react';
import { cleanNarrativeText } from '../utils/cleanNarrativeText';

interface Citation {
  id?: string;           // "[1]", "[2]", etc.
  source_url?: string | null;
  source_name?: string;
  claim?: string;
}

interface SourceLinkedTextProps {
  text: string;
  citations?: Citation[];
  isDark: boolean;
  /** Use muted colors for better readability in dense text blocks */
  subtle?: boolean;
}

/**
 * URLs that should never be linked to (broken, hostile, or inappropriate)
 */
const BLOCKED_URL_PATTERNS = [
  'guidestar.org',  // Broken - Candid rebranded
  'ngo-monitor.org',
  'canarymission.org',
];

/**
 * Check if a URL should be blocked
 */
function isBlockedUrl(url: string): boolean {
  const urlLower = url.toLowerCase();
  return BLOCKED_URL_PATTERNS.some(pattern => urlLower.includes(pattern));
}

/**
 * Check if text is just a year (shouldn't link to homepage)
 */
function isJustYear(text: string): boolean {
  const trimmed = text.trim();
  return /^(19|20)\d{2}$/.test(trimmed);
}

/**
 * Check if URL is just a homepage (no path)
 */
function isHomepageUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.pathname === '/' || parsed.pathname === '';
  } catch {
    return false;
  }
}

/**
 * Build a map from citation ID to URL for quick lookup.
 * Normalizes IDs to handle both "[1]" and "1" formats.
 * Filters out blocked URLs.
 */
function buildCitationMap(citations: Citation[]): Map<string, { url: string; name: string }> {
  const map = new Map();
  for (const c of citations) {
    // Only add if URL exists and is not blocked
    if (c.id && c.source_url && !isBlockedUrl(c.source_url)) {
      const name = c.source_name || 'Source';
      // Store with normalized ID (just the number)
      const numericId = c.id.replace(/[\[\]]/g, '');
      map.set(numericId, { url: c.source_url, name });
      // Also store with brackets for legacy format
      map.set(c.id, { url: c.source_url, name });
    }
  }
  return map;
}

/**
 * Parse text containing <cite id="X">text</cite> tags and [X] markers.
 * Returns array of segments: either plain text or citation objects.
 *
 * Handles both properly closed tags AND unclosed cite tags (LLM artifact).
 * Unclosed: <cite id="7">text here  →  treats text to next < or end as cited.
 */
function parseText(text: string): Array<{ type: 'text' | 'cite' | 'legacy'; content: string; id?: string }> {
  const segments: Array<{ type: 'text' | 'cite' | 'legacy'; content: string; id?: string }> = [];

  let lastIndex = 0;
  // Match: closed cite | unclosed cite (grab to next < or end) | legacy [N]
  const combinedPattern = /<cite\s+id=["']\[?(\d+)\]?["']>(.*?)<\/cite>|<cite\s+id=["']\[?(\d+)\]?["']>([^<]*)|\[(\d+)\]/g;
  let match;

  while ((match = combinedPattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({
        type: 'text',
        content: text.slice(lastIndex, match.index)
      });
    }

    if (match[1] !== undefined && match[2] !== undefined) {
      // Properly closed: <cite id="X">text</cite>
      segments.push({ type: 'cite', content: match[2], id: match[1] });
    } else if (match[3] !== undefined && match[4] !== undefined) {
      // Unclosed: <cite id="X">text (to next < or end)
      segments.push({ type: 'cite', content: match[4], id: match[3] });
    } else if (match[5] !== undefined) {
      // Legacy [X]
      segments.push({ type: 'legacy', content: `[${match[5]}]`, id: match[5] });
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    segments.push({ type: 'text', content: text.slice(lastIndex) });
  }

  return segments;
}

/**
 * SourceLinkedText component.
 *
 * Renders Wikipedia-style inline citations as clickable links.
 */
// Exported for testing
export { parseText, buildCitationMap };
export type { Citation };

export const SourceLinkedText: React.FC<SourceLinkedTextProps> = ({
  text,
  citations = [],
  isDark,
  subtle = false
}) => {
  const citationMap = buildCitationMap(citations);
  const segments = parseText(cleanNarrativeText(text));

  return (
    <>
      {segments.map((segment, i) => {
        if (segment.type === 'text') {
          return <span key={i}>{segment.content}</span>;
        }

        const citation = segment.id ? citationMap.get(segment.id) : null;

        if (segment.type === 'cite') {
          // Wikipedia-style: the text itself is the link
          // Clean styling - just color change, underline on hover only
          // Skip linking if: no URL, or text is just a year linking to homepage
          const shouldLink = citation?.url &&
            !(isJustYear(segment.content) && isHomepageUrl(citation.url));

          if (shouldLink) {
            // Subtle mode: muted underline only, no color change
            const linkClass = subtle
              ? `underline decoration-dotted ${
                  isDark
                    ? 'text-inherit decoration-slate-500 hover:decoration-slate-400'
                    : 'text-inherit decoration-slate-400 hover:decoration-slate-500'
                } underline-offset-2 transition-colors cursor-pointer`
              : `${
                  isDark
                    ? 'text-emerald-400 hover:text-emerald-300 hover:underline decoration-emerald-500/50'
                    : 'text-emerald-700 hover:text-emerald-600 hover:underline decoration-emerald-600/50'
                } underline-offset-2 transition-colors cursor-pointer`;

            return (
              <a
                key={i}
                href={citation!.url}
                target="_blank"
                rel="noopener noreferrer"
                title={`Source: ${citation!.name} (Cmd+click for background tab)`}
                className={linkClass}
              >
                {segment.content}
              </a>
            );
          } else {
            // No URL or bad link - render as plain text
            return <span key={i}>{segment.content}</span>;
          }
        }

        if (segment.type === 'legacy') {
          // Legacy [X] format - render as inline citation badge
          if (citation?.url) {
            return (
              <a
                key={i}
                href={citation.url}
                target="_blank"
                rel="noopener noreferrer"
                title={`${citation.name} (click to view source)`}
                className={`inline-flex items-center gap-0.5 mx-0.5 px-1 py-0.5 rounded text-[10px] font-medium align-baseline transition-colors ${
                  isDark
                    ? 'bg-emerald-900/40 text-emerald-400 hover:bg-emerald-900/60'
                    : 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                }`}
              >
                <span>{segment.content.replace(/[\[\]]/g, '')}</span>
                <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            );
          } else {
            return (
              <span
                key={i}
                className={`inline-flex items-center mx-0.5 px-1 py-0.5 rounded text-[10px] font-medium align-baseline ${
                  isDark ? 'bg-slate-700/50 text-slate-500' : 'bg-slate-200 text-slate-400'
                }`}
                title="Source not available"
              >
                {segment.content.replace(/[\[\]]/g, '')}
              </span>
            );
          }
        }

        return null;
      })}
    </>
  );
};

export default SourceLinkedText;

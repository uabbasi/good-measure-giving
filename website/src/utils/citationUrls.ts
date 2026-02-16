export interface CitationLike {
  source_name?: string;
  source_url?: string | null;
  claim?: string;
  quote?: string;
}

const URL_PATTERN = /https?:\/\/[^\s"'<>)\]]+/gi;

const FINANCIAL_TOPIC = /(financial|revenue|expense|assets?|liabilit|working capital|fundraising|audit|990|ratio)/i;
const RATING_TOPIC = /(rating|score|stars?|accountability|leadership|overall)/i;

const TOPIC_PATH_HINTS: Array<{ topic: RegExp; path: RegExp }> = [
  { topic: /(zakat|sadaq)/i, path: /\/(zakat|sadaq)/i },
  { topic: /(donat|give|support)/i, path: /\/(donate|give|support|contribute)/i },
  { topic: /(about|mission|history|founded|who we are)/i, path: /\/(about|mission|history|our-story|who-we-are)/i },
  { topic: /(program|service|initiative|project)/i, path: /\/(program|service|our-work|what-we-do|initiative)/i },
  { topic: /(impact|outcome|beneficiar|theory of change|model|evidence|evaluation|results)/i, path: /(\/(impact|outcome|result|evaluation|theory|model|learn)|\/s\/|\.pdf$)/i },
  { topic: /(financial|revenue|expense|asset|liabilit|audit|annual report|transparency|990)/i, path: /\/(financial|annual|report|transparency|accountability|audit|990)/i },
  { topic: /(board|leadership|team|ceo|governance|staff)/i, path: /\/(board|leadership|team|governance|staff)/i },
  { topic: /(geographic|region|country|coverage|where)/i, path: /\/(where-we-work|country|countries|location|coverage|region)/i },
];

function trimUrlCandidate(raw: string): string {
  return raw.replace(/[),.;:!?]+$/, '');
}

function parseUrl(value: string): URL | null {
  try {
    return new URL(value);
  } catch {
    return null;
  }
}

function normalizeHost(hostname: string): string {
  return hostname.toLowerCase().replace(/^www\./, '');
}

function canonicalize(url: URL): string {
  const pathname = url.pathname || '/';
  return `${url.protocol}//${normalizeHost(url.hostname)}${pathname}${url.search}${url.hash}`;
}

function isHomepageLikeUrl(url: URL): boolean {
  const pathname = url.pathname || '/';
  return (pathname === '/' || pathname === '') && !url.search && !url.hash;
}

function isDeepUrl(url: URL): boolean {
  const pathname = url.pathname || '/';
  return pathname !== '/' || !!url.search || !!url.hash;
}

function collectUrls(value: unknown, out: Set<string>, seen: Set<unknown>): void {
  if (value == null) return;

  if (typeof value === 'string') {
    if (!value.includes('http://') && !value.includes('https://')) {
      return;
    }
    const matches = value.match(URL_PATTERN);
    if (!matches) return;
    for (const raw of matches) {
      out.add(trimUrlCandidate(raw));
    }
    return;
  }

  if (typeof value !== 'object') return;
  if (seen.has(value)) return;
  seen.add(value);

  if (Array.isArray(value)) {
    for (const item of value) {
      collectUrls(item, out, seen);
    }
    return;
  }

  for (const nested of Object.values(value as Record<string, unknown>)) {
    collectUrls(nested, out, seen);
  }
}

function bestTopicMatch(topicText: string, candidates: URL[]): URL | null {
  let best: URL | null = null;
  let bestScore = 0;

  for (const candidate of candidates) {
    const haystack = `${candidate.pathname}${candidate.search}${candidate.hash}`.toLowerCase();
    let score = 0;

    for (const hint of TOPIC_PATH_HINTS) {
      if (hint.topic.test(topicText) && hint.path.test(haystack)) {
        score += 5;
      }
    }

    if (score > bestScore) {
      best = candidate;
      bestScore = score;
    }
  }

  return bestScore > 0 ? best : null;
}

function scoreGenericCandidate(topicText: string, candidate: URL): number {
  const haystack = `${candidate.pathname}${candidate.search}${candidate.hash}`.toLowerCase();
  let score = 0;

  if (/\/s\/|\.pdf$/i.test(haystack)) score += 5;
  if (/(impact|outcome|result|annual|report|audit|evaluation|program|project|learn|theory|model|metric|financial|transparency)/i.test(haystack)) {
    score += 4;
  }
  if (/(donate|volunteer|contact|checkout|cart|login|signup|privacy|terms)/i.test(haystack)) {
    score -= 3;
  }
  if (candidate.pathname && candidate.pathname !== '/') score += 1;
  if (candidate.hash) score += 1;

  // Extra weight when claim text is outcome/beneficiary-oriented.
  if (/(beneficiar|outcome|impact|served annually|people served|students served)/i.test(topicText)
    && /(report|audit|impact|outcome|result|program|\.pdf|\/s\/)/i.test(haystack)) {
    score += 4;
  }

  return score;
}

function bestGenericMatch(topicText: string, candidates: URL[]): URL | null {
  let best: URL | null = null;
  let bestScore = Number.NEGATIVE_INFINITY;

  for (const candidate of candidates) {
    const score = scoreGenericCandidate(topicText, candidate);
    if (score > bestScore) {
      best = candidate;
      bestScore = score;
    }
  }

  return best && bestScore > 0 ? best : null;
}

function maybeUpgradeKnownSource(url: URL, topicText: string): string | null {
  const host = normalizeHost(url.hostname);
  const isCharityNavigator = host.endsWith('charitynavigator.org');
  const einPath = /^\/ein\/\d+\/?$/i;

  if (!isCharityNavigator || !einPath.test(url.pathname) || url.hash) {
    return null;
  }

  if (FINANCIAL_TOPIC.test(topicText)) {
    return `${url.origin}${url.pathname.replace(/\/$/, '')}#financials`;
  }

  if (RATING_TOPIC.test(topicText)) {
    return `${url.origin}${url.pathname.replace(/\/$/, '')}#ratings`;
  }

  return null;
}

function indexDeepUrls(...values: unknown[]): Map<string, URL[]> {
  const discovered = new Set<string>();
  const seen = new Set<unknown>();
  for (const value of values) {
    collectUrls(value, discovered, seen);
  }

  const byHost = new Map<string, Map<string, URL>>();

  for (const raw of discovered) {
    const parsed = parseUrl(raw);
    if (!parsed || !isDeepUrl(parsed)) continue;

    const host = normalizeHost(parsed.hostname);
    const canonical = canonicalize(parsed);
    if (!byHost.has(host)) {
      byHost.set(host, new Map<string, URL>());
    }
    byHost.get(host)!.set(canonical, parsed);
  }

  const result = new Map<string, URL[]>();
  for (const [host, urls] of byHost.entries()) {
    result.set(host, Array.from(urls.values()));
  }
  return result;
}

export function resolveCitationUrls<T extends CitationLike>(citations: T[], context?: unknown): T[] {
  if (!citations || citations.length === 0) return citations;

  const deepUrlsByHost = indexDeepUrls(citations, context);

  return citations.map((citation) => {
    if (!citation.source_url) return citation;

    const parsed = parseUrl(citation.source_url);
    if (!parsed) return citation;

    const topicText = `${citation.source_name || ''} ${citation.claim || ''} ${citation.quote || ''}`.toLowerCase();
    const knownUpgrade = maybeUpgradeKnownSource(parsed, topicText);
    if (knownUpgrade && knownUpgrade !== citation.source_url) {
      return { ...citation, source_url: knownUpgrade };
    }

    if (!isHomepageLikeUrl(parsed)) return citation;

    const host = normalizeHost(parsed.hostname);
    const candidates = deepUrlsByHost.get(host) || [];
    if (candidates.length === 0) return citation;

    const topicMatch = bestTopicMatch(topicText, candidates);
    if (topicMatch && topicMatch.href !== citation.source_url) {
      return { ...citation, source_url: topicMatch.href };
    }

    const genericMatch = bestGenericMatch(topicText, candidates);
    if (genericMatch && genericMatch.href !== citation.source_url) {
      return { ...citation, source_url: genericMatch.href };
    }

    return citation;
  });
}

export function resolveSourceUrl(
  sourceUrl: string | null | undefined,
  context?: unknown,
  hints?: Pick<CitationLike, 'source_name' | 'claim' | 'quote'>
): string | null {
  if (!sourceUrl) return null;
  const [resolved] = resolveCitationUrls([{ source_url: sourceUrl, ...hints }], context);
  return resolved?.source_url || sourceUrl;
}

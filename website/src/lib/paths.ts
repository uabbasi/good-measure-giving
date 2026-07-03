// Internal route path builders.
//
// These emit the TRAILING-SLASH canonical form to match the sitemap,
// `<link rel="canonical">` tags, and Cloudflare's URL handling (which serves
// `/route/` as 200 and 308-redirects the no-slash form). Routing every internal
// `<Link>` through these helpers prevents Googlebot from discovering
// non-canonical no-slash duplicates via our own links — those duplicates were
// piling up as "Discovered - currently not indexed" in Search Console.
//
// The absolute-URL equivalent for external embeds lives in `charityUrl()` in
// ./trustBadge.ts.

export const charityPath = (ein: string): string => `/charity/${ein}/`;
export const causePath = (slug: string): string => `/causes/${slug}/`;
export const guidePath = (slug: string): string => `/guides/${slug}/`;
export const promptPath = (id: string): string => `/prompts/${id}/`;
export const zakatCalculatorPath = (slug: string): string => `/zakat-calculator/${slug}/`;

// Static content routes (trailing slash to match their canonical URLs).
export const paths = {
  browse: '/browse/',
  compare: '/compare/',
  causes: '/causes/',
  guides: '/guides/',
  prompts: '/prompts/',
  zakatCalculator: '/zakat-calculator/',
  methodology: '/methodology/',
  about: '/about/',
  faq: '/faq/',
} as const;

// Compare a location pathname to a route ignoring a trailing slash. Routes are
// canonicalized with a trailing slash, but in-app navigation may omit it, so an
// exact `pathname === '/browse'` check breaks on the canonical `/browse/`. Use
// this for active-state / current-page checks instead of `===`.
export const isPath = (pathname: string, route: string): boolean =>
  pathname.replace(/\/+$/, '') === route.replace(/\/+$/, '');

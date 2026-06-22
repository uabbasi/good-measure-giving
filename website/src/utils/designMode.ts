/**
 * Design mode selector.
 *
 * The GMG "Modern" motif (sage-on-bone, Harvey balls) is the DEFAULT experience
 * for every visitor — anonymous, authenticated, and Googlebot/SSG alike. The
 * legacy design is kept behind an escape hatch (`?design=legacy`) for fallback
 * and side-by-side comparison; it is not linked from anywhere.
 *
 * Pass `location.search` (from react-router's useLocation) so this resolves
 * correctly during build-time SSR, where `window` is undefined.
 */
export function isLegacyDesign(search: string): boolean {
  return new URLSearchParams(search).get('design') === 'legacy';
}

/** Inverse of {@link isLegacyDesign}: true when the motif should render. */
export function isMotifDesign(search: string): boolean {
  return !isLegacyDesign(search);
}

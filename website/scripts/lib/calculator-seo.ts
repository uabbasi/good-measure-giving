/**
 * Zakat calculator taxonomy helpers.
 *
 * The list of known asset slugs is canonical — any asset slug rendered must
 * appear here. This is intentionally stricter than a free-form pattern:
 * calculator pages depend on fiqh-accurate per-asset content, and we don't
 * want crawlers finding thin auto-generated asset pages.
 */

export const KNOWN_ASSET_SLUGS = [
  'cash-savings',
  'gold-silver',
  'stocks',
  '401k-retirement',
  'crypto',
  'business-assets',
  'real-estate',
] as const;

export type AssetSlug = (typeof KNOWN_ASSET_SLUGS)[number];

export function isValidAssetSlug(slug: string): slug is AssetSlug {
  return (KNOWN_ASSET_SLUGS as readonly string[]).includes(slug);
}

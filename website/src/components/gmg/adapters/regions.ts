// The browse index carries no targeting block — only causeTags — so a row's
// geography has to be read out of the tag vocabulary. Insertion order here
// is the display order (by corpus frequency), so output is stable
// regardless of tag order.
//
// `international` is deliberately excluded: it is a scope marker, not a
// place, and does not belong in a "Where it works" geography facet.

export const REGION_TAGS: Record<string, string> = {
  usa: 'United States',
  palestine: 'Palestine',
  pakistan: 'Pakistan',
  bangladesh: 'Bangladesh',
  sudan: 'Sudan',
  lebanon: 'Lebanon',
  syria: 'Syria',
  yemen: 'Yemen',
  india: 'India',
  jordan: 'Jordan',
  somalia: 'Somalia',
  afghanistan: 'Afghanistan',
  kenya: 'Kenya',
  ukraine: 'Ukraine',
  indonesia: 'Indonesia',
  turkey: 'Türkiye',
  haiti: 'Haiti',
  iraq: 'Iraq',
  egypt: 'Egypt',
  'south-africa': 'South Africa',
  nigeria: 'Nigeria',
  ethiopia: 'Ethiopia',
  myanmar: 'Myanmar',
  kashmir: 'Kashmir',
  malaysia: 'Malaysia',
};

export const regionsFromCauseTags = (raw: unknown): string[] => {
  if (!Array.isArray(raw)) return [];
  const present = new Set(
    raw.filter((t): t is string => typeof t === 'string').map((t) => t.toLowerCase()),
  );
  return Object.keys(REGION_TAGS)
    .filter((key) => present.has(key))
    .map((key) => REGION_TAGS[key]);
};

export const regionLabel = (regions: string[]): string => {
  if (regions.length === 0) return 'Multi';
  if (regions.length === 1) return regions[0];
  // Naming the first tag reads as a real "leading region" for a short list,
  // but REGION_TAGS order is corpus frequency, not this charity's own
  // emphasis — past a handful of matches, leading with one is arbitrary
  // (e.g. an org in 40+ countries reading "Palestine +12"). Say so plainly
  // instead of picking a tag to feature.
  if (regions.length > 3) return `Multi-region (${regions.length})`;
  return `${regions[0]} +${regions.length - 1}`;
};

// The eight asnaf are the Qur'anic categories of zakat recipient. Only four
// appear in the corpus; the other four are listed so the facet does not need
// changing when the pipeline starts emitting them, and a value with a zero
// count is simply not rendered.
export const ASNAF_TAGS: Record<string, string> = {
  fuqara: 'Fuqara (the poor)',
  masakin: 'Masakin (the needy)',
  amilin: 'Amilin (zakat administrators)',
  muallaf: 'Muallaf (reconciliation of hearts)',
  riqab: 'Riqab (freeing captives)',
  gharimin: 'Gharimin (the indebted)',
  fisabilillah: 'Fisabilillah (in the path of God)',
  'ibn-sabil': 'Ibn al-Sabil (the wayfarer)',
};

const keysPresent = (raw: unknown, vocabulary: Record<string, string>): string[] => {
  if (!Array.isArray(raw)) return [];
  const present = new Set(
    raw.filter((t): t is string => typeof t === 'string').map((t) => t.toLowerCase()),
  );
  return Object.keys(vocabulary).filter((key) => present.has(key));
};

/** Region *keys* (e.g. 'usa'), as opposed to display names from regionsFromCauseTags. */
export const regionKeysFromCauseTags = (raw: unknown): string[] =>
  keysPresent(raw, REGION_TAGS);

export const asnafKeysFromCauseTags = (raw: unknown): string[] =>
  keysPresent(raw, ASNAF_TAGS);

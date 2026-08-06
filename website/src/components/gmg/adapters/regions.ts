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
  return `${regions[0]} +${regions.length - 1}`;
};

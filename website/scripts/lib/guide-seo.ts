/**
 * Editorial guide type definitions and helpers.
 * Guides are structured JSON with typed sections — no markdown dependency.
 */

export interface GuideSection {
  heading: string;
  paragraphs: string[];
}

export interface GuideCallout {
  label: string;
  text: string;
}

export interface GuideFaqItem {
  q: string;
  a: string;
}

export interface GuideFeaturedCharity {
  ein: string;
  blurb: string;
}

export interface Guide {
  slug: string;
  title: string;
  metaTitle: string;
  metaDescription: string;
  tldr: string;
  publishedOn: string;
  updatedOn: string;
  readingTimeMinutes: number;
  sections: GuideSection[];
  callouts?: GuideCallout[];
  featuredCharities?: GuideFeaturedCharity[];
  faq: GuideFaqItem[];
  relatedGuides?: string[];
  relatedCauses?: string[];
}

export interface GuideSummary {
  slug: string;
  title: string;
  description: string;
  publishedOn: string;
  readingTimeMinutes: number;
}

export interface GuidesIndex {
  guides: GuideSummary[];
}

const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function isValidGuideSlug(slug: string): boolean {
  if (slug.length === 0) return false;
  return SLUG_PATTERN.test(slug);
}

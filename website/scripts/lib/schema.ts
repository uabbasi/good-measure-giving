/**
 * Reusable Schema.org JSON-LD builders for the prerender pipeline.
 * Each builder is a pure function that returns a serializable object
 * (or null when input is insufficient).
 */

export interface JsonLdObject {
  '@context': string;
  '@type': string;
  [key: string]: unknown;
}

export interface FaqPair {
  question: string;
  answer: string;
}

export function buildFaqPageSchema(pairs: FaqPair[]): JsonLdObject | null {
  if (pairs.length === 0) return null;
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: pairs.map((p) => ({
      '@type': 'Question',
      name: p.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: p.answer,
      },
    })),
  };
}

export interface Breadcrumb {
  name: string;
  url: string;
}

export function buildBreadcrumbSchema(crumbs: Breadcrumb[]): JsonLdObject | null {
  if (crumbs.length === 0) return null;
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: crumbs.map((c, idx) => ({
      '@type': 'ListItem',
      position: idx + 1,
      name: c.name,
      item: c.url,
    })),
  };
}

export interface ArticleInput {
  type?: 'Article' | 'TechArticle';
  headline: string;
  description: string;
  url: string;
  datePublished: string;
  dateModified: string;
  authorName: string;
}

export function buildArticleSchema(input: ArticleInput): JsonLdObject {
  return {
    '@context': 'https://schema.org',
    '@type': input.type ?? 'Article',
    headline: input.headline,
    description: input.description,
    url: input.url,
    datePublished: input.datePublished,
    dateModified: input.dateModified,
    author: { '@type': 'Organization', name: input.authorName },
    publisher: { '@type': 'Organization', name: input.authorName },
  };
}

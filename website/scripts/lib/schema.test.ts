import { describe, it, expect } from 'vitest';
import { buildFaqPageSchema, buildBreadcrumbSchema, buildArticleSchema, buildOrganizationSchema } from './schema';

describe('buildFaqPageSchema', () => {
  it('produces a valid FAQPage schema from Q&A pairs', () => {
    const result = buildFaqPageSchema([
      { question: 'What is zakat?', answer: 'An Islamic obligation.' },
      { question: 'Who pays zakat?', answer: 'Muslims meeting nisab.' },
    ]);

    expect(result).toEqual({
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: [
        {
          '@type': 'Question',
          name: 'What is zakat?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: 'An Islamic obligation.',
          },
        },
        {
          '@type': 'Question',
          name: 'Who pays zakat?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: 'Muslims meeting nisab.',
          },
        },
      ],
    });
  });

  it('returns null when given an empty array', () => {
    expect(buildFaqPageSchema([])).toBeNull();
  });
});

describe('buildBreadcrumbSchema', () => {
  it('produces a BreadcrumbList from ordered crumbs', () => {
    const result = buildBreadcrumbSchema([
      { name: 'Home', url: 'https://goodmeasuregiving.org/' },
      { name: 'Browse', url: 'https://goodmeasuregiving.org/browse' },
      { name: 'Islamic Relief', url: 'https://goodmeasuregiving.org/charity/95-4251543' },
    ]);

    expect(result).toEqual({
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://goodmeasuregiving.org/' },
        { '@type': 'ListItem', position: 2, name: 'Browse', item: 'https://goodmeasuregiving.org/browse' },
        { '@type': 'ListItem', position: 3, name: 'Islamic Relief', item: 'https://goodmeasuregiving.org/charity/95-4251543' },
      ],
    });
  });

  it('returns null when given an empty crumb list', () => {
    expect(buildBreadcrumbSchema([])).toBeNull();
  });
});

describe('buildArticleSchema', () => {
  it('produces a TechArticle with all fields', () => {
    const result = buildArticleSchema({
      type: 'TechArticle',
      headline: 'How We Evaluate Charities',
      description: 'Methodology for scoring Muslim charities on impact and alignment.',
      url: 'https://goodmeasuregiving.org/methodology',
      datePublished: '2026-02-01',
      dateModified: '2026-04-19',
      authorName: 'Good Measure Giving',
    });

    expect(result).toEqual({
      '@context': 'https://schema.org',
      '@type': 'TechArticle',
      headline: 'How We Evaluate Charities',
      description: 'Methodology for scoring Muslim charities on impact and alignment.',
      url: 'https://goodmeasuregiving.org/methodology',
      datePublished: '2026-02-01',
      dateModified: '2026-04-19',
      author: { '@type': 'Organization', name: 'Good Measure Giving' },
      publisher: { '@type': 'Organization', name: 'Good Measure Giving' },
    });
  });

  it('defaults to Article when type is omitted', () => {
    const result = buildArticleSchema({
      headline: 'Test',
      description: 'Test description.',
      url: 'https://goodmeasuregiving.org/test',
      datePublished: '2026-04-19',
      dateModified: '2026-04-19',
      authorName: 'GMG',
    });
    expect(result['@type']).toBe('Article');
  });
});

describe('buildOrganizationSchema', () => {
  it('produces an Organization schema with sameAs links', () => {
    const result = buildOrganizationSchema({
      name: 'Good Measure Giving',
      url: 'https://goodmeasuregiving.org',
      description: 'Independent charity evaluator for Muslim charities.',
      foundingDate: '2025-12-01',
      sameAs: ['https://twitter.com/goodmeasure', 'https://github.com/goodmeasure'],
    });

    expect(result).toEqual({
      '@context': 'https://schema.org',
      '@type': 'Organization',
      name: 'Good Measure Giving',
      url: 'https://goodmeasuregiving.org',
      description: 'Independent charity evaluator for Muslim charities.',
      foundingDate: '2025-12-01',
      sameAs: ['https://twitter.com/goodmeasure', 'https://github.com/goodmeasure'],
    });
  });

  it('omits sameAs when empty', () => {
    const result = buildOrganizationSchema({
      name: 'GMG',
      url: 'https://goodmeasuregiving.org',
      description: 'desc',
      foundingDate: '2025-12-01',
      sameAs: [],
    });
    expect('sameAs' in result).toBe(false);
  });
});

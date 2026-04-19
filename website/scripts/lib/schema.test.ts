import { describe, it, expect } from 'vitest';
import { buildFaqPageSchema, buildBreadcrumbSchema } from './schema';

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

import { describe, it, expect } from 'vitest';
import { buildFaqPageSchema } from './schema';

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

/**
 * Reusable Schema.org JSON-LD builders for the prerender pipeline.
 * Each builder is a pure function that returns a serializable object
 * (or null when input is insufficient).
 */

export interface FaqPair {
  question: string;
  answer: string;
}

export function buildFaqPageSchema(pairs: FaqPair[]): object | null {
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

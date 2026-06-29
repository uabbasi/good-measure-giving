// Good Measure Giving — "Modern" motif FAQ page (/faq).
// Motif-only (no legacy variant): renders its own GmgNav + footer via the content kit.
// All Q&A stays visible (open <dl> via FaqList) so the page text matches the
// FAQPage JSON-LD emitted by the prerenderer (built from the same FAQ_ITEMS).

import React from 'react';
import {
  GmgContentFrame,
  ContentHero,
  Em,
  Section,
  P,
  FaqList,
  ALink,
  type ContentCtx,
} from '../src/components/gmg/content';
import { FAQ_ITEMS, type FaqItem } from '../src/data/faq';

const CATEGORIES: { id: FaqItem['category']; label: string; description: string }[] = [
  { id: 'general', label: 'General', description: 'About Good Measure Giving' },
  { id: 'methodology', label: 'Our Methodology', description: 'How we score charities' },
  { id: 'ai', label: 'AI & Technology', description: 'How we use AI responsibly' },
  { id: 'zakat', label: 'Zakat & Sadaqah', description: 'Religious classifications' },
  { id: 'data', label: 'Data & Accuracy', description: 'Sources and updates' },
];

export const FAQPage: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  React.useEffect(() => {
    document.title = 'FAQ | Good Measure Giving';
    return () => {
      document.title = 'Good Measure Giving | Muslim Charity Evaluator';
    };
  }, []);

  return (
    <GmgContentFrame isDark={isDark} maxWidth={760}>
      {(ctx: ContentCtx) => {
        const { p } = ctx;
        return (
          <>
            <ContentHero
              ctx={ctx}
              kicker="FAQ"
              title={
                <>
                  Frequently asked <Em p={p}>questions.</Em>
                </>
              }
              lead="Everything you need to know about how we evaluate charities."
            />

            {CATEGORIES.map((category, i) => {
              const items = FAQ_ITEMS.filter((f) => f.category === category.id).map((f) => ({
                q: f.q,
                a: f.a,
              }));
              if (items.length === 0) return null;
              return (
                <Section key={category.id} ctx={ctx} title={category.label} first={i === 0}>
                  <P p={p} muted>
                    {category.description}
                  </P>
                  <FaqList p={p} items={items} />
                </Section>
              );
            })}

            <Section ctx={ctx} title="Still have questions?">
              <P p={p}>
                We're here to help. Reach out at{' '}
                <ALink p={p} to="/about">
                  about us
                </ALink>{' '}
                or email{' '}
                <a
                  href="mailto:hello@goodmeasuregiving.org"
                  style={{ color: p.accent, textDecoration: 'none', fontWeight: 500 }}
                >
                  hello@goodmeasuregiving.org
                </a>{' '}
                and we'll get back to you as soon as we can.
              </P>
            </Section>
          </>
        );
      }}
    </GmgContentFrame>
  );
};

export default FAQPage;

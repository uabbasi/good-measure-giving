// Good Measure Giving — "Modern" motif About page (/about).
// Motif-only (no legacy variant): renders its own GmgNav + footer via the content kit.

import React from 'react';
import {
  GmgContentFrame,
  ContentHero,
  Em,
  Section,
  P,
  H3,
  UL,
  ALink,
  Callout,
  CardGrid,
  CtaLink,
  type ContentCtx,
} from '../src/components/gmg/content';

const DATA_SOURCES: [string, string][] = [
  ['IRS Form 990 filings (via ProPublica)', 'Financials, governance, compensation, and grant data — the official public record.'],
  ['Charity Navigator', 'Financial health scores, accountability ratings, and 990 analysis.'],
  ['Candid (GuideStar)', 'Transparency seals and organizational profiles.'],
  ['BBB Wise Giving Alliance', 'Standards-based accreditation for governance and fundraising.'],
  ['Charity websites & reports', 'Annual reports, impact data, and program descriptions.'],
  ['Web discovery', 'Zakat claims, third-party evaluations, and awards found across the web.'],
];

const DIMENSIONS: { title: string; desc: string }[] = [
  {
    title: 'Impact',
    desc: 'How effectively does this charity turn donations into change? We evaluate cost per beneficiary, program efficiency, financial health, evidence of outcomes, and governance quality.',
  },
  {
    title: 'Alignment',
    desc: 'Is this the right charity for Muslim donors? We assess Muslim donor fit, cause urgency, underserved space, track record, and funding gap.',
  },
];

const INDEPENDENCE: string[] = [
  'No charity pays to be listed or to influence scores.',
  'All scoring criteria and AI prompts are published openly.',
  'We serve donors, not organizations.',
];

export const AboutPage: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  React.useEffect(() => {
    document.title = 'About | Good Measure Giving';
    return () => {
      document.title = 'Good Measure Giving | Muslim Charity Evaluator';
    };
  }, []);

  return (
    <GmgContentFrame isDark={isDark} active="About" maxWidth={760}>
      {(ctx: ContentCtx) => {
        const { p } = ctx;
        return (
          <>
            <ContentHero
              ctx={ctx}
              kicker="About"
              title={
                <>
                  About Good <Em p={p}>Measure.</Em>
                </>
              }
              lead="Rigorous, independent charity research for Muslim donors — so every dollar of Zakat and Sadaqah creates the deepest possible impact."
            />

            <Section ctx={ctx} title="The problem" first>
              <P p={p}>
                Every year, billions of dollars flow through Zakat, Sadaqah, and charitable giving in Muslim
                communities. Yet most donors lack access to independent, rigorous evaluations of the charities they
                support. General-purpose evaluators like Charity Navigator focus heavily on financial ratios and often
                miss nuances critical to our community — whether a charity publicly says it accepts Zakat, work in
                conflict zones, and grassroots organizations serving underserved populations. The result:
                well-intentioned giving that could do more.
              </P>
            </Section>

            <Section ctx={ctx} title="Our approach">
              <CardGrid min={260}>
                {DIMENSIONS.map((d) => (
                  <div
                    key={d.title}
                    style={{ background: p.card, border: `1px solid ${p.rule}`, borderRadius: 12, padding: '18px 20px' }}
                  >
                    <H3 p={p}>{d.title}</H3>
                    <P p={p} muted>
                      {d.desc}
                    </P>
                  </div>
                ))}
              </CardGrid>
              <P p={p} muted>
                Each dimension contributes up to 50 points to the GMG Score (0–100).{' '}
                <ALink p={p} to="/methodology">
                  See full methodology →
                </ALink>
              </P>
            </Section>

            <Section ctx={ctx} title="Where our data comes from">
              <P p={p}>We don't rely only on charity self-reporting. Our pipeline aggregates data from multiple independent sources:</P>
              <UL
                p={p}
                items={DATA_SOURCES.map(([source, detail]) => (
                  <>
                    <strong style={{ color: p.fg, fontWeight: 600 }}>{source}</strong>
                    {' — '}
                    {detail}
                  </>
                ))}
              />
            </Section>

            <Section ctx={ctx} title="AI-assisted, human-guided">
              <Callout p={p} tone="neutral">
                We use AI to synthesize large volumes of public data into structured evaluations. Core prompts, scoring
                rubrics, and decision rules are published on our <ALink p={p} to="/prompts">AI transparency page</ALink>.
                The pipeline is deterministic: same data in, same scores out. AI writes the narratives; the methodology,
                weights, and data sources are human-designed.
              </Callout>
            </Section>

            <Section ctx={ctx} title="Independence">
              <UL p={p} items={INDEPENDENCE} />
            </Section>

            <Section ctx={ctx}>
              <div style={{ textAlign: 'center', paddingTop: 8 }}>
                <CtaLink p={p} to="/browse">
                  Browse evaluated charities →
                </CtaLink>
              </div>
            </Section>
          </>
        );
      }}
    </GmgContentFrame>
  );
};

export default AboutPage;

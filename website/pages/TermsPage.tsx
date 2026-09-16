import React from 'react';
import { Link } from 'react-router-dom';
import { GmgContentFrame, ContentHero, Section, P, UL } from '../src/components/gmg/content';

export const TermsPage: React.FC<{ isDark: boolean }> = ({ isDark }) => (
  <GmgContentFrame isDark={isDark} maxWidth={760}>
    {(ctx) => {
      const { p } = ctx;
      return <>
        <ContentHero ctx={ctx} kicker="Terms" title="Terms of Use" lead="Last updated: September 16, 2026. These terms explain how you may use Good Measure Giving." />
        <Section ctx={ctx} title="1. Our service" first>
          <P p={p}>Good Measure Giving provides independent charity research, comparisons, calculators, and tools for organizing your giving. These terms apply when you use the website or create an account.</P>
        </Section>
        <Section ctx={ctx} title="2. Research and estimates">
          <P p={p}>Evaluations combine public records, reported information, and analysis that may include AI-assisted research. Sources can be incomplete, outdated, or incorrect. Scores and estimates are not guarantees of a charity’s conduct or future results.</P>
          <P p={p}>Our content is general information, not personalized financial, tax, legal, or religious advice. Calculator results depend on your inputs and assumptions. Confirm donation details with the charity, and consult a qualified adviser or scholar when your circumstances require it.</P>
        </Section>
        <Section ctx={ctx} title="3. Donations and outside websites">
          <P p={p}>Donation links take you to third-party websites. We do not collect or process your donation payments. The receiving charity or payment provider handles payments, refunds, receipts, and its own terms and privacy practices. A donation recorded in your giving plan is your record; it does not verify that a charity received funds or establish tax deductibility.</P>
        </Section>
        <Section ctx={ctx} title="4. Accounts and shared plans">
          <P p={p}>Keep your sign-in credentials secure and provide information you are entitled to share. Only invite people you intend to give access to a shared plan, and treat invitation links as private. Other plan members may see information you add to the plan. Contact us if you believe someone has accessed your account without permission.</P>
        </Section>
        <Section ctx={ctx} title="5. Responsible use">
          <UL p={p} items={[
            'Do not impersonate others, submit misleading reports, or upload information you do not have permission to share.',
            'Do not attempt unauthorized access, disrupt the service, or bypass access controls.',
            'You may link to our research and quote short excerpts with attribution. Third-party source material remains subject to its owner’s rights. Contact us about broader republication.',
          ]} />
          <P p={p}>We may restrict access to address abuse, security problems, or violations of these terms.</P>
        </Section>
        <Section ctx={ctx} title="6. Availability and responsibility">
          <P p={p}>We aim to keep the site useful and accurate, but cannot promise uninterrupted availability or error-free information. Keep your own copies of important giving records. You remain responsible for your giving decisions. Nothing in these terms excludes rights or responsibilities that applicable law does not allow us to exclude.</P>
        </Section>
        <Section ctx={ctx} title="7. Privacy, updates, and contact">
          <P p={p}>Our <Link to="/privacy/" style={{ color: p.accent }}>Privacy Policy</Link> explains data use and your analytics choices. We may update these terms as the service changes; the date above identifies the current version.</P>
          <P p={p}>For questions, corrections, or account requests, email <a href="mailto:hello@goodmeasuregiving.org" style={{ color: p.accent }}>hello@goodmeasuregiving.org</a>.</P>
        </Section>
      </>;
    }}
  </GmgContentFrame>
);

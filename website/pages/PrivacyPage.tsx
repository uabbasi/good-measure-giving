// Good Measure Giving — "Modern" motif Privacy Policy page (/privacy).
// Motif-only (no legacy variant): renders its own GmgNav + footer via the content kit.

import React from 'react';
import {
  GmgContentFrame,
  ContentHero,
  Section,
  P,
  UL,
  type ContentCtx,
} from '../src/components/gmg/content';

export const PrivacyPage: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  React.useEffect(() => {
    document.title = 'Privacy Policy | Good Measure Giving';
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
              kicker="Privacy"
              title="Privacy Policy"
              lead="Last updated: June 8, 2026. We respect your privacy and are committed to protecting your personal data."
            />

            <Section ctx={ctx} title="1. Overview" first>
              <P p={p}>
                Good Measure Giving operates as an evidence-based charity evaluator. This Privacy Policy describes how we
                collect, use, and process your personal data when you visit our website, use our tools (such as the Zakat
                Calculator), register an account, or submit feedback and suggestions.
              </P>
            </Section>

            <Section ctx={ctx} title="2. Information We Collect">
              <P p={p}>We collect information to provide a better experience to our users. This includes:</P>
              <UL
                p={p}
                items={[
                  <>
                    <strong style={{ color: p.fg, fontWeight: 600 }}>Account Credentials:</strong> If you sign up or log
                    in, we collect your email address and profile identifiers using our secure authentication provider
                    (Firebase Auth).
                  </>,
                  <>
                    <strong style={{ color: p.fg, fontWeight: 600 }}>User Interactions:</strong> Saved bookmarks, tour
                    completion statuses, or comparison sets stored to customize your dashboard.
                  </>,
                  <>
                    <strong style={{ color: p.fg, fontWeight: 600 }}>Feedback &amp; Suggestions:</strong> Any information
                    you voluntarily provide when suggesting a charity or sending feedback.
                  </>,
                  <>
                    <strong style={{ color: p.fg, fontWeight: 600 }}>Usage Data:</strong> Anonymized analytical data
                    showing how visitors navigate and interact with the site, using privacy-respecting aggregate tools.
                  </>,
                ]}
              />
            </Section>

            <Section ctx={ctx} title="3. How We Use Your Data">
              <P p={p}>We only use your data for legitimate, specific purposes, including:</P>
              <UL
                p={p}
                items={[
                  'Providing, maintaining, and improving our charity evaluation services.',
                  'Securing and authenticating user accounts.',
                  'Allowing you to save bookmarks and personalize your experience.',
                  'Aggregating anonymous metrics to measure website performance.',
                ]}
              />
            </Section>

            <Section ctx={ctx} title="4. Cookies and Local Storage">
              <P p={p}>
                We use standard browser local storage and cookies to store session states, active UI themes (light vs.
                dark), and bookmarks. You can control cookie preferences in your browser settings.
              </P>
            </Section>

            <Section ctx={ctx} title="5. Third-Party Services">
              <P p={p}>
                We do not sell your personal data. We only share data with essential infrastructure providers,
                specifically <strong style={{ color: p.fg, fontWeight: 600 }}>Firebase Authentication</strong> for user
                logins. All data sharing is secured and encrypted.
              </P>
            </Section>

            <Section ctx={ctx} title="6. Your Rights">
              <P p={p}>
                You have the right to access, rectify, or request the deletion of your personal account data at any time.
                To make a request or ask questions about our data practices, please contact us at{' '}
                <a href="mailto:hello@goodmeasuregiving.org" style={{ color: p.accent, textDecoration: 'none', fontWeight: 500 }}>
                  hello@goodmeasuregiving.org
                </a>
                .
              </P>
            </Section>
          </>
        );
      }}
    </GmgContentFrame>
  );
};

export default PrivacyPage;

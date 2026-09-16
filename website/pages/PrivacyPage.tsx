// Good Measure Giving — "Modern" motif Privacy Policy page (/privacy).
// Motif-only (no legacy variant): renders its own GmgNav + footer via the content kit.

import React from 'react';
import { AnalyticsConsent } from '../src/components/AnalyticsConsent';
import {
  GmgContentFrame,
  ContentHero,
  Section,
  P,
  UL,
  type ContentCtx,
} from '../src/components/gmg/content';

export const PrivacyPage: React.FC<{ isDark: boolean }> = ({ isDark }) => {

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
              lead="Last updated: September 16, 2026. This page explains what we collect, why we use it, and the choices you have."
            />

            <AnalyticsConsent preferences />

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
                    <strong style={{ color: p.fg, fontWeight: 600 }}>Giving Tools:</strong> Profile details, saved charities,
                    giving plans, donation records, and shared-plan memberships that you choose to save. Information in a shared plan is available to its members.
                  </>,
                  <>
                    <strong style={{ color: p.fg, fontWeight: 600 }}>Feedback &amp; Suggestions:</strong> Any information
                    you voluntarily provide when suggesting a charity or sending feedback.
                  </>,
                  <>
                    <strong style={{ color: p.fg, fontWeight: 600 }}>Optional Analytics:</strong> With your permission,
                    page views, feature interactions, donation-link clicks, and browser/device information. Google Analytics uses cookies and pseudonymous browser and session identifiers; this is not the same as fully anonymous data.
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
                  'Understanding site use and performance when you accept optional analytics.',
                ]}
              />
            </Section>

            <Section ctx={ctx} title="4. Cookies and Local Storage">
              <P p={p}>
                Cookies and browser storage support sign-in, your saved preferences, and site features. We also store
                your analytics choice in this browser. Google Analytics and the Cloudflare analytics script remain off
                until you choose “Accept analytics.” Declining does not prevent you from using the site.
              </P>
              <P p={p}>You can change your choice using the controls at the top of this page, accessible through “Privacy &amp; analytics preferences” in the footer. Declining after accepting stops future analytics collection, removes Google Analytics cookies we can access, and reloads the page to unload the analytics scripts. It does not automatically erase data already received by our providers. If your browser blocks storage, your choice may last only for the current page session.</P>
            </Section>

            <Section ctx={ctx} title="5. Third-Party Services">
              <P p={p}>
                We do not sell your personal data. Google Firebase Authentication handles sign-in, and Cloud Firestore
                stores account-related data, saved giving records, shared plans, and submitted feedback. Cloudflare
                hosts and delivers the site and may process request information, including IP addresses, for delivery,
                security, and operational logs regardless of your optional analytics choice.
              </P>
              <P p={p}>When you accept analytics, Google Analytics measures visits and feature use, and Cloudflare Web Analytics measures traffic and performance. We disable Google signals and advertising-personalization signals in our site configuration. The site also requests fonts from Google Fonts. These providers may process information outside your country.</P>
              <P p={p}>See <a href="https://policies.google.com/privacy" style={{ color: p.accent }}>Google’s privacy policy</a> and <a href="https://www.cloudflare.com/privacypolicy/" style={{ color: p.accent }}>Cloudflare’s privacy policy</a> for their practices. Donation links open the charity’s or payment provider’s website; their privacy policies apply there. We do not process donation payments.</P>
            </Section>

            <Section ctx={ctx} title="6. Storage and deletion">
              <P p={p}>Browser preferences remain until you change them or clear the relevant storage. Saved account information and giving records remain available to support your account and plans. Provider logs, backups, and analytics data follow the retention settings of those services. Contact us to request deletion or ask about the data associated with your account. We may need to retain limited information for security or legal obligations.</P>
            </Section>
            <Section ctx={ctx} title="7. Your Choices and Contact">
              <P p={p}>
                You can request access, correction, or deletion of your personal account data. Your legal rights depend on where you live.
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

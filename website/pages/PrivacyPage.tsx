import React from 'react';
import { useLandingTheme } from '../contexts/LandingThemeContext';

export const PrivacyPage: React.FC = () => {
  const { isDark } = useLandingTheme();

  React.useEffect(() => {
    document.title = 'Privacy Policy | Good Measure Giving';
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
      {/* Hero */}
      <div className={`border-b ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <h1 className={`text-4xl font-bold font-merriweather mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>
            Privacy Policy
          </h1>
          <p className={`text-lg ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            Last updated: June 8, 2026. We respect your privacy and are committed to protecting your personal data.
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className={`prose max-w-none ${isDark ? 'prose-invert text-slate-300' : 'text-slate-700'} space-y-8`}>
          <section>
            <h2 className={`text-2xl font-bold font-merriweather mb-4 ${isDark ? 'text-white' : 'text-slate-900'}`}>
              1. Overview
            </h2>
            <p className="leading-relaxed">
              Good Measure Giving operates as an evidence-based charity evaluator. This Privacy Policy describes how we collect, use, and process your personal data when you visit our website, use our tools (such as the Zakat Calculator), register an account, or submit feedback and suggestions.
            </p>
          </section>

          <section>
            <h2 className={`text-2xl font-bold font-merriweather mb-4 ${isDark ? 'text-white' : 'text-slate-900'}`}>
              2. Information We Collect
            </h2>
            <p className="leading-relaxed mb-4">
              We collect information to provide a better experience to our users. This includes:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li><strong>Account Credentials:</strong> If you sign up or log in, we collect your email address and profile identifiers using our secure authentication provider (Firebase Auth).</li>
              <li><strong>User Interactions:</strong> Saved bookmarks, tour completion statuses, or comparison sets stored to customize your dashboard.</li>
              <li><strong>Feedback & Suggestions:</strong> Any information you voluntarily provide when suggesting a charity or sending feedback.</li>
              <li><strong>Usage Data:</strong> Anonymized analytical data showing how visitors navigate and interact with the site, using privacy-respecting aggregate tools.</li>
            </ul>
          </section>

          <section>
            <h2 className={`text-2xl font-bold font-merriweather mb-4 ${isDark ? 'text-white' : 'text-slate-900'}`}>
              3. How We Use Your Data
            </h2>
            <p className="leading-relaxed mb-4">
              We only use your data for legitimate, specific purposes, including:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Providing, maintaining, and improving our charity evaluation services.</li>
              <li>Securing and authenticating user accounts.</li>
              <li>Allowing you to save bookmarks and personalize your experience.</li>
              <li>Aggregating anonymous metrics to measure website performance.</li>
            </ul>
          </section>

          <section>
            <h2 className={`text-2xl font-bold font-merriweather mb-4 ${isDark ? 'text-white' : 'text-slate-900'}`}>
              4. Cookies and Local Storage
            </h2>
            <p className="leading-relaxed">
              We use standard browser local storage and cookies to store session states, active UI themes (light vs. dark), and bookmarks. You can control cookie preferences in your browser settings.
            </p>
          </section>

          <section>
            <h2 className={`text-2xl font-bold font-merriweather mb-4 ${isDark ? 'text-white' : 'text-slate-900'}`}>
              5. Third-Party Services
            </h2>
            <p className="leading-relaxed">
              We do not sell your personal data. We only share data with essential infrastructure providers, specifically:
              <strong> Firebase Authentication</strong> for user logins. All data sharing is secured and encrypted.
            </p>
          </section>

          <section>
            <h2 className={`text-2xl font-bold font-merriweather mb-4 ${isDark ? 'text-white' : 'text-slate-900'}`}>
              6. Your Rights
            </h2>
            <p className="leading-relaxed">
              You have the right to access, rectify, or request the deletion of your personal account data at any time. To make a request or ask questions about our data practices, please contact us at <a href="mailto:hello@goodmeasuregiving.org" className="text-emerald-600 hover:text-emerald-500 underline">hello@goodmeasuregiving.org</a>.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
};

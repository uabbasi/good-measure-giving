/**
 * BetaBanner: Dismissible early-access banner below navbar
 *
 * Persists dismissal in localStorage. Links to FeedbackButton modal.
 */

import React, { useState } from 'react';
import { useLandingTheme } from '../../contexts/LandingThemeContext';
import { FeedbackButton } from './FeedbackButton';

export const BetaBanner: React.FC = () => {
  const { isDark } = useLandingTheme();
  const [showFeedback, setShowFeedback] = useState(false);

  const handleFeedbackClick = () => {
    if (typeof window !== 'undefined' && window.gtag) {
      window.gtag('event', 'beta_banner_feedback_click');
    }
    setShowFeedback(true);
  };

  return (
    <>
      <div className={`text-center px-4 py-2 text-sm ${
        isDark
          ? 'bg-amber-900/30 border-b border-amber-800/40 text-amber-200'
          : 'bg-amber-50 border-b border-amber-200 text-amber-800'
      }`}>
        <span className={`font-semibold ${isDark ? 'text-amber-300' : 'text-amber-900'}`}>Early Access</span>
        {' \u2014 '}
        <span className="hidden sm:inline">We{'\u2019'}re actively improving our evaluations. Found something off? Help us get it right.{' '}</span>
        <span className="sm:hidden">Found something off?{' '}</span>
        <button
          onClick={handleFeedbackClick}
          className={`font-semibold underline underline-offset-2 transition-colors ${
            isDark ? 'text-amber-300 hover:text-amber-200' : 'text-amber-900 hover:text-amber-700'
          }`}
        >
          Share Feedback
        </button>
      </div>

      {/* FeedbackButton modal triggered from banner */}
      {showFeedback && (
        <FeedbackButton
          defaultOpen
          initialFeedbackType="general_feedback"
          onClose={() => setShowFeedback(false)}
        />
      )}
    </>
  );
};

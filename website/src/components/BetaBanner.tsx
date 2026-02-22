/**
 * BetaBanner: Dismissible early-access banner below navbar
 *
 * Persists dismissal in localStorage. Links to FeedbackButton modal.
 */

import React, { useState } from 'react';
import { X } from 'lucide-react';
import { useLandingTheme } from '../../contexts/LandingThemeContext';
import { FeedbackButton } from './FeedbackButton';

const DISMISS_KEY = 'beta-banner-dismissed';

export const BetaBanner: React.FC = () => {
  const { isDark } = useLandingTheme();
  const [showFeedback, setShowFeedback] = useState(false);
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem(DISMISS_KEY) === '1';
  });

  if (dismissed) return null;

  const handleFeedbackClick = () => {
    if (typeof window !== 'undefined' && window.gtag) {
      window.gtag('event', 'beta_banner_feedback_click');
    }
    setShowFeedback(true);
  };

  const handleDismiss = () => {
    localStorage.setItem(DISMISS_KEY, '1');
    setDismissed(true);
    if (typeof window !== 'undefined' && window.gtag) {
      window.gtag('event', 'beta_banner_dismiss');
    }
  };

  return (
    <>
      <div className={`relative text-center px-8 py-2 text-sm ${
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
        <button
          onClick={handleDismiss}
          aria-label="Dismiss banner"
          className={`absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-full transition-colors ${
            isDark ? 'text-amber-400 hover:text-amber-200 hover:bg-amber-800/40' : 'text-amber-600 hover:text-amber-900 hover:bg-amber-200/60'
          }`}
        >
          <X className="w-4 h-4" />
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

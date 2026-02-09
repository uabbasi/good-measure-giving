/**
 * FeedbackButton: Floating feedback widget for site-wide and charity-specific feedback
 *
 * - Floats in bottom-right corner on all pages
 * - Detects if on a charity page and pre-fills charity info
 * - Stores feedback in Supabase reported_issues table
 */

import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, X, Send, CheckCircle } from 'lucide-react';
import { useAuth } from '../auth/useAuth';
import { useSupabase } from '../auth/SupabaseProvider';
import { useLandingTheme } from '../../contexts/LandingThemeContext';

type FeedbackType = 'data_error' | 'outdated_info' | 'missing_info' | 'general_feedback' | 'feature_request' | 'other';

const FEEDBACK_TYPES: { value: FeedbackType; label: string; description: string; charityOnly?: boolean }[] = [
  { value: 'general_feedback', label: 'General Feedback', description: 'Comments about the site' },
  { value: 'feature_request', label: 'Feature Request', description: 'Suggest an improvement' },
  { value: 'data_error', label: 'Data Error', description: 'Incorrect information displayed', charityOnly: true },
  { value: 'outdated_info', label: 'Outdated Info', description: 'Information needs updating', charityOnly: true },
  { value: 'missing_info', label: 'Missing Info', description: 'Important information not shown', charityOnly: true },
  { value: 'other', label: 'Other', description: 'Something else' },
];

interface CharityContext {
  id: string;
  name: string;
}

interface FeedbackButtonProps {
  /** If true, renders as an inline text link instead of a floating button */
  inline?: boolean;
}

export const FeedbackButton: React.FC<FeedbackButtonProps> = ({ inline = false }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [feedbackType, setFeedbackType] = useState<FeedbackType | ''>('');
  const [description, setDescription] = useState('');
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [charityContext, setCharityContext] = useState<CharityContext | null>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const { user } = useAuth();
  const { supabase } = useSupabase();
  const { isDark } = useLandingTheme();

  // Detect if we're on a charity page
  useEffect(() => {
    const detectCharityPage = () => {
      const path = window.location.pathname;
      const match = path.match(/\/charity\/([^/]+)/);
      if (match) {
        const charityId = match[1];
        // Try to get charity name from the page title or DOM
        const titleEl = document.querySelector('h1');
        const charityName = titleEl?.textContent || 'Unknown Charity';
        setCharityContext({ id: charityId, name: charityName });
      } else {
        setCharityContext(null);
      }
    };

    detectCharityPage();
    // Re-detect on navigation
    window.addEventListener('popstate', detectCharityPage);
    return () => window.removeEventListener('popstate', detectCharityPage);
  }, [isOpen]);

  // Pre-fill email if user is logged in
  useEffect(() => {
    if (user?.email && !email) {
      setEmail(user.email);
    }
  }, [user, email]);

  // Close on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen]);

  // Close on outside click
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
      setIsOpen(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!feedbackType || !description.trim()) {
      setError('Please select a feedback type and provide a description');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      if (supabase) {
        const { error: insertError } = await supabase
          .from('reported_issues')
          .insert({
            charity_id: charityContext?.id || 'general',
            charity_name: charityContext?.name || 'General Feedback',
            issue_type: feedbackType,
            description: description.trim(),
            reporter_email: email?.trim() || null,
            reporter_user_id: user?.id || null,
          });

        if (insertError) {
          console.error('Failed to submit feedback:', insertError);
          throw insertError;
        }
      } else {
        console.log('Feedback submitted (Supabase not configured):', {
          charityContext,
          feedbackType,
          description,
          email,
        });
      }

      // Track the event
      if (typeof window !== 'undefined' && window.gtag) {
        window.gtag('event', 'feedback_submit', {
          feedback_type: feedbackType,
          has_charity_context: !!charityContext,
        });
      }

      setIsSubmitted(true);
      setTimeout(() => {
        setIsOpen(false);
        setTimeout(() => {
          setIsSubmitted(false);
          setFeedbackType('');
          setDescription('');
          setError(null);
        }, 300);
      }, 2000);
    } catch (err) {
      setError('Failed to submit feedback. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Filter feedback types based on context
  const availableTypes = FEEDBACK_TYPES.filter(
    type => !type.charityOnly || charityContext
  );

  return (
    <>
      {/* Trigger */}
      {inline ? (
        <button
          onClick={() => setIsOpen(true)}
          className={`hover:text-emerald-600 transition-colors ${isDark ? 'text-slate-400' : 'text-slate-500'}`}
        >
          Feedback
        </button>
      ) : (
        <button
          onClick={() => setIsOpen(true)}
          className={`fixed bottom-6 left-6 z-50 flex items-center gap-2 px-4 py-3 rounded-full shadow-lg transition-all hover:scale-105 ${
            isDark
              ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
              : 'bg-emerald-600 hover:bg-emerald-700 text-white'
          }`}
          aria-label="Send feedback"
        >
          <MessageSquare className="w-5 h-5" />
          <span className="text-sm font-medium">Feedback</span>
        </button>
      )}

      {/* Modal */}
      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          onClick={handleBackdropClick}
        >
          <div
            ref={modalRef}
            className={`w-full max-w-md rounded-xl shadow-xl ${
              isDark ? 'bg-slate-800' : 'bg-white'
            }`}
          >
            {/* Header */}
            <div className={`flex items-center justify-between p-4 border-b ${
              isDark ? 'border-slate-700' : 'border-slate-200'
            }`}>
              <div>
                <h2 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  Send Feedback
                </h2>
                {charityContext && (
                  <p className={`text-xs mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    About: {charityContext.name}
                  </p>
                )}
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className={`p-1 rounded-lg transition-colors ${
                  isDark ? 'hover:bg-slate-700 text-slate-400' : 'hover:bg-slate-100 text-slate-500'
                }`}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="p-4">
              {isSubmitted ? (
                <div className="text-center py-8">
                  <CheckCircle className={`w-12 h-12 mx-auto mb-3 ${
                    isDark ? 'text-emerald-400' : 'text-emerald-500'
                  }`} />
                  <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    Thank you for your feedback!
                  </p>
                  <p className={`text-sm mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    We appreciate you taking the time to help us improve.
                  </p>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-4">
                  {/* Feedback Type */}
                  <div>
                    <label className={`block text-sm font-medium mb-2 ${
                      isDark ? 'text-slate-300' : 'text-slate-700'
                    }`}>
                      What's this about?
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      {availableTypes.map((type) => (
                        <button
                          key={type.value}
                          type="button"
                          onClick={() => setFeedbackType(type.value)}
                          className={`p-3 rounded-lg text-left transition-all ${
                            feedbackType === type.value
                              ? isDark
                                ? 'bg-emerald-900/50 border-emerald-500 border-2'
                                : 'bg-emerald-50 border-emerald-500 border-2'
                              : isDark
                                ? 'bg-slate-700 border-slate-600 border hover:border-slate-500'
                                : 'bg-slate-50 border-slate-200 border hover:border-slate-300'
                          }`}
                        >
                          <div className={`text-sm font-medium ${
                            feedbackType === type.value
                              ? isDark ? 'text-emerald-400' : 'text-emerald-700'
                              : isDark ? 'text-white' : 'text-slate-900'
                          }`}>
                            {type.label}
                          </div>
                          <div className={`text-xs mt-0.5 ${
                            isDark ? 'text-slate-400' : 'text-slate-500'
                          }`}>
                            {type.description}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Description */}
                  <div>
                    <label className={`block text-sm font-medium mb-2 ${
                      isDark ? 'text-slate-300' : 'text-slate-700'
                    }`}>
                      Tell us more
                    </label>
                    <textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Please describe in detail..."
                      rows={4}
                      className={`w-full px-3 py-2 rounded-lg border text-sm transition-colors ${
                        isDark
                          ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-400 focus:border-emerald-500'
                          : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-emerald-500'
                      } focus:outline-none focus:ring-1 focus:ring-emerald-500`}
                    />
                  </div>

                  {/* Email (optional) */}
                  <div>
                    <label className={`block text-sm font-medium mb-2 ${
                      isDark ? 'text-slate-300' : 'text-slate-700'
                    }`}>
                      Email <span className={isDark ? 'text-slate-500' : 'text-slate-400'}>(optional)</span>
                    </label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="For follow-up if needed"
                      className={`w-full px-3 py-2 rounded-lg border text-sm transition-colors ${
                        isDark
                          ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-400 focus:border-emerald-500'
                          : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-emerald-500'
                      } focus:outline-none focus:ring-1 focus:ring-emerald-500`}
                    />
                  </div>

                  {/* Error */}
                  {error && (
                    <p className="text-sm text-red-500">{error}</p>
                  )}

                  {/* Submit */}
                  <button
                    type="submit"
                    disabled={isSubmitting || !feedbackType || !description.trim()}
                    className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-colors ${
                      isSubmitting || !feedbackType || !description.trim()
                        ? isDark
                          ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                          : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                        : isDark
                          ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                          : 'bg-emerald-600 hover:bg-emerald-700 text-white'
                    }`}
                  >
                    {isSubmitting ? (
                      <>
                        <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                        Sending...
                      </>
                    ) : (
                      <>
                        <Send className="w-4 h-4" />
                        Send Feedback
                      </>
                    )}
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default FeedbackButton;

/**
 * FeedbackButton: Floating feedback widget for site-wide and charity-specific feedback
 *
 * - Floats in bottom-right corner on all pages
 * - Detects if on a charity page and pre-fills charity info
 * - Stores feedback in Firestore reported_issues collection
 * - Supports suggest_charity type for charity suggestions
 */

import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, X, Send, CheckCircle } from 'lucide-react';
import { useAuth } from '../auth/useAuth';
import { useFirebaseData } from '../auth/FirebaseProvider';
import { collection, addDoc, Timestamp } from 'firebase/firestore';
import { useLandingTheme } from '../../contexts/LandingThemeContext';

const SUBMISSION_COUNT_KEY = 'gmg-submission-count';
const SUBMISSION_CAP = 5;

type FeedbackType = 'data_error' | 'outdated_info' | 'missing_info' | 'general_feedback' | 'feature_request' | 'suggest_charity' | 'other';

const FEEDBACK_TYPES: { value: FeedbackType; label: string; description: string; charityOnly?: boolean }[] = [
  { value: 'general_feedback', label: 'General Feedback', description: 'Comments about the site' },
  { value: 'feature_request', label: 'Feature Request', description: 'Suggest an improvement' },
  { value: 'suggest_charity', label: 'Suggest a Charity', description: 'Request a new evaluation' },
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
  /** Pre-select a feedback type when opening */
  initialFeedbackType?: FeedbackType;
  /** If true, open the modal immediately on mount (no trigger button rendered) */
  defaultOpen?: boolean;
  /** Called when the modal closes (useful with defaultOpen) */
  onClose?: () => void;
}

function getSessionSubmissionCount(): number {
  if (typeof window === 'undefined') return 0;
  return parseInt(sessionStorage.getItem(SUBMISSION_COUNT_KEY) || '0', 10);
}

function incrementSessionSubmissionCount(): void {
  if (typeof window === 'undefined') return;
  const current = getSessionSubmissionCount();
  sessionStorage.setItem(SUBMISSION_COUNT_KEY, (current + 1).toString());
}

export const FeedbackButton: React.FC<FeedbackButtonProps> = ({ inline = false, initialFeedbackType, defaultOpen = false, onClose }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [feedbackType, setFeedbackType] = useState<FeedbackType | ''>('');
  const [description, setDescription] = useState('');
  const [email, setEmail] = useState('');
  // Suggest charity fields
  const [organizationName, setOrganizationName] = useState('');
  const [organizationEin, setOrganizationEin] = useState('');
  const [organizationWebsite, setOrganizationWebsite] = useState('');
  const [submitterRole, setSubmitterRole] = useState<'donor' | 'org_representative' | 'other'>('donor');
  // Honeypot anti-spam: silent discard if filled. Shows success UI but writes nothing.
  const [honeypot, setHoneypot] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSubmitTime, setLastSubmitTime] = useState(0);
  const [charityContext, setCharityContext] = useState<CharityContext | null>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const { email: userEmail, uid } = useAuth();
  const { db } = useFirebaseData();
  const { isDark } = useLandingTheme();

  const closeModal = () => {
    setIsOpen(false);
    onClose?.();
  };

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
    if (userEmail && !email) {
      setEmail(userEmail);
    }
  }, [userEmail, email]);

  // Apply initialFeedbackType when modal opens
  useEffect(() => {
    if (isOpen && initialFeedbackType) {
      setFeedbackType(initialFeedbackType);
    }
  }, [isOpen, initialFeedbackType]);

  // Close on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        closeModal();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen]);

  // Close on outside click
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
      closeModal();
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Cooldown: prevent rapid re-submission
    const now = Date.now();
    if (now - lastSubmitTime < 3000) {
      setError('Please wait a moment before submitting again.');
      return;
    }

    // Session cap check
    if (getSessionSubmissionCount() >= SUBMISSION_CAP) {
      setError('Thank you for your feedback \u2014 you\u2019ve been very active! Please email us at hello@goodmeasuregiving.org for additional submissions.');
      return;
    }

    if (!feedbackType) {
      setError('Please select a feedback type');
      return;
    }

    const isSuggest = feedbackType === 'suggest_charity';

    if (isSuggest) {
      if (!organizationName.trim()) {
        setError('Please provide the organization name');
        return;
      }
      if (organizationWebsite.trim() && !/^https?:\/\//.test(organizationWebsite.trim())) {
        setError('Website must start with http:// or https://');
        return;
      }
    } else if (!description.trim()) {
      setError('Please provide a description');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setLastSubmitTime(now);

    try {
      // Honeypot check: if filled, show success but skip writes
      if (honeypot) {
        console.debug('Submission filtered');
      } else {
        const payload: Record<string, unknown> = {
          charityId: isSuggest ? 'general' : (charityContext?.id || 'general'),
          charityName: isSuggest ? 'Suggestion' : (charityContext?.name || 'General Feedback'),
          issueType: feedbackType,
          description: isSuggest
            ? `Suggest: ${organizationName.trim().slice(0, 200)}`
            : description.trim().slice(0, 3000),
          reporterEmail: email?.trim() || null,
          reporterUserId: uid || null,
          createdAt: Timestamp.now(),
        };

        if (isSuggest) {
          payload.organizationName = organizationName.trim().slice(0, 200);
          payload.organizationEin = organizationEin.trim() || null;
          payload.organizationWebsite = organizationWebsite.trim() || null;
          payload.submitterRole = submitterRole;
        }

        if (db) {
          await addDoc(collection(db, 'reported_issues'), payload);
        } else {
          console.log('Feedback submitted (Firebase not configured):', payload);
        }

        // Track the event
        if (typeof window !== 'undefined' && window.gtag) {
          if (isSuggest) {
            window.gtag('event', 'suggest_charity_submit', {
              submitter_role: submitterRole,
            });
          } else {
            window.gtag('event', 'feedback_submit', {
              feedback_type: feedbackType,
              has_charity_context: !!charityContext,
            });
          }
        }

        incrementSessionSubmissionCount();
      }

      setIsSubmitted(true);
      setTimeout(() => {
        closeModal();
        setTimeout(() => {
          setIsSubmitted(false);
          setFeedbackType('');
          setDescription('');
          setOrganizationName('');
          setOrganizationEin('');
          setOrganizationWebsite('');
          setSubmitterRole('donor');
          setHoneypot('');
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

  const isSuggest = feedbackType === 'suggest_charity';

  const inputClasses = `w-full px-3 py-2 rounded-lg border text-sm transition-colors ${
    isDark
      ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-400 focus:border-emerald-500'
      : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-emerald-500'
  } focus:outline-none focus:ring-1 focus:ring-emerald-500`;

  const successMessage = isSuggest
    ? 'Thank you! We prioritize 501(c)(3) organizations serving Muslim communities.'
    : 'We appreciate you taking the time to help us improve.';

  return (
    <>
      {/* Trigger (hidden when defaultOpen - modal only) */}
      {!defaultOpen && (inline ? (
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
      ))}

      {/* Modal */}
      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          onClick={handleBackdropClick}
        >
          <div
            ref={modalRef}
            className={`w-full max-w-md rounded-xl shadow-xl max-h-[90vh] overflow-y-auto ${
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
                {charityContext && !isSuggest && (
                  <p className={`text-xs mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    About: {charityContext.name}
                  </p>
                )}
              </div>
              <button
                onClick={closeModal}
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
                    {successMessage}
                  </p>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-4">
                  {/* Honeypot anti-spam: silent discard if filled. Shows success UI but writes nothing. */}
                  <input
                    type="text"
                    name="website_url_confirm"
                    value={honeypot}
                    onChange={e => setHoneypot(e.target.value)}
                    tabIndex={-1}
                    autoComplete="off"
                    style={{ position: 'absolute', left: '-9999px' }}
                    aria-hidden="true"
                  />

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

                  {/* Suggest Charity fields */}
                  {isSuggest && (
                    <>
                      <div>
                        <label className={`block text-sm font-medium mb-2 ${
                          isDark ? 'text-slate-300' : 'text-slate-700'
                        }`}>
                          Organization name *
                        </label>
                        <input
                          type="text"
                          value={organizationName}
                          onChange={e => setOrganizationName(e.target.value.slice(0, 200))}
                          placeholder="e.g. Islamic Relief USA"
                          maxLength={200}
                          className={inputClasses}
                        />
                      </div>
                      <div>
                        <label className={`block text-sm font-medium mb-2 ${
                          isDark ? 'text-slate-300' : 'text-slate-700'
                        }`}>
                          EIN <span className={isDark ? 'text-slate-500' : 'text-slate-400'}>(optional)</span>
                        </label>
                        <input
                          type="text"
                          value={organizationEin}
                          onChange={e => setOrganizationEin(e.target.value)}
                          placeholder="e.g. 12-3456789"
                          className={inputClasses}
                        />
                        <p className={`text-xs mt-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                          Federal tax ID (found on IRS Form 990)
                        </p>
                      </div>
                      <div>
                        <label className={`block text-sm font-medium mb-2 ${
                          isDark ? 'text-slate-300' : 'text-slate-700'
                        }`}>
                          Website <span className={isDark ? 'text-slate-500' : 'text-slate-400'}>(optional)</span>
                        </label>
                        <input
                          type="url"
                          value={organizationWebsite}
                          onChange={e => setOrganizationWebsite(e.target.value)}
                          placeholder="https://..."
                          className={inputClasses}
                        />
                      </div>
                      <div>
                        <label className={`block text-sm font-medium mb-2 ${
                          isDark ? 'text-slate-300' : 'text-slate-700'
                        }`}>
                          Your role
                        </label>
                        <div className="flex flex-wrap gap-2">
                          {([
                            { value: 'donor', label: "I'm a donor" },
                            { value: 'org_representative', label: 'I represent this organization' },
                            { value: 'other', label: 'Other' },
                          ] as const).map(option => (
                            <button
                              key={option.value}
                              type="button"
                              onClick={() => setSubmitterRole(option.value)}
                              className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                                submitterRole === option.value
                                  ? isDark
                                    ? 'bg-emerald-900/50 border-emerald-500 border text-emerald-400'
                                    : 'bg-emerald-50 border-emerald-500 border text-emerald-700'
                                  : isDark
                                    ? 'bg-slate-700 border-slate-600 border text-slate-300 hover:border-slate-500'
                                    : 'bg-slate-50 border-slate-200 border text-slate-600 hover:border-slate-300'
                              }`}
                            >
                              {option.label}
                            </button>
                          ))}
                        </div>
                      </div>
                    </>
                  )}

                  {/* Description (not shown for suggest_charity) */}
                  {!isSuggest && (
                    <div>
                      <label className={`block text-sm font-medium mb-2 ${
                        isDark ? 'text-slate-300' : 'text-slate-700'
                      }`}>
                        Tell us more
                      </label>
                      <textarea
                        value={description}
                        onChange={(e) => setDescription(e.target.value.slice(0, 3000))}
                        placeholder="Please describe in detail..."
                        rows={4}
                        maxLength={3000}
                        className={inputClasses}
                      />
                    </div>
                  )}

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
                      className={inputClasses}
                    />
                  </div>

                  {/* Error */}
                  {error && (
                    <p className="text-sm text-red-500">{error}</p>
                  )}

                  {/* Submit */}
                  <button
                    type="submit"
                    disabled={isSubmitting || !feedbackType || (!isSuggest && !description.trim()) || (isSuggest && !organizationName.trim())}
                    className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-colors ${
                      isSubmitting || !feedbackType || (!isSuggest && !description.trim()) || (isSuggest && !organizationName.trim())
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
                        {isSuggest ? 'Submit Suggestion' : 'Send Feedback'}
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

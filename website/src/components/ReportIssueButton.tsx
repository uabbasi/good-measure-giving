/**
 * ReportIssueButton: Report data issues for a specific charity
 *
 * Opens a modal with structured form for reporting:
 * - Data errors
 * - Outdated information
 * - Missing information
 * - Organization feedback (I represent this charity)
 * - Other issues
 */

import React, { useState, useRef, useEffect } from 'react';
import { Flag, X, Send, CheckCircle } from 'lucide-react';
import { useAuth } from '../auth/useAuth';
import { useFirebaseData } from '../auth/FirebaseProvider';
import { collection, addDoc, Timestamp } from 'firebase/firestore';

const SUBMISSION_COUNT_KEY = 'gmg-submission-count';
const SUBMISSION_CAP = 5;

interface ReportIssueButtonProps {
  charityId: string;
  charityName: string;
  /** Visual variant: icon (default with icon) or text (inline link, no icon) */
  variant?: 'icon' | 'text';
  /** Additional CSS classes */
  className?: string;
  /** Dark mode */
  isDark?: boolean;
  /** Pre-select an issue type when opening */
  initialIssueType?: IssueType;
  /** If true, open the modal immediately on mount (no trigger button rendered) */
  defaultOpen?: boolean;
  /** Called when the modal closes (useful with defaultOpen) */
  onClose?: () => void;
}

type IssueType = 'data_error' | 'outdated_info' | 'missing_info' | 'organization_feedback' | 'other';

const ISSUE_TYPES: { value: IssueType; label: string; description: string }[] = [
  { value: 'data_error', label: 'Data Error', description: 'Incorrect information displayed' },
  { value: 'outdated_info', label: 'Outdated Info', description: 'Information needs updating' },
  { value: 'missing_info', label: 'Missing Info', description: 'Important information not shown' },
  { value: 'organization_feedback', label: 'Org Feedback', description: 'I represent this charity' },
  { value: 'other', label: 'Other', description: 'Something else' },
];

function getSessionSubmissionCount(): number {
  if (typeof window === 'undefined') return 0;
  return parseInt(sessionStorage.getItem(SUBMISSION_COUNT_KEY) || '0', 10);
}

function incrementSessionSubmissionCount(): void {
  if (typeof window === 'undefined') return;
  const current = getSessionSubmissionCount();
  sessionStorage.setItem(SUBMISSION_COUNT_KEY, (current + 1).toString());
}

export const ReportIssueButton: React.FC<ReportIssueButtonProps> = ({
  charityId,
  charityName,
  variant = 'icon',
  className = '',
  isDark = false,
  initialIssueType,
  defaultOpen = false,
  onClose,
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [issueType, setIssueType] = useState<IssueType | ''>('');
  const [description, setDescription] = useState('');
  const [email, setEmail] = useState('');
  const [orgRole, setOrgRole] = useState('');
  const [evidenceUrl, setEvidenceUrl] = useState('');
  // Honeypot anti-spam: silent discard if filled. Shows success UI but writes nothing.
  const [honeypot, setHoneypot] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSubmitTime, setLastSubmitTime] = useState(0);
  const modalRef = useRef<HTMLDivElement>(null);
  const { email: userEmail, uid } = useAuth();
  const { db } = useFirebaseData();

  const closeModal = () => {
    setIsOpen(false);
    onClose?.();
  };

  // Pre-fill email if user is logged in
  useEffect(() => {
    if (userEmail && !email) {
      setEmail(userEmail);
    }
  }, [userEmail, email]);

  // Apply initialIssueType when modal opens
  useEffect(() => {
    if (isOpen && initialIssueType) {
      setIssueType(initialIssueType);
    }
  }, [isOpen, initialIssueType]);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeModal();
    };
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
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

    if (!issueType || !description.trim()) {
      setError('Please select an issue type and provide a description');
      return;
    }

    // Validate org feedback fields
    if (issueType === 'organization_feedback') {
      if (evidenceUrl.trim() && !/^https?:\/\//.test(evidenceUrl.trim())) {
        setError('Supporting link must start with http:// or https://');
        return;
      }
    }

    setIsSubmitting(true);
    setError(null);
    setLastSubmitTime(now);

    try {
      // Honeypot check: if filled, show success but skip writes
      if (honeypot) {
        console.debug('Submission filtered');
      } else {
        // Build Firestore payload
        const payload: Record<string, unknown> = {
          charityId,
          charityName,
          issueType,
          description: description.trim().slice(0, 3000),
          reporterEmail: email?.trim() || null,
          reporterUserId: uid || null,
          createdAt: Timestamp.now(),
        };

        // Add org feedback fields
        if (issueType === 'organization_feedback') {
          payload.submitterRole = 'org_representative';
          payload.orgRole = orgRole.trim().slice(0, 120) || null;
          payload.evidenceUrl = evidenceUrl.trim() || null;
        }

        if (db) {
          await addDoc(collection(db, 'reported_issues'), payload);
        } else {
          console.log('Report submitted (Firebase not configured):', payload);
        }

        // Track the report event
        if (typeof window !== 'undefined' && window.gtag) {
          if (issueType === 'organization_feedback') {
            window.gtag('event', 'organization_feedback_submit', {
              charity_id: charityId,
            });
          } else {
            window.gtag('event', 'report_issue', {
              charity_id: charityId,
              issue_type: issueType,
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
          setIssueType('');
          setDescription('');
          setOrgRole('');
          setEvidenceUrl('');
          setHoneypot('');
          setError(null);
        }, 300);
      }, 2000);
    } catch (err) {
      setError('Failed to submit report. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isOrgFeedback = issueType === 'organization_feedback';

  const buttonClasses = variant === 'text'
    ? `hover:underline ${isDark ? 'hover:text-slate-300' : 'hover:text-slate-600'}`
    : `inline-flex items-center gap-1.5 text-sm ${
        isDark ? 'text-slate-500 hover:text-slate-400' : 'text-slate-400 hover:text-slate-600'
      }`;

  const inputClasses = `w-full px-3 py-2 rounded-lg text-sm border transition-colors ${
    isDark
      ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-500 focus:border-emerald-500'
      : 'bg-white border-slate-200 text-slate-900 placeholder-slate-400 focus:border-emerald-500'
  } focus:outline-none focus:ring-1 focus:ring-emerald-500`;

  return (
    <>
      {/* Trigger (hidden when defaultOpen - modal only) */}
      {!defaultOpen && (
      <button
        onClick={() => setIsOpen(true)}
        className={`${buttonClasses} ${className}`}
        aria-label="Report an issue with this charity's data"
      >
        {variant === 'text' ? (
          <span className="inline-flex items-center gap-1">
            <Flag className="w-3 h-3" />
            Report Issue
          </span>
        ) : (
          <>
            <Flag className="w-4 h-4" />
            <span className="hidden sm:inline">Report Issue</span>
          </>
        )}
      </button>
      )}

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
              <h2 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                Report an Issue
              </h2>
              <button
                onClick={closeModal}
                className={`p-1 rounded-lg transition-colors ${
                  isDark ? 'hover:bg-slate-700 text-slate-400' : 'hover:bg-slate-100 text-slate-500'
                }`}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Body */}
            <div className="p-4">
              {isSubmitted ? (
                <div className="text-center py-8">
                  <CheckCircle className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
                  <p className={`font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    Thank you for your report!
                  </p>
                  <p className={`text-sm mt-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    We'll review this and update the data if needed.
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

                  {/* Charity name (read-only) */}
                  <div>
                    <label className={`block text-xs uppercase tracking-wide font-medium mb-1 ${
                      isDark ? 'text-slate-400' : 'text-slate-500'
                    }`}>
                      Charity
                    </label>
                    <div className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                      {charityName}
                    </div>
                  </div>

                  {/* Issue type */}
                  <div>
                    <label className={`block text-xs uppercase tracking-wide font-medium mb-2 ${
                      isDark ? 'text-slate-400' : 'text-slate-500'
                    }`}>
                      Issue Type *
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      {ISSUE_TYPES.map(type => (
                        <button
                          key={type.value}
                          type="button"
                          onClick={() => setIssueType(type.value)}
                          className={`p-3 rounded-lg text-left transition-colors border ${
                            issueType === type.value
                              ? isDark
                                ? 'bg-emerald-900/30 border-emerald-600 text-emerald-400'
                                : 'bg-emerald-50 border-emerald-500 text-emerald-700'
                              : isDark
                                ? 'bg-slate-700 border-slate-600 hover:border-slate-500 text-slate-300'
                                : 'bg-white border-slate-200 hover:border-slate-300 text-slate-700'
                          }`}
                        >
                          <div className="text-sm font-medium">{type.label}</div>
                          <div className={`text-xs ${
                            issueType === type.value
                              ? isDark ? 'text-emerald-500' : 'text-emerald-600'
                              : isDark ? 'text-slate-500' : 'text-slate-400'
                          }`}>
                            {type.description}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Organization feedback: role field */}
                  {isOrgFeedback && (
                    <div>
                      <label className={`block text-xs uppercase tracking-wide font-medium mb-1 ${
                        isDark ? 'text-slate-400' : 'text-slate-500'
                      }`}>
                        Your role at the organization
                      </label>
                      <input
                        type="text"
                        value={orgRole}
                        onChange={e => setOrgRole(e.target.value.slice(0, 120))}
                        placeholder="e.g. Executive Director"
                        maxLength={120}
                        className={inputClasses}
                      />
                    </div>
                  )}

                  {/* Description */}
                  <div>
                    <label className={`block text-xs uppercase tracking-wide font-medium mb-1 ${
                      isDark ? 'text-slate-400' : 'text-slate-500'
                    }`}>
                      {isOrgFeedback ? 'What would you like us to know? *' : 'Description *'}
                    </label>
                    <textarea
                      value={description}
                      onChange={e => setDescription(e.target.value.slice(0, 3000))}
                      placeholder={isOrgFeedback ? 'Share corrections, context, or updated information...' : 'Please describe the issue...'}
                      rows={3}
                      maxLength={3000}
                      className={inputClasses}
                    />
                  </div>

                  {/* Organization feedback: evidence URL */}
                  {isOrgFeedback && (
                    <div>
                      <label className={`block text-xs uppercase tracking-wide font-medium mb-1 ${
                        isDark ? 'text-slate-400' : 'text-slate-500'
                      }`}>
                        Supporting links (optional)
                      </label>
                      <input
                        type="url"
                        value={evidenceUrl}
                        onChange={e => setEvidenceUrl(e.target.value)}
                        placeholder="https://..."
                        className={inputClasses}
                      />
                    </div>
                  )}

                  {/* Organization feedback: process note */}
                  {isOrgFeedback && (
                    <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                      We review organization feedback and update evaluations when warranted.
                    </p>
                  )}

                  {/* Email (optional) */}
                  <div>
                    <label className={`block text-xs uppercase tracking-wide font-medium mb-1 ${
                      isDark ? 'text-slate-400' : 'text-slate-500'
                    }`}>
                      Email (optional)
                    </label>
                    <input
                      type="email"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      placeholder="your@email.com"
                      className={inputClasses}
                    />
                    <p className={`text-xs mt-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                      We'll only contact you if we need more information
                    </p>
                  </div>

                  {/* Error message */}
                  {error && (
                    <p className="text-sm text-red-500">{error}</p>
                  )}

                  {/* Submit button */}
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-colors ${
                      isSubmitting
                        ? 'bg-slate-400 cursor-not-allowed'
                        : 'bg-emerald-600 hover:bg-emerald-700'
                    } text-white`}
                  >
                    {isSubmitting ? (
                      <>Submitting...</>
                    ) : (
                      <>
                        <Send className="w-4 h-4" />
                        Submit Report
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

export default ReportIssueButton;

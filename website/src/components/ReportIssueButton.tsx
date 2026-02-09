/**
 * ReportIssueButton: Report data issues for a specific charity
 *
 * Opens a modal with structured form for reporting:
 * - Data errors
 * - Outdated information
 * - Missing information
 * - Other issues
 */

import React, { useState, useRef, useEffect } from 'react';
import { Flag, X, Send, CheckCircle } from 'lucide-react';
import { useAuth } from '../auth/useAuth';
import { useSupabase } from '../auth/SupabaseProvider';

interface ReportIssueButtonProps {
  charityId: string;
  charityName: string;
  /** Visual variant: icon (default with icon) or text (inline link, no icon) */
  variant?: 'icon' | 'text';
  /** Additional CSS classes */
  className?: string;
  /** Dark mode */
  isDark?: boolean;
}

type IssueType = 'data_error' | 'outdated_info' | 'missing_info' | 'other';

const ISSUE_TYPES: { value: IssueType; label: string; description: string }[] = [
  { value: 'data_error', label: 'Data Error', description: 'Incorrect information displayed' },
  { value: 'outdated_info', label: 'Outdated Info', description: 'Information needs updating' },
  { value: 'missing_info', label: 'Missing Info', description: 'Important information not shown' },
  { value: 'other', label: 'Other', description: 'Something else' },
];

export const ReportIssueButton: React.FC<ReportIssueButtonProps> = ({
  charityId,
  charityName,
  variant = 'icon',
  className = '',
  isDark = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [issueType, setIssueType] = useState<IssueType | ''>('');
  const [description, setDescription] = useState('');
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const { user } = useAuth();
  const { supabase } = useSupabase();

  // Pre-fill email if user is logged in
  useEffect(() => {
    if (user?.email && !email) {
      setEmail(user.email);
    }
  }, [user, email]);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
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
      setIsOpen(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!issueType || !description.trim()) {
      setError('Please select an issue type and provide a description');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      // Submit to Supabase
      if (supabase) {
        const { error: insertError } = await supabase
          .from('reported_issues')
          .insert({
            charity_id: charityId,
            charity_name: charityName,
            issue_type: issueType,
            description: description.trim(),
            reporter_email: email?.trim() || null,
            reporter_user_id: user?.id || null,
          });

        if (insertError) {
          console.error('Failed to submit report:', insertError);
          throw insertError;
        }
      } else {
        // Fallback: log to console if Supabase not configured
        console.log('Report submitted (Supabase not configured):', {
          charityId,
          charityName,
          issueType,
          description,
          email: email || undefined,
        });
      }

      // Track the report event
      if (typeof window !== 'undefined' && window.gtag) {
        window.gtag('event', 'report_issue', {
          charity_id: charityId,
          issue_type: issueType,
        });
      }

      setIsSubmitted(true);
      setTimeout(() => {
        setIsOpen(false);
        // Reset form after close
        setTimeout(() => {
          setIsSubmitted(false);
          setIssueType('');
          setDescription('');
          setError(null);
        }, 300);
      }, 2000);
    } catch (err) {
      setError('Failed to submit report. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const buttonClasses = variant === 'text'
    ? `hover:underline ${isDark ? 'hover:text-slate-300' : 'hover:text-slate-600'}`
    : `inline-flex items-center gap-1.5 text-sm ${
        isDark ? 'text-slate-500 hover:text-slate-400' : 'text-slate-400 hover:text-slate-600'
      }`;

  return (
    <>
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
              <h2 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                Report an Issue
              </h2>
              <button
                onClick={() => setIsOpen(false)}
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

                  {/* Description */}
                  <div>
                    <label className={`block text-xs uppercase tracking-wide font-medium mb-1 ${
                      isDark ? 'text-slate-400' : 'text-slate-500'
                    }`}>
                      Description *
                    </label>
                    <textarea
                      value={description}
                      onChange={e => setDescription(e.target.value)}
                      placeholder="Please describe the issue..."
                      rows={3}
                      className={`w-full px-3 py-2 rounded-lg text-sm border transition-colors ${
                        isDark
                          ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-500 focus:border-emerald-500'
                          : 'bg-white border-slate-200 text-slate-900 placeholder-slate-400 focus:border-emerald-500'
                      } focus:outline-none focus:ring-1 focus:ring-emerald-500`}
                    />
                  </div>

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
                      className={`w-full px-3 py-2 rounded-lg text-sm border transition-colors ${
                        isDark
                          ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-500 focus:border-emerald-500'
                          : 'bg-white border-slate-200 text-slate-900 placeholder-slate-400 focus:border-emerald-500'
                      } focus:outline-none focus:ring-1 focus:ring-emerald-500`}
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

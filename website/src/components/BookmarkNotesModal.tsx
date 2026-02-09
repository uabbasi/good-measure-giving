/**
 * BookmarkNotesModal - Modal for editing private notes on bookmarks
 */

import React, { useState, useEffect, useRef } from 'react';
import { useLandingTheme } from '../../contexts/LandingThemeContext';

interface BookmarkNotesModalProps {
  ein: string;
  currentNotes: string | null;
  charityName?: string;
  onSave: (notes: string | null) => Promise<void>;
  onClose: () => void;
}

export function BookmarkNotesModal({
  ein,
  currentNotes,
  charityName,
  onSave,
  onClose,
}: BookmarkNotesModalProps) {
  const { isDark } = useLandingTheme();
  const [notes, setNotes] = useState(currentNotes || '');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Focus textarea on mount
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    try {
      // Trim and normalize empty strings to null
      const trimmedNotes = notes.trim() || null;
      await onSave(trimmedNotes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save notes');
      setIsSaving(false);
    }
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="notes-modal-title"
    >
      <div
        className={`
          w-full max-w-md rounded-xl shadow-xl
          ${isDark ? 'bg-slate-900' : 'bg-white'}
        `}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={`
          px-4 py-3 border-b flex items-center justify-between
          ${isDark ? 'border-slate-800' : 'border-slate-200'}
        `}>
          <h2
            id="notes-modal-title"
            className={`font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}
          >
            {currentNotes ? 'Edit Notes' : 'Add Notes'}
          </h2>
          <button
            onClick={onClose}
            className={`
              p-1 rounded-lg transition-colors
              ${isDark
                ? 'hover:bg-slate-800 text-slate-400'
                : 'hover:bg-slate-100 text-slate-500'
              }
            `}
            aria-label="Close"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="p-4">
          {charityName && (
            <p className={`text-sm mb-3 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              Notes for <span className="font-medium">{charityName}</span>
            </p>
          )}

          <textarea
            ref={textareaRef}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add private notes about this charity..."
            maxLength={1000}
            rows={4}
            className={`
              w-full px-3 py-2 rounded-lg border resize-none
              ${isDark
                ? 'bg-slate-800 border-slate-700 text-white placeholder-slate-500'
                : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400'
              }
              focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent
            `}
          />

          <div className="flex items-center justify-between mt-2">
            <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              {notes.length}/1000 characters
            </span>
            <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              Only you can see these notes
            </span>
          </div>

          {error && (
            <p className="mt-2 text-sm text-red-500">{error}</p>
          )}
        </div>

        {/* Footer */}
        <div className={`
          px-4 py-3 border-t flex justify-end gap-2
          ${isDark ? 'border-slate-800' : 'border-slate-200'}
        `}>
          <button
            onClick={onClose}
            disabled={isSaving}
            className={`
              px-4 py-2 rounded-lg font-medium transition-colors
              ${isDark
                ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }
              disabled:opacity-50
            `}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className={`
              px-4 py-2 rounded-lg font-medium transition-colors
              bg-emerald-600 text-white hover:bg-emerald-700
              disabled:opacity-50 disabled:cursor-not-allowed
              flex items-center gap-2
            `}
          >
            {isSaving && (
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            )}
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

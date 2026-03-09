/**
 * BookmarkToast: Post-bookmark confirmation toast.
 * Listens for 'gmg:bookmark-added' custom event, shows a brief message, auto-dismisses after 4s.
 * Includes a "View Giving Plan" link when user isn't already on /profile.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { X, Heart, ArrowRight } from 'lucide-react';
import { useLocation, Link } from 'react-router-dom';

interface BookmarkAddedDetail {
  charityEin: string;
  charityName: string;
  causeTags?: string[];
}

export const BookmarkToast: React.FC = () => {
  const [visible, setVisible] = useState(false);
  const [charityName, setCharityName] = useState('');
  const location = useLocation();
  const isOnProfile = location.pathname === '/profile';

  const dismiss = useCallback(() => setVisible(false), []);

  useEffect(() => {
    const handleBookmarkAdded = (e: Event) => {
      if (isOnProfile) return;
      const detail = (e as CustomEvent<BookmarkAddedDetail>).detail;
      setCharityName(detail.charityName || 'Charity');
      setVisible(true);
    };

    window.addEventListener('gmg:bookmark-added', handleBookmarkAdded);
    return () => window.removeEventListener('gmg:bookmark-added', handleBookmarkAdded);
  }, [isOnProfile]);

  // Auto-dismiss after 4s
  useEffect(() => {
    if (!visible) return;
    const timer = setTimeout(dismiss, 4000);
    return () => clearTimeout(timer);
  }, [visible, dismiss]);

  if (!visible) return null;

  return (
    <div
      className="fixed bottom-20 right-6 md:bottom-6 z-[200] max-w-sm animate-slide-in-right"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-start gap-3 px-5 py-4 rounded-xl shadow-2xl border bg-white border-slate-200 text-slate-800">
        <Heart className="w-5 h-5 text-rose-500 fill-current flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm font-semibold">{charityName} added to your Giving Plan</p>
          <Link
            to="/profile"
            onClick={dismiss}
            className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 hover:text-emerald-700 mt-1.5 transition-colors"
          >
            View Giving Plan
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
        <button
          onClick={dismiss}
          aria-label="Close"
          className="p-1 text-slate-400 hover:text-slate-600 rounded-full transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

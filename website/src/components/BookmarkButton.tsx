/**
 * BookmarkButton - Toggle bookmark status on charities
 * Shows filled heart when bookmarked, outline when not
 * Requires authentication - prompts sign-in if not logged in
 */

import React, { useState } from 'react';
import { useBookmarkState } from '../contexts/UserFeaturesContext';
import { useAuth } from '../auth';
import { useLandingTheme } from '../../contexts/LandingThemeContext';

interface BookmarkButtonProps {
  charityEin: string;
  charityName?: string;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  fullWidth?: boolean;
  className?: string;
  buttonClassName?: string;
  labelClassName?: string;
}

export function BookmarkButton({
  charityEin,
  charityName,
  size = 'md',
  showLabel = false,
  fullWidth = false,
  className = '',
  buttonClassName = '',
  labelClassName = '',
}: BookmarkButtonProps) {
  const { isDark } = useLandingTheme();
  const { isSignedIn } = useAuth();
  const { isBookmarked, toggleBookmark, isLoading } = useBookmarkState();
  const [isAnimating, setIsAnimating] = useState(false);
  const [showSignInHint, setShowSignInHint] = useState(false);

  const bookmarked = isBookmarked(charityEin);

  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6',
  };

  const buttonSizeClasses = {
    sm: 'p-1',
    md: 'p-1.5',
    lg: 'p-2',
  };

  const labelledButtonClasses = {
    sm: 'inline-flex items-center gap-1.5 px-2.5 py-1.5 min-h-[40px]',
    md: 'inline-flex items-center gap-1.5 px-3 py-2 min-h-[44px]',
    lg: 'inline-flex items-center gap-2 px-3.5 py-2.5 min-h-[48px]',
  };

  const handleClick = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!isSignedIn) {
      setShowSignInHint(true);
      setTimeout(() => setShowSignInHint(false), 3000);
      return;
    }

    if (isLoading) return;

    setIsAnimating(true);
    try {
      await toggleBookmark(charityEin);
    } catch (err) {
      console.error('Failed to toggle bookmark:', err);
    }
    setTimeout(() => setIsAnimating(false), 300);
  };

  const label = bookmarked ? 'Remove from saved' : 'Save charity';
  const ariaLabel = charityName
    ? `${bookmarked ? 'Remove' : 'Save'} ${charityName}`
    : label;

  return (
    <div className={`relative inline-flex items-center ${className}`}>
      <button
        onClick={handleClick}
        disabled={isLoading}
        aria-label={ariaLabel}
        aria-pressed={bookmarked}
        title={label}
        className={`
          ${showLabel ? labelledButtonClasses[size] : buttonSizeClasses[size]}
          rounded-full
          transition-all duration-200
          ${isDark
            ? 'hover:bg-slate-700/50 active:bg-slate-600/50'
            : 'hover:bg-slate-100 active:bg-slate-200'
          }
          ${isAnimating ? 'scale-125' : 'scale-100'}
          ${isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          ${fullWidth ? 'w-full justify-center' : ''}
          focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2
          ${isDark ? 'focus:ring-offset-slate-800' : 'focus:ring-offset-white'}
          ${buttonClassName}
        `}
      >
        {bookmarked ? (
          <svg
            className={`${sizeClasses[size]} text-rose-500 fill-current`}
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
          </svg>
        ) : (
          <svg
            className={`${sizeClasses[size]} ${isDark ? 'text-slate-400' : 'text-slate-500'}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"
            />
          </svg>
        )}

        {showLabel && (
          <span className={`text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'} ${labelClassName}`}>
            {bookmarked ? 'Saved' : 'Save'}
          </span>
        )}
      </button>

      {/* Sign-in hint tooltip */}
      {showSignInHint && (
        <div
          className={`
            absolute bottom-full left-1/2 -translate-x-1/2 mb-2
            px-3 py-1.5 rounded-lg text-xs font-medium
            whitespace-nowrap z-50
            ${isDark ? 'bg-slate-700 text-white' : 'bg-slate-800 text-white'}
            animate-fade-in
          `}
        >
          Sign in to save charities
          <div
            className={`
              absolute top-full left-1/2 -translate-x-1/2
              border-4 border-transparent
              ${isDark ? 'border-t-slate-700' : 'border-t-slate-800'}
            `}
          />
        </div>
      )}
    </div>
  );
}

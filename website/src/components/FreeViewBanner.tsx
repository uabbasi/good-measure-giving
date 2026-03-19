/**
 * FreeViewBanner — Shows anonymous visitors their remaining free views.
 *
 * Two states:
 * - Soft: "You're viewing X of 3 free evaluations" (views remaining)
 * - Strong: "You've used your free evaluations" (views exhausted)
 */

import React from 'react';
import { SignInButton } from '../auth/SignInButton';
import { useLandingTheme } from '../../contexts/LandingThemeContext';

interface FreeViewBannerProps {
  viewsUsed: number;
  viewsRemaining: number;
}

export const FreeViewBanner: React.FC<FreeViewBannerProps> = ({ viewsUsed, viewsRemaining }) => {
  const { isDark } = useLandingTheme();
  const isExhausted = viewsRemaining <= 0;

  if (isExhausted) {
    return (
      <div className={`flex items-center justify-between gap-3 px-4 py-3 rounded-xl mb-4 ${
        isDark
          ? 'bg-slate-800 border border-slate-700'
          : 'bg-slate-900 border border-slate-800'
      }`}>
        <span className="text-sm text-slate-300">
          You've used your free evaluations
        </span>
        <SignInButton
          variant="custom"
          context="free_view_banner_exhausted"
          className="cursor-pointer"
        >
          <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-semibold bg-blue-600 text-white hover:bg-blue-500 transition-colors whitespace-nowrap">
            Sign in — Free, always
          </span>
        </SignInButton>
      </div>
    );
  }

  return (
    <div className={`flex items-center justify-between gap-3 px-4 py-2.5 rounded-xl mb-4 ${
      isDark
        ? 'bg-blue-950/40 border border-blue-800/30'
        : 'bg-blue-50 border border-blue-200'
    }`}>
      <span className={`text-sm ${isDark ? 'text-blue-300/80' : 'text-blue-700'}`}>
        You're viewing{' '}
        <strong className={isDark ? 'text-blue-200' : 'text-blue-900'}>
          {viewsUsed} of 3
        </strong>{' '}
        free full evaluations
      </span>
      <SignInButton
        variant="custom"
        context="free_view_banner_soft"
        className="cursor-pointer"
      >
        <span className={`text-sm font-medium whitespace-nowrap transition-colors ${
          isDark ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-800'
        }`}>
          Sign in for unlimited →
        </span>
      </SignInButton>
    </div>
  );
};

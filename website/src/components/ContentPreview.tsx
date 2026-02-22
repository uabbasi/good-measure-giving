/**
 * ContentPreview: Soft gate component for anonymous users.
 * Shows section title + placeholder bars + sign-in link.
 */

import React from 'react';
import { Lock } from 'lucide-react';
import { SignInButton } from '../auth/SignInButton';
import { useLandingTheme } from '../../contexts/LandingThemeContext';

interface ContentPreviewProps {
  title: string;
  description: string;
  teaser?: string;
}

export const ContentPreview: React.FC<ContentPreviewProps> = ({ title, description, teaser }) => {
  const { isDark } = useLandingTheme();

  return (
    <div className={`rounded-lg border p-4 ${
      isDark ? 'bg-slate-800/30 border-slate-700/50' : 'bg-slate-50 border-slate-200'
    }`}>
      <div className={`text-xs uppercase tracking-widest font-semibold mb-3 ${
        isDark ? 'text-slate-500' : 'text-slate-400'
      }`}>
        {title}
      </div>
      {teaser ? (
        <div className="relative mb-3 overflow-hidden" style={{ maxHeight: '3.5rem' }}>
          <p className={`text-sm blur-[6px] select-none ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
            {teaser}
          </p>
          <div className={`absolute inset-0 bg-gradient-to-b ${
            isDark ? 'from-transparent to-slate-800/80' : 'from-transparent to-slate-50/80'
          }`} />
        </div>
      ) : (
        <div className="space-y-2 mb-3">
          <div className={`h-2.5 rounded-full w-full ${isDark ? 'bg-slate-700/60' : 'bg-slate-200'}`} />
          <div className={`h-2.5 rounded-full w-4/5 ${isDark ? 'bg-slate-700/60' : 'bg-slate-200'}`} />
          <div className={`h-2.5 rounded-full w-3/5 ${isDark ? 'bg-slate-700/60' : 'bg-slate-200'}`} />
        </div>
      )}
      <SignInButton
        variant="custom"
        context={description}
        className={`text-sm flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity ${
          isDark ? 'text-emerald-400' : 'text-emerald-600'
        }`}
      >
        <Lock className="w-3.5 h-3.5 flex-shrink-0" />
        <span>
          <span className="underline font-medium">Sign in</span>
          {' '}to see {description}
        </span>
      </SignInButton>
    </div>
  );
};

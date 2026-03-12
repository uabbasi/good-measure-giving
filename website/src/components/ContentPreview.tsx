/**
 * ContentPreview: Gate component for anonymous users.
 * Shows section title + value prop + prominent sign-in CTA.
 */

import React from 'react';
import { Lock, ChevronRight } from 'lucide-react';
import { SignInButton } from '../auth/SignInButton';
import { useLandingTheme } from '../../contexts/LandingThemeContext';

interface ContentPreviewProps {
  title: string;
  description: string;
  teaser?: string;
  /** Bullet points describing what's behind the gate */
  valueProps?: string[];
}

export const ContentPreview: React.FC<ContentPreviewProps> = ({ title, description, teaser, valueProps }) => {
  const { isDark } = useLandingTheme();

  return (
    <div className={`rounded-xl border-2 border-dashed p-5 ${
      isDark ? 'bg-slate-800/40 border-slate-600/60' : 'bg-slate-50/80 border-slate-300'
    }`}>
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-lg shrink-0 ${
          isDark ? 'bg-slate-700/60' : 'bg-slate-200/80'
        }`}>
          <Lock className={`w-4 h-4 ${isDark ? 'text-slate-400' : 'text-slate-500'}`} />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className={`text-sm font-bold mb-1 ${isDark ? 'text-white' : 'text-slate-900'}`}>
            {title}
          </h4>
          {teaser && (
            <p className={`text-xs mb-2 line-clamp-2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              {teaser}
            </p>
          )}
          {valueProps && valueProps.length > 0 && (
            <ul className={`text-xs space-y-1 mb-3 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              {valueProps.map((prop, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <ChevronRight className={`w-3 h-3 mt-0.5 shrink-0 ${isDark ? 'text-emerald-500' : 'text-emerald-600'}`} />
                  {prop}
                </li>
              ))}
            </ul>
          )}
          <SignInButton
            variant="custom"
            context={description}
            className="cursor-pointer"
          >
            <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
              isDark
                ? 'bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30 border border-emerald-600/40'
                : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-300'
            }`}>
              <Lock className="w-3 h-3" />
              Sign in to unlock
            </span>
          </SignInButton>
        </div>
      </div>
    </div>
  );
};

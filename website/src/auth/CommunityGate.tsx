/**
 * Community Gate Component
 *
 * Wraps content that should only be visible to community members.
 * Non-members see a friendly join prompt (not a hard block).
 */

import React from 'react';
import { useCommunityMember } from './useAuth';
import { SignInButton } from './SignInButton';
import { useLandingTheme } from '../../contexts/LandingThemeContext';

interface CommunityGateProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

/**
 * Shows children to community members, fallback to others.
 *
 * Usage:
 *   <CommunityGate fallback={<BaselineView />}>
 *     <RichView />
 *   </CommunityGate>
 */
export const CommunityGate: React.FC<CommunityGateProps> = ({
  children,
  fallback
}) => {
  const isMember = useCommunityMember();

  if (isMember) {
    return <>{children}</>;
  }

  return <>{fallback}</>;
};

/**
 * Join the community prompt - compelling CTA for premium content
 */
export const JoinCommunityPrompt: React.FC<{ className?: string }> = ({
  className = ''
}) => {
  const { isDark } = useLandingTheme();

  const benefits = [
    'Full charity analysis with detailed breakdowns',
    'Evidence quality ratings and source citations',
    'Priority access to new evaluations',
  ];

  return (
    <div className={`rounded-2xl overflow-hidden ${isDark ? 'bg-gradient-to-br from-slate-900 to-slate-800 border border-slate-700' : 'bg-gradient-to-br from-slate-50 to-white border border-slate-200'} ${className}`}>
      <div className="p-8">
        {/* Headline */}
        <h3 className={`text-2xl lg:text-3xl font-merriweather font-bold mb-3 ${isDark ? 'text-white' : 'text-slate-900'}`}>
          Unlock Full Analysis
        </h3>

        {/* Subtext */}
        <p className={`text-base mb-6 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
          Get the complete picture on every charity—detailed breakdowns, evidence grades, and source citations.
        </p>

        {/* Benefits list with checkmarks */}
        <ul className="space-y-3 mb-8">
          {benefits.map((benefit, i) => (
            <li key={i} className={`flex items-center gap-3 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              <svg className="w-5 h-5 text-emerald-500 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>{benefit}</span>
            </li>
          ))}
        </ul>

        {/* CTA Button */}
        <SignInButton
          variant="button"
          className={`w-full sm:w-auto px-8 py-3.5 text-base font-bold rounded-full transition-all ${
            isDark
              ? 'bg-emerald-600 text-white hover:bg-emerald-500 shadow-lg shadow-emerald-900/30'
              : 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-lg shadow-emerald-600/20'
          }`}
        />

        {/* Reassurance text */}
        <p className={`text-xs mt-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
          Free forever. We just want to stay connected with thoughtful donors.
        </p>
      </div>
    </div>
  );
};

export default CommunityGate;

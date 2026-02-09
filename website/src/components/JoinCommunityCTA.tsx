/**
 * Join the Community CTA Component
 *
 * Reusable component showing community benefits and sign-in button.
 * Used on landing page, charity detail pages, etc.
 */

import React from 'react';
import { CheckCircle } from 'lucide-react';
import { SignInButton, useCommunityMember } from '../auth';

interface JoinCommunityCTAProps {
  /** Visual variant */
  variant?: 'dark' | 'light';
  /** Optional custom heading */
  heading?: string;
  /** Optional custom description */
  description?: string;
  /** Additional CSS classes */
  className?: string;
}

const benefits = [
  'See which charities have proof their programs work',
  'Compare cost-effectiveness across similar organizations',
  'Know if a charity qualifies for your Zakat',
];

export const JoinCommunityCTA: React.FC<JoinCommunityCTAProps> = ({
  variant = 'dark',
  heading = 'Give with Confidence',
  description = 'Join thousands of Muslim donors who want more than a star rating. See the evidence behind every charity.',
  className = '',
}) => {
  const isMember = useCommunityMember();

  // Don't show if already a member
  if (isMember) {
    return null;
  }

  const isDark = variant === 'dark';

  return (
    <div className={className}>
      <h2 className={`text-2xl lg:text-3xl font-merriweather font-bold mb-4 leading-tight ${
        isDark ? 'text-white' : 'text-slate-900'
      }`}>
        {heading}
      </h2>
      <p className={`mb-6 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
        {description}
      </p>
      <ul className={`space-y-3 mb-6 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
        {benefits.map((benefit, i) => (
          <li key={i} className="flex items-center gap-3">
            <CheckCircle className="w-5 h-5 text-emerald-500 shrink-0" />
            <span>{benefit}</span>
          </li>
        ))}
      </ul>
      <SignInButton
        variant="button"
        className={`px-6 py-3 font-bold rounded-full transition-colors ${
          isDark
            ? 'bg-emerald-600 text-white hover:bg-emerald-500'
            : 'bg-emerald-700 text-white hover:bg-emerald-600'
        }`}
      />
    </div>
  );
};

export default JoinCommunityCTA;

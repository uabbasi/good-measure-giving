/**
 * CompareButton - Toggle compare status on charities
 * Shows checkmark when in compare list
 */

import React from 'react';
import { Plus, Check } from 'lucide-react';
import { useLandingTheme } from '../../contexts/LandingThemeContext';
import { useCompareState } from '../contexts/UserFeaturesContext';
import { trackCompareToggle } from '../utils/analytics';

interface CompareButtonProps {
  charityEin: string;
  charityName?: string;
  size?: 'sm' | 'md';
  /** Whether to show the text label. Defaults to true. Set false for icon-only (mobile). */
  showLabel?: boolean;
  className?: string;
}

export function CompareButton({
  charityEin,
  charityName,
  size = 'md',
  showLabel = true,
  className = '',
}: CompareButtonProps) {
  const { isDark } = useLandingTheme();
  const { isComparing, toggleCompare, canAddMore } = useCompareState();

  const inCompare = isComparing(charityEin);
  const disabled = !inCompare && !canAddMore;

  const sizeClasses = {
    sm: 'p-1 text-[10px]',
    md: 'p-1.5 text-xs',
  };

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
  };

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (disabled) return;
    toggleCompare(charityEin);
    trackCompareToggle(charityEin, charityName || '', inCompare ? 'remove' : 'add');
  };

  const label = inCompare
    ? 'Remove from compare'
    : disabled
    ? 'Compare limit reached (3 max)'
    : 'Add to compare';
  const ariaLabel = charityName ? `${label}: ${charityName}` : label;

  return (
    <button
      onClick={handleClick}
      disabled={disabled}
      aria-label={ariaLabel}
      aria-pressed={inCompare}
      title={label}
      className={`
        ${sizeClasses[size]}
        rounded-lg
        transition-all duration-200
        flex items-center gap-1
        font-medium uppercase tracking-wider
        ${inCompare
          ? `bg-emerald-100 text-emerald-700 border border-emerald-200 ${isDark ? 'bg-emerald-900/30 text-emerald-400 border-emerald-800' : ''}`
          : disabled
          ? `${isDark ? 'bg-slate-800 text-slate-600 cursor-not-allowed' : 'bg-slate-100 text-slate-400 cursor-not-allowed'}`
          : `${isDark
              ? 'bg-slate-700/50 text-slate-400 hover:bg-slate-700 hover:text-slate-200 border border-slate-600'
              : 'bg-slate-50 text-slate-500 hover:bg-slate-100 hover:text-slate-700 border border-slate-200'
            }`
        }
        focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2
        ${isDark ? 'focus:ring-offset-slate-800' : 'focus:ring-offset-white'}
        ${className}
      `}
    >
      {inCompare ? (
        <Check className={iconSizes[size]} />
      ) : (
        <Plus className={iconSizes[size]} />
      )}
      {showLabel && <span>{inCompare ? 'Added' : 'Compare'}</span>}
    </button>
  );
}

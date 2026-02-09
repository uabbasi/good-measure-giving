/**
 * Card showing progress for a giving bucket
 * Supports both new bucket-based and legacy category-based interfaces
 */

import React from 'react';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import type { GivingBucket } from '../../../types';

// New bucket-based interface
interface BucketProgressCardProps {
  bucket: GivingBucket;
  allocationPercent: number;
  targetAmount: number;
  actualAmount: number;
  charityCount: number;
  onClick?: () => void;
}

// Legacy category-based interface for backward compatibility
interface LegacyCategoryProgressCardProps {
  category: string;
  allocationPercent: number;
  targetAmount: number;
  actualAmount: number;
  charityCount: number;
  onClick?: () => void;
}

type CategoryProgressCardProps = BucketProgressCardProps | LegacyCategoryProgressCardProps;

// Check if props are bucket-based
function isBucketProps(props: CategoryProgressCardProps): props is BucketProgressCardProps {
  return 'bucket' in props;
}

// Default icon for buckets
function BucketIcon({ color, isDark }: { color?: string; isDark: boolean }) {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
    </svg>
  );
}

export function CategoryProgressCard(props: CategoryProgressCardProps) {
  const { isDark } = useLandingTheme();

  // Extract values based on which interface is used
  const {
    allocationPercent,
    targetAmount,
    actualAmount,
    charityCount,
    onClick,
  } = props;

  const name = isBucketProps(props) ? props.bucket.name : props.category;
  const color = isBucketProps(props) ? props.bucket.color : undefined;
  const tags = isBucketProps(props) ? props.bucket.tags : [];

  const remainingAmount = Math.max(0, targetAmount - actualAmount);
  const progressPercent = targetAmount > 0 ? Math.min(100, (actualAmount / targetAmount) * 100) : 0;
  const isComplete = actualAmount >= targetAmount && targetAmount > 0;
  const isOverTarget = actualAmount > targetAmount && targetAmount > 0;

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  // Use bucket color or a default
  const bucketColor = color || '#10b981';

  return (
    <div
      onClick={onClick}
      className={`
        p-4 rounded-xl border transition-all
        ${onClick ? 'cursor-pointer' : ''}
        ${isDark
          ? `bg-slate-900 border-slate-800 ${onClick ? 'hover:border-slate-700' : ''}`
          : `bg-white border-slate-200 ${onClick ? 'hover:border-slate-300 hover:shadow-sm' : ''}`
        }
      `}
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center"
          style={{
            backgroundColor: isComplete
              ? 'rgba(16, 185, 129, 0.2)'
              : `${bucketColor}20`,
            color: isComplete ? '#10b981' : bucketColor,
          }}
        >
          <BucketIcon color={bucketColor} isDark={isDark} />
        </div>
        <div className="flex-grow min-w-0">
          <h3 className={`font-medium truncate ${isDark ? 'text-white' : 'text-slate-900'}`}>
            {name || 'Unnamed Bucket'}
          </h3>
          <p className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
            {allocationPercent}% allocation
          </p>
        </div>
        {isComplete && (
          <div className="text-emerald-500 flex-shrink-0">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
        )}
      </div>

      {/* Tags (only for bucket-based cards) */}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {tags.slice(0, 3).map(tag => (
            <span
              key={tag}
              className={`text-xs px-2 py-0.5 rounded-full ${isDark ? 'bg-slate-800 text-slate-400' : 'bg-slate-100 text-slate-600'}`}
            >
              {tag}
            </span>
          ))}
          {tags.length > 3 && (
            <span className={`text-xs px-2 py-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              +{tags.length - 3}
            </span>
          )}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2 mb-3 text-sm">
        <div>
          <p className={isDark ? 'text-slate-500' : 'text-slate-500'}>Target</p>
          <p className={`font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
            {formatCurrency(targetAmount)}
          </p>
        </div>
        <div>
          <p className={isDark ? 'text-slate-500' : 'text-slate-500'}>Given</p>
          <p className={`font-medium ${isOverTarget ? 'text-emerald-500' : isDark ? 'text-white' : 'text-slate-900'}`}>
            {formatCurrency(actualAmount)}
          </p>
        </div>
        <div>
          <p className={isDark ? 'text-slate-500' : 'text-slate-500'}>Remaining</p>
          <p className={`font-medium ${remainingAmount === 0 ? 'text-emerald-500' : isDark ? 'text-slate-300' : 'text-slate-700'}`}>
            {formatCurrency(remainingAmount)}
          </p>
        </div>
      </div>

      {/* Progress bar */}
      <div className={`h-2 rounded-full overflow-hidden ${isDark ? 'bg-slate-800' : 'bg-slate-200'}`}>
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{
            width: `${Math.min(100, progressPercent)}%`,
            backgroundColor: isComplete ? '#10b981' : bucketColor,
          }}
        />
      </div>

      {/* Footer */}
      <div className="mt-2 flex items-center justify-between text-xs">
        <span className={isDark ? 'text-slate-500' : 'text-slate-500'}>
          {charityCount} {charityCount === 1 ? 'charity' : 'charities'}
        </span>
        <span className={`font-medium ${isComplete ? 'text-emerald-500' : isDark ? 'text-slate-400' : 'text-slate-600'}`}>
          {Math.round(progressPercent)}%
        </span>
      </div>
    </div>
  );
}

// Alias for new naming
export const BucketProgressCard = CategoryProgressCard;

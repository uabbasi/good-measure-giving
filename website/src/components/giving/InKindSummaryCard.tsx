/**
 * Summary card showing tax year totals, category breakdown, and IRS threshold warnings
 * for in-kind (non-cash) donations
 */

import React from 'react';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import type { InKindYearSummary } from '../../hooks/useInKindDonations';
import { VALUE_GUIDE_SOURCES } from '../../data/donationValueGuide';

interface InKindSummaryCardProps {
  summary: InKindYearSummary;
  taxYear: number;
}

export function InKindSummaryCard({ summary, taxYear }: InKindSummaryCardProps) {
  const { isDark } = useLandingTheme();

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  if (summary.donationCount === 0) return null;

  return (
    <div className={`rounded-xl border p-5 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
      <h3 className={`text-sm font-semibold mb-4 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
        {taxYear} In-Kind Summary
      </h3>

      {/* Top-level stats */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div>
          <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Total Value</p>
          <p className={`text-xl font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
            {formatCurrency(summary.totalValue)}
          </p>
        </div>
        <div>
          <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Donations</p>
          <p className={`text-xl font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
            {summary.donationCount}
          </p>
        </div>
        <div>
          <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Items</p>
          <p className={`text-xl font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
            {summary.itemCount}
          </p>
        </div>
      </div>

      {/* IRS Threshold Warnings */}
      {summary.totalValue > 5000 && (
        <div className={`p-3 rounded-lg text-xs mb-3 ${isDark ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'bg-red-50 text-red-700 border border-red-200'}`}>
          <strong>Qualified Appraisal Required:</strong> Your {taxYear} non-cash donations exceed $5,000. You need a qualified appraisal and must file Form 8283 Section B with your tax return.
        </div>
      )}
      {summary.totalValue > 500 && summary.totalValue <= 5000 && (
        <div className={`p-3 rounded-lg text-xs mb-3 ${isDark ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'bg-amber-50 text-amber-700 border border-amber-200'}`}>
          <strong>Form 8283 Required:</strong> Your {taxYear} non-cash donations exceed $500. You need to file Form 8283 (Noncash Charitable Contributions) with your tax return — it documents what you donated, to whom, and how you determined fair market value.
        </div>
      )}

      {/* Category breakdown */}
      {summary.categoryBreakdown.length > 0 && (
        <div>
          <h4 className={`text-xs font-medium mb-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
            By Category
          </h4>
          <div className="space-y-1.5">
            {summary.categoryBreakdown.map(cat => {
              const pct = summary.totalValue > 0 ? (cat.total / summary.totalValue) * 100 : 0;
              return (
                <div key={cat.category}>
                  <div className="flex items-center justify-between text-sm mb-0.5">
                    <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>{cat.category}</span>
                    <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                      {formatCurrency(cat.total)}
                      <span className={`ml-1 text-xs font-normal ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                        ({cat.itemCount} item{cat.itemCount !== 1 ? 's' : ''})
                      </span>
                    </span>
                  </div>
                  <div className={`h-1.5 rounded-full ${isDark ? 'bg-slate-800' : 'bg-slate-100'}`}>
                    <div
                      className="h-full rounded-full bg-emerald-500 transition-all"
                      style={{ width: `${Math.max(2, pct)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recipient breakdown */}
      {summary.recipientBreakdown.length > 1 && (
        <div className="mt-4">
          <h4 className={`text-xs font-medium mb-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
            By Recipient
          </h4>
          <div className="space-y-1">
            {summary.recipientBreakdown.map(r => (
              <div key={r.name} className="flex items-center justify-between text-sm">
                <span className={isDark ? 'text-slate-400' : 'text-slate-600'}>{r.name}</span>
                <span className={`font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  {formatCurrency(r.total)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* IRS disclaimer */}
      <p className={`text-xs mt-4 ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
        Estimates based on{' '}
        {VALUE_GUIDE_SOURCES.map((s, i) => (
          <span key={s.url}>
            {i > 0 && ' and '}
            <a href={s.url} target="_blank" rel="noopener noreferrer" className="underline hover:text-emerald-500">{s.name}</a>
          </span>
        ))}
        . Consult a tax professional.
      </p>
    </div>
  );
}

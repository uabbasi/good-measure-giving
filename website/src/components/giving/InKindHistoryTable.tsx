/**
 * Table component for displaying in-kind donation history
 * Expandable rows showing individual items within each donation
 */

import React, { useState, useMemo } from 'react';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import type { InKindDonation } from '../../hooks/useInKindDonations';
import type { ItemCondition } from '../../data/donationValueGuide';

interface InKindHistoryTableProps {
  donations: InKindDonation[];
  onEdit: (donation: InKindDonation) => void;
  onDelete: (id: string) => void;
  onExport: (year?: number) => void;
}

export function InKindHistoryTable({
  donations,
  onEdit,
  onDelete,
  onExport,
}: InKindHistoryTableProps) {
  const { isDark } = useLandingTheme();
  const [yearFilter, setYearFilter] = useState<number | 'all'>('all');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);

  const years = useMemo(() => {
    const yearSet = new Set<number>();
    donations.forEach(d => yearSet.add(d.taxYear));
    return Array.from(yearSet).sort((a, b) => b - a);
  }, [donations]);

  const filteredDonations = useMemo(() => {
    if (yearFilter === 'all') return donations;
    return donations.filter(d => d.taxYear === yearFilter);
  }, [donations, yearFilter]);

  const totalValue = useMemo(() => {
    return filteredDonations.reduce((sum, d) => sum + d.totalValue, 0);
  }, [filteredDonations]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const formatCondition = (c: ItemCondition) => c.charAt(0).toUpperCase() + c.slice(1);

  const selectClass = `
    text-sm px-2 py-1.5 rounded-lg border
    ${isDark
      ? 'bg-slate-800 border-slate-700 text-white'
      : 'bg-white border-slate-200 text-slate-900'
    }
    focus:outline-none focus:ring-1 focus:ring-emerald-500
  `;

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <select
          value={yearFilter}
          onChange={(e) => setYearFilter(e.target.value === 'all' ? 'all' : parseInt(e.target.value))}
          className={selectClass}
        >
          <option value="all">All Years</option>
          {years.map(y => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>

        <div className="flex-grow" />

        <button
          onClick={() => onExport(yearFilter === 'all' ? undefined : yearFilter)}
          className={`
            text-sm px-3 py-1.5 rounded-lg border flex items-center gap-1.5 transition-colors
            ${isDark
              ? 'border-slate-700 text-slate-300 hover:bg-slate-800'
              : 'border-slate-200 text-slate-600 hover:bg-slate-50'
            }
          `}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Export CSV
        </button>
      </div>

      {/* Summary */}
      <div className={`flex flex-wrap items-center gap-x-6 gap-y-2 text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
        <span>{filteredDonations.length} donation{filteredDonations.length !== 1 ? 's' : ''}</span>
        <span>Total: <strong className={isDark ? 'text-white' : 'text-slate-900'}>{formatCurrency(totalValue)}</strong></span>
      </div>

      {/* Table */}
      {filteredDonations.length === 0 ? (
        <div className={`text-center py-12 rounded-xl border-2 border-dashed ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
          <svg
            className={`w-12 h-12 mx-auto mb-4 ${isDark ? 'text-slate-600' : 'text-slate-400'}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
          <p className={isDark ? 'text-slate-400' : 'text-slate-600'}>
            {donations.length === 0 ? 'No in-kind donations recorded yet' : 'No donations match your filter'}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {filteredDonations.map(donation => (
            <div
              key={donation.id}
              className={`rounded-lg border ${isDark ? 'bg-slate-800/50 border-slate-700' : 'bg-white border-slate-200'}`}
            >
              {/* Donation header row */}
              <div
                className={`flex items-center gap-3 px-4 py-3 cursor-pointer ${
                  isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-50'
                }`}
                onClick={() => setExpandedId(expandedId === donation.id ? null : donation.id)}
              >
                {/* Expand icon */}
                <svg
                  className={`w-4 h-4 flex-shrink-0 transition-transform ${
                    expandedId === donation.id ? 'rotate-90' : ''
                  } ${isDark ? 'text-slate-500' : 'text-slate-400'}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>

                <div className="flex-grow min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                      {donation.recipientName}
                    </span>
                    <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                      {formatDate(donation.date)}
                    </span>
                  </div>
                  <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    {donation.items.length} item{donation.items.length !== 1 ? 's' : ''}
                    {donation.notes && ` · ${donation.notes}`}
                  </div>
                </div>

                <div className={`text-right font-medium whitespace-nowrap ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {formatCurrency(donation.totalValue)}
                </div>

                {/* Actions */}
                <div className="flex gap-1 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                  {confirmingDeleteId === donation.id ? (
                    <div className="flex items-center gap-2">
                      <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Delete?</span>
                      <button
                        onClick={() => setConfirmingDeleteId(null)}
                        className={`px-2 py-1 text-xs rounded transition-colors ${
                          isDark ? 'bg-slate-700 text-slate-300 hover:bg-slate-600' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
                        }`}
                      >
                        No
                      </button>
                      <button
                        onClick={() => {
                          onDelete(donation.id);
                          setConfirmingDeleteId(null);
                        }}
                        className="px-2 py-1 text-xs rounded bg-red-600 text-white hover:bg-red-700 transition-colors"
                      >
                        Yes
                      </button>
                    </div>
                  ) : (
                    <>
                      <button
                        onClick={() => onEdit(donation)}
                        className={`p-1.5 rounded transition-colors ${isDark ? 'hover:bg-slate-700' : 'hover:bg-slate-200'}`}
                        title="Edit"
                      >
                        <svg className={`w-4 h-4 ${isDark ? 'text-slate-400' : 'text-slate-500'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                        </svg>
                      </button>
                      <button
                        onClick={() => setConfirmingDeleteId(donation.id)}
                        className={`p-1.5 rounded transition-colors ${isDark ? 'hover:bg-red-500/20' : 'hover:bg-red-50'}`}
                        title="Delete"
                      >
                        <svg className={`w-4 h-4 ${isDark ? 'text-red-400' : 'text-red-500'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* Expanded items */}
              {expandedId === donation.id && (
                <div className={`px-4 pb-3 border-t ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
                  <table className="w-full text-sm mt-2">
                    <thead>
                      <tr className={isDark ? 'text-slate-500' : 'text-slate-400'}>
                        <th className="text-left py-1 font-medium text-xs">Item</th>
                        <th className="text-left py-1 font-medium text-xs">Category</th>
                        <th className="text-center py-1 font-medium text-xs">Condition</th>
                        <th className="text-center py-1 font-medium text-xs">Qty</th>
                        <th className="text-right py-1 font-medium text-xs">Unit</th>
                        <th className="text-right py-1 font-medium text-xs">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {donation.items.map((item, idx) => (
                        <tr key={idx} className={`border-t ${isDark ? 'border-slate-700/50' : 'border-slate-50'}`}>
                          <td className={`py-1.5 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                            {item.itemName}
                            {item.isManualValue && (
                              <span className={`ml-1 text-xs ${isDark ? 'text-amber-400' : 'text-amber-600'}`} title="Manual value">*</span>
                            )}
                          </td>
                          <td className={`py-1.5 text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{item.category}</td>
                          <td className="py-1.5 text-center">
                            <span className={`text-xs px-1.5 py-0.5 rounded ${
                              item.condition === 'excellent' ? 'bg-emerald-500/20 text-emerald-500' :
                              item.condition === 'good' ? isDark ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-700' :
                              item.condition === 'fair' ? isDark ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-100 text-amber-700' :
                              isDark ? 'bg-slate-700 text-slate-400' : 'bg-slate-200 text-slate-600'
                            }`}>
                              {formatCondition(item.condition)}
                            </span>
                          </td>
                          <td className={`py-1.5 text-center ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>{item.quantity}</td>
                          <td className={`py-1.5 text-right ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>${item.unitValue.toFixed(2)}</td>
                          <td className={`py-1.5 text-right font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>${item.totalValue.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

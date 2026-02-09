/**
 * Table component for displaying giving history
 */

import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import type { GivingHistoryEntry } from '../../../types';

interface GivingHistoryTableProps {
  donations: GivingHistoryEntry[];
  onEdit: (donation: GivingHistoryEntry) => void;
  onDelete: (id: string) => void;
  onExport: (year?: number) => void;
}

type FilterCategory = 'all' | 'zakat' | 'sadaqah' | 'other';
type FilterReceipt = 'all' | 'received' | 'pending';
type FilterMatch = 'all' | 'eligible' | 'submitted' | 'received';

export function GivingHistoryTable({
  donations,
  onEdit,
  onDelete,
  onExport,
}: GivingHistoryTableProps) {
  const { isDark } = useLandingTheme();

  // Filter state
  const [yearFilter, setYearFilter] = useState<number | 'all'>('all');
  const [categoryFilter, setCategoryFilter] = useState<FilterCategory>('all');
  const [receiptFilter, setReceiptFilter] = useState<FilterReceipt>('all');
  const [matchFilter, setMatchFilter] = useState<FilterMatch>('all');

  // Inline delete confirmation
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);

  // Get unique years from donations
  const years = useMemo(() => {
    const yearSet = new Set<number>();
    donations.forEach(d => {
      yearSet.add(new Date(d.date).getFullYear());
      if (d.zakatYear) yearSet.add(d.zakatYear);
    });
    return Array.from(yearSet).sort((a, b) => b - a);
  }, [donations]);

  // Apply filters
  const filteredDonations = useMemo(() => {
    return donations.filter(d => {
      // Year filter
      if (yearFilter !== 'all') {
        const donationYear = new Date(d.date).getFullYear();
        if (donationYear !== yearFilter && d.zakatYear !== yearFilter) {
          return false;
        }
      }

      // Category filter
      if (categoryFilter !== 'all' && d.category !== categoryFilter) {
        return false;
      }

      // Receipt filter
      if (receiptFilter === 'received' && !d.receiptReceived) return false;
      if (receiptFilter === 'pending' && d.receiptReceived) return false;

      // Match filter
      if (matchFilter === 'eligible' && !d.matchEligible) return false;
      if (matchFilter === 'submitted' && d.matchStatus !== 'submitted') return false;
      if (matchFilter === 'received' && d.matchStatus !== 'received') return false;

      return true;
    });
  }, [donations, yearFilter, categoryFilter, receiptFilter, matchFilter]);

  // Calculate totals
  const totals = useMemo(() => {
    return filteredDonations.reduce(
      (acc, d) => ({
        amount: acc.amount + d.amount,
        matched: acc.matched + (d.matchStatus === 'received' ? (d.matchAmount || 0) : 0),
      }),
      { amount: 0, matched: 0 }
    );
  }, [filteredDonations]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

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

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value as FilterCategory)}
          className={selectClass}
        >
          <option value="all">All Categories</option>
          <option value="zakat">Zakat</option>
          <option value="sadaqah">Sadaqah</option>
          <option value="other">Other</option>
        </select>

        <select
          value={receiptFilter}
          onChange={(e) => setReceiptFilter(e.target.value as FilterReceipt)}
          className={selectClass}
        >
          <option value="all">All Receipts</option>
          <option value="received">Receipt Received</option>
          <option value="pending">Receipt Pending</option>
        </select>

        <select
          value={matchFilter}
          onChange={(e) => setMatchFilter(e.target.value as FilterMatch)}
          className={selectClass}
        >
          <option value="all">All Match Status</option>
          <option value="eligible">Match Eligible</option>
          <option value="submitted">Match Submitted</option>
          <option value="received">Match Received</option>
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
      <div className={`flex items-center gap-6 text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
        <span>{filteredDonations.length} donations</span>
        <span>Total: <strong className={isDark ? 'text-white' : 'text-slate-900'}>{formatCurrency(totals.amount)}</strong></span>
        {totals.matched > 0 && (
          <span>Matched: <strong className="text-emerald-500">{formatCurrency(totals.matched)}</strong></span>
        )}
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
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <p className={isDark ? 'text-slate-400' : 'text-slate-600'}>
            {donations.length === 0 ? 'No donations recorded yet' : 'No donations match your filters'}
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className={`border-b ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                <th className={`text-left py-3 px-2 font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Date</th>
                <th className={`text-left py-3 px-2 font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Charity</th>
                <th className={`text-right py-3 px-2 font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Amount</th>
                <th className={`text-center py-3 px-2 font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Type</th>
                <th className={`text-left py-3 px-2 font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Source</th>
                <th className={`text-center py-3 px-2 font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Receipt</th>
                <th className={`text-center py-3 px-2 font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Match</th>
                <th className={`text-right py-3 px-2 font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredDonations.map(donation => (
                <tr
                  key={donation.id}
                  className={`border-b ${isDark ? 'border-slate-800 hover:bg-slate-800/50' : 'border-slate-100 hover:bg-slate-50'}`}
                >
                  <td className={`py-3 px-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    {formatDate(donation.date)}
                  </td>
                  <td className={`py-3 px-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {donation.charityEin ? (
                      <Link
                        to={`/charity/${donation.charityEin}`}
                        className="hover:underline text-emerald-600"
                      >
                        {donation.charityName}
                      </Link>
                    ) : (
                      donation.charityName
                    )}
                  </td>
                  <td className={`py-3 px-2 text-right font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {formatCurrency(donation.amount)}
                  </td>
                  <td className="py-3 px-2 text-center">
                    <span className={`
                      text-xs font-medium px-2 py-0.5 rounded
                      ${donation.category === 'zakat'
                        ? 'bg-emerald-600 text-white'
                        : donation.category === 'sadaqah'
                        ? isDark ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-700'
                        : isDark ? 'bg-slate-700 text-slate-300' : 'bg-slate-200 text-slate-700'
                      }
                    `}>
                      {donation.category}
                      {donation.zakatYear && ` '${donation.zakatYear.toString().slice(-2)}`}
                    </span>
                  </td>
                  <td className={`py-3 px-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {donation.paymentSource || '-'}
                  </td>
                  <td className="py-3 px-2 text-center">
                    {donation.receiptReceived ? (
                      <span className="text-emerald-500" title="Receipt received">&#10003;</span>
                    ) : (
                      <span className={isDark ? 'text-slate-600' : 'text-slate-400'}>-</span>
                    )}
                  </td>
                  <td className="py-3 px-2 text-center">
                    {donation.matchEligible ? (
                      donation.matchStatus === 'received' ? (
                        <span className="text-emerald-500" title={`Matched: ${formatCurrency(donation.matchAmount || 0)}`}>
                          +{formatCurrency(donation.matchAmount || 0)}
                        </span>
                      ) : donation.matchStatus === 'submitted' ? (
                        <span className="text-amber-500" title="Match submitted">&#9679;</span>
                      ) : (
                        <span className={isDark ? 'text-slate-500' : 'text-slate-400'} title="Match eligible">&#9675;</span>
                      )
                    ) : (
                      <span className={isDark ? 'text-slate-600' : 'text-slate-400'}>-</span>
                    )}
                  </td>
                  <td className="py-3 px-2 text-right">
                    {confirmingDeleteId === donation.id ? (
                      <div className="flex justify-end items-center gap-2">
                        <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Delete?</span>
                        <button
                          onClick={() => setConfirmingDeleteId(null)}
                          className={`px-2 py-1 text-xs rounded transition-colors ${
                            isDark ? 'bg-slate-700 text-slate-300 hover:bg-slate-600' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
                          }`}
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => {
                            onDelete(donation.id);
                            setConfirmingDeleteId(null);
                          }}
                          className="px-2 py-1 text-xs rounded bg-red-600 text-white hover:bg-red-700 transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                    ) : (
                      <div className="flex justify-end gap-1">
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
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

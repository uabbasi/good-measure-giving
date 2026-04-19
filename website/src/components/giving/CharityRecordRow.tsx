/**
 * CharityRecordRow - row component for the unified record (M4).
 *
 * Renders a single charity line with:
 *  - color bar tied to bucket
 *  - charity name (link to detail page)
 *  - intended amount (editable)
 *  - given amount (display)
 *  - status chip (Planned / Sent / Confirmed)
 *  - action button (Log donation / Mark confirmed / [disabled] Confirmed)
 *
 * Two layouts share this file: desktop table-row + mobile card.
 * Keep the rendering dumb — all behavior is pushed up to the container.
 */

import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, X } from 'lucide-react';
import type { AssignmentStatus } from '../../utils/recordStatus';

export interface CharityRecordRowData {
  ein: string;
  name: string;
  bucketColor?: string;
  status: AssignmentStatus;
  intended: number;
  given: number;
}

interface CharityRecordRowProps {
  charity: CharityRecordRowData;
  isDark: boolean;
  onSetIntended: (ein: string, amount: number) => void;
  onLogDonation: (ein: string, name: string) => void;
  onMarkConfirmed: (ein: string) => void;
  onRemove?: (ein: string) => void;
  /** If true, render the desktop table-row variant; otherwise the mobile card. */
  desktop?: boolean;
  /** For zebra striping on desktop. */
  isEvenRow?: boolean;
}

/** Currency format: compact $1.2k when >= $1000, else `$n`. */
function fmt(n: number): string {
  if (n >= 1000) return `$${(n / 1000).toFixed(n % 1000 === 0 ? 0 : 1)}k`;
  return `$${n}`;
}

/** Status pill content: label + color classes. */
function statusPillClasses(status: AssignmentStatus, isDark: boolean): {
  label: string;
  className: string;
} {
  if (status === 'confirmed') {
    return {
      label: 'Confirmed',
      className: isDark
        ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
        : 'bg-emerald-50 text-emerald-700 border-emerald-200',
    };
  }
  if (status === 'sent') {
    return {
      label: 'Sent',
      className: isDark
        ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
        : 'bg-amber-50 text-amber-700 border-amber-200',
    };
  }
  return {
    label: 'Planned',
    className: isDark
      ? 'bg-slate-700/60 text-slate-300 border-slate-600'
      : 'bg-slate-100 text-slate-600 border-slate-200',
  };
}

export function CharityRecordRow({
  charity,
  isDark,
  onSetIntended,
  onLogDonation,
  onMarkConfirmed,
  onRemove,
  desktop = false,
  isEvenRow = false,
}: CharityRecordRowProps) {
  const [localIntended, setLocalIntended] = useState<string>(
    charity.intended ? String(charity.intended) : '',
  );

  useEffect(() => {
    setLocalIntended(charity.intended ? String(charity.intended) : '');
  }, [charity.intended]);

  const commit = () => {
    const n = parseInt(localIntended.replace(/\D/g, ''), 10) || 0;
    if (n !== charity.intended) onSetIntended(charity.ein, n);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      (e.target as HTMLInputElement).blur();
    }
  };

  const pill = statusPillClasses(charity.status, isDark);

  // Shared action button -----------------------------------------------------
  const actionButton = (() => {
    if (charity.status === 'intended') {
      return (
        <button
          type="button"
          data-testid={`record-log-${charity.ein}`}
          onClick={() => onLogDonation(charity.ein, charity.name)}
          className={`text-[11px] font-semibold px-2.5 py-1 rounded-md border transition-colors whitespace-nowrap ${
            isDark
              ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20'
              : 'text-emerald-700 border-emerald-200 bg-emerald-50 hover:bg-emerald-100'
          }`}
        >
          Log donation
        </button>
      );
    }
    if (charity.status === 'sent') {
      return (
        <button
          type="button"
          data-testid={`record-confirm-${charity.ein}`}
          onClick={() => onMarkConfirmed(charity.ein)}
          className={`text-[11px] font-semibold px-2.5 py-1 rounded-md border transition-colors whitespace-nowrap ${
            isDark
              ? 'text-amber-400 border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20'
              : 'text-amber-700 border-amber-200 bg-amber-50 hover:bg-amber-100'
          }`}
        >
          Mark confirmed
        </button>
      );
    }
    return (
      <span
        data-testid={`record-done-${charity.ein}`}
        className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-md border whitespace-nowrap ${
          isDark
            ? 'text-emerald-500 border-emerald-500/30 bg-emerald-500/10'
            : 'text-emerald-700 border-emerald-200 bg-emerald-50'
        }`}
      >
        <Check className="w-3 h-3" /> Confirmed
      </span>
    );
  })();

  // Shared intended input ----------------------------------------------------
  const intendedInput = (
    <div
      className={`inline-flex items-center px-2 py-0.5 rounded-md border ${
        isDark ? 'border-slate-700 bg-slate-800/50' : 'border-slate-200 bg-slate-50'
      } focus-within:border-emerald-500 transition-colors`}
    >
      <span className={`text-[11px] mr-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
        $
      </span>
      <input
        type="text"
        inputMode="numeric"
        data-testid={`record-intended-${charity.ein}`}
        value={localIntended}
        onChange={e => setLocalIntended(e.target.value.replace(/\D/g, ''))}
        onBlur={commit}
        onKeyDown={onKeyDown}
        placeholder="0"
        aria-label={`Intended amount for ${charity.name}`}
        className={`w-20 text-right bg-transparent border-0 focus:outline-none focus:ring-0 p-0 text-sm tabular-nums ${
          isDark ? 'text-slate-200 placeholder-slate-600' : 'text-slate-700 placeholder-slate-300'
        }`}
      />
    </div>
  );

  // Status chip --------------------------------------------------------------
  const statusChip = (
    <span
      data-testid={`record-status-${charity.ein}`}
      className={`inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full border ${pill.className}`}
    >
      {pill.label}
      {charity.status === 'confirmed' && (
        <Check className="w-3 h-3 ml-0.5" aria-hidden />
      )}
    </span>
  );

  // Desktop table row --------------------------------------------------------
  if (desktop) {
    const rowBg = isEvenRow && charity.bucketColor
      ? isDark
        ? `${charity.bucketColor}12`
        : `${charity.bucketColor}08`
      : undefined;
    return (
      <tr
        data-testid={`record-row-${charity.ein}`}
        className={`hidden sm:table-row border-b group transition-colors ${
          isDark ? 'border-slate-800/50 hover:bg-slate-800/40' : 'border-slate-100 hover:bg-slate-50'
        }`}
        style={{
          backgroundColor: rowBg,
          borderBottomColor: charity.bucketColor ? `${charity.bucketColor}25` : undefined,
        }}
      >
        <td
          className="w-1 p-0"
          style={{
            borderLeft: charity.bucketColor ? `4px solid ${charity.bucketColor}55` : undefined,
          }}
        />
        <td className="px-2.5 py-1.5">
          <Link
            to={`/charity/${charity.ein}`}
            className={`text-[13px] font-medium hover:underline ${
              isDark ? 'text-slate-200 hover:text-white' : 'text-slate-700 hover:text-slate-900'
            }`}
          >
            {charity.name}
          </Link>
        </td>
        <td className="px-2.5 py-1.5 text-right">{intendedInput}</td>
        <td className="px-2.5 py-1.5 text-right text-[13px] tabular-nums">
          {charity.given > 0 ? (
            <span className={isDark ? 'text-emerald-400 font-semibold' : 'text-emerald-700 font-semibold'}>
              {fmt(charity.given)}
            </span>
          ) : (
            <span className={isDark ? 'text-slate-600' : 'text-slate-300'}>—</span>
          )}
        </td>
        <td className="px-2.5 py-1.5">{statusChip}</td>
        <td className="px-2.5 py-1.5 text-right">
          <div className="flex items-center justify-end gap-1.5">
            {actionButton}
            {onRemove && (
              <button
                type="button"
                onClick={() => onRemove(charity.ein)}
                className={`p-1.5 rounded-md transition-colors opacity-40 hover:opacity-100 ${
                  isDark ? 'hover:bg-red-500/10' : 'hover:bg-red-50'
                }`}
                title={`Remove ${charity.name}`}
                aria-label={`Remove ${charity.name}`}
              >
                <X
                  className={`w-3.5 h-3.5 ${
                    isDark ? 'text-slate-500 hover:text-red-400' : 'text-slate-400 hover:text-red-500'
                  }`}
                />
              </button>
            )}
          </div>
        </td>
      </tr>
    );
  }

  // Mobile card --------------------------------------------------------------
  return (
    <div
      data-testid={`record-card-${charity.ein}`}
      className={`rounded-md border px-2.5 py-2 ${
        isDark ? 'border-slate-700 bg-slate-800/40' : 'border-slate-200 bg-slate-50/60'
      }`}
      style={{
        borderLeft: charity.bucketColor ? `4px solid ${charity.bucketColor}` : undefined,
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <Link
          to={`/charity/${charity.ein}`}
          className={`min-w-0 truncate text-[13px] font-medium ${
            isDark ? 'text-slate-200 hover:text-white' : 'text-slate-700 hover:text-slate-900'
          } hover:underline`}
        >
          {charity.name}
        </Link>
        <div className="shrink-0 flex items-center gap-1.5">
          {statusChip}
          {onRemove && (
            <button
              type="button"
              onClick={() => onRemove(charity.ein)}
              className={`p-1 rounded-md transition-colors ${
                isDark ? 'hover:bg-red-500/10' : 'hover:bg-red-50'
              }`}
              aria-label={`Remove ${charity.name}`}
            >
              <X
                className={`w-3.5 h-3.5 ${
                  isDark ? 'text-slate-500 hover:text-red-400' : 'text-slate-400 hover:text-red-500'
                }`}
              />
            </button>
          )}
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <div className={`text-[11px] ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          Given{' '}
          <span className={charity.given > 0 ? 'font-semibold text-emerald-500' : ''}>
            {fmt(charity.given || 0)}
          </span>
          {charity.intended > 0 && (
            <>
              {' '}· of {fmt(charity.intended)}
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          {intendedInput}
          {actionButton}
        </div>
      </div>
    </div>
  );
}

/**
 * Modal for adding or editing an in-kind donation
 * Optimized for high-volume entry (30-50 items per donation)
 *
 * Flow: Set recipient + date + default condition → rapid-fire item search → inline edits
 */

import React, { useState, useEffect, useCallback } from 'react';
import { AnimatePresence, m } from 'motion/react';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import { ItemPicker } from './ItemPicker';
import { CONDITION_DEFINITIONS, getMidpointValue, ALL_VALUE_GUIDE_ITEMS } from '../../data/donationValueGuide';
import type { InKindDonation, InKindDonationInput, InKindDonationItem } from '../../hooks/useInKindDonations';
import type { ItemCondition } from '../../data/donationValueGuide';

interface AddInKindModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (input: InKindDonationInput) => Promise<void>;
  existingDonation?: InKindDonation;
}

import { VALUE_GUIDE_SOURCES } from '../../data/donationValueGuide';
const CONDITIONS: ItemCondition[] = ['excellent', 'good', 'fair', 'poor'];
const CONDITION_LABELS: Record<ItemCondition, string> = {
  excellent: 'Excellent',
  good: 'Good',
  fair: 'Fair',
  poor: 'Poor',
};
const CONDITION_SHORT: Record<ItemCondition, string> = {
  excellent: 'Exc',
  good: 'Good',
  fair: 'Fair',
  poor: 'Poor',
};

export function AddInKindModal({
  isOpen,
  onClose,
  onSave,
  existingDonation,
}: AddInKindModalProps) {
  const { isDark } = useLandingTheme();
  const [isSaving, setIsSaving] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Header fields
  const [recipientName, setRecipientName] = useState('');
  const [recipientEin, setRecipientEin] = useState('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [notes, setNotes] = useState('');

  // Default condition for new items
  const [defaultCondition, setDefaultCondition] = useState<ItemCondition>('good');

  // Items
  const [items, setItems] = useState<InKindDonationItem[]>([]);

  const taxYear = new Date(date).getFullYear();
  const totalValue = items.reduce((sum, item) => sum + item.totalValue, 0);
  const totalItems = items.reduce((sum, item) => sum + item.quantity, 0);

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      if (existingDonation) {
        setRecipientName(existingDonation.recipientName);
        setRecipientEin(existingDonation.recipientEin || '');
        setDate(existingDonation.date);
        setNotes(existingDonation.notes || '');
        setItems([...existingDonation.items]);
      } else {
        setRecipientName('');
        setRecipientEin('');
        setDate(new Date().toISOString().split('T')[0]);
        setNotes('');
        setItems([]);
      }
      setDefaultCondition('good');
      setSubmitError(null);
    }
  }, [isOpen, existingDonation]);

  const handleAddItem = useCallback((item: InKindDonationItem) => {
    setItems(prev => [...prev, item]);
  }, []);

  const handleRemoveItem = useCallback((index: number) => {
    setItems(prev => prev.filter((_, i) => i !== index));
  }, []);

  const handleUpdateItem = useCallback((index: number, updates: Partial<InKindDonationItem>) => {
    setItems(prev => prev.map((item, i) => {
      if (i !== index) return item;
      const updated = { ...item, ...updates };

      // Recalculate value if condition changed and not manual
      if (updates.condition && !updated.isManualValue && updated.catalogItemId) {
        const guideItem = ALL_VALUE_GUIDE_ITEMS.find(g => g.id === updated.catalogItemId);
        if (guideItem) {
          updated.unitValue = getMidpointValue(guideItem, updated.condition);
        }
      }

      // Recalculate total
      updated.totalValue = updated.quantity * updated.unitValue;
      return updated;
    }));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recipientName.trim() || items.length === 0) return;

    setSubmitError(null);
    setIsSaving(true);

    try {
      await onSave({
        recipientName: recipientName.trim(),
        recipientEin: recipientEin.trim() || null,
        date,
        taxYear,
        items,
        notes: notes.trim() || null,
      });
      onClose();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to save donation');
    } finally {
      setIsSaving(false);
    }
  };

  const inputClass = `
    w-full px-3 py-2 rounded-lg border text-sm
    ${isDark
      ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-emerald-500'
      : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-emerald-500'
    }
    focus:outline-none focus:ring-1 focus:ring-emerald-500
  `;

  const labelClass = `block text-xs font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`;

  return (
    <AnimatePresence>
      {isOpen && (
        <m.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          {/* Backdrop */}
          <m.div
            className="absolute inset-0 bg-black/50"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />

          {/* Modal */}
          <m.div
            className={`
              relative w-full max-w-3xl max-h-[90vh] flex flex-col rounded-xl border shadow-xl
              ${isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}
            `}
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2 }}
          >
            <form onSubmit={handleSubmit} className="flex flex-col max-h-[90vh]">
              {/* ── Header: Recipient + Date + Condition ── */}
              <div className={`flex-shrink-0 px-5 py-4 border-b ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                <div className="flex items-center justify-between mb-3">
                  <h2 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {existingDonation ? 'Edit In-Kind Donation' : 'Log In-Kind Donation'}
                  </h2>
                  <button
                    type="button"
                    onClick={onClose}
                    className={`p-1 rounded-lg transition-colors ${isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-100'}`}
                  >
                    <svg className={`w-5 h-5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div>
                    <label className={labelClass}>Recipient *</label>
                    <input
                      type="text"
                      value={recipientName}
                      onChange={(e) => setRecipientName(e.target.value)}
                      className={inputClass}
                      placeholder="Goodwill..."
                      list="in-kind-recipients"
                      required
                    />
                    <datalist id="in-kind-recipients">
                      <option value="Goodwill" />
                      <option value="Salvation Army" />
                      <option value="Habitat for Humanity ReStore" />
                      <option value="Local Thrift Store" />
                    </datalist>
                  </div>
                  <div>
                    <label className={labelClass}>Date *</label>
                    <input
                      type="date"
                      value={date}
                      onChange={(e) => setDate(e.target.value)}
                      className={inputClass}
                      required
                    />
                  </div>
                  <div>
                    <label className={labelClass}>Default condition</label>
                    <select
                      value={defaultCondition}
                      onChange={(e) => setDefaultCondition(e.target.value as ItemCondition)}
                      className={inputClass}
                      title={CONDITION_DEFINITIONS[defaultCondition]}
                    >
                      {CONDITIONS.map(c => (
                        <option key={c} value={c}>{CONDITION_LABELS[c]}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className={labelClass}>EIN (optional)</label>
                    <input
                      type="text"
                      value={recipientEin}
                      onChange={(e) => setRecipientEin(e.target.value)}
                      className={inputClass}
                      placeholder="XX-XXXXXXX"
                    />
                  </div>
                </div>
              </div>

              {/* ── Search bar (always visible, sticky) ── */}
              <div className={`flex-shrink-0 px-5 py-3 border-b ${isDark ? 'border-slate-800 bg-slate-900/80' : 'border-slate-100 bg-white/80'}`}>
                <ItemPicker
                  defaultCondition={defaultCondition}
                  onAdd={handleAddItem}
                />
              </div>

              {/* ── Scrollable items list ── */}
              <div className="flex-grow overflow-y-auto min-h-0 px-5 py-3">
                {submitError && (
                  <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-500 text-sm mb-3">
                    {submitError}
                  </div>
                )}

                {items.length === 0 ? (
                  <div className={`text-center py-10 ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
                    <p className="text-sm">Start typing above to add items</p>
                    <p className={`text-xs mt-1 ${isDark ? 'text-slate-700' : 'text-slate-300'}`}>
                      Arrow keys to navigate, Enter to add
                    </p>
                  </div>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                        <th className="text-left py-1 font-medium">#</th>
                        <th className="text-left py-1 font-medium">Item</th>
                        <th className="text-center py-1 font-medium w-20">Cond.</th>
                        <th className="text-center py-1 font-medium w-16">Qty</th>
                        <th className="text-right py-1 font-medium w-20">Value</th>
                        <th className="text-right py-1 font-medium w-20">Total</th>
                        <th className="w-8"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item, index) => (
                        <ItemRow
                          key={index}
                          item={item}
                          index={index}
                          isDark={isDark}
                          onUpdate={(updates) => handleUpdateItem(index, updates)}
                          onRemove={() => handleRemoveItem(index)}
                        />
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* ── Footer: totals + warnings + save ── */}
              <div className={`flex-shrink-0 px-5 py-3 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                {/* IRS warnings */}
                {totalValue > 5000 && (
                  <div className={`p-2 rounded-lg text-xs mb-2 ${isDark ? 'bg-red-500/10 text-red-400' : 'bg-red-50 text-red-700'}`}>
                    <strong>IRS:</strong> Non-cash donations over $5,000 require a qualified appraisal and Form 8283 Section B with your tax return.
                  </div>
                )}
                {totalValue > 500 && totalValue <= 5000 && (
                  <div className={`p-2 rounded-lg text-xs mb-2 ${isDark ? 'bg-amber-500/10 text-amber-400' : 'bg-amber-50 text-amber-700'}`}>
                    <strong>IRS:</strong> If your total non-cash donations for the year exceed $500, you need to file Form 8283 (Noncash Charitable Contributions) with your tax return.
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <div className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {items.length > 0 ? (
                      <>
                        <strong className={`text-lg ${isDark ? 'text-white' : 'text-slate-900'}`}>
                          ${totalValue.toFixed(2)}
                        </strong>
                        <span className="ml-2">
                          {totalItems} item{totalItems !== 1 ? 's' : ''}
                        </span>
                      </>
                    ) : (
                      <span className={`text-xs ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
                        Estimates based on{' '}
                        {VALUE_GUIDE_SOURCES.map((s, i) => (
                          <span key={s.url}>
                            {i > 0 && ' and '}
                            <a href={s.url} target="_blank" rel="noopener noreferrer" className="underline hover:text-emerald-500">{s.name}</a>
                          </span>
                        ))}
                        . Consult a tax professional.
                      </span>
                    )}
                  </div>

                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={onClose}
                      disabled={isSaving}
                      className={`
                        px-4 py-2 rounded-lg text-sm font-medium transition-colors
                        ${isDark
                          ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                        }
                        disabled:opacity-50
                      `}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isSaving || items.length === 0 || !recipientName.trim()}
                      className="px-4 py-2 rounded-lg text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700 transition-colors disabled:opacity-50 flex items-center gap-2"
                    >
                      {isSaving && (
                        <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                      )}
                      {existingDonation ? 'Save Changes' : 'Save'}
                    </button>
                  </div>
                </div>

                {/* Notes toggle */}
                {items.length > 0 && (
                  <div className="mt-2">
                    <input
                      type="text"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      className={`w-full px-3 py-1.5 rounded-lg border text-xs ${
                        isDark
                          ? 'bg-slate-800 border-slate-700 text-slate-300 placeholder-slate-600'
                          : 'bg-slate-50 border-slate-200 text-slate-700 placeholder-slate-400'
                      } focus:outline-none focus:ring-1 focus:ring-emerald-500`}
                      placeholder="Optional notes..."
                    />
                  </div>
                )}
              </div>
            </form>
          </m.div>
        </m.div>
      )}
    </AnimatePresence>
  );
}

// ────────────────────────────────────────────────────────
// Inline-editable item row
// ────────────────────────────────────────────────────────

function ItemRow({
  item,
  index,
  isDark,
  onUpdate,
  onRemove,
}: {
  item: InKindDonationItem;
  index: number;
  isDark: boolean;
  onUpdate: (updates: Partial<InKindDonationItem>) => void;
  onRemove: () => void;
}) {
  const cellClass = `py-1.5 ${isDark ? 'border-slate-800' : 'border-slate-50'}`;
  const miniSelectClass = `
    text-xs px-1 py-0.5 rounded border appearance-none cursor-pointer
    ${isDark
      ? 'bg-slate-800 border-slate-700 text-slate-300'
      : 'bg-slate-50 border-slate-200 text-slate-700'
    }
    focus:outline-none focus:ring-1 focus:ring-emerald-500
  `;
  const miniInputClass = `
    text-xs px-1.5 py-0.5 rounded border text-right w-full
    ${isDark
      ? 'bg-slate-800 border-slate-700 text-slate-300'
      : 'bg-slate-50 border-slate-200 text-slate-700'
    }
    focus:outline-none focus:ring-1 focus:ring-emerald-500
  `;

  return (
    <tr className={`border-t ${isDark ? 'border-slate-800/50' : 'border-slate-100'}`}>
      <td className={`${cellClass} text-xs ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
        {index + 1}
      </td>
      <td className={cellClass}>
        <div className={`text-sm truncate max-w-[200px] ${isDark ? 'text-slate-200' : 'text-slate-800'}`} title={item.itemName}>
          {item.itemName}
        </div>
        <div className={`text-xs ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
          {item.category}
        </div>
      </td>
      <td className={`${cellClass} text-center`}>
        <select
          value={item.condition}
          onChange={(e) => onUpdate({ condition: e.target.value as ItemCondition })}
          className={miniSelectClass}
        >
          {CONDITIONS.map(c => (
            <option key={c} value={c}>{CONDITION_SHORT[c]}</option>
          ))}
        </select>
      </td>
      <td className={`${cellClass} text-center`}>
        <div className="flex items-center justify-center gap-0.5">
          <button
            type="button"
            onClick={() => onUpdate({ quantity: Math.max(1, item.quantity - 1) })}
            className={`w-5 h-5 rounded text-xs flex items-center justify-center ${
              isDark ? 'hover:bg-slate-700 text-slate-400' : 'hover:bg-slate-200 text-slate-500'
            } ${item.quantity <= 1 ? 'opacity-30 cursor-default' : ''}`}
            disabled={item.quantity <= 1}
          >
            -
          </button>
          <span className={`w-6 text-center text-xs font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
            {item.quantity}
          </span>
          <button
            type="button"
            onClick={() => onUpdate({ quantity: item.quantity + 1 })}
            className={`w-5 h-5 rounded text-xs flex items-center justify-center ${
              isDark ? 'hover:bg-slate-700 text-slate-400' : 'hover:bg-slate-200 text-slate-500'
            }`}
          >
            +
          </button>
        </div>
      </td>
      <td className={cellClass}>
        <input
          type="number"
          value={item.unitValue || ''}
          onChange={(e) => {
            const val = parseFloat(e.target.value) || 0;
            onUpdate({ unitValue: val, isManualValue: true });
          }}
          className={miniInputClass}
          step="0.01"
          min="0"
        />
      </td>
      <td className={`${cellClass} text-right`}>
        <span className={`text-xs font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
          ${item.totalValue.toFixed(2)}
        </span>
      </td>
      <td className={cellClass}>
        <button
          type="button"
          onClick={onRemove}
          className={`p-0.5 rounded transition-colors ${isDark ? 'hover:bg-red-500/20 text-red-400/60 hover:text-red-400' : 'hover:bg-red-50 text-red-300 hover:text-red-500'}`}
          title="Remove"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </td>
    </tr>
  );
}

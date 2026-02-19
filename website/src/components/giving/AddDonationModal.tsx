/**
 * Modal for adding or editing a donation entry
 * Uses React Hook Form + Zod for validation, Motion for animations
 */

import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { AnimatePresence, m } from 'motion/react';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import type { GivingHistoryEntry } from '../../../types';
import type { DonationInput } from '../../hooks/useGivingHistory';

// --------------- Zod schema ---------------
const donationSchema = z.object({
  charityName: z.string().min(1, 'Charity name is required'),
  charityEin: z.string().optional().default(''),
  amount: z.coerce.number().positive('Amount must be greater than 0'),
  date: z.string().min(1, 'Date is required'),
  category: z.enum(['zakat', 'sadaqah', 'other']),
  zakatYear: z.string().optional().default(''),
  paymentSource: z.string().optional().default(''),
  receiptReceived: z.boolean(),
  taxDeductible: z.boolean(),
  matchEligible: z.boolean(),
  matchStatus: z.string().optional().default(''),
  matchAmount: z.string().optional().default(''),
  notes: z.string().optional().default(''),
});

type DonationFormValues = z.output<typeof donationSchema>;

// --------------- Component ---------------
interface AddDonationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (donation: DonationInput) => Promise<void>;
  existingDonation?: GivingHistoryEntry;
  paymentSources: string[];
  prefillCharity?: { ein: string; name: string };
}

function buildDefaults(
  existing?: GivingHistoryEntry,
  prefill?: { ein: string; name: string },
): DonationFormValues {
  if (existing) {
    return {
      charityName: existing.charityName,
      charityEin: existing.charityEin || '',
      amount: existing.amount,
      date: existing.date,
      category: existing.category,
      zakatYear: existing.zakatYear?.toString() || '',
      paymentSource: existing.paymentSource || '',
      receiptReceived: existing.receiptReceived,
      taxDeductible: existing.taxDeductible,
      matchEligible: existing.matchEligible,
      matchStatus: existing.matchStatus || '',
      matchAmount: existing.matchAmount?.toString() || '',
      notes: existing.notes || '',
    };
  }

  return {
    charityName: prefill?.name || '',
    charityEin: prefill?.ein || '',
    amount: '' as unknown as number, // empty field renders blank
    date: new Date().toISOString().split('T')[0],
    category: 'zakat',
    zakatYear: new Date().getFullYear().toString(),
    paymentSource: '',
    receiptReceived: false,
    taxDeductible: true,
    matchEligible: false,
    matchStatus: '',
    matchAmount: '',
    notes: '',
  };
}

export function AddDonationModal({
  isOpen,
  onClose,
  onSave,
  existingDonation,
  paymentSources,
  prefillCharity,
}: AddDonationModalProps) {
  const { isDark } = useLandingTheme();
  const [isSaving, setIsSaving] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setFocus,
    formState: { errors },
  } = useForm<DonationFormValues>({
    resolver: zodResolver(donationSchema) as any,
    defaultValues: buildDefaults(existingDonation, prefillCharity),
  });

  const category = watch('category');
  const matchEligible = watch('matchEligible');

  // Reset form when modal opens with new data
  useEffect(() => {
    if (isOpen) {
      reset(buildDefaults(existingDonation, prefillCharity));
      setSubmitError(null);
      // Focus charity name after animation settles
      setTimeout(() => {
        try { setFocus('charityName'); } catch { /* field may not be mounted yet */ }
      }, 100);
    }
  }, [isOpen, existingDonation, prefillCharity, reset, setFocus]);

  const onSubmit = async (values: DonationFormValues) => {
    setSubmitError(null);
    setIsSaving(true);

    try {
      const donation: DonationInput = {
        charityName: values.charityName.trim(),
        charityEin: values.charityEin?.trim() || null,
        amount: values.amount,
        date: values.date,
        category: values.category,
        zakatYear: values.category === 'zakat' && values.zakatYear ? parseInt(values.zakatYear) : null,
        paymentSource: values.paymentSource?.trim() || null,
        receiptReceived: values.receiptReceived,
        taxDeductible: values.taxDeductible,
        matchEligible: values.matchEligible,
        matchStatus: values.matchEligible && values.matchStatus ? (values.matchStatus as 'submitted' | 'received') : null,
        matchAmount: values.matchEligible && values.matchAmount ? parseFloat(values.matchAmount) : null,
        notes: values.notes?.trim() || null,
      };

      await onSave(donation);
      onClose();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to save donation');
    } finally {
      setIsSaving(false);
    }
  };

  const inputClass = `
    w-full px-3 py-2 rounded-lg border
    ${isDark
      ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-emerald-500'
      : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-emerald-500'
    }
    focus:outline-none focus:ring-1 focus:ring-emerald-500
  `;

  const labelClass = `block text-sm font-medium mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`;

  const fieldError = (name: keyof DonationFormValues) =>
    errors[name] ? (
      <p className="text-red-500 text-xs mt-1">{errors[name]?.message as string}</p>
    ) : null;

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
          relative w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-xl border shadow-xl
          ${isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}
        `}
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        transition={{ duration: 0.2 }}
      >
        <form onSubmit={handleSubmit(onSubmit as any)}>
          {/* Header */}
          <div className={`sticky top-0 px-6 py-4 border-b ${isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`}>
            <div className="flex items-center justify-between">
              <h2 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                {existingDonation ? 'Edit Donation' : 'Log Donation'}
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
          </div>

          {/* Body */}
          <div className="px-6 py-4 space-y-4">
            {submitError && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-500 text-sm">
                {submitError}
              </div>
            )}

            {/* Charity Name */}
            <div>
              <label className={labelClass}>Charity Name *</label>
              <input
                {...register('charityName')}
                type="text"
                className={inputClass}
                placeholder="Enter charity name"
              />
              {fieldError('charityName')}
            </div>

            {/* Charity EIN (optional) */}
            <div>
              <label className={labelClass}>EIN (optional)</label>
              <input
                {...register('charityEin')}
                type="text"
                className={inputClass}
                placeholder="XX-XXXXXXX"
              />
            </div>

            {/* Amount and Date */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Amount *</label>
                <div className="relative">
                  <span className={`absolute left-3 top-1/2 -translate-y-1/2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>$</span>
                  <input
                    {...register('amount')}
                    type="number"
                    className={`${inputClass} pl-7`}
                    placeholder="0.00"
                    step="0.01"
                    min="0"
                  />
                </div>
                {fieldError('amount')}
              </div>
              <div>
                <label className={labelClass}>Date *</label>
                <input
                  {...register('date')}
                  type="date"
                  className={inputClass}
                />
                {fieldError('date')}
              </div>
            </div>

            {/* Category and Zakat Year */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Category *</label>
                <select
                  {...register('category')}
                  className={inputClass}
                >
                  <option value="zakat">Zakat</option>
                  <option value="sadaqah">Sadaqah</option>
                  <option value="other">Other</option>
                </select>
              </div>
              {category === 'zakat' && (
                <div>
                  <label className={labelClass}>Zakat Year</label>
                  <input
                    {...register('zakatYear')}
                    type="number"
                    className={inputClass}
                    placeholder={new Date().getFullYear().toString()}
                    min="2000"
                    max="2100"
                  />
                </div>
              )}
            </div>

            {/* Payment Source */}
            <div>
              <label className={labelClass}>Payment Source</label>
              <input
                {...register('paymentSource')}
                type="text"
                className={inputClass}
                placeholder="e.g., Chase Credit Card, Bank Transfer"
                list="payment-sources"
              />
              <datalist id="payment-sources">
                {paymentSources.map(source => (
                  <option key={source} value={source} />
                ))}
              </datalist>
            </div>

            {/* Checkboxes */}
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  {...register('receiptReceived')}
                  type="checkbox"
                  className="w-4 h-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
                <span className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>Receipt received</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  {...register('taxDeductible')}
                  type="checkbox"
                  className="w-4 h-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
                <span className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>Tax deductible</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  {...register('matchEligible')}
                  type="checkbox"
                  className="w-4 h-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
                <span className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>Match eligible</span>
              </label>
            </div>

            {/* Match details (conditional) */}
            {matchEligible && (
              <div className="grid grid-cols-2 gap-4 pl-6 border-l-2 border-emerald-500/30">
                <div>
                  <label className={labelClass}>Match Status</label>
                  <select
                    {...register('matchStatus')}
                    className={inputClass}
                  >
                    <option value="">Not submitted</option>
                    <option value="submitted">Submitted</option>
                    <option value="received">Received</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass}>Match Amount</label>
                  <div className="relative">
                    <span className={`absolute left-3 top-1/2 -translate-y-1/2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>$</span>
                    <input
                      {...register('matchAmount')}
                      type="number"
                      className={`${inputClass} pl-7`}
                      placeholder="0.00"
                      step="0.01"
                      min="0"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Notes */}
            <div>
              <label className={labelClass}>Notes</label>
              <textarea
                {...register('notes')}
                className={`${inputClass} resize-none`}
                rows={2}
                placeholder="Optional notes..."
              />
            </div>
          </div>

          {/* Footer */}
          <div className={`sticky bottom-0 px-6 py-4 border-t flex justify-end gap-3 ${isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`}>
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className={`
                px-4 py-2 rounded-lg font-medium transition-colors
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
              disabled={isSaving}
              className="px-4 py-2 rounded-lg font-medium bg-emerald-600 text-white hover:bg-emerald-700 transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              {isSaving && (
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              )}
              {existingDonation ? 'Save Changes' : 'Add Donation'}
            </button>
          </div>
        </form>
      </m.div>
    </m.div>
    )}
    </AnimatePresence>
  );
}

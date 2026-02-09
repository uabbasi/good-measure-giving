/**
 * Hook for managing giving history (donation tracking)
 * ItsDeductible-style donation log with CRUD, summaries, and export
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useSupabase } from '../auth/SupabaseProvider';
import type { GivingHistoryEntry } from '../../types';

export interface DonationInput {
  charityEin?: string | null;
  charityName: string;
  amount: number;
  date: string; // ISO date
  category: 'zakat' | 'sadaqah' | 'other';
  zakatYear?: number | null;
  paymentSource?: string | null;
  receiptReceived?: boolean;
  taxDeductible?: boolean;
  matchEligible?: boolean;
  matchStatus?: 'submitted' | 'received' | null;
  matchAmount?: number | null;
  notes?: string | null;
}

export interface YearSummary {
  year: number;
  totalZakat: number;
  totalSadaqah: number;
  totalOther: number;
  total: number;
  donationCount: number;
  matchedAmount: number;
}

export interface CategorySummary {
  category: 'zakat' | 'sadaqah' | 'other';
  total: number;
  donationCount: number;
  charities: string[]; // Unique charity names
}

interface UseGivingHistoryResult {
  donations: GivingHistoryEntry[];
  isLoading: boolean;
  error: string | null;
  addDonation: (input: DonationInput) => Promise<GivingHistoryEntry>;
  updateDonation: (id: string, updates: Partial<DonationInput>) => Promise<void>;
  deleteDonation: (id: string) => Promise<void>;
  getYearSummary: (year: number) => YearSummary;
  getCategorySummary: (category: 'zakat' | 'sadaqah' | 'other') => CategorySummary;
  getPaymentSources: () => string[];
  getCharityTotal: (ein: string, zakatYear?: number) => number;
  exportCSV: (year?: number) => string;
  refreshDonations: () => Promise<void>;
}

// Convert snake_case DB row to camelCase
function dbToDonation(row: Record<string, unknown>): GivingHistoryEntry {
  return {
    id: row.id as string,
    userId: row.user_id as string,
    charityEin: row.charity_ein as string | null,
    charityName: row.charity_name as string,
    amount: Number(row.amount),
    date: row.date as string,
    category: row.category as 'zakat' | 'sadaqah' | 'other',
    zakatYear: row.zakat_year as number | null,
    paymentSource: row.payment_source as string | null,
    receiptReceived: (row.receipt_received as boolean) ?? false,
    taxDeductible: (row.tax_deductible as boolean) ?? true,
    matchEligible: (row.match_eligible as boolean) ?? false,
    matchStatus: row.match_status as 'submitted' | 'received' | null,
    matchAmount: row.match_amount ? Number(row.match_amount) : null,
    notes: row.notes as string | null,
    createdAt: row.created_at as string,
  };
}

// Convert camelCase input to snake_case for DB
function inputToDb(input: DonationInput): Record<string, unknown> {
  return {
    charity_ein: input.charityEin ?? null,
    charity_name: input.charityName,
    amount: input.amount,
    date: input.date,
    category: input.category,
    zakat_year: input.zakatYear ?? null,
    payment_source: input.paymentSource ?? null,
    receipt_received: input.receiptReceived ?? false,
    tax_deductible: input.taxDeductible ?? true,
    match_eligible: input.matchEligible ?? false,
    match_status: input.matchStatus ?? null,
    match_amount: input.matchAmount ?? null,
    notes: input.notes ?? null,
  };
}

export function useGivingHistory(): UseGivingHistoryResult {
  const { supabase, session } = useSupabase();
  const [donations, setDonations] = useState<GivingHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const userId = session?.user?.id;

  // Fetch all donations
  const fetchDonations = useCallback(async () => {
    if (!supabase || !userId) {
      setDonations([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const { data, error: fetchError } = await supabase
        .from('giving_history')
        .select('*')
        .eq('user_id', userId)
        .order('date', { ascending: false });

      if (fetchError) throw fetchError;
      setDonations((data || []).map(dbToDonation));
    } catch (err) {
      console.error('Error fetching donations:', err);
      setError(err instanceof Error ? err.message : 'Failed to load donations');
    } finally {
      setIsLoading(false);
    }
  }, [supabase, userId]);

  useEffect(() => {
    fetchDonations();
  }, [fetchDonations]);

  // Add a new donation
  const addDonation = useCallback(async (input: DonationInput): Promise<GivingHistoryEntry> => {
    if (!supabase || !userId) {
      throw new Error('Not authenticated');
    }

    setError(null);

    try {
      const dbData = { ...inputToDb(input), user_id: userId };
      const { data, error: insertError } = await supabase
        .from('giving_history')
        .insert(dbData)
        .select()
        .single();

      if (insertError) throw insertError;

      const newDonation = dbToDonation(data);
      // Insert at correct position based on date
      setDonations(prev => {
        const updated = [...prev, newDonation];
        return updated.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
      });
      return newDonation;
    } catch (err) {
      console.error('Error adding donation:', err);
      const message = err instanceof Error ? err.message : 'Failed to add donation';
      setError(message);
      throw new Error(message);
    }
  }, [supabase, userId]);

  // Update an existing donation
  const updateDonation = useCallback(async (id: string, updates: Partial<DonationInput>) => {
    if (!supabase || !userId) {
      throw new Error('Not authenticated');
    }

    const existing = donations.find(d => d.id === id);
    if (!existing) throw new Error('Donation not found');

    // Optimistic update
    const dbUpdates: Record<string, unknown> = {};
    if (updates.charityEin !== undefined) dbUpdates.charity_ein = updates.charityEin;
    if (updates.charityName !== undefined) dbUpdates.charity_name = updates.charityName;
    if (updates.amount !== undefined) dbUpdates.amount = updates.amount;
    if (updates.date !== undefined) dbUpdates.date = updates.date;
    if (updates.category !== undefined) dbUpdates.category = updates.category;
    if (updates.zakatYear !== undefined) dbUpdates.zakat_year = updates.zakatYear;
    if (updates.paymentSource !== undefined) dbUpdates.payment_source = updates.paymentSource;
    if (updates.receiptReceived !== undefined) dbUpdates.receipt_received = updates.receiptReceived;
    if (updates.taxDeductible !== undefined) dbUpdates.tax_deductible = updates.taxDeductible;
    if (updates.matchEligible !== undefined) dbUpdates.match_eligible = updates.matchEligible;
    if (updates.matchStatus !== undefined) dbUpdates.match_status = updates.matchStatus;
    if (updates.matchAmount !== undefined) dbUpdates.match_amount = updates.matchAmount;
    if (updates.notes !== undefined) dbUpdates.notes = updates.notes;

    setError(null);

    try {
      const { error: updateError } = await supabase
        .from('giving_history')
        .update(dbUpdates)
        .eq('id', id)
        .eq('user_id', userId);

      if (updateError) throw updateError;

      // Refresh to get updated data with correct sorting
      await fetchDonations();
    } catch (err) {
      console.error('Error updating donation:', err);
      const message = err instanceof Error ? err.message : 'Failed to update donation';
      setError(message);
      throw new Error(message);
    }
  }, [supabase, userId, donations, fetchDonations]);

  // Delete a donation
  const deleteDonation = useCallback(async (id: string) => {
    if (!supabase || !userId) {
      throw new Error('Not authenticated');
    }

    const existing = donations.find(d => d.id === id);
    if (!existing) return;

    // Optimistic update
    setDonations(prev => prev.filter(d => d.id !== id));
    setError(null);

    try {
      const { error: deleteError } = await supabase
        .from('giving_history')
        .delete()
        .eq('id', id)
        .eq('user_id', userId);

      if (deleteError) throw deleteError;
    } catch (err) {
      // Rollback
      setDonations(prev => [...prev, existing].sort((a, b) =>
        new Date(b.date).getTime() - new Date(a.date).getTime()
      ));
      console.error('Error deleting donation:', err);
      const message = err instanceof Error ? err.message : 'Failed to delete donation';
      setError(message);
      throw new Error(message);
    }
  }, [supabase, userId, donations]);

  // Get summary for a specific year
  const getYearSummary = useCallback((year: number): YearSummary => {
    const yearDonations = donations.filter(d => {
      // For zakat, use zakatYear; for others, use calendar year of date
      if (d.category === 'zakat') {
        return d.zakatYear === year;
      }
      return new Date(d.date).getFullYear() === year;
    });

    const totalZakat = yearDonations
      .filter(d => d.category === 'zakat')
      .reduce((sum, d) => sum + d.amount, 0);

    const totalSadaqah = yearDonations
      .filter(d => d.category === 'sadaqah')
      .reduce((sum, d) => sum + d.amount, 0);

    const totalOther = yearDonations
      .filter(d => d.category === 'other')
      .reduce((sum, d) => sum + d.amount, 0);

    const matchedAmount = yearDonations
      .filter(d => d.matchStatus === 'received' && d.matchAmount)
      .reduce((sum, d) => sum + (d.matchAmount || 0), 0);

    return {
      year,
      totalZakat,
      totalSadaqah,
      totalOther,
      total: totalZakat + totalSadaqah + totalOther,
      donationCount: yearDonations.length,
      matchedAmount,
    };
  }, [donations]);

  // Get summary for a category
  const getCategorySummary = useCallback((category: 'zakat' | 'sadaqah' | 'other'): CategorySummary => {
    const categoryDonations = donations.filter(d => d.category === category);
    const charities = [...new Set(categoryDonations.map(d => d.charityName))];

    return {
      category,
      total: categoryDonations.reduce((sum, d) => sum + d.amount, 0),
      donationCount: categoryDonations.length,
      charities,
    };
  }, [donations]);

  // Get unique payment sources for autocomplete
  const getPaymentSources = useCallback((): string[] => {
    const sources = donations
      .map(d => d.paymentSource)
      .filter((s): s is string => s !== null && s.trim() !== '');
    return [...new Set(sources)].sort();
  }, [donations]);

  // Get total donated to a specific charity (optionally filtered by zakat year)
  const getCharityTotal = useCallback((ein: string, zakatYear?: number): number => {
    return donations
      .filter(d => {
        if (d.charityEin !== ein) return false;
        if (zakatYear !== undefined && d.zakatYear !== zakatYear) return false;
        return true;
      })
      .reduce((sum, d) => sum + d.amount, 0);
  }, [donations]);

  // Export donations as CSV
  const exportCSV = useCallback((year?: number): string => {
    let filtered = donations;
    if (year !== undefined) {
      filtered = donations.filter(d => {
        if (d.category === 'zakat') return d.zakatYear === year;
        return new Date(d.date).getFullYear() === year;
      });
    }

    const headers = [
      'Date',
      'Charity',
      'EIN',
      'Amount',
      'Category',
      'Zakat Year',
      'Payment Source',
      'Receipt',
      'Tax Deductible',
      'Match Eligible',
      'Match Status',
      'Match Amount',
      'Notes',
    ];

    const rows = filtered.map(d => [
      d.date,
      `"${d.charityName.replace(/"/g, '""')}"`,
      d.charityEin || '',
      d.amount.toFixed(2),
      d.category,
      d.zakatYear?.toString() || '',
      d.paymentSource || '',
      d.receiptReceived ? 'Yes' : 'No',
      d.taxDeductible ? 'Yes' : 'No',
      d.matchEligible ? 'Yes' : 'No',
      d.matchStatus || '',
      d.matchAmount?.toFixed(2) || '',
      d.notes ? `"${d.notes.replace(/"/g, '""')}"` : '',
    ]);

    return [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
  }, [donations]);

  return {
    donations,
    isLoading,
    error,
    addDonation,
    updateDonation,
    deleteDonation,
    getYearSummary,
    getCategorySummary,
    getPaymentSources,
    getCharityTotal,
    exportCSV,
    refreshDonations: fetchDonations,
  };
}

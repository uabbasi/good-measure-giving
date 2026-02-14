/**
 * Hook for managing giving history (donation tracking)
 * ItsDeductible-style donation log with CRUD, summaries, and export
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { collection, doc, getDocs, addDoc, updateDoc, deleteDoc, orderBy, query, Timestamp } from 'firebase/firestore';
import { useFirebaseData } from '../auth/FirebaseProvider';
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

function docToDonation(data: Record<string, unknown>, docId: string, userId: string): GivingHistoryEntry {
  return {
    id: docId,
    userId,
    charityEin: (data.charityEin as string) || null,
    charityName: data.charityName as string,
    amount: Number(data.amount),
    date: data.date as string,
    category: data.category as 'zakat' | 'sadaqah' | 'other',
    zakatYear: (data.zakatYear as number) || null,
    paymentSource: (data.paymentSource as string) || null,
    receiptReceived: (data.receiptReceived as boolean) ?? false,
    taxDeductible: (data.taxDeductible as boolean) ?? true,
    matchEligible: (data.matchEligible as boolean) ?? false,
    matchStatus: (data.matchStatus as 'submitted' | 'received') || null,
    matchAmount: data.matchAmount != null ? Number(data.matchAmount) : null,
    notes: (data.notes as string) || null,
    createdAt: data.createdAt instanceof Timestamp
      ? data.createdAt.toDate().toISOString()
      : (data.createdAt as string) || new Date().toISOString(),
  };
}

function inputToFirestore(input: DonationInput): Record<string, unknown> {
  return {
    charityEin: input.charityEin ?? null,
    charityName: input.charityName,
    amount: input.amount,
    date: input.date,
    category: input.category,
    zakatYear: input.zakatYear ?? null,
    paymentSource: input.paymentSource ?? null,
    receiptReceived: input.receiptReceived ?? false,
    taxDeductible: input.taxDeductible ?? true,
    matchEligible: input.matchEligible ?? false,
    matchStatus: input.matchStatus ?? null,
    matchAmount: input.matchAmount ?? null,
    notes: input.notes ?? null,
  };
}

export function useGivingHistory(): UseGivingHistoryResult {
  const { db, userId } = useFirebaseData();
  const [donations, setDonations] = useState<GivingHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch all donations
  const fetchDonations = useCallback(async () => {
    if (!db || !userId) {
      setDonations([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const colRef = collection(db, 'users', userId, 'giving_history');
      const q = query(colRef, orderBy('date', 'desc'));
      const snapshot = await getDocs(q);
      setDonations(snapshot.docs.map(d => docToDonation(d.data(), d.id, userId)));
    } catch (err) {
      console.error('Error fetching donations:', err);
      setError(err instanceof Error ? err.message : 'Failed to load donations');
    } finally {
      setIsLoading(false);
    }
  }, [db, userId]);

  useEffect(() => {
    fetchDonations();
  }, [fetchDonations]);

  // Add a new donation
  const addDonation = useCallback(async (input: DonationInput): Promise<GivingHistoryEntry> => {
    if (!db || !userId) {
      throw new Error('Not authenticated');
    }

    setError(null);

    try {
      const colRef = collection(db, 'users', userId, 'giving_history');
      const data = { ...inputToFirestore(input), createdAt: Timestamp.now() };
      const docRef = await addDoc(colRef, data);

      const newDonation = docToDonation(data, docRef.id, userId);
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
  }, [db, userId]);

  // Update an existing donation
  const updateDonation = useCallback(async (id: string, updates: Partial<DonationInput>) => {
    if (!db || !userId) {
      throw new Error('Not authenticated');
    }

    const existing = donations.find(d => d.id === id);
    if (!existing) throw new Error('Donation not found');

    setError(null);

    try {
      const docRef = doc(db, 'users', userId, 'giving_history', id);
      // Build partial update from provided fields
      const firestoreUpdates = Object.fromEntries(
        Object.entries(updates).filter(([, v]) => v !== undefined)
      );

      await updateDoc(docRef, firestoreUpdates);

      // Refresh to get updated data with correct sorting
      await fetchDonations();
    } catch (err) {
      console.error('Error updating donation:', err);
      const message = err instanceof Error ? err.message : 'Failed to update donation';
      setError(message);
      throw new Error(message);
    }
  }, [db, userId, donations, fetchDonations]);

  // Delete a donation
  const deleteDonation = useCallback(async (id: string) => {
    if (!db || !userId) {
      throw new Error('Not authenticated');
    }

    const existing = donations.find(d => d.id === id);
    if (!existing) return;

    // Optimistic update
    setDonations(prev => prev.filter(d => d.id !== id));
    setError(null);

    try {
      const docRef = doc(db, 'users', userId, 'giving_history', id);
      await deleteDoc(docRef);
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
  }, [db, userId, donations]);

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

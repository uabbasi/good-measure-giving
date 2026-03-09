/**
 * Hook for managing in-kind (non-cash) donation tracking
 * Follows useGivingHistory.ts pattern: Firestore CRUD with optimistic local state
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { collection, doc, getDocs, addDoc, updateDoc, deleteDoc, orderBy, query, Timestamp } from 'firebase/firestore';
import { useFirebaseData } from '../auth/FirebaseProvider';
import type { ItemCondition } from '../data/donationValueGuide';

// --------------- Types ---------------

export interface InKindDonationItem {
  category: string;
  itemName: string;
  catalogItemId: string | null;
  condition: ItemCondition;
  quantity: number;
  unitValue: number;
  isManualValue: boolean;
  totalValue: number;
}

export interface InKindDonation {
  id: string;
  userId: string;
  recipientName: string;
  recipientEin: string | null;
  date: string;
  taxYear: number;
  items: InKindDonationItem[];
  totalValue: number;
  notes: string | null;
  createdAt: string;
}

export interface InKindDonationInput {
  recipientName: string;
  recipientEin?: string | null;
  date: string;
  taxYear: number;
  items: InKindDonationItem[];
  notes?: string | null;
}

export interface InKindYearSummary {
  year: number;
  totalValue: number;
  donationCount: number;
  itemCount: number;
  categoryBreakdown: { category: string; total: number; itemCount: number }[];
  recipientBreakdown: { name: string; total: number }[];
}

interface UseInKindDonationsResult {
  donations: InKindDonation[];
  isLoading: boolean;
  error: string | null;
  addDonation: (input: InKindDonationInput) => Promise<InKindDonation>;
  updateDonation: (id: string, input: InKindDonationInput) => Promise<void>;
  deleteDonation: (id: string) => Promise<void>;
  getYearSummary: (year: number) => InKindYearSummary;
  exportCSV: (year?: number) => string;
  refreshDonations: () => Promise<void>;
}

// --------------- Converters ---------------

function docToDonation(data: Record<string, unknown>, docId: string, userId: string): InKindDonation {
  const items = (data.items as Record<string, unknown>[] || []).map(item => ({
    category: item.category as string,
    itemName: item.itemName as string,
    catalogItemId: (item.catalogItemId as string) || null,
    condition: item.condition as ItemCondition,
    quantity: Number(item.quantity),
    unitValue: Number(item.unitValue),
    isManualValue: (item.isManualValue as boolean) ?? false,
    totalValue: Number(item.totalValue),
  }));

  return {
    id: docId,
    userId,
    recipientName: data.recipientName as string,
    recipientEin: (data.recipientEin as string) || null,
    date: data.date as string,
    taxYear: Number(data.taxYear),
    items,
    totalValue: Number(data.totalValue),
    notes: (data.notes as string) || null,
    createdAt: data.createdAt instanceof Timestamp
      ? data.createdAt.toDate().toISOString()
      : (data.createdAt as string) || new Date().toISOString(),
  };
}

function inputToFirestore(input: InKindDonationInput): Record<string, unknown> {
  const totalValue = input.items.reduce((sum, item) => sum + item.totalValue, 0);
  return {
    recipientName: input.recipientName,
    recipientEin: input.recipientEin ?? null,
    date: input.date,
    taxYear: input.taxYear,
    items: input.items.map(item => ({
      category: item.category,
      itemName: item.itemName,
      catalogItemId: item.catalogItemId ?? null,
      condition: item.condition,
      quantity: item.quantity,
      unitValue: item.unitValue,
      isManualValue: item.isManualValue,
      totalValue: item.totalValue,
    })),
    totalValue,
    notes: input.notes ?? null,
  };
}

// --------------- Hook ---------------

export function useInKindDonations(): UseInKindDonationsResult {
  const { db, userId } = useFirebaseData();
  const [donations, setDonations] = useState<InKindDonation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDonations = useCallback(async () => {
    if (!db || !userId) {
      setDonations([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const colRef = collection(db, 'users', userId, 'in_kind_donations');
      const q = query(colRef, orderBy('date', 'desc'));
      const snapshot = await getDocs(q);
      setDonations(snapshot.docs.map(d => docToDonation(d.data(), d.id, userId)));
    } catch (err) {
      console.error('Error fetching in-kind donations:', err);
      setError(err instanceof Error ? err.message : 'Failed to load in-kind donations');
    } finally {
      setIsLoading(false);
    }
  }, [db, userId]);

  useEffect(() => {
    fetchDonations();
  }, [fetchDonations]);

  const addDonation = useCallback(async (input: InKindDonationInput): Promise<InKindDonation> => {
    if (!db || !userId) throw new Error('Not authenticated');
    setError(null);

    try {
      const colRef = collection(db, 'users', userId, 'in_kind_donations');
      const data = { ...inputToFirestore(input), createdAt: Timestamp.now() };
      const docRef = await addDoc(colRef, data);
      const newDonation = docToDonation(data, docRef.id, userId);

      setDonations(prev => {
        const updated = [...prev, newDonation];
        return updated.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
      });
      return newDonation;
    } catch (err) {
      console.error('Error adding in-kind donation:', err);
      const message = err instanceof Error ? err.message : 'Failed to add donation';
      setError(message);
      throw new Error(message);
    }
  }, [db, userId]);

  const updateDonation = useCallback(async (id: string, input: InKindDonationInput) => {
    if (!db || !userId) throw new Error('Not authenticated');
    setError(null);

    try {
      const docRef = doc(db, 'users', userId, 'in_kind_donations', id);
      await updateDoc(docRef, inputToFirestore(input) as Record<string, any>);
      await fetchDonations();
    } catch (err) {
      console.error('Error updating in-kind donation:', err);
      const message = err instanceof Error ? err.message : 'Failed to update donation';
      setError(message);
      throw new Error(message);
    }
  }, [db, userId, fetchDonations]);

  const deleteDonation = useCallback(async (id: string) => {
    if (!db || !userId) throw new Error('Not authenticated');

    const existing = donations.find(d => d.id === id);
    if (!existing) return;

    // Optimistic delete
    setDonations(prev => prev.filter(d => d.id !== id));
    setError(null);

    try {
      const docRef = doc(db, 'users', userId, 'in_kind_donations', id);
      await deleteDoc(docRef);
    } catch (err) {
      // Rollback
      setDonations(prev => [...prev, existing].sort((a, b) =>
        new Date(b.date).getTime() - new Date(a.date).getTime()
      ));
      console.error('Error deleting in-kind donation:', err);
      const message = err instanceof Error ? err.message : 'Failed to delete donation';
      setError(message);
      throw new Error(message);
    }
  }, [db, userId, donations]);

  const getYearSummary = useCallback((year: number): InKindYearSummary => {
    const yearDonations = donations.filter(d => d.taxYear === year);

    const categoryMap = new Map<string, { total: number; itemCount: number }>();
    const recipientMap = new Map<string, number>();

    let itemCount = 0;

    yearDonations.forEach(d => {
      recipientMap.set(d.recipientName, (recipientMap.get(d.recipientName) || 0) + d.totalValue);
      d.items.forEach(item => {
        itemCount += item.quantity;
        const existing = categoryMap.get(item.category) || { total: 0, itemCount: 0 };
        categoryMap.set(item.category, {
          total: existing.total + item.totalValue,
          itemCount: existing.itemCount + item.quantity,
        });
      });
    });

    return {
      year,
      totalValue: yearDonations.reduce((sum, d) => sum + d.totalValue, 0),
      donationCount: yearDonations.length,
      itemCount,
      categoryBreakdown: Array.from(categoryMap, ([category, data]) => ({
        category,
        total: data.total,
        itemCount: data.itemCount,
      })).sort((a, b) => b.total - a.total),
      recipientBreakdown: Array.from(recipientMap, ([name, total]) => ({
        name,
        total,
      })).sort((a, b) => b.total - a.total),
    };
  }, [donations]);

  const exportCSV = useCallback((year?: number): string => {
    let filtered = donations;
    if (year !== undefined) {
      filtered = donations.filter(d => d.taxYear === year);
    }

    const headers = [
      'Date',
      'Recipient',
      'Recipient EIN',
      'Item',
      'Category',
      'Condition',
      'Quantity',
      'Unit Value',
      'Total Value',
      'Manual Value',
      'Notes',
    ];

    const rows: string[][] = [];
    filtered.forEach(d => {
      d.items.forEach(item => {
        rows.push([
          d.date,
          `"${d.recipientName.replace(/"/g, '""')}"`,
          d.recipientEin || '',
          `"${item.itemName.replace(/"/g, '""')}"`,
          item.category,
          item.condition,
          item.quantity.toString(),
          item.unitValue.toFixed(2),
          item.totalValue.toFixed(2),
          item.isManualValue ? 'Yes' : 'No',
          d.notes ? `"${d.notes.replace(/"/g, '""')}"` : '',
        ]);
      });
    });

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
    exportCSV,
    refreshDonations: fetchDonations,
  };
}

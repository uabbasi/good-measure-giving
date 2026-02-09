/**
 * Hook for managing charity comparison state
 * Client-side only, persisted to localStorage
 * Maximum 3 charities can be compared at once
 */

import { useState, useCallback, useEffect } from 'react';

const STORAGE_KEY = 'gmg-compare-charities';
const MAX_COMPARE = 3;

interface UseCompareResult {
  compareList: string[]; // EINs
  isComparing: (ein: string) => boolean;
  canAddMore: boolean;
  addToCompare: (ein: string) => void;
  removeFromCompare: (ein: string) => void;
  toggleCompare: (ein: string) => void;
  clearCompare: () => void;
  compareCount: number;
}

export function useCompare(): UseCompareResult {
  const [compareList, setCompareList] = useState<string[]>(() => {
    // Initialize from localStorage
    if (typeof window === 'undefined') return [];
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Persist to localStorage on change
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(compareList));
    } catch {
      // localStorage might be full or unavailable
    }
  }, [compareList]);

  const isComparing = useCallback((ein: string): boolean => {
    return compareList.includes(ein);
  }, [compareList]);

  const canAddMore = compareList.length < MAX_COMPARE;

  const addToCompare = useCallback((ein: string) => {
    setCompareList(prev => {
      if (prev.includes(ein)) return prev;
      if (prev.length >= MAX_COMPARE) return prev;
      return [...prev, ein];
    });
  }, []);

  const removeFromCompare = useCallback((ein: string) => {
    setCompareList(prev => prev.filter(e => e !== ein));
  }, []);

  const toggleCompare = useCallback((ein: string) => {
    setCompareList(prev => {
      if (prev.includes(ein)) {
        return prev.filter(e => e !== ein);
      }
      if (prev.length >= MAX_COMPARE) {
        // Replace oldest (first) if at max
        return [...prev.slice(1), ein];
      }
      return [...prev, ein];
    });
  }, []);

  const clearCompare = useCallback(() => {
    setCompareList([]);
  }, []);

  return {
    compareList,
    isComparing,
    canAddMore,
    addToCompare,
    removeFromCompare,
    toggleCompare,
    clearCompare,
    compareCount: compareList.length,
  };
}

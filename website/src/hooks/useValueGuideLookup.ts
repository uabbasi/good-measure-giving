/**
 * Hook for searching and filtering the donation value guide
 * Pure computation — no API calls
 */

import { useState, useMemo, useCallback } from 'react';
import {
  VALUE_GUIDE_CATEGORIES,
  ALL_VALUE_GUIDE_ITEMS,
  type ValueGuideItem,
  type ValueGuideCategory,
} from '../data/donationValueGuide';

interface UseValueGuideLookupResult {
  query: string;
  setQuery: (q: string) => void;
  results: ValueGuideItem[];
  categories: ValueGuideCategory[];
  selectedCategory: string | null;
  setSelectedCategory: (id: string | null) => void;
  getItemById: (id: string) => ValueGuideItem | undefined;
}

export function useValueGuideLookup(): UseValueGuideLookupResult {
  const [query, setQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const itemMap = useMemo(() => {
    return new Map(ALL_VALUE_GUIDE_ITEMS.map(item => [item.id, item]));
  }, []);

  const results = useMemo(() => {
    let items = selectedCategory
      ? VALUE_GUIDE_CATEGORIES.find(c => c.id === selectedCategory)?.items ?? []
      : ALL_VALUE_GUIDE_ITEMS;

    if (query.trim()) {
      const lower = query.toLowerCase().trim();
      const terms = lower.split(/\s+/);
      items = items.filter(item => {
        const searchText = `${item.name} ${item.category}`.toLowerCase();
        return terms.every(term => searchText.includes(term));
      });
    }

    return items;
  }, [query, selectedCategory]);

  const getItemById = useCallback((id: string) => itemMap.get(id), [itemMap]);

  return {
    query,
    setQuery,
    results,
    categories: VALUE_GUIDE_CATEGORIES,
    selectedCategory,
    setSelectedCategory,
    getItemById,
  };
}

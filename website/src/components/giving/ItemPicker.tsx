/**
 * Fast autocomplete item picker optimized for high-volume entry (30-50 items)
 * Type → arrow → Enter = item added. No extra clicks.
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import {
  ALL_VALUE_GUIDE_ITEMS,
  getMidpointValue,
  type ValueGuideItem,
  type ItemCondition,
} from '../../data/donationValueGuide';
import type { InKindDonationItem } from '../../hooks/useInKindDonations';

interface ItemPickerProps {
  defaultCondition: ItemCondition;
  onAdd: (item: InKindDonationItem) => void;
}

/** Pre-build search index once */
const SEARCH_INDEX = ALL_VALUE_GUIDE_ITEMS.map(item => ({
  item,
  searchText: `${item.name} ${item.category}`.toLowerCase(),
}));

function search(query: string): ValueGuideItem[] {
  if (!query.trim()) return [];
  const terms = query.toLowerCase().trim().split(/\s+/);
  const results: ValueGuideItem[] = [];
  for (const entry of SEARCH_INDEX) {
    if (terms.every(t => entry.searchText.includes(t))) {
      results.push(entry.item);
      if (results.length >= 12) break;
    }
  }
  return results;
}

export function ItemPicker({ defaultCondition, onAdd }: ItemPickerProps) {
  const { isDark } = useLandingTheme();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<ValueGuideItem[]>([]);
  const [highlightIndex, setHighlightIndex] = useState(0);
  const [showDropdown, setShowDropdown] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Search on query change
  useEffect(() => {
    const r = search(query);
    setResults(r);
    setHighlightIndex(0);
    setShowDropdown(query.trim().length > 0);
  }, [query]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current && !inputRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const addItem = useCallback((guideItem: ValueGuideItem) => {
    const unitValue = getMidpointValue(guideItem, defaultCondition);
    onAdd({
      category: guideItem.category,
      itemName: guideItem.name,
      catalogItemId: guideItem.id,
      condition: defaultCondition,
      quantity: 1,
      unitValue,
      isManualValue: false,
      totalValue: unitValue,
    });
    setQuery('');
    setShowDropdown(false);
    // Re-focus for next item
    setTimeout(() => inputRef.current?.focus(), 0);
  }, [defaultCondition, onAdd]);

  const addCustomItem = useCallback(() => {
    const name = query.trim();
    if (!name) return;
    onAdd({
      category: 'Other',
      itemName: name,
      catalogItemId: null,
      condition: defaultCondition,
      quantity: 1,
      unitValue: 0,
      isManualValue: true,
      totalValue: 0,
    });
    setQuery('');
    setShowDropdown(false);
    setTimeout(() => inputRef.current?.focus(), 0);
  }, [query, defaultCondition, onAdd]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showDropdown) {
      if (e.key === 'Enter') {
        e.preventDefault();
        if (query.trim()) addCustomItem();
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightIndex(i => Math.min(i + 1, results.length)); // +1 for custom option
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightIndex(i => Math.max(i - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightIndex < results.length) {
          addItem(results[highlightIndex]);
        } else {
          addCustomItem();
        }
        break;
      case 'Escape':
        setShowDropdown(false);
        break;
      case 'Tab':
        if (results.length > 0 && highlightIndex < results.length) {
          e.preventDefault();
          addItem(results[highlightIndex]);
        }
        break;
    }
  };

  // Scroll highlighted item into view
  useEffect(() => {
    if (!showDropdown || !dropdownRef.current) return;
    const el = dropdownRef.current.children[highlightIndex] as HTMLElement | undefined;
    if (el) el.scrollIntoView({ block: 'nearest' });
  }, [highlightIndex, showDropdown]);

  const inputClass = `
    w-full px-3 py-2.5 rounded-lg border text-sm
    ${isDark
      ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-emerald-500'
      : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-emerald-500'
    }
    focus:outline-none focus:ring-1 focus:ring-emerald-500
  `;

  return (
    <div className="relative">
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => { if (query.trim()) setShowDropdown(true); }}
        onKeyDown={handleKeyDown}
        className={inputClass}
        placeholder="Type to search items... (jeans, sofa, laptop)"
        autoComplete="off"
      />

      {/* Keyboard hint */}
      {!showDropdown && !query && (
        <div className={`absolute right-3 top-1/2 -translate-y-1/2 text-xs ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
          type &amp; Enter
        </div>
      )}

      {/* Dropdown */}
      {showDropdown && (
        <div
          ref={dropdownRef}
          className={`absolute z-20 w-full mt-1 max-h-64 overflow-y-auto rounded-lg border shadow-lg ${
            isDark ? 'bg-slate-800 border-slate-600' : 'bg-white border-slate-200'
          }`}
        >
          {results.map((guideItem, i) => {
            const range = guideItem.values[defaultCondition];
            const mid = getMidpointValue(guideItem, defaultCondition);
            return (
              <button
                key={guideItem.id}
                type="button"
                onClick={() => addItem(guideItem)}
                className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 ${
                  i === highlightIndex
                    ? isDark ? 'bg-emerald-600/20 text-white' : 'bg-emerald-50 text-slate-900'
                    : isDark ? 'text-slate-200 hover:bg-slate-700' : 'text-slate-900 hover:bg-slate-50'
                }`}
              >
                <span className="flex-grow truncate">{guideItem.name}</span>
                <span className={`text-xs whitespace-nowrap ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  {guideItem.category}
                </span>
                <span className={`text-xs font-medium whitespace-nowrap ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                  ${mid}
                  <span className={`font-normal ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
                    {' '}(${range[0]}-${range[1]})
                  </span>
                </span>
              </button>
            );
          })}

          {/* Custom item option — always shown at bottom */}
          {query.trim() && (
            <button
              type="button"
              onClick={addCustomItem}
              className={`w-full text-left px-3 py-2 text-sm border-t ${
                highlightIndex === results.length
                  ? isDark ? 'bg-emerald-600/20 text-white border-slate-700' : 'bg-emerald-50 text-slate-900 border-slate-100'
                  : isDark ? 'text-slate-400 hover:bg-slate-700 border-slate-700' : 'text-slate-500 hover:bg-slate-50 border-slate-100'
              }`}
            >
              + Add "<strong>{query.trim()}</strong>" as custom item (set value manually)
            </button>
          )}
        </div>
      )}
    </div>
  );
}

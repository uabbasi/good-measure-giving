import React, { useMemo, useState } from 'react';

/**
 * Charity search-and-add. Searches the charities index by name/EIN and calls
 * onPick(ein). Shared by the plan view (add to plan) and the shortlist panel.
 */
export const CharitySearchAdd: React.FC<{
  charities: { ein?: string; name: string }[];
  existingEins: Set<string>;
  onPick: (ein: string) => void;
  disabled?: boolean;
  placeholder?: string;
}> = ({ charities, existingEins, onPick, disabled, placeholder = 'Add a charity — search by name…' }) => {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (q.length < 2) return [];
    const out: { ein: string; name: string }[] = [];
    for (const c of charities) {
      if (!c.ein || existingEins.has(c.ein)) continue;
      if (c.name.toLowerCase().includes(q) || c.ein.includes(q)) {
        out.push({ ein: c.ein, name: c.name });
        if (out.length >= 10) break;
      }
    }
    return out;
  }, [query, charities, existingEins]);

  const pick = (ein: string) => { onPick(ein); setQuery(''); setOpen(false); };

  return (
    <div className="relative max-w-md">
      <input
        type="text"
        value={query}
        disabled={disabled}
        onChange={e => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder={placeholder}
        aria-label="Search charities to add"
        className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 disabled:opacity-50"
      />
      {open && results.length > 0 && (
        <div className="absolute z-20 w-full mt-1 max-h-64 overflow-y-auto rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-lg">
          {results.map(c => (
            <button
              key={c.ein}
              type="button"
              onMouseDown={e => e.preventDefault()}
              onClick={() => pick(c.ein)}
              className="w-full text-left px-3 py-2 text-sm text-slate-900 dark:text-slate-100 hover:bg-emerald-50 dark:hover:bg-emerald-600/20"
            >
              <span className="block truncate">{c.name}</span>
              <span className="block text-xs text-slate-400 dark:text-slate-500">{c.ein}</span>
            </button>
          ))}
        </div>
      )}
      {open && query.trim().length >= 2 && results.length === 0 && (
        <div className="absolute z-20 w-full mt-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-lg px-3 py-2 text-sm text-slate-500 dark:text-slate-400">
          No matching charities.
        </div>
      )}
    </div>
  );
};

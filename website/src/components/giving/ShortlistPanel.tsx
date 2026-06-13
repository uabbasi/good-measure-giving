/**
 * ShortlistPanel — the explore-together surface. The family adds charities it is
 * "still considering" to a shared shortlist (everyone sees it live). Promotion
 * into the committed plan happens in the Decide step (SharedPlanView).
 */
import React, { useMemo } from 'react';
import { useSharedPlan } from '../../hooks/useSharedPlan';
import { useCharities } from '../../hooks/useCharities';
import { CharitySearchAdd } from './CharitySearchAdd';

export const ShortlistPanel: React.FC<{ planId: string }> = ({ planId }) => {
  const { plan, members, addToShortlist, removeFromShortlist } = useSharedPlan(planId);
  const { charities } = useCharities();

  const nameByEin = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of charities) if (c.ein) m.set(c.ein, c.name);
    return m;
  }, [charities]);
  const nameByUid = useMemo(() => {
    const m = new Map<string, string>();
    for (const mem of members) m.set(mem.uid, mem.displayName);
    return m;
  }, [members]);

  const shortlist = plan?.shortlist ?? [];
  const committedEins = new Set((plan?.items ?? []).filter(i => i.kind === 'charity').map(i => i.ref));
  const shortlistedEins = new Set(shortlist.map(c => c.ref));
  const existing = new Set([...committedEins, ...shortlistedEins]);

  return (
    <div className="space-y-3">
      <CharitySearchAdd
        charities={charities}
        existingEins={existing}
        onPick={(ein) => void addToShortlist(ein)}
        placeholder="Suggest a charity to consider together…"
      />
      {shortlist.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Nothing shortlisted yet. Add charities your family wants to consider.
        </p>
      ) : (
        <ul className="space-y-2">
          {shortlist.map(c => {
            const name = nameByEin.get(c.ref) ?? c.ref;
            return (
              <li key={c.ref} className="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2">
                <div>
                  <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{name}</span>
                  <span className="block text-xs text-slate-500 dark:text-slate-400">
                    suggested by {nameByUid.get(c.addedBy) ?? 'a family member'}
                  </span>
                </div>
                <button
                  onClick={() => void removeFromShortlist(c.ref)}
                  aria-label={`Remove ${name}`}
                  className="text-slate-400 hover:text-red-500"
                >
                  ✕
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};

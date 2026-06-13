/**
 * SharedPlanView — proportional, money-free view of a shared household plan.
 *
 * Renders the plan's items as proportional rows (name + percent + editable
 * weight), plus a PRIVATE "Your share" column computed client-side from the
 * signed-in user's own personal zakat target (never written to the shared doc).
 * Adding/editing/removing items goes through the thin-sync `useSharedPlan` hook.
 */

import React, { useMemo, useState, useEffect } from 'react';
import { useSharedPlan } from '../../hooks/useSharedPlan';
import { useProfile } from '../../hooks/useProfile';
import { useCharities } from '../../hooks/useCharities';
import { useFirebaseData } from '../../auth/FirebaseProvider';
import { weightsToPercents, computeYourShare } from '../../lib/sharedPlanLogic';
import type { PlanItem } from '../../types/sharedPlan';
import { InviteFamilyPanel } from './InviteFamilyPanel';
import { AssignCause } from './AssignCause';
import { CharitySearchAdd } from './CharitySearchAdd';

const ITEM_CAP = 100;

export const SharedPlanView: React.FC<{ planId: string }> = ({ planId }) => {
  const { plan, members, isLoading, isOwner, upsertItem, removeItem, setMyNote } = useSharedPlan(planId);
  const { profile } = useProfile();
  const { charities } = useCharities();
  const { userId } = useFirebaseData();

  // Personal target lives only on the signer's own profile — never on the shared doc.
  const personalTarget = (profile?.targetZakatAmount as number | null) ?? null;

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

  if (isLoading || !plan) {
    return <div className="p-6 text-slate-500 dark:text-slate-400">Loading plan…</div>;
  }

  const items = plan.items;
  const percents = weightsToPercents(items);
  const shares = computeYourShare(items, personalTarget);
  const atCap = items.length >= ITEM_CAP;

  const setWeight = (item: PlanItem, weight: number) =>
    void upsertItem({ ...item, weight }); // hook re-stamps updatedAt/updatedBy

  const setAssignee = (item: PlanItem, assigneeUid: string | null) =>
    void upsertItem({ ...item, assigneeUid }); // hook re-stamps updatedAt/updatedBy

  const addCharity = (ein: string) => {
    if (atCap) return;
    void upsertItem({
      id: crypto.randomUUID(),
      kind: 'charity',
      ref: ein,
      weight: 1,
      assigneeUid: null,
      updatedAt: Date.now(),
      updatedBy: '',
    });
  };

  const rowLabel = (item: PlanItem) =>
    item.kind === 'charity'
      ? nameByEin.get(item.ref) ?? item.ref
      : item.ref.replace(/-/g, ' ');

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-slate-900 dark:text-white">{plan.name}</h2>
        <span className="text-sm text-slate-500 dark:text-slate-400">
          {members.length} member{members.length === 1 ? '' : 's'}
        </span>
      </div>

      {/* Add charity — above the table */}
      <CharitySearchAdd
        charities={charities}
        existingEins={new Set(items.filter(i => i.kind === 'charity').map(i => i.ref))}
        onPick={addCharity}
        disabled={atCap}
      />
      {atCap && (
        <p className="text-sm text-amber-700 dark:text-amber-400">
          This plan has reached the {ITEM_CAP}-item limit. Remove an item before adding another.
        </p>
      )}

      {items.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          No charities yet. Add one above to start splitting your giving together.
        </p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 dark:text-slate-400">
              <th className="font-medium py-2">What we support</th>
              <th className="font-medium py-2">Share</th>
              <th className="font-medium py-2">Weight</th>
              <th className="font-medium py-2">Assigned to</th>
              {personalTarget != null && <th className="font-medium py-2">Your share</th>}
              <th aria-label="actions" />
            </tr>
          </thead>
          <tbody>
            {items.map(item => (
              <tr key={item.id} className="border-t border-slate-200 dark:border-slate-700">
                <td className="py-2 text-slate-900 dark:text-slate-100 align-top">
                  <div>{rowLabel(item)}</div>
                  <NoteCell
                    item={item}
                    members={members}
                    myUid={userId}
                    onSave={(text) => void setMyNote(item.id, text)}
                  />
                </td>
                <td className="py-2 text-slate-600 dark:text-slate-300">{percents[item.id]}%</td>
                <td className="py-2">
                  <input
                    type="number"
                    min={0}
                    step={1}
                    value={item.weight}
                    onChange={e => setWeight(item, parseFloat(e.target.value) || 0)}
                    aria-label={`Weight for ${rowLabel(item)}`}
                    className="w-20 px-2 py-1 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
                  />
                </td>
                <td className="py-2">
                  <div className="flex items-center gap-2">
                    <AssignCause
                      members={members}
                      value={item.assigneeUid}
                      onChange={uid => setAssignee(item, uid)}
                      aria-label={`Assign a member to ${rowLabel(item)}`}
                    />
                    {item.assigneeUid != null && (
                      <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
                        {nameByUid.get(item.assigneeUid) ?? 'Someone'} is researching this
                      </span>
                    )}
                  </div>
                </td>
                {personalTarget != null && (
                  <td className="py-2 text-slate-700 dark:text-slate-200">
                    ${(shares[item.id] || 0).toLocaleString()}
                  </td>
                )}
                <td className="py-2 text-right">
                  <button
                    onClick={() => void removeItem(item.id)}
                    aria-label={`Remove ${rowLabel(item)}`}
                    className="text-slate-400 hover:text-red-500"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {personalTarget == null && (
        <p className="text-sm text-amber-700 dark:text-amber-400">
          Set your zakat target on your personal plan to see your share.
        </p>
      )}

      <InviteFamilyPanel planId={planId} canManage={isOwner()} />
    </div>
  );
};

const NoteCell: React.FC<{
  item: PlanItem;
  members: { uid: string; displayName: string }[];
  myUid: string | null;
  onSave: (text: string) => void;
}> = ({ item, members, myUid, onSave }) => {
  const nameByUid = useMemo(() => {
    const m = new Map<string, string>();
    for (const mem of members) m.set(mem.uid, mem.displayName);
    return m;
  }, [members]);
  const notes = item.notes ?? {};
  const mine = myUid ? notes[myUid]?.text ?? '' : '';
  const [draft, setDraft] = useState(mine);
  useEffect(() => { setDraft(mine); }, [mine]);

  const others = Object.entries(notes).filter(([uid]) => uid !== myUid);

  return (
    <div className="mt-1 space-y-1">
      {others.map(([uid, n]) => (
        <p key={uid} className="text-xs text-slate-500 dark:text-slate-400">
          <span className="font-medium">{nameByUid.get(uid) ?? 'Someone'}:</span> {n.text}
        </p>
      ))}
      {myUid && (
        <input
          type="text"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onBlur={() => { if (draft !== mine) onSave(draft); }}
          placeholder="Your reason for giving here…"
          aria-label={`Your reason for ${item.ref}`}
          className="w-full max-w-xs px-2 py-1 text-xs rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500"
        />
      )}
    </div>
  );
};


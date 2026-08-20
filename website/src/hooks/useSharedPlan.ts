import { useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  doc, collection, getDoc, getDocs, setDoc, deleteDoc, runTransaction, query, where, Timestamp,
} from 'firebase/firestore';
import { useFirebaseData } from '../auth/FirebaseProvider';
import type { SharedPlan, PlanItem, PlanMember, PlanHistoryEntry, ShortlistCandidate } from '../types/sharedPlan';
import { applyItemLWW, addCharityItem, removeItemById, setMemberNote, addShortlistCandidate, removeShortlistCandidate, promoteCandidate, HISTORY_MAX, revisionToPrune } from '../lib/sharedPlanLogic';

export function useSharedPlan(planId: string | null) {
  const { db, userId } = useFirebaseData();
  const qc = useQueryClient();
  const key = ['sharedPlan', planId];

  const { data, isLoading, error } = useQuery({
    queryKey: key,
    enabled: !!db && !!planId,
    // Other members' edits land via their own writes, not ours — the app-wide
    // default (staleTime: Infinity, no window-focus refetch) would otherwise
    // leave this plan looking stale forever to anyone not doing the writing.
    // Poll gently while a plan is actually open so co-editors converge within
    // a few seconds instead of needing a hard reload.
    staleTime: 2_000,
    refetchInterval: 4_000,
    queryFn: async (): Promise<{ plan: SharedPlan | null; members: PlanMember[] }> => {
      if (!db || !planId) return { plan: null, members: [] };
      const snap = await getDoc(doc(db, 'shared_plans', planId));
      if (!snap.exists()) return { plan: null, members: [] };
      const plan = { id: snap.id, ...(snap.data() as Omit<SharedPlan, 'id'>) };
      const memSnap = await getDocs(collection(db, 'shared_plans', planId, 'members'));
      const members = memSnap.docs.map(d => ({ uid: d.id, ...(d.data() as Omit<PlanMember, 'uid'>) }));
      return { plan, members };
    },
  });

  // One transactional write: re-read the plan, apply a change, bump revision,
  // append a revision-keyed history entry, then best-effort prune the ring buffer.
  // `build` returns the field patch to write and (optionally) the item history.
  const commit = async (
    build: (current: Omit<SharedPlan, 'id'>) => {
      fields: Partial<Pick<SharedPlan, 'items' | 'shortlist'>>;
      history?: { itemId: string; before: PlanItem | null; after: PlanItem | null };
    },
  ): Promise<void> => {
    if (!db || !planId || !userId) throw new Error('Not authenticated');
    const ref = doc(db, 'shared_plans', planId);
    const revision = await runTransaction(db, async (tx) => {
      const snap = await tx.get(ref);
      if (!snap.exists()) throw new Error('Plan not found');
      const current = snap.data() as Omit<SharedPlan, 'id'>;
      const { fields, history } = build(current);
      const rev = (current.revision ?? 0) + 1;
      tx.set(ref, { ...fields, revision: rev, updatedAt: Timestamp.now() }, { merge: true });
      if (history) {
        const entry: PlanHistoryEntry = {
          revision: rev, itemId: history.itemId, before: history.before,
          after: history.after, updatedBy: userId, at: Date.now(),
        };
        // Auto-generated id — NOT the revision number. Two members' commits can
        // both read the plan at the same revision before Firestore's
        // optimistic-concurrency check on the plan doc forces the loser to
        // retry; a revision-keyed history id would then collide with the
        // winner's already-created (rules-immutable) entry, and the whole
        // transaction would be denied by the "history is immutable" rule
        // instead of cleanly retried — silently dropping the loser's write.
        tx.set(doc(collection(db, 'shared_plans', planId, 'history')), entry);
      }
      return rev;
    });
    const pruneRevision = revisionToPrune(revision, HISTORY_MAX);
    if (pruneRevision != null) {
      try {
        const stale = await getDocs(
          query(collection(db, 'shared_plans', planId, 'history'), where('revision', '==', pruneRevision)),
        );
        await Promise.all(stale.docs.map(d => deleteDoc(d.ref)));
      } catch { /* best-effort */ }
    }
  };

  const upsertItem = useMutation({
    mutationFn: (incoming: PlanItem) =>
      commit((current) => {
        const stamped = { ...incoming, updatedAt: Date.now(), updatedBy: userId! };
        const before = current.items.find(i => i.id === incoming.id) ?? null;
        const items = applyItemLWW(current.items, stamped);
        const after = items.find(i => i.id === incoming.id) ?? null;
        // applyItemLWW returns the SAME item reference when the write is stale
        // (LWW lost). Don't record a no-op history entry falsely attributed to
        // the losing member; only log when something actually changed.
        const history = before !== after ? { itemId: incoming.id, before, after } : undefined;
        return { fields: { items }, history };
      }),
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  // Add a charity by EIN, deduped by ref (not id) inside the transaction — two
  // members adding the same charity at once must land as one item, not two.
  // Unlike upsertItem/applyItemLWW (edit-only, never inserts), this is the only
  // mutation allowed to insert a new item.
  const addCharity = useMutation({
    mutationFn: (ein: string) =>
      commit((current) => {
        const items = addCharityItem(current.items, ein, userId!);
        if (items === current.items) return { fields: {} }; // already present — no-op
        const after = items[items.length - 1];
        return { fields: { items }, history: { itemId: after.id, before: null, after } };
      }),
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const removeItem = useMutation({
    mutationFn: (itemId: string) =>
      commit((current) => {
        const before = current.items.find(i => i.id === itemId) ?? null;
        return { fields: { items: removeItemById(current.items, itemId) }, history: { itemId, before, after: null } };
      }),
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const setMyNote = useMutation({
    mutationFn: ({ itemId, text }: { itemId: string; text: string }) =>
      commit((current) => {
        const idx = current.items.findIndex(i => i.id === itemId);
        if (idx === -1) throw new Error('Item not found');
        const before = current.items[idx];
        const after = { ...setMemberNote(before, userId!, text), updatedAt: Date.now(), updatedBy: userId! };
        const items = current.items.slice();
        items[idx] = after;
        return { fields: { items }, history: { itemId, before, after } };
      }),
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const addToShortlist = useMutation({
    mutationFn: (ref: string) =>
      commit((current) => ({
        fields: { shortlist: addShortlistCandidate(current.shortlist ?? [], ref, userId!) },
        // shortlist changes are not item edits → no history entry
      })),
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const removeFromShortlist = useMutation({
    mutationFn: (ref: string) =>
      commit((current) => ({
        fields: { shortlist: removeShortlistCandidate(current.shortlist ?? [], ref) },
      })),
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const promoteToPlan = useMutation({
    mutationFn: (ref: string) =>
      commit((current) => {
        const before = current.items.find(i => i.kind === 'charity' && i.ref === ref) ?? null;
        const next = promoteCandidate(current.items, current.shortlist ?? [], ref, userId!);
        const after = next.items.find(i => i.kind === 'charity' && i.ref === ref) ?? null;
        // Only an item history entry when a NEW item was actually added — if the
        // charity was already committed (raced promote), promote just drops the
        // candidate from the shortlist (no item change → no phantom "added").
        const history = !before && after ? { itemId: after.id, before: null, after } : undefined;
        return { fields: { items: next.items, shortlist: next.shortlist }, history };
      }),
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const join = useMutation({
    mutationFn: async ({ token, displayName }: { token: string; displayName: string }) => {
      if (!db || !planId || !userId) throw new Error('Not authenticated');
      // Member-create rule checks token matches the plan's inviteToken.
      await setDoc(doc(db, 'shared_plans', planId, 'members', userId), {
        role: 'editor', displayName, joinedAt: Timestamp.now(), token,
      });
      // Point the user's profile at this plan (array-union via merge).
      const userRef = doc(db, 'users', userId);
      const userSnap = await getDoc(userRef);
      const existing: string[] = (userSnap.data()?.sharedPlanIds as string[]) || [];
      if (!existing.includes(planId)) {
        await setDoc(userRef, { sharedPlanIds: [...existing, planId] }, { merge: true });
      }
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const removeMember = useMutation({
    mutationFn: async (uid: string) => {
      if (!db || !planId) throw new Error('Not authenticated');
      await deleteDoc(doc(db, 'shared_plans', planId, 'members', uid));
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const rename = useMutation({
    mutationFn: async (name: string) => {
      if (!db || !planId) throw new Error('Not authenticated');
      await setDoc(doc(db, 'shared_plans', planId), { name, updatedAt: Timestamp.now() }, { merge: true });
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const rotateToken = useMutation({
    mutationFn: async (token: string) => {
      if (!db || !planId) throw new Error('Not authenticated');
      await setDoc(doc(db, 'shared_plans', planId), { inviteToken: token, updatedAt: Timestamp.now() }, { merge: true });
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const isOwner = useCallback(() => !!data?.plan && data.plan.ownerId === userId, [data, userId]);

  return {
    plan: data?.plan ?? null,
    members: data?.members ?? [],
    isLoading,
    error: error ? (error instanceof Error ? error.message : 'Failed to load plan') : null,
    isOwner,
    upsertItem: (i: PlanItem) => upsertItem.mutateAsync(i),
    addCharity: (ein: string) => addCharity.mutateAsync(ein),
    removeItem: (id: string) => removeItem.mutateAsync(id),
    setMyNote: (itemId: string, text: string) => setMyNote.mutateAsync({ itemId, text }),
    addToShortlist: (ref: string) => addToShortlist.mutateAsync(ref),
    removeFromShortlist: (ref: string) => removeFromShortlist.mutateAsync(ref),
    promoteToPlan: (ref: string) => promoteToPlan.mutateAsync(ref),
    join: (token: string, displayName: string) => join.mutateAsync({ token, displayName }),
    removeMember: (uid: string) => removeMember.mutateAsync(uid),
    rename: (n: string) => rename.mutateAsync(n),
    rotateToken: (t: string) => rotateToken.mutateAsync(t),
  };
}

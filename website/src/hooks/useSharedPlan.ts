import { useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  doc, collection, getDoc, getDocs, setDoc, deleteDoc, runTransaction, Timestamp,
} from 'firebase/firestore';
import { useFirebaseData } from '../auth/FirebaseProvider';
import type { SharedPlan, PlanItem, PlanMember, PlanHistoryEntry, ShortlistCandidate } from '../types/sharedPlan';
import { applyItemLWW, removeItemById, setMemberNote, addShortlistCandidate, removeShortlistCandidate, promoteCandidate, HISTORY_MAX, historyIdToPrune } from '../lib/sharedPlanLogic';

export function useSharedPlan(planId: string | null) {
  const { db, userId } = useFirebaseData();
  const qc = useQueryClient();
  const key = ['sharedPlan', planId];

  const { data, isLoading, error } = useQuery({
    queryKey: key,
    enabled: !!db && !!planId,
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
        tx.set(doc(db, 'shared_plans', planId, 'history', String(rev)), entry);
      }
      return rev;
    });
    const pruneId = historyIdToPrune(revision, HISTORY_MAX);
    if (pruneId) {
      try { await deleteDoc(doc(db, 'shared_plans', planId, 'history', pruneId)); } catch { /* best-effort */ }
    }
  };

  const upsertItem = useMutation({
    mutationFn: (incoming: PlanItem) =>
      commit((current) => {
        const stamped = { ...incoming, updatedAt: Date.now(), updatedBy: userId! };
        const before = current.items.find(i => i.id === incoming.id) ?? null;
        const items = applyItemLWW(current.items, stamped);
        const after = items.find(i => i.id === incoming.id) ?? null;
        return { fields: { items }, history: { itemId: incoming.id, before, after } };
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
        const next = promoteCandidate(current.items, current.shortlist ?? [], ref, userId!);
        const added = next.items.find(i => i.kind === 'charity' && i.ref === ref) ?? null;
        return {
          fields: { items: next.items, shortlist: next.shortlist },
          history: { itemId: added?.id ?? ref, before: null, after: added },
        };
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

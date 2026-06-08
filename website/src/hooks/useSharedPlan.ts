import { useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  doc, collection, getDoc, getDocs, setDoc, deleteDoc, Timestamp,
} from 'firebase/firestore';
import { useFirebaseData } from '../auth/FirebaseProvider';
import type { SharedPlan, PlanItem, PlanMember } from '../types/sharedPlan';

/** Replace an item by id, or append if absent. Whole-item last-write-wins
 *  (thin sync — no per-row timestamp compare; the saver's value wins). */
export function replaceOrAppendItem(items: PlanItem[], incoming: PlanItem): PlanItem[] {
  const idx = items.findIndex(i => i.id === incoming.id);
  if (idx === -1) return [...items, incoming];
  const next = items.slice();
  next[idx] = incoming;
  return next;
}

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

  // Thin sync: read-modify-write the whole items array, no transaction/history.
  const upsertItem = useMutation({
    mutationFn: async (incoming: PlanItem) => {
      if (!db || !planId || !userId) throw new Error('Not authenticated');
      const ref = doc(db, 'shared_plans', planId);
      const snap = await getDoc(ref);
      if (!snap.exists()) throw new Error('Plan not found');
      const current = snap.data() as Omit<SharedPlan, 'id'>;
      const stamped = { ...incoming, updatedAt: Date.now(), updatedBy: userId };
      const items = replaceOrAppendItem(current.items, stamped);
      await setDoc(ref, { items, revision: (current.revision ?? 0) + 1, updatedAt: Timestamp.now() }, { merge: true });
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const removeItem = useMutation({
    mutationFn: async (itemId: string) => {
      if (!db || !planId || !userId) throw new Error('Not authenticated');
      const ref = doc(db, 'shared_plans', planId);
      const snap = await getDoc(ref);
      if (!snap.exists()) return;
      const current = snap.data() as Omit<SharedPlan, 'id'>;
      const items = current.items.filter(i => i.id !== itemId);
      await setDoc(ref, { items, revision: (current.revision ?? 0) + 1, updatedAt: Timestamp.now() }, { merge: true });
    },
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
    join: (token: string, displayName: string) => join.mutateAsync({ token, displayName }),
    removeMember: (uid: string) => removeMember.mutateAsync(uid),
    rename: (n: string) => rename.mutateAsync(n),
    rotateToken: (t: string) => rotateToken.mutateAsync(t),
  };
}

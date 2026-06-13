import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { doc, getDoc, setDoc, collection, Timestamp } from 'firebase/firestore';
import { useFirebaseData, useFirebaseAuth } from '../auth/FirebaseProvider';
import { newInviteToken, addCharityItem, removeCharityItem } from '../lib/sharedPlanLogic';
import type { SharedPlan, PlanItem } from '../types/sharedPlan';

export function useSharedPlans() {
  const { db, userId } = useFirebaseData();
  // `user` is not exposed by useFirebaseData; the auth context provides it.
  const { user } = useFirebaseAuth();
  const qc = useQueryClient();
  const key = ['sharedPlans', userId];

  const { data: plans = [], isLoading } = useQuery({
    queryKey: key,
    enabled: !!db && !!userId,
    queryFn: async (): Promise<{ id: string; name: string }[]> => {
      if (!db || !userId) return [];
      const userSnap = await getDoc(doc(db, 'users', userId));
      const ids: string[] = (userSnap.data()?.sharedPlanIds as string[]) || [];
      const out: { id: string; name: string }[] = [];
      for (const id of ids) {
        const snap = await getDoc(doc(db, 'shared_plans', id));
        if (snap.exists()) out.push({ id, name: (snap.data().name as string) || 'Shared plan' }); // dangling ids filtered
      }
      return out;
    },
  });

  const createPlan = useMutation({
    mutationFn: async (name: string): Promise<string> => {
      if (!db || !userId) throw new Error('Not authenticated');
      const ref = doc(collection(db, 'shared_plans'));
      const now = Date.now();
      const plan: Omit<SharedPlan, 'id'> = {
        name, ownerId: userId, createdAt: now, updatedAt: now, revision: 0,
        inviteToken: newInviteToken(), items: [],
      };
      await setDoc(ref, plan);
      await setDoc(doc(db, 'shared_plans', ref.id, 'members', userId), {
        role: 'owner', displayName: user?.displayName || 'You', joinedAt: Timestamp.now(),
        token: plan.inviteToken,
      });
      const userRef = doc(db, 'users', userId);
      const existing: string[] = ((await getDoc(userRef)).data()?.sharedPlanIds as string[]) || [];
      await setDoc(userRef, { sharedPlanIds: [...existing, ref.id] }, { merge: true });
      return ref.id;
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  // Thin-sync read-modify-write of one shared plan's whole items array.
  // `mutate(items)` returns the next array, or the same reference to skip the write.
  const writePlanItems = async (planId: string, mutate: (items: PlanItem[]) => PlanItem[]) => {
    if (!db || !userId) throw new Error('Not authenticated');
    const ref = doc(db, 'shared_plans', planId);
    const snap = await getDoc(ref);
    if (!snap.exists()) throw new Error('Plan not found');
    const items: PlanItem[] = (snap.data().items as PlanItem[]) || [];
    const next = mutate(items);
    if (next === items) return false; // no change — skip the write
    await setDoc(
      ref,
      { items: next, revision: ((snap.data().revision as number) || 0) + 1, updatedAt: Date.now() },
      { merge: true },
    );
    return true;
  };

  // Bridge: add/remove a charity (by EIN) on one shared plan (dedupes, bumps revision).
  const addCharityToPlan = useMutation({
    mutationFn: ({ planId, ein }: { planId: string; ein: string }) =>
      writePlanItems(planId, items => addCharityItem(items, ein, userId!)),
  });
  const removeCharityFromPlan = useMutation({
    mutationFn: ({ planId, ein }: { planId: string; ein: string }) =>
      writePlanItems(planId, items => removeCharityItem(items, ein)),
  });

  // Sync helpers: mirror a personal-plan add/remove across EVERY shared plan the
  // user belongs to (keeps the family plan(s) in lockstep with the personal plan).
  const addCharityToAllPlans = async (ein: string) => {
    for (const p of plans) await writePlanItems(p.id, items => addCharityItem(items, ein, userId!));
  };
  const removeCharityFromAllPlans = async (ein: string) => {
    for (const p of plans) await writePlanItems(p.id, items => removeCharityItem(items, ein));
  };

  return {
    plans,
    isLoading,
    hasPlans: plans.length > 0,
    createPlan: (n: string) => createPlan.mutateAsync(n),
    addCharityToPlan: (planId: string, ein: string) => addCharityToPlan.mutateAsync({ planId, ein }),
    removeCharityFromPlan: (planId: string, ein: string) => removeCharityFromPlan.mutateAsync({ planId, ein }),
    addCharityToAllPlans,
    removeCharityFromAllPlans,
  };
}

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { doc, getDoc, setDoc, collection, Timestamp } from 'firebase/firestore';
import { useFirebaseData, useFirebaseAuth } from '../auth/FirebaseProvider';
import { newInviteToken } from '../lib/sharedPlanLogic';
import type { SharedPlan } from '../types/sharedPlan';

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

  return { plans, isLoading, createPlan: (n: string) => createPlan.mutateAsync(n) };
}

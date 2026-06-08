import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Navigate } from 'react-router-dom';
import { doc, getDoc, collection, getDocs } from 'firebase/firestore';
import { db } from '../src/auth/firebase';
import { useFirebaseData, useFirebaseAuth } from '../src/auth/FirebaseProvider';
import { useSharedPlan } from '../src/hooks/useSharedPlan';
import { useCharities } from '../src/hooks/useCharities';
import { weightsToPercents } from '../src/lib/sharedPlanLogic';
import { trackPlanPreview, trackPlanJoined } from '../src/utils/analytics';
import type { SharedPlan, PlanMember } from '../src/types/sharedPlan';

export const JoinPlanPage: React.FC = () => {
  const { planId, token } = useParams<{ planId: string; token: string }>();
  const { userId } = useFirebaseData();
  const { user } = useFirebaseAuth();
  const navigate = useNavigate();
  const { join } = useSharedPlan(planId ?? null);
  const { summaries } = useCharities();
  const [plan, setPlan] = useState<SharedPlan | null>(null);
  const [members, setMembers] = useState<PlanMember[]>([]);
  const [state, setState] = useState<'loading' | 'ok' | 'notfound'>('loading');

  // Public read of the money-free plan for the preview.
  useEffect(() => {
    if (!db || !planId) return;
    (async () => {
      try {
        const snap = await getDoc(doc(db, 'shared_plans', planId));
        if (!snap.exists()) { setState('notfound'); return; }
        const p = { id: snap.id, ...(snap.data() as Omit<SharedPlan, 'id'>) };
        if (p.inviteToken !== token) { setState('notfound'); return; } // revoked/old link
        const mem = await getDocs(collection(db, 'shared_plans', planId, 'members'));
        setPlan(p);
        setMembers(mem.docs.map(d => ({ uid: d.id, ...(d.data() as Omit<PlanMember, 'uid'>) })));
        setState('ok');
        trackPlanPreview(planId);
      } catch {
        setState('notfound');
      }
    })();
  }, [planId, token]);

  if (state === 'notfound') return <Navigate to="/" replace />;
  if (state === 'loading' || !plan) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-500">
        Loading…
      </div>
    );
  }

  const percents = weightsToPercents(plan.items);
  const alreadyMember = !!userId && members.some(m => m.uid === userId);

  const charityName = (ein: string): string =>
    summaries.find(s => s.ein === ein)?.name ?? ein;

  const onJoin = async () => {
    if (!userId) { navigate('/profile'); return; } // sign-in surface; returns here after auth
    await join(token!, user?.displayName || 'Family member');
    trackPlanJoined(planId!);
    navigate('/profile');
  };

  return (
    <div className="min-h-screen max-w-2xl mx-auto px-4 py-12">
      <p className="text-sm uppercase tracking-wide text-emerald-700">You're invited</p>
      <h1 className="text-3xl font-semibold mb-2">The {plan.name} is planning their giving</h1>
      <p className="text-slate-600 mb-8">Here's how they're splitting it. Join to add your own giving.</p>

      <ul className="divide-y divide-slate-200 dark:divide-slate-700 mb-8">
        {plan.items.map(i => (
          <li key={i.id} className="flex justify-between py-2">
            <span>{i.kind === 'charity' ? charityName(i.ref) : i.ref.replace(/-/g, ' ')}</span>
            <span className="text-slate-500">{percents[i.id]}%</span>
          </li>
        ))}
      </ul>

      <button
        onClick={onJoin}
        className="px-5 py-2.5 rounded-lg bg-emerald-600 text-white font-semibold"
      >
        {alreadyMember ? 'Open this plan' : userId ? 'Join your family' : 'Sign in to join your family'}
      </button>
    </div>
  );
};

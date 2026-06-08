import React, { useState } from 'react';
import { useSharedPlan } from '../../hooks/useSharedPlan';
import { newInviteToken } from '../../lib/sharedPlanLogic';
import { trackInviteCreated } from '../../utils/analytics';

export const InviteFamilyPanel: React.FC<{ planId: string; canManage: boolean }> = ({ planId, canManage }) => {
  const { plan, members, rotateToken, removeMember } = useSharedPlan(planId);
  const [copied, setCopied] = useState(false);
  if (!plan) return null;

  const link = `${window.location.origin}/plan/join/${planId}/${plan.inviteToken}`;

  const share = async () => {
    trackInviteCreated(planId);
    if (navigator.share) {
      await navigator.share({ title: `${plan.name} — plan giving together`, url: link }).catch(() => {});
    } else {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Invite family</h3>
        <button onClick={share} className="px-3 py-1.5 rounded bg-emerald-600 text-white text-sm">
          {copied ? 'Link copied' : 'Invite family'}
        </button>
      </div>
      <ul className="text-sm text-slate-600 dark:text-slate-300">
        {members.map(m => (
          <li key={m.uid} className="flex justify-between py-1">
            <span>{m.displayName}{m.role === 'owner' ? ' (owner)' : ''}</span>
            {canManage && m.role !== 'owner' && (
              <button onClick={() => removeMember(m.uid)} className="text-slate-400 hover:text-red-500">Remove</button>
            )}
          </li>
        ))}
      </ul>
      {canManage && (
        <button onClick={() => rotateToken(newInviteToken())} className="text-xs text-slate-500 hover:underline">
          Revoke &amp; regenerate link
        </button>
      )}
    </div>
  );
};

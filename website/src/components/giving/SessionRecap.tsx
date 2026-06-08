/**
 * SessionRecap — end-of-session, money-free shareable summary card.
 *
 * Headline: "The {name} is supporting N charities across M causes this {year}."
 * Renders the proportional list (names + %), and a Share button that points at
 * the plan's join link so the recap doubles as the next invite. No dollars.
 *
 * Note: the existing `ShareButton` hard-codes its URL to `/charity/{id}` and
 * cannot accept an arbitrary URL, so we use a minimal copy-link/native-share
 * button here (same pattern as InviteFamilyPanel) pointed at the join link.
 */

import React, { useMemo, useState } from 'react';
import { Share2, Check } from 'lucide-react';
import { useSharedPlan } from '../../hooks/useSharedPlan';
import { useCharities } from '../../hooks/useCharities';
import { weightsToPercents } from '../../lib/sharedPlanLogic';
import { summarize } from '../../lib/recapSummary';
import { trackInviteCreated } from '../../utils/analytics';
import type { PlanItem } from '../../types/sharedPlan';

export const SessionRecap: React.FC<{ planId: string }> = ({ planId }) => {
  const { plan, isLoading } = useSharedPlan(planId);
  const { charities } = useCharities();
  const [copied, setCopied] = useState(false);

  const nameByEin = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of charities) if (c.ein) m.set(c.ein, c.name);
    return m;
  }, [charities]);

  if (isLoading || !plan) {
    return <div className="p-6 text-slate-500 dark:text-slate-400">Loading recap…</div>;
  }

  const items = plan.items;
  const { charityCount, causeCount } = summarize(items);
  const percents = weightsToPercents(items);
  const year = new Date().getFullYear();
  const link = `${window.location.origin}/plan/join/${plan.id}/${plan.inviteToken}`;

  const rowLabel = (item: PlanItem) =>
    item.kind === 'charity'
      ? nameByEin.get(item.ref) ?? item.ref
      : item.ref.replace(/-/g, ' ');

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
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-6 space-y-5">
      <h2 className="text-2xl font-semibold text-slate-900 dark:text-white leading-snug">
        The {plan.name} is supporting {charityCount} {charityCount === 1 ? 'charity' : 'charities'}{' '}
        across {causeCount} {causeCount === 1 ? 'cause' : 'causes'} this {year}
      </h2>

      {items.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          No charities yet — add some to your plan to build your recap.
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map(item => (
            <li
              key={item.id}
              className="flex items-center justify-between text-sm border-t border-slate-200 dark:border-slate-700 pt-2 first:border-t-0 first:pt-0"
            >
              <span className="text-slate-900 dark:text-slate-100">{rowLabel(item)}</span>
              <span className="text-slate-600 dark:text-slate-300 tabular-nums">{percents[item.id]}%</span>
            </li>
          ))}
        </ul>
      )}

      <div className="flex justify-end">
        <button
          onClick={share}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium"
          aria-label="Share this plan"
        >
          {copied ? <Check className="w-4 h-4" /> : <Share2 className="w-4 h-4" />}
          {copied ? 'Link copied' : 'Share'}
        </button>
      </div>
    </div>
  );
};

export default SessionRecap;

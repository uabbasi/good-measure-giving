/**
 * GivingSession — the ritual spine.
 *
 * A guided arc wrapping the shared-plan view: gather → explore → decide → recap.
 * Not a new data model; a stateful wrapper over the existing components that gives
 * a giving session a beginning and an end. Step logic lives in `lib/givingSession`.
 */

import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  SESSION_STEPS,
  nextStep,
  prevStep,
  isLastStep,
  type SessionStep,
} from '../../lib/givingSession';
import { useSharedPlan } from '../../hooks/useSharedPlan';
import { InviteFamilyPanel } from './InviteFamilyPanel';
import { SharedPlanView } from './SharedPlanView';
import { SessionRecap } from './SessionRecap';

const STEP_LABELS: Record<SessionStep, string> = {
  gather: 'Gather',
  explore: 'Explore',
  decide: 'Decide',
  recap: 'Recap',
};

export const GivingSession: React.FC<{ planId: string; onExit?: () => void }> = ({
  planId,
  onExit,
}) => {
  const { isOwner } = useSharedPlan(planId);
  const [step, setStep] = useState<SessionStep>('gather');

  const onLast = isLastStep(step);

  return (
    <div className="space-y-6">
      {/* Step indicator */}
      <ol className="flex items-center gap-2 text-xs">
        {SESSION_STEPS.map((s, i) => {
          const active = s === step;
          const done = SESSION_STEPS.indexOf(s) < SESSION_STEPS.indexOf(step);
          return (
            <li key={s} className="flex items-center gap-2">
              <span
                className={
                  'rounded-full px-2.5 py-1 font-medium ' +
                  (active
                    ? 'bg-emerald-600 text-white'
                    : done
                    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                    : 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400')
                }
              >
                {STEP_LABELS[s]}
              </span>
              {i < SESSION_STEPS.length - 1 && (
                <span className="text-slate-300 dark:text-slate-600">→</span>
              )}
            </li>
          );
        })}
      </ol>

      {/* Step body */}
      {step === 'gather' && (
        <div className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Gather the family</h2>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Bring everyone together and invite the people you give with. Once
              they&apos;ve joined, move on to explore charities as a family.
            </p>
          </div>
          <InviteFamilyPanel planId={planId} canManage={isOwner()} />
        </div>
      )}

      {step === 'explore' && (
        <div className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Explore together</h2>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Browse charities side by side and talk about what matters to your
              family. You can add the ones you choose to your plan in the next
              step.
            </p>
          </div>
          <Link
            to="/browse"
            className="inline-block px-4 py-2 rounded bg-emerald-600 text-white text-sm font-medium"
          >
            Browse charities
          </Link>
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm dark:border-emerald-900/50 dark:bg-emerald-900/20">
            <p className="font-medium text-emerald-800 dark:text-emerald-200">
              Give everyone a cause
            </p>
            <p className="mt-1 text-emerald-700 dark:text-emerald-300">
              Turn this into a teaching moment: in the next step you can assign each
              charity to a family member — even the kids — so they can research it and
              bring back what they learn.
            </p>
          </div>
        </div>
      )}

      {step === 'decide' && (
        <div className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Decide as a family</h2>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Add the charities you explored and set how much weight each one
              carries in your plan.
            </p>
          </div>
          <SharedPlanView planId={planId} />
        </div>
      )}

      {step === 'recap' && (
        <div className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Recap</h2>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Here&apos;s what your family decided together.
            </p>
          </div>
          <SessionRecap planId={planId} />
        </div>
      )}

      {/* Bottom bar */}
      <div className="flex items-center justify-between border-t border-slate-200 dark:border-slate-700 pt-4">
        <button
          onClick={() => setStep(prevStep(step))}
          disabled={step === 'gather'}
          className="px-4 py-2 rounded border border-slate-300 dark:border-slate-600 text-sm disabled:opacity-40"
        >
          Back
        </button>
        {onLast ? (
          <button
            onClick={() => onExit?.()}
            className="px-4 py-2 rounded bg-emerald-600 text-white text-sm font-medium"
          >
            Finish
          </button>
        ) : (
          <button
            onClick={() => setStep(nextStep(step))}
            className="px-4 py-2 rounded bg-emerald-600 text-white text-sm font-medium"
          >
            Next
          </button>
        )}
      </div>
    </div>
  );
};

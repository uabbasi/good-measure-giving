/**
 * AssignCause — a small, reusable picker for assigning a plan member to a cause.
 *
 * Reuses the existing `assigneeUid` field on `PlanItem` (no schema change). The
 * "Unassigned" option maps to `null`; every other option is a member by uid,
 * labelled with their `displayName`.
 */

import React from 'react';
import type { PlanMember } from '../../types/sharedPlan';

export const AssignCause: React.FC<{
  members: PlanMember[];
  value: string | null;
  onChange: (uid: string | null) => void;
  'aria-label'?: string;
  className?: string;
}> = ({ members, value, onChange, 'aria-label': ariaLabel, className }) => (
  <select
    value={value ?? ''}
    onChange={e => onChange(e.target.value === '' ? null : e.target.value)}
    aria-label={ariaLabel ?? 'Assign a member to this cause'}
    className={
      className ??
      'px-2 py-1 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500'
    }
  >
    <option value="">Unassigned</option>
    {members.map(m => (
      <option key={m.uid} value={m.uid}>
        {m.displayName}
      </option>
    ))}
  </select>
);

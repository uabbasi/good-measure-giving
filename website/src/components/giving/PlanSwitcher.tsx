import React, { useState } from 'react';
import { useSharedPlans } from '../../hooks/useSharedPlans';

export const PlanSwitcher: React.FC<{
  selected: string | null;                 // null = personal plan
  onSelect: (planId: string | null) => void;
}> = ({ selected, onSelect }) => {
  const { plans, createPlan } = useSharedPlans();
  // Guards against a fast double-click firing two concurrent createPlan()
  // calls, which can race on the non-transactional read-modify-write of
  // users/{uid}.sharedPlanIds and silently drop one of the two plan ids.
  const [isCreating, setIsCreating] = useState(false);

  const onCreate = async () => {
    if (isCreating) return;
    const name = window.prompt('Name this shared plan (e.g., "Khan Family")');
    if (!name) return;
    setIsCreating(true);
    try {
      const id = await createPlan(name);
      onSelect(id);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="flex items-center gap-2 mb-6">
      <button onClick={() => onSelect(null)}
        className={`px-3 py-1.5 rounded-full text-sm ${selected === null ? 'bg-emerald-600 text-white' : 'border border-slate-300'}`}>
        My plan
      </button>
      {plans.map(p => (
        <button key={p.id} onClick={() => onSelect(p.id)}
          className={`px-3 py-1.5 rounded-full text-sm ${selected === p.id ? 'bg-emerald-600 text-white' : 'border border-slate-300'}`}>
          {p.name}
        </button>
      ))}
      <button
        onClick={onCreate}
        disabled={isCreating}
        className="px-3 py-1.5 rounded-full text-sm border border-dashed border-slate-300 text-slate-500 disabled:opacity-50"
      >
        + Shared plan
      </button>
    </div>
  );
};

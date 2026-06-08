import React from 'react';
import { useSharedPlans } from '../../hooks/useSharedPlans';

export const PlanSwitcher: React.FC<{
  selected: string | null;                 // null = personal plan
  onSelect: (planId: string | null) => void;
}> = ({ selected, onSelect }) => {
  const { plans, createPlan } = useSharedPlans();

  const onCreate = async () => {
    const name = window.prompt('Name this shared plan (e.g., "Khan Family")');
    if (!name) return;
    const id = await createPlan(name);
    onSelect(id);
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
      <button onClick={onCreate} className="px-3 py-1.5 rounded-full text-sm border border-dashed border-slate-300 text-slate-500">
        + Shared plan
      </button>
    </div>
  );
};

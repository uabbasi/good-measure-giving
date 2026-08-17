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
  const [isNaming, setIsNaming] = useState(false);
  const [nameInput, setNameInput] = useState('');

  const cancelNaming = () => {
    setIsNaming(false);
    setNameInput('');
  };

  const onCreate = async () => {
    const name = nameInput.trim();
    if (!name || isCreating) return;
    setIsCreating(true);
    try {
      const id = await createPlan(name);
      onSelect(id);
      cancelNaming();
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="flex items-center gap-2 mb-6 flex-wrap">
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
      {isNaming ? (
        <div className="flex items-center gap-1.5">
          <input
            type="text"
            autoFocus
            value={nameInput}
            onChange={e => setNameInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') onCreate();
              if (e.key === 'Escape') cancelNaming();
            }}
            placeholder='Plan name, e.g. "Khan Family"'
            aria-label="New shared plan name"
            className="px-3 py-1.5 rounded-full text-sm border border-slate-300 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
          />
          <button
            onClick={onCreate}
            disabled={!nameInput.trim() || isCreating}
            className="px-3 py-1.5 rounded-full text-sm bg-emerald-600 text-white disabled:opacity-50"
          >
            Create
          </button>
          <button onClick={cancelNaming} className="px-3 py-1.5 rounded-full text-sm text-slate-500">
            Cancel
          </button>
        </div>
      ) : (
        <button
          onClick={() => setIsNaming(true)}
          className="px-3 py-1.5 rounded-full text-sm border border-dashed border-slate-300 text-slate-500"
        >
          + Shared plan
        </button>
      )}
    </div>
  );
};

import type { PlanItem } from '../types/sharedPlan';

export interface RecapSummary { charityCount: number; causeCount: number; }

export function summarize(items: PlanItem[]): RecapSummary {
  return {
    charityCount: items.filter(i => i.kind === 'charity').length,
    causeCount: new Set(items.filter(i => i.kind === 'category').map(i => i.ref)).size,
  };
}

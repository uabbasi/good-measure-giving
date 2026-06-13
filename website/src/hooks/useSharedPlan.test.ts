import { describe, it, expect } from 'vitest';
import { historyIdToPrune } from '../lib/sharedPlanLogic';

// useSharedPlan's transactional writes are covered by the emulator e2e
// (tests/e2e/shared-plan-emulator.spec.ts). Pure merge/prune logic is unit-tested
// in sharedPlanLogic.test.ts; this asserts the prune wiring contract the hook relies on.
describe('useSharedPlan history wiring', () => {
  it('prunes the (revision - HISTORY_MAX) entry once the buffer is full', () => {
    expect(historyIdToPrune(21, 20)).toBe('1');
  });
});

import { describe, it, expect } from 'vitest';
import { SESSION_STEPS, nextStep, prevStep, isLastStep } from './givingSession';

describe('giving session steps', () => {
  it('orders gather → explore → decide → recap', () => {
    expect(SESSION_STEPS).toEqual(['gather', 'explore', 'decide', 'recap']);
  });
  it('advances and stops at recap', () => {
    expect(nextStep('gather')).toBe('explore');
    expect(nextStep('recap')).toBe('recap');
    expect(isLastStep('recap')).toBe(true);
  });
  it('goes back and stops at gather', () => {
    expect(prevStep('explore')).toBe('gather');
    expect(prevStep('gather')).toBe('gather');
  });
});

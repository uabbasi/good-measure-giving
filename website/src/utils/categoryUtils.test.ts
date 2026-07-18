import { describe, expect, it } from 'vitest';
import { normalizeCauseArea } from './categoryUtils';

describe('normalizeCauseArea — tolerant separator matching', () => {
  // The live bug: space-form labels silently dropped out of the browse
  // cause-filter buckets because only the underscore form was registered.
  it('maps space-form and underscore-form GLOBAL HEALTH to the same bucket', () => {
    expect(normalizeCauseArea('GLOBAL_HEALTH')).toBe('health');
    expect(normalizeCauseArea('GLOBAL HEALTH')).toBe('health');
    expect(normalizeCauseArea('GLOBAL HEALTH')).toBe(normalizeCauseArea('GLOBAL_HEALTH'));
  });

  it('tolerates hyphen, space, and underscore variants of other canonical labels', () => {
    expect(normalizeCauseArea('RELIGIOUS_CULTURAL')).toBe('muslim-community');
    expect(normalizeCauseArea('RELIGIOUS-CULTURAL')).toBe('muslim-community');
    expect(normalizeCauseArea('RELIGIOUS CULTURAL')).toBe('muslim-community');

    expect(normalizeCauseArea('DOMESTIC_POVERTY')).toBe('domestic-poverty');
    expect(normalizeCauseArea('DOMESTIC POVERTY')).toBe('domestic-poverty');

    expect(normalizeCauseArea('RELIGIOUS_EDUCATION')).toBe('education');
    expect(normalizeCauseArea('RELIGIOUS EDUCATION')).toBe('education');
  });

  it('is case-insensitive', () => {
    expect(normalizeCauseArea('global health')).toBe('health');
    expect(normalizeCauseArea('Humanitarian')).toBe('emergency-relief');
  });

  it('preserves bucket membership for previously-working exact values', () => {
    expect(normalizeCauseArea('HUMANITARIAN')).toBe('emergency-relief');
    expect(normalizeCauseArea('EDUCATION')).toBe('education');
    expect(normalizeCauseArea('ADVOCACY')).toBe('advocacy');
    expect(normalizeCauseArea('EXTREME_POVERTY')).toBe('emergency-relief');
    expect(normalizeCauseArea('CIVIC_ADVOCACY')).toBe('advocacy');
  });

  it('returns null for unmapped labels and empty input (no taxonomy change)', () => {
    expect(normalizeCauseArea(null)).toBeNull();
    expect(normalizeCauseArea(undefined)).toBeNull();
    expect(normalizeCauseArea('')).toBeNull();
    // Compound labels that were never in any bucket stay unmapped.
    expect(normalizeCauseArea('YOUTH DEVELOPMENT')).toBeNull();
    expect(normalizeCauseArea('GLOBAL HEALTH / CANCER RESEARCH')).toBeNull();
  });
});

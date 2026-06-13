import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { VerdictHero } from './VerdictHero';
import { buildCdpData } from './useCdpData';
import type { CharityProfile } from '../../../types';

vi.mock('../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const make = (over: any = {}): CharityProfile => ({
  name: 'Test Org', category: 'relief',
  amalEvaluation: {
    charity_ein: '1', charity_name: 'Test Org', amal_score: 82, wallet_tag: 'ZAKAT-ELIGIBLE',
    evaluation_date: '2026-01-01', confidence_scores: { impact: 44, alignment: 41 },
    score_details: { risks: {}, risk_deduction: 3 }, ...over.amal,
  },
  rawData: {}, ...over,
} as unknown as CharityProfile);

describe('VerdictHero', () => {
  it('renders the GMG score and dimension values', () => {
    render(<VerdictHero data={buildCdpData(make(), true)} />);
    expect(screen.getByText('82')).toBeTruthy();
    expect(screen.getByText(/44/)).toBeTruthy();
    expect(screen.getByText(/41/)).toBeTruthy();
  });

  it('shows assessment label instead of a number when amal_score is null', () => {
    const c = make({ amal: { amal_score: null } });
    render(<VerdictHero data={buildCdpData(c, true)} />);
    expect(screen.queryByText('82')).toBeNull();
    // With a null score the org is treated as new/pre-990, so the fallback
    // assessment label ('Limited Basis') renders in place of the number.
    expect(screen.getByText('Limited Basis')).toBeTruthy();
  });
});

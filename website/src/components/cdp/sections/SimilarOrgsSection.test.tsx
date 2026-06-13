import type { ReactElement } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SimilarOrgsSection } from './SimilarOrgsSection';
import { buildCdpData } from '../useCdpData';

vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));
vi.mock('../../../hooks/useCharities', () => ({ useCharities: () => ({ charities: [] }) }));

const charity = {
  name: 'T', category: 'relief', ein: '1', rawData: {},
  amalEvaluation: {
    charity_ein: '1', charity_name: 'T', amal_score: 82,
    wallet_tag: 'SADAQAH-ELIGIBLE', evaluation_date: 'x',
    confidence_scores: { impact: 44, alignment: 41 },
    score_details: { risks: {}, risk_deduction: 3 },
    rich_narrative: {
      all_citations: [],
      peer_comparison: { peer_group: 'US relief peers' },
      similar_organizations: [{ name: 'Alpha Relief' }, { name: 'Beta Aid' }, { name: 'Gamma Fund' }, { name: 'Delta Org' }],
    },
    baseline_narrative: { summary: 's', headline: 'h', strengths: [], areas_for_improvement: [], amal_score_rationale: 'r' },
  },
} as any;

const renderIn = (ui: ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('SimilarOrgsSection', () => {
  it('renders #similar-orgs anchor with peer group and orgs when signed in', () => {
    const { container } = renderIn(<SimilarOrgsSection data={buildCdpData(charity, true)} />);
    expect(container.querySelector('#similar-orgs')).toBeTruthy();
    expect(screen.getByText('US relief peers')).toBeTruthy();
    expect(screen.getByText('Alpha Relief')).toBeTruthy();
  });

  it('shows only first 3 names and a sign-in CTA when anonymous', () => {
    renderIn(<SimilarOrgsSection data={buildCdpData(charity, false)} />);
    expect(screen.getByText('Alpha Relief')).toBeTruthy();
    expect(screen.getByText('Gamma Fund')).toBeTruthy();
    expect(screen.queryByText('Delta Org')).toBeNull();
    expect(screen.getByText(/Sign in/)).toBeTruthy();
  });
});

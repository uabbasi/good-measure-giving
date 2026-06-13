import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FinancialsSection } from './FinancialsSection';
import { buildCdpData } from '../useCdpData';

vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const charity = {
  name: 'T', category: 'relief', ein: '1',
  rawData: {},
  financials: {
    totalRevenue: 5_000_000,
    totalExpenses: 4_000_000,
    programExpenses: 3_400_000,
    adminExpenses: 400_000,
    fundraisingExpenses: 200_000,
    netAssets: 8_000_000,
    totalAssets: 9_000_000,
    totalLiabilities: 1_000_000,
    workingCapitalMonths: 14.2,
  },
  amalEvaluation: {
    charity_ein: '1', charity_name: 'T', amal_score: 82,
    wallet_tag: 'SADAQAH-ELIGIBLE', evaluation_date: 'x',
    confidence_scores: { impact: 44, alignment: 41 },
    score_details: { risks: {}, risk_deduction: 3 },
    rich_narrative: {
      financial_deep_dive: {
        yearly_financials: [
          { year: 2021, revenue: 4_000_000 },
          { year: 2022, revenue: 4_500_000 },
          { year: 2023, revenue: 5_000_000 },
        ],
        revenue_cagr_3yr: 11.8,
        reserves_months: 14.2,
      },
      grantmaking_profile: {
        is_significant_grantmaker: true,
        total_grants: 1_200_000,
        grant_count: 12,
        domestic_grants: 800_000,
        foreign_grants: 400_000,
        top_recipients: ['Org A', 'Org B', 'Org C'],
        regions_served: ['USA', 'Kenya'],
      },
      all_citations: [],
    },
    baseline_narrative: { summary: 's', headline: 'h', strengths: [], areas_for_improvement: [], amal_score_rationale: 'r' },
  },
} as any;

describe('FinancialsSection', () => {
  it('renders #financials anchor for a rich charity', () => {
    const { container } = render(<FinancialsSection data={buildCdpData(charity, true)} />);
    expect(container.querySelector('#financials')).toBeTruthy();
  });

  it('shows rich-only values (net assets) when signed in', () => {
    render(<FinancialsSection data={buildCdpData(charity, true)} />);
    expect(screen.getByText('Net Assets')).toBeTruthy();
    expect(screen.getByText('Expense Breakdown')).toBeTruthy();
  });

  it('partial gate: anon sees revenue but rich detail is gated', () => {
    const { container } = render(<FinancialsSection data={buildCdpData(charity, false)} />);
    expect(container.querySelector('#financials')).toBeTruthy();
    // Revenue still visible
    expect(screen.getByText('Annual Revenue')).toBeTruthy();
    // Net assets (rich-only) absent
    expect(screen.queryByText('Net Assets')).toBeNull();
    // Expense breakdown shows ContentPreview title, not the real card
    expect(screen.getByText('Expense Breakdown')).toBeTruthy();
    // Partial-gate CTA for the overview rows (expenses/assets/working capital)
    expect(screen.getByText(/to see expenses, assets, and working capital/i)).toBeTruthy();
  });
});

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LeadershipSection } from './LeadershipSection';
import { buildCdpData } from '../useCdpData';

vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const charity = {
  name: 'Test Org', category: 'relief', ein: '12-3456789', rawData: {},
  amalEvaluation: {
    charity_ein: '12-3456789', charity_name: 'Test Org', amal_score: 82,
    wallet_tag: 'SADAQAH-ELIGIBLE', evaluation_date: 'x',
    baseline_narrative: { summary: 'A summary.', headline: 'A headline', strengths: [], areas_for_improvement: [], amal_score_rationale: 'r' },
    rich_narrative: {
      headline: 'rich-h',
      organizational_capacity: { ceo_name: 'Jane Doe', board_size: 9 },
      long_term_outlook: { years_operating: 12, maturity_stage: 'Mature', room_for_funding: 'Moderate' },
    },
  },
} as any;

describe('LeadershipSection', () => {
  it('renders a #leadership section anchor', () => {
    const { container } = render(<LeadershipSection data={buildCdpData(charity, true)} />);
    expect(container.querySelector('#leadership')).toBeTruthy();
  });

  it('renders the CEO name when rich data is available', () => {
    render(<LeadershipSection data={buildCdpData(charity, true)} />);
    expect(screen.getByText('Jane Doe')).toBeTruthy();
  });

  it('shows ContentPreview gate for leadership when canViewRich is false', () => {
    render(<LeadershipSection data={buildCdpData(charity, false)} />);
    // ContentPreview renders its title prop instead of the authed leadership card.
    expect(screen.getByText('Leadership & Governance')).toBeTruthy();
    // Rich-only value (CEO name) must NOT leak to anonymous viewers.
    expect(screen.queryByText('Jane Doe')).toBeNull();
  });
});

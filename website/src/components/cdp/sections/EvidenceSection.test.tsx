import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EvidenceSection } from './EvidenceSection';
import { buildCdpData } from '../useCdpData';

vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const charity = {
  name: 'T', category: 'relief', ein: '1', rawData: {},
  amalEvaluation: {
    charity_ein: '1', charity_name: 'T', amal_score: 82,
    wallet_tag: 'SADAQAH-ELIGIBLE', evaluation_date: 'x',
    confidence_scores: { impact: 44, alignment: 41 },
    score_details: { risks: {}, risk_deduction: 3 },
    rich_narrative: {
      impact_evidence: { evidence_grade: 'A', evidence_grade_explanation: 'Strong RCT evidence base.', rct_available: true },
      all_citations: [],
    },
    baseline_narrative: { summary: 's', headline: 'h', strengths: [], areas_for_improvement: [], amal_score_rationale: 'r' },
  },
} as any;

describe('EvidenceSection', () => {
  it('renders #evidence anchor for a rich charity', () => {
    const { container } = render(<EvidenceSection data={buildCdpData(charity, true)} />);
    expect(container.querySelector('#evidence')).toBeTruthy();
  });

  it('renders the evidence grade explanation when rich', () => {
    render(<EvidenceSection data={buildCdpData(charity, true)} />);
    expect(screen.getByText(/Strong RCT evidence base/i)).toBeTruthy();
  });

  it('shows the ContentPreview gate and hides rich detail when anonymous', () => {
    const { container } = render(<EvidenceSection data={buildCdpData(charity, false)} />);
    expect(container.querySelector('#evidence')).toBeTruthy();
    expect(screen.getByText('Evidence')).toBeTruthy();
    expect(screen.queryByText(/Strong RCT evidence base/i)).toBeNull();
  });
});

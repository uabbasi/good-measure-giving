// GmgBrowse's Risk column and the charity detail page's Risk stat come from
// two disjoint fields — /browse's light index carries only ui_signals_v1
// (a governance-completeness/red-flag signal), while the detail page reads
// score_details.risks.overall_risk_level (the full, named risk register).
// Found via manual QA: Against Malaria Foundation shows Weak on /browse
// (0/10 Governance — unknown board size, not a red flag) and LOW risk on
// its own page — a direct contradiction across 44 of 135 published
// charities. The full fix (make the two agree) needs either a pipeline
// export change or a heavier index and is filed separately; this pins the
// scoped fix that ships today: the column no longer claims to BE the risk
// assessment, so the two numbers reads as different signals, not a bug.

import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { GmgBrowse } from './GmgBrowse';

vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => false }));

const charity = {
  ein: '00-0000000',
  name: 'Test Charity',
  category: 'Humanitarian Relief',
  primaryCategory: 'HUMANITARIAN',
  totalRevenue: 5_000_000,
  isMuslimCharity: false,
  amalEvaluation: {
    wallet_tag: 'SADAQAH-ONLY',
    amal_score: 60,
    confidence_scores: { impact: 40, alignment: 40, dataConfidence: 0.8 },
  },
  ui_signals_v1: {
    signal_states: { financial_health: 'moderate', risk: 'limited', donor_fit: 'moderate' },
    evidence_stage: 'Verified',
  },
};

vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ charities: [charity], summaries: [charity], loading: false, error: null }),
}));

describe('GmgBrowse — Risk column tooltip', () => {
  it('does not claim to be the full risk assessment', () => {
    const { container } = render(
      <MemoryRouter>
        <GmgBrowse isDark={false} />
      </MemoryRouter>,
    );
    const riskHeader = [...container.querySelectorAll('[title]')].find((el) =>
      el.textContent?.includes('Risk'),
    );
    expect(riskHeader).toBeTruthy();
    const tip = riskHeader!.getAttribute('title') ?? '';
    expect(tip).not.toContain('governance, transparency and red-flag checks. Strong = lowest risk.'); // the old, unqualified claim
    expect(tip).toMatch(/not the full risk assessment/i);
    expect(tip).toMatch(/charity's own page/i);
  });
});

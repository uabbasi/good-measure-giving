/**
 * GmgCharityDetail — similar-charities block
 *
 * Asserts that the SSR-crawlable similar-charities section renders real
 * trailing-slash <a href="/charity/<ein>/"> links for every visitor (no
 * auth gate), and correctly excludes the current charity from the list.
 */

import type { ReactElement } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { GmgCharityDetail } from './GmgCharityDetail';

// Suppress sub-components that have their own context/auth dependencies
// so we can test the similar-charities block in isolation.
vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => false }));

// Provide a mock charities index that includes the current charity plus
// two same-category same-zakatStatus peers and one different-category org.
vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({
    summaries: [
      {
        ein: '12-3456789',
        name: 'Target Org',
        category: 'HUMANITARIAN',
        primaryCategory: 'HUMANITARIAN',
        walletTag: 'SADAQAH-ELIGIBLE',
        zakatClassification: null,
        amalScore: 80,
      },
      {
        ein: '11-1111111',
        name: 'Similar Alpha',
        category: 'HUMANITARIAN',
        primaryCategory: 'HUMANITARIAN',
        walletTag: 'SADAQAH-ELIGIBLE',
        zakatClassification: null,
        amalScore: 75,
      },
      {
        ein: '22-2222222',
        name: 'Similar Beta',
        category: 'HUMANITARIAN',
        primaryCategory: 'HUMANITARIAN',
        walletTag: 'SADAQAH-ELIGIBLE',
        zakatClassification: null,
        amalScore: 70,
      },
      {
        ein: '33-3333333',
        name: 'Different Category Org',
        category: 'EDUCATION',
        primaryCategory: 'EDUCATION',
        walletTag: 'SADAQAH-ELIGIBLE',
        zakatClassification: null,
        amalScore: 90,
      },
    ],
    loading: false,
    charities: [],
  }),
}));

/** Minimal charity prop that satisfies adaptCharity without crashing. */
const targetCharity: any = {
  ein: '12-3456789',
  name: 'Target Org',
  category: 'HUMANITARIAN',
  primaryCategory: 'HUMANITARIAN',
  programs: [],
  populationsServed: [],
  geographicCoverage: [],
  amalEvaluation: {
    charity_ein: '12-3456789',
    charity_name: 'Target Org',
    amal_score: 80,
    wallet_tag: 'SADAQAH-ELIGIBLE',
    zakat_classification: null,
    evaluation_date: '2026-01-01',
    confidence_scores: { impact: 40, alignment: 40 },
    score_details: { risks: {}, risk_deduction: 0 },
    baseline_narrative: {
      summary: 'Test summary',
      headline: 'Test headline',
      strengths: [],
      areas_for_improvement: [],
      amal_score_rationale: '',
    },
  },
  financials: {
    totalRevenue: 1_000_000,
    programExpenseRatio: 0.85,
    programExpenses: 850_000,
    adminExpenses: 100_000,
    fundraisingExpenses: 50_000,
  },
};

/** A charity whose cause area matches nothing in the mock pool — produces 0 similar. */
const uniqueCharity: any = {
  ...targetCharity,
  ein: '99-9999999',
  category: 'UNIQUE_CAUSE_XYZ',
  primaryCategory: 'UNIQUE_CAUSE_XYZ',
  amalEvaluation: {
    ...targetCharity.amalEvaluation,
    charity_ein: '99-9999999',
  },
};

const renderIn = (ui: ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('GmgCharityDetail — similar charities block', () => {
  it('renders trailing-slash /charity/<ein>/ links for same-category peers (SSR-crawlable)', () => {
    const { container } = renderIn(<GmgCharityDetail charity={targetCharity} isDark={false} />);

    // The section uses aria-labelledby to satisfy the accessible heading requirement.
    const section = container.querySelector('[aria-labelledby="gmg-similar-heading"]');
    expect(section).toBeTruthy();

    const hrefs = Array.from(section!.querySelectorAll('a[href]')).map((a) => a.getAttribute('href'));
    expect(hrefs).toContain('/charity/11-1111111/');
    expect(hrefs).toContain('/charity/22-2222222/');
  });

  it('excludes the current charity from the similar block', () => {
    const { container } = renderIn(<GmgCharityDetail charity={targetCharity} isDark={false} />);

    const section = container.querySelector('[aria-labelledby="gmg-similar-heading"]');
    expect(section).toBeTruthy();

    const hrefs = Array.from(section!.querySelectorAll('a[href]')).map((a) => a.getAttribute('href'));
    // Current charity must NOT appear in its own similar list.
    expect(hrefs).not.toContain('/charity/12-3456789/');
  });

  it('does not render the section when fewer than 2 similar charities are found', () => {
    // uniqueCharity has a cause area not present in the mock pool → 0 matches.
    const { container } = renderIn(<GmgCharityDetail charity={uniqueCharity} isDark={false} />);

    const section = container.querySelector('[aria-labelledby="gmg-similar-heading"]');
    expect(section).toBeNull();
  });

  it('does not render the different-category org in the similar block', () => {
    const { container } = renderIn(<GmgCharityDetail charity={targetCharity} isDark={false} />);

    const section = container.querySelector('[aria-labelledby="gmg-similar-heading"]');
    // EDUCATION charity should not appear even though it has a higher score.
    const hrefs = Array.from(section!.querySelectorAll('a[href]')).map((a) => a.getAttribute('href'));
    expect(hrefs).not.toContain('/charity/33-3333333/');
  });
});

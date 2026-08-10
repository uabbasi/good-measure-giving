/**
 * GmgCharityDetail — page content max-width
 *
 * Before this fix the page had no width cap at all: body copy ran the full
 * viewport (~180 characters per line at 1440px). The header, stat strip, and
 * six-section grid must all sit inside a centered, capped-width container.
 */

import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import GmgCharityDetail from './GmgCharityDetail';

vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => false }));
vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ summaries: [], loading: false, charities: [] }),
}));

const charity = {
  ein: '12-3456789',
  name: 'Test Charity',
  lastUpdated: '2026-08-02',
  financials: { fiscalYear: 2024, totalRevenue: 1000000 },
  amalEvaluation: { amal_score: 60, score_details: { data_confidence: { data_age_years: 1 } } },
};

describe('GmgCharityDetail — content max-width', () => {
  it('wraps the header inside a centered, capped-width container', () => {
    const { container } = render(
      <MemoryRouter>
        <GmgCharityDetail charity={charity} isDark={false} />
      </MemoryRouter>,
    );
    const h1 = container.querySelector('h1');
    expect(h1).not.toBeNull();
    let capped: HTMLElement | null = h1;
    while (capped && capped.style.maxWidth !== '1280px') capped = capped.parentElement;
    expect(capped).not.toBeNull();
    expect(capped?.style.margin).toBe('0px auto');
  });
});

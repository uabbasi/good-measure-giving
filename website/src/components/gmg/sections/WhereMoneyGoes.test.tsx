import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { WhereMoneyGoes } from './WhereMoneyGoes';
import { gmgPalette } from '../tokens';
import { adaptCharity } from '../charityAdapter';

const mockMember = vi.fn(() => false);
vi.mock('../../../auth/useAuth', () => ({ useCommunityMember: () => mockMember() }));
vi.mock('../../../auth/SignInButton', () => ({ SignInButton: () => <button>Sign in</button> }));
vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const p = gmgPalette(false);
const dir = path.resolve(__dirname, '../../../../data/charities');
const load = (file: string) => adaptCharity(JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8')));

// charity: water — grantsData is 56 rows, none with a name or EIN, so
// topRecipients is empty while unattributed.amount is ~$88.0M. Exactly the
// "empty list would lie" case the brief calls out.
const charityWater = () => load('charity-22-3936753.json');
// Has named topRecipients (10) — the ordinary gated-list case.
const withNamedRecipients = () => load('charity-04-2535767.json');
// Save the Children — most recent tax year has BOTH named domestic
// recipients ($55.5M named) and anonymous foreign grants ($550.7M
// unattributed). This is the case Fix 1 covers: a ternary previously
// rendered only the named list here, hiding the unattributed total.
const bothNamedAndUnattributed = () => load('charity-06-0726487.json');
// No grantsData at all -> grantFlows is null.
const noGrants = () => load('charity-01-0548371.json');
// All three GIK signals present, including domesticBurnRate: 0 (a real
// value, not an absent one).
const allGikSignals = () => load('charity-13-1760110.json');

describe('WhereMoneyGoes', () => {
  it('renders the expense split derived from real filed figures', () => {
    const c = withNamedRecipients();
    expect(c.programRatioPct).not.toBeNull();
    const { container } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain('Expense allocation');
  });

  it('renders the exact dollar figures behind the expense-split percentages', () => {
    // charity-04-2535767 (withNamedRecipients) has all four figures filed.
    const c = withNamedRecipients();
    expect(c.programExpenses).not.toBeNull();
    expect(c.adminExpenses).not.toBeNull();
    expect(c.fundraisingExpenses).not.toBeNull();
    expect(c.netAssets).not.toBeNull();

    const { container } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain('Program expenses');
    expect(container.textContent).toContain('$43,724,145');
    expect(container.textContent).toContain('Admin expenses');
    expect(container.textContent).toContain('$3,667,068');
    expect(container.textContent).toContain('Fundraising');
    expect(container.textContent).toContain('$2,888,100');
    expect(container.textContent).toContain('Net assets');
    expect(container.textContent).toContain('$61,915,117');
  });

  it('omits a figure row rather than rendering it blank or as $0 when that field is unfiled', () => {
    // charity-93-1556038: programExpenses/adminExpenses/fundraisingExpenses
    // are filed, but netAssets is specifically null — the one-field-missing
    // case a "guard the whole grid" implementation would get wrong. Only one
    // year of financials, so the multi-year trend chart (which has its own,
    // unrelated "Net assets" series legend) does not render and cannot mask
    // a false pass on the assertion below.
    const c = load('charity-93-1556038.json');
    expect(c.financialSeries.length).toBeLessThan(2);
    expect(c.programExpenses).not.toBeNull();
    expect(c.netAssets).toBeNull();

    const { container, queryByText } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    // The fields that ARE filed still render.
    expect(container.textContent).toContain('Program expenses');
    // The missing field's label must not appear at all — not as a blank
    // value next to it, and never fabricated as $0.
    expect(queryByText('Net assets')).toBeNull();
    expect(container.textContent).not.toContain('$0');
  });

  it('renders the multi-year trend chart only when there are >= 2 years', () => {
    const withSeries = load('charity-01-0548371.json');
    expect(withSeries.financialSeries.length).toBeGreaterThanOrEqual(2);
    const { container } = render(<WhereMoneyGoes c={withSeries} p={p} isMobile={false} padX={16} />);
    expect(container.querySelector('svg')).not.toBeNull();

    const noSeries = load('charity-20-8085421.json');
    expect(noSeries.financialSeries.length).toBeLessThan(2);
    const { container: container2 } = render(<WhereMoneyGoes c={noSeries} p={p} isMobile={false} padX={16} />);
    expect(container2.querySelector('svg')).toBeNull();
  });

  it('states the unattributed total plainly instead of rendering an empty recipient list', () => {
    mockMember.mockReturnValue(false);
    const c = charityWater();
    expect(c.grantFlows).not.toBeNull();
    expect(c.grantFlows!.topRecipients).toHaveLength(0);
    expect(c.grantFlows!.unattributed.amount).toBeGreaterThan(0);

    const { container, queryByText } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    // The unattributed total (~$88.0M across 56 grants) must be stated.
    expect(container.textContent).toContain('56 grants');
    expect(container.textContent).toMatch(/\$88(\.0)?M/);
    // No gate/sign-in prompt should appear here — there is nothing gated to tease.
    expect(queryByText('Sign in')).toBeNull();
  });

  it('explains anonymous grants by IRS form design, not by inventing a disaster-relief/households reason', () => {
    const c = charityWater();
    const { container } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    const text = container.textContent ?? '';
    // The old copy claimed these were commonly disaster relief paid to
    // individual households — false, and it implies the money went to
    // individuals rather than (typically) foreign implementing
    // organizations. Every anonymous row in the corpus is actually a
    // foreign grant that Schedule F reports without a name field at all.
    expect(text).not.toContain('individual households');
    expect(text).not.toContain('disaster relief');
    expect(text.toLowerCase()).toContain('outside the us');
    expect(text.toLowerCase()).toContain('schedule f');
  });

  it('shows a by-purpose breakdown for the unattributed total when purposes are available', () => {
    const c = charityWater();
    expect(c.grantFlows!.unattributedByPurpose.length).toBeGreaterThan(0);
    const { container } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    for (const u of c.grantFlows!.unattributedByPurpose) {
      expect(container.textContent).toContain(u.purpose);
    }
  });

  it('renders both the named recipients and the unattributed total for a charity with both, instead of hiding one', () => {
    mockMember.mockReturnValue(false);
    const c = bothNamedAndUnattributed();
    expect(c.grantFlows!.topRecipients.length).toBeGreaterThan(0);
    expect(c.grantFlows!.unattributed.amount).toBeGreaterThan(0);

    const { container, queryByText } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    // The gate for named recipients is present (there IS something to gate)...
    expect(queryByText('Sign in')).not.toBeNull();
    for (const r of c.grantFlows!.topRecipients) {
      expect(queryByText(r.name)).toBeNull();
    }
    // ...and the public unattributed total is ALSO present, not suppressed
    // by the gated block existing. Before the fix this branch was an
    // if/else, so this total never rendered when topRecipients was non-empty.
    expect(container.textContent).toContain('90 grants');
    expect(container.textContent).toMatch(/\$550\.7M/);
  });

  it('gates topRecipients behind CommunityGate when they exist, but keeps totals and byRegion public', () => {
    mockMember.mockReturnValue(false);
    const c = withNamedRecipients();
    expect(c.grantFlows!.topRecipients.length).toBeGreaterThan(0);

    const { queryByText, container } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    // Signed out: the named recipients must not leak into the DOM.
    for (const r of c.grantFlows!.topRecipients) {
      expect(queryByText(r.name)).toBeNull();
    }
    // But the public totals must still render.
    expect(container.textContent).toContain('Total granted');
  });

  it('shows named recipients to a signed-in community member', () => {
    mockMember.mockReturnValue(true);
    const c = withNamedRecipients();
    const first = c.grantFlows!.topRecipients[0];
    const { getByText } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    expect(getByText(first.name, { exact: false })).toBeInTheDocument();
  });

  it('renders byRegion as a public breakdown', () => {
    const c = load('charity-06-0726487.json');
    expect(c.grantFlows?.byRegion.length).toBeGreaterThan(0);
    mockMember.mockReturnValue(false);
    const { container } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    for (const r of c.grantFlows!.byRegion) {
      expect(container.textContent).toContain(r.region);
    }
  });

  it('renders money and reserves concerns', () => {
    const c = load('charity-04-3810161.json');
    expect(c.concerns.byAnchor.money.length).toBeGreaterThan(0);
    const { container } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    for (const concern of c.concerns.byAnchor.money) {
      expect(container.textContent).toContain(concern.headline);
    }
  });

  it('renders a charity with no grants at all without throwing and without a grants block', () => {
    const c = noGrants();
    expect(c.grantFlows).toBeNull();
    const { container } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).not.toContain('Total granted');
  });

  it('renders all three GIK/burn-rate signals with a plain-language gloss', () => {
    const c = allGikSignals();
    expect(c.noncashRatio).not.toBeNull();
    expect(c.cashAdjustedProgramRatio).not.toBeNull();
    expect(c.domesticBurnRate).toBe(0);
    const { container } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    // Values, rounded to whole percent.
    expect(container.textContent).toContain('16%');
    expect(container.textContent).toContain('78%');
    expect(container.textContent).toContain('0%');
    // domesticBurnRate: 0 must still render its label — a falsy-value bug
    // would drop this fact even though 0 is a real, present signal.
    expect(container.textContent).toContain('Domestic spending share');
    // Non-expert glosses, not bare numbers.
    expect(container.textContent).toContain('gift');
    expect(container.textContent).toContain('cash');
  });

  it('renders only the GIK signals a charity actually has', () => {
    const c = withNamedRecipients(); // noncashRatio present, the other two null
    expect(c.noncashRatio).not.toBeNull();
    expect(c.cashAdjustedProgramRatio).toBeNull();
    expect(c.domesticBurnRate).toBeNull();
    const { container, queryByText } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain('Non-cash share of revenue');
    expect(queryByText('Program ratio, cash only')).toBeNull();
    expect(queryByText('Domestic spending share')).toBeNull();
  });

  it('collapses the GIK block cleanly when a charity has none of the three signals', () => {
    const c = noGrants();
    expect(c.noncashRatio).toBeNull();
    expect(c.cashAdjustedProgramRatio).toBeNull();
    expect(c.domesticBurnRate).toBeNull();
    const { queryByText } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    expect(queryByText('Non-cash share of revenue')).toBeNull();
    expect(queryByText('Program ratio, cash only')).toBeNull();
    expect(queryByText('Domestic spending share')).toBeNull();
  });

  it('lays out GIK signals as a single column on mobile and a grid on desktop', () => {
    const c = allGikSignals();
    const { container: mobile } = render(<WhereMoneyGoes c={c} p={p} isMobile={true} padX={16} />);
    expect(mobile.innerHTML).toContain('grid-template-columns: 1fr;');

    const { container: desktop } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
    expect(desktop.innerHTML).toContain('repeat(auto-fit');
  });

  it('always mounts the section wrapper even for a minimal charity', () => {
    const bare = adaptCharity({ ein: '00-0000000', name: 'Bare Org' });
    const { container } = render(<WhereMoneyGoes c={bare} p={p} isMobile={false} padX={16} />);
    expect(container.querySelector('[data-section="money"]')).not.toBeNull();
  });

  it('renders every real charity in the corpus without throwing', () => {
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
    let rendered = 0;
    for (const f of files) {
      const c = load(f);
      const { unmount } = render(<WhereMoneyGoes c={c} p={p} isMobile={false} padX={16} />);
      rendered += 1;
      unmount();
    }
    expect(rendered).toBe(files.length);
  }, 30000); // renders 166 charities; generous margin under worker contention
});

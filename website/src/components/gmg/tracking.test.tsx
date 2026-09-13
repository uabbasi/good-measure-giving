// @vitest-environment-options {"url":"https://goodmeasuregiving.org/"}
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { GmgBrowse } from './GmgBrowse';
import { GmgCharityDetail } from './GmgCharityDetail';
import { GmgLanding } from './GmgLanding';

const charities = [{ ein: '12-3456789', name: 'Test Relief', tier: 'rich', website: 'https://example.org', donationUrl: 'https://example.org/donate' }];
let mobile = false;
vi.mock('../../hooks/useCharities', () => ({ useCharities: () => ({ charities, summaries: [], loading: false }) }));
vi.mock('../../auth/useAuth', () => ({ useCommunityMember: () => false }));
vi.mock('../../auth/SignInButton', () => ({ SignInButton: () => <button>Sign in</button> }));
vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => mobile }));

beforeEach(() => {
  window.gtag = vi.fn();
  window.history.replaceState(null, '', '/');
  sessionStorage.clear();
  vi.useFakeTimers();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  delete window.gtag;
});
const events = (name: string) => vi.mocked(window.gtag!).mock.calls.filter(([, event]) => event === name);

it.each([false, true])('tracks a row or name click once, excluding compare controls (mobile=%s)', (isMobile) => {
  mobile = isMobile;
  const { container } = render(<MemoryRouter><GmgBrowse isDark={false} /></MemoryRouter>);
  fireEvent.click(screen.getByRole('checkbox', { name: /Select Test Relief to compare/ }));
  expect(events('charity_card_click')).toHaveLength(0);
  fireEvent.click(screen.getByRole('link', { name: 'Test Relief' }));
  expect(events('charity_card_click')).toHaveLength(1);
  fireEvent.click(container.querySelector(isMobile ? '[data-charity-card]' : 'tbody tr')!);
  expect(events('charity_card_click')).toHaveLength(2);
  expect(events('charity_card_click')[0][2]).toMatchObject({ charity_id: '12-3456789', charity_name: 'Test Relief', charity_tier: 'rich', list_position: 0 });
});

it('tracks a settled search once with its result count, including zero matches', () => {
  render(<MemoryRouter><GmgBrowse isDark={false} /></MemoryRouter>);
  const search = screen.getByRole('textbox', { name: 'Search charities' });
  fireEvent.change(search, { target: { value: 'Te' } });
  fireEvent.change(search, { target: { value: 'Test' } });
  act(() => vi.advanceTimersByTime(600));
  expect(events('search')).toHaveLength(1);
  expect(events('search')[0][2]).toMatchObject({ search_term: 'Test', result_count: 1 });
  fireEvent.change(search, { target: { value: 'no matches' } });
  act(() => vi.advanceTimersByTime(600));
  expect(events('search')[1][2]).toMatchObject({ search_term: 'no matches', result_count: 0 });
  fireEvent.change(search, { target: { value: '' } });
  act(() => vi.advanceTimersByTime(600));
  expect(events('search')).toHaveLength(2);
});

it('tracks charity views and distinguishes donate from website clicks', () => {
  const page = render(<MemoryRouter><GmgCharityDetail charity={charities[0]} isDark={false} /></MemoryRouter>);
  page.rerender(<MemoryRouter><GmgCharityDetail charity={{ ...charities[0] }} isDark={true} /></MemoryRouter>);
  expect(events('charity_view')).toHaveLength(1);
  fireEvent.click(screen.getByRole('link', { name: 'Donate ↗' }));
  fireEvent.click(screen.getByRole('link', { name: 'Visit website ↗' }));
  expect(events('donate_click')).toHaveLength(1);
  expect(events('donate_click')[0][2]).toMatchObject({ charity_id: '12-3456789', destination_url: 'https://example.org/donate' });
  expect(events('outbound_click')).toHaveLength(1);
});

it('tracks the landing page browse CTA', () => {
  render(<MemoryRouter><GmgLanding isDark={false} /></MemoryRouter>);
  fireEvent.click(screen.getByRole('link', { name: 'Browse charities' }));
  expect(events('hero_cta_click')).toHaveLength(1);
});

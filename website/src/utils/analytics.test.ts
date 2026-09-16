import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import type { UserCredential } from 'firebase/auth';
import { initializeAnalytics, trackPageView, trackSignInSuccess } from './analytics';

vi.hoisted(() => vi.stubEnv('VITE_GA_MEASUREMENT_ID', 'G-TEST123'));

vi.mock('firebase/auth', () => ({ getAdditionalUserInfo: (result: any) => result.additionalUserInfo }));

function memoryStorage() {
  const map = new Map<string, string>();
  return {
    getItem: (key: string) => (map.has(key) ? map.get(key)! : null),
    setItem: (key: string, value: string) => { map.set(String(key), String(value)); },
    removeItem: (key: string) => { map.delete(key); },
    clear: () => { map.clear(); },
    get length() { return map.size; },
    key: (index: number) => [...map.keys()][index] ?? null,
  };
}

beforeEach(() => {
  const local = memoryStorage();
  const session = memoryStorage();
  vi.stubGlobal('window', {
    location: new URL('https://goodmeasuregiving.org/'),
    localStorage: local,
    sessionStorage: session,
  });
  vi.stubGlobal('localStorage', local);
  vi.stubGlobal('sessionStorage', session);
  local.setItem('gmg_analytics_consent', 'accepted');
});

it.each([null, 'declined', 'invalid'])('does not load analytics or emit events without consent: %s', (choice) => {
  if (choice === null) localStorage.removeItem('gmg_analytics_consent');
  else localStorage.setItem('gmg_analytics_consent', choice);
  initializeAnalytics();
  expect(document.head.querySelector('script')).toBeNull();
  window.gtag = vi.fn();
  trackPageView('/browse/');
  expect(window.gtag).not.toHaveBeenCalled();
  expect(sessionStorage.length).toBe(0);
});
afterEach(() => {
  document.head.querySelectorAll('script').forEach((script) => script.remove());
  vi.unstubAllGlobals();
});

it('initializes once and leaves page views to the router', () => {
  initializeAnalytics();
  initializeAnalytics();
  const commands = window.dataLayer!.map((entry: any) => Array.from(entry));
  expect(commands.filter(([command]) => command === 'config')).toEqual([
    ['config', expect.any(String), expect.objectContaining({ send_page_view: false })],
  ]);
  expect(document.head.querySelectorAll('script[src*="googletagmanager"]')).toHaveLength(1);
  expect(document.head.querySelectorAll('script[data-cf-beacon]')).toHaveLength(1);
  trackPageView('/browse/');
  expect(window.dataLayer!.map((entry: any) => Array.from(entry)).filter(([, event]) => event === 'page_view')).toHaveLength(1);
});

it.each(['localhost', '127.0.0.1', 'roshni.local', 'amal-metrics.pages.dev', 'preview.goodmeasuregiving.org'])('excludes %s from production tracking', (hostname) => {
  Object.defineProperty(window, 'location', { value: new URL(`https://${hostname}/`) });
  initializeAnalytics();
  expect(document.head.querySelector('script')).toBeNull();
  window.gtag = vi.fn();
  trackPageView('/');
  expect(window.gtag).not.toHaveBeenCalled();
});

it.each([true, false])('uses the authentication result to classify a new user: %s', (isNewUser) => {
  window.gtag = vi.fn();
  const result = { providerId: 'google.com', user: {}, additionalUserInfo: { isNewUser } } as unknown as UserCredential;
  trackSignInSuccess(result);
  expect(window.gtag).toHaveBeenCalledWith('event', 'sign_in_success', expect.objectContaining({
    method: 'google', auth_type: isNewUser ? 'signup' : 'login',
  }));
});

it('keeps analytics off when consent storage cannot be read', () => {
  const getItem = vi.spyOn(localStorage, 'getItem').mockImplementation(() => { throw new Error('Storage blocked'); });
  try {
    initializeAnalytics();
    expect(document.querySelector('script')).toBeNull();
  } finally { getItem.mockRestore(); }
});

it('withdraws consent without deleting login cookies, and allows opting in again', async () => {
  vi.resetModules();
  const analytics = await import('./analytics');
  window.dispatchEvent = vi.fn();
  document.cookie = '_ga=test; path=/';
  document.cookie = 'login_session=keep; path=/';
  analytics.initializeAnalytics();
  analytics.trackPageView('/');
  analytics.setAnalyticsConsent('declined');
  expect(analytics.getAnalyticsConsent()).toBe('declined');
  expect(document.querySelector('script')).toBeNull();
  expect(document.cookie).not.toContain('_ga=');
  expect(document.cookie).toContain('login_session=keep');
  expect(sessionStorage.getItem('gmg_flow_id')).toBeNull();
  expect((window as any)['ga-disable-G-TEST123']).toBe(true);
  window.gtag = vi.fn();
  analytics.trackPageView('/browse/');
  expect(window.gtag).not.toHaveBeenCalled();
  window.gtag = undefined;
  analytics.setAnalyticsConsent('accepted');
  expect((window as any)['ga-disable-G-TEST123']).toBe(false);
  expect(document.querySelector('script[src*="googletagmanager"]')).not.toBeNull();
});

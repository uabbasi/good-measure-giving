import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import type { UserCredential } from 'firebase/auth';
import { initializeAnalytics, trackPageView, trackSignInSuccess } from './analytics';

vi.mock('firebase/auth', () => ({ getAdditionalUserInfo: (result: any) => result.additionalUserInfo }));

beforeEach(() => {
  vi.stubGlobal('window', { location: new URL('https://goodmeasuregiving.org/') });
  sessionStorage.clear();
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

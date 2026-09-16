import React from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import { LandingThemeProvider } from '../../contexts/LandingThemeContext';
import { MemoryRouter } from 'react-router-dom';
import { AnalyticsConsent } from './AnalyticsConsent';

vi.hoisted(() => vi.stubEnv('VITE_GA_MEASUREMENT_ID', 'G-TEST123'));

vi.mock('../utils/analytics', async (orig) => {
  const actual = await (orig as any)();
  return {
    ...actual,
    initializeAnalytics: vi.fn(),
    trackPageView: vi.fn(),
  };
});

describe('AnalyticsConsent cross-tab acceptance', () => {
  const local = (() => {
    const map = new Map<string, string>();
    return {
      getItem: (key: string) => (map.has(key) ? map.get(key)! : null),
      setItem: (key: string, value: string) => { map.set(String(key), String(value)); },
      removeItem: (key: string) => { map.delete(key); },
      clear: () => { map.clear(); },
      get length() { return map.size; },
      key: (index: number) => [...map.keys()][index] ?? null,
    };
  })();

  beforeEach(() => {
    const mm = () => ({
      matches: false,
      media: '',
      onchange: null as any,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {}, // deprecated, included for safety
      removeListener: () => {}, // deprecated
      dispatchEvent: () => true,
    });
    Object.defineProperty(globalThis, 'matchMedia', { value: mm, writable: true });
    vi.stubGlobal('window', {
      location: new URL('https://goodmeasuregiving.org/'),
      matchMedia: mm,
      addEventListener: window.addEventListener.bind(window),
      removeEventListener: window.removeEventListener.bind(window),
      dispatchEvent: window.dispatchEvent.bind(window),
      localStorage: local,
      sessionStorage: local,
      document,
    });
    vi.stubGlobal('localStorage', local);
    vi.stubGlobal('sessionStorage', local);
    local.clear();
  });

  afterEach(() => {
    document.head.querySelectorAll('script').forEach((s) => s.remove());
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('initializes analytics and records a page view when another tab accepts', async () => {
    // Start with no consent, mount the component to install storage listener.
    const { initializeAnalytics, trackPageView } = await import('../utils/analytics');
    render(
      <MemoryRouter>
        <LandingThemeProvider>
          <AnalyticsConsent />
        </LandingThemeProvider>
      </MemoryRouter>,
    );
    // Simulate cross-tab acceptance.
    local.setItem('gmg_analytics_consent', 'accepted');
    window.dispatchEvent(new StorageEvent('storage', { key: 'gmg_analytics_consent', newValue: 'accepted' }));
    expect(initializeAnalytics).toHaveBeenCalled();
    expect(trackPageView).toHaveBeenCalledWith('/'); // default test path
  });
});


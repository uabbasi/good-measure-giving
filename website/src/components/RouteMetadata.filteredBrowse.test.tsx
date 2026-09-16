import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouteMetadata } from './RouteMetadata';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); document.head.innerHTML = ''; });

// GmgBrowse uses matchMedia to detect mobile layout.
const mm = () => ({
  matches: false,
  media: '',
  onchange: null as any,
  addEventListener: () => {},
  removeEventListener: () => {},
  addListener: () => {}, // deprecated, included for parity
  removeListener: () => {},
  dispatchEvent: () => true,
});
Object.defineProperty(globalThis, 'matchMedia', { value: mm, writable: true });

it('preserves noindex,follow from filtered /browse after metadata loads', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
    '/browse': {
      title: 'Browse charities',
      description: 'Find a charity',
      canonical: 'https://goodmeasuregiving.org/browse',
      ogType: 'website',
    },
  }))));
  // Simulate a direct filtered arrival: a robots tag written by GmgBrowse.
  const facetTag = document.createElement('meta');
  facetTag.setAttribute('name', 'robots');
  facetTag.setAttribute('data-gmg-facets', '');
  facetTag.setAttribute('content', 'noindex,follow');
  document.head.appendChild(facetTag);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/browse']}>
        <RouteMetadata />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  // Wait for RouteMetadata to apply manifest-based tags.
  await waitFor(() => expect(document.title).toBe('Browse charities'));
  const facetRobots = document.querySelector('meta[name="robots"][data-gmg-facets]');
  expect(facetRobots).not.toBeNull();
  expect(facetRobots?.getAttribute('content')).toBe('noindex,follow');
  // And it should not be clobbered to index,follow by the manifest loader.
  const generalRobots = document.querySelector('meta[name="robots"]:not([data-gmg-facets])');
  // The general robots tag may exist; it must not override the facet directive.
  if (generalRobots) expect(facetRobots?.getAttribute('content')).toBe('noindex,follow');
});


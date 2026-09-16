import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Link, MemoryRouter } from 'react-router-dom';
import { RouteMetadata } from './RouteMetadata';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); document.head.innerHTML = ''; });

it('updates page metadata on navigation and clears private-page robots directives', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
    '/profile': { title: 'Your profile', description: 'Private account', canonical: 'https://goodmeasuregiving.org/profile', ogType: 'website', noindex: true },
    '/browse': { title: 'Browse charities', description: 'Find a charity', canonical: 'https://goodmeasuregiving.org/browse', ogType: 'website' },
  }))));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={['/profile/']}><RouteMetadata /><Link to="/browse/">Browse</Link><Link to="/missing/">Missing</Link></MemoryRouter>
  </QueryClientProvider>);
  await waitFor(() => expect(document.title).toBe('Your profile'));
  expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toContain('noindex');
  fireEvent.click(screen.getByText('Browse'));
  await waitFor(() => expect(document.title).toBe('Browse charities'));
  expect(document.querySelector('meta[name="description"]')?.getAttribute('content')).toBe('Find a charity');
  expect(document.querySelector('meta[property="og:title"]')?.getAttribute('content')).toBe('Browse charities');
  expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe('https://goodmeasuregiving.org/browse/');
  expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('index,follow');
  fireEvent.click(screen.getByText('Missing'));
  await waitFor(() => expect(document.title).toBe('Page Not Found | Good Measure Giving'));
  expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toContain('noindex');
});

import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { LandingThemeProvider } from '../../contexts/LandingThemeContext';
import { GuidesIndexPage } from '../../pages/GuidesIndexPage';

// renderToStaticMarkup uses the server-side React renderer (no DOM APIs).
// Stub the localStorage + matchMedia that LandingThemeProvider calls in its useState initializer.
Object.defineProperty(globalThis, 'localStorage', {
  value: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  writable: true,
});
Object.defineProperty(globalThis, 'matchMedia', {
  value: () => ({ matches: false }),
  writable: true,
});

test('GuidesIndexPage renders seeded guides synchronously (SSR)', () => {
  const qc = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  qc.setQueryData(['guides'], { guides: [{ slug: 'zakat-101', title: 'Zakat 101', description: 'x', readingTimeMinutes: 5 }] });
  const html = renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <LandingThemeProvider>
        <MemoryRouter><GuidesIndexPage /></MemoryRouter>
      </LandingThemeProvider>
    </QueryClientProvider>
  );
  expect(html).toContain('Zakat 101');
  expect(html).not.toContain('Loading guides');
});

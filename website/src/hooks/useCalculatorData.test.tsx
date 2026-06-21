import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { LandingThemeProvider } from '../../contexts/LandingThemeContext';
import { ZakatCalculatorHubPage } from '../../pages/ZakatCalculatorHubPage';

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

test('calculator hub renders seeded hero text synchronously', () => {
  const qc = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  qc.setQueryData(['calculator-data'], {
    hub: { metaTitle: 't', metaDescription: 'd', heroText: 'Calculate your zakat now' },
    assets: [{ slug: 'cash-savings', displayName: 'Cash', heroAnswer: 'a' }],
  });
  const html = renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <LandingThemeProvider>
        <MemoryRouter><ZakatCalculatorHubPage /></MemoryRouter>
      </LandingThemeProvider>
    </QueryClientProvider>
  );
  expect(html).toContain('Calculate your zakat now');
});

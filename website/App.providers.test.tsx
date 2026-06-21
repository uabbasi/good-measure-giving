// @vitest-environment node
import { renderToStaticMarkup } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server';
import { AppProviders, AppContent, createAppQueryClient } from './App';

test('AppProviders + AppContent render the shell server-side without throwing', () => {
  const qc = createAppQueryClient();
  const html = renderToStaticMarkup(
    <AppProviders queryClient={qc}>
      <StaticRouter location="/about">
        <AppContent />
      </StaticRouter>
    </AppProviders>
  );
  expect(html).toContain('Skip to main content');
});

test('charts and tour widgets are absent from server markup', () => {
  const qc = createAppQueryClient();
  const html = renderToStaticMarkup(
    <AppProviders queryClient={qc}>
      <StaticRouter location="/about"><AppContent /></StaticRouter>
    </AppProviders>
  );
  // driver.js / recharts containers must not appear server-side
  expect(html).not.toContain('recharts');
  expect(html).not.toContain('driver-');
});

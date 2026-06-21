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

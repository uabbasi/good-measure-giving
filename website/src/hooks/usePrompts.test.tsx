import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { LandingThemeProvider } from '../../contexts/LandingThemeContext';
import { PromptsPage } from '../../pages/PromptsPage';
import { PromptDetailPage } from '../../pages/PromptDetailPage';

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

const seedIndex = {
  prompts: [
    {
      id: 'baseline-v3',
      name: 'Baseline Narrative',
      category: 'narrative_generation',
      description: 'Generates baseline narrative for charities',
      status: 'active' as const,
    },
  ],
  categories: [
    {
      id: 'narrative_generation',
      name: 'Narrative Generation',
      description: 'Prompts that generate narrative content',
    },
  ],
  total_count: 1,
  active_count: 1,
  planned_count: 0,
};

const seedDetail = {
  id: 'baseline-v3',
  name: 'Baseline Narrative',
  category: 'narrative_generation',
  description: 'Generates baseline narrative for charities',
  status: 'active' as const,
  source_file: 'prompts/baseline_narrative.py',
  content: 'PROMPT CONTENT HERE',
  annotations: [],
};

test('PromptsPage renders seeded prompts index synchronously (SSR)', () => {
  const qc = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  qc.setQueryData(['prompts'], seedIndex);
  const html = renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <LandingThemeProvider>
        <MemoryRouter>
          <PromptsPage />
        </MemoryRouter>
      </LandingThemeProvider>
    </QueryClientProvider>
  );
  expect(html).toContain('Baseline Narrative');
  expect(html).not.toContain('Loading prompts');
});

test('PromptDetailPage renders seeded prompt synchronously (SSR)', () => {
  const qc = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  qc.setQueryData(['prompt', 'baseline-v3'], seedDetail);
  const html = renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <LandingThemeProvider>
        <MemoryRouter initialEntries={['/prompts/baseline-v3']}>
          <Routes>
            <Route path="/prompts/:promptId" element={<PromptDetailPage />} />
          </Routes>
        </MemoryRouter>
      </LandingThemeProvider>
    </QueryClientProvider>
  );
  expect(html).toContain('Baseline Narrative');
  expect(html).not.toContain('Loading prompt');
});

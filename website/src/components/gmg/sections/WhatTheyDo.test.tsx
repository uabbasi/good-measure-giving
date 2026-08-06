import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { WhatTheyDo } from './WhatTheyDo';
import { gmgPalette } from '../tokens';
import { adaptCharity } from '../charityAdapter';

const p = gmgPalette(false);
const dir = path.resolve(__dirname, '../../../../data/charities');
const load = (file: string) => adaptCharity(JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8')));

// charity-01-0548371.json: no grants, but has an evidence grade, root-level
// theoryOfChange, externalEvaluations, and both whatTheyDo concerns — a rich
// fixture for this section specifically.
const richNoGrants = () => load('charity-01-0548371.json');

describe('WhatTheyDo', () => {
  it('renders the About lede and Quick facts card ahead of the cited summary', () => {
    const c = richNoGrants();
    const { container, getByText } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);

    expect(getByText('About')).toBeInTheDocument();
    expect(getByText(c.headline)).toBeInTheDocument();
    expect(getByText('Quick facts')).toBeInTheDocument();
    // A representative sample of quick-facts rows this fixture has values for.
    expect(getByText(c.category)).toBeInTheDocument();
    expect(getByText(c.riskLevel)).toBeInTheDocument();

    // Composition, not just presence: the headline must appear before the
    // cited summary text in document order — a regression that keeps both
    // fields but drops the About block (e.g. moves the headline back into
    // page header meta only) would still pass a bare "is present" check.
    const html = container.innerHTML;
    const headlineIdx = html.indexOf(c.headline);
    const summaryIdx = html.indexOf('Sources');
    expect(headlineIdx).toBeGreaterThan(-1);
    expect(headlineIdx).toBeLessThan(summaryIdx);
  });

  it('renders the cited summary and its source list', () => {
    const c = richNoGrants();
    expect(c.cited.summary.length).toBeGreaterThan(0);
    const { container } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain('Sources');
  });

  it('renders the evaluator theory of change and the charity-reported one as separate blocks, not merged', () => {
    const c = richNoGrants();
    expect(c.evidence.theoryOfChange).toBeTruthy();
    expect(c.theoryOfChange).toBeTruthy();
    // Load-bearing: if the two were merged into one field, this would fail —
    // both distinct passages must appear in the rendered output.
    const { getByText } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    expect(getByText(c.evidence.theoryOfChange)).toBeInTheDocument();
    expect(getByText(c.theoryOfChange as string)).toBeInTheDocument();
    expect(c.evidence.theoryOfChange).not.toBe(c.theoryOfChange);
  });

  it('renders the evidence grade and its explanation', () => {
    const c = richNoGrants();
    expect(c.evidence.grade).toBeTruthy();
    const { container } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain(`Evidence grade ${c.evidence.grade}`);
    if (c.evidence.gradeExplanation) expect(container.textContent).toContain(c.evidence.gradeExplanation);
  });

  it('renders external evaluations as a list', () => {
    const c = richNoGrants();
    expect(c.evidence.externalEvaluations.length).toBeGreaterThan(0);
    const { container } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    for (const e of c.evidence.externalEvaluations) expect(container.textContent).toContain(e);
  });

  it('renders programs, populations, and geography as tag rows', () => {
    const c = richNoGrants();
    const { container } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    for (const item of [...c.programs, ...c.populations, ...c.geography]) {
      expect(container.textContent).toContain(item);
    }
  });

  it('renders whatTheyDo concerns', () => {
    const c = richNoGrants();
    expect(c.concerns.byAnchor.whatTheyDo.length).toBeGreaterThan(0);
    const { container } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    for (const concern of c.concerns.byAnchor.whatTheyDo) {
      expect(container.textContent).toContain(concern.headline);
    }
  });

  it('always mounts the section wrapper even when a charity has none of the optional content', () => {
    const bare = adaptCharity({ ein: '00-0000000', name: 'Bare Org' });
    const { container } = render(<WhatTheyDo c={bare} p={p} isMobile={false} padX={16} />);
    expect(container.querySelector('[data-section="what-they-do"]')).not.toBeNull();
  });

  it('renders every real charity in the corpus without throwing', () => {
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
    let rendered = 0;
    for (const f of files) {
      const c = load(f);
      const { unmount } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
      rendered += 1;
      unmount();
    }
    expect(rendered).toBe(files.length);
  }, 30000); // renders 166 charities; generous margin under worker contention
});

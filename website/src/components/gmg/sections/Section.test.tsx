import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Section } from './Section';
import { gmgPalette } from '../tokens';

const p = gmgPalette(false);

describe('Section', () => {
  it('always mounts the [data-section] wrapper, even with no children content', () => {
    // This is the mount-order invariant the whole rail depends on: the
    // wrapper must exist independent of whatever gating happens inside it.
    const { container } = render(
      <Section id="money" title="Where your money goes" p={p} padX={16}>
        {null}
      </Section>,
    );
    const el = container.querySelector('[data-section="money"]');
    expect(el).not.toBeNull();
    expect(el?.id).toBe('money');
  });

  it('renders the title and the children content', () => {
    const { getByText } = render(
      <Section id="what-they-do" title="What they do, and is it real?" p={p} padX={16}>
        <span>child content</span>
      </Section>,
    );
    expect(getByText('What they do, and is it real?')).toBeInTheDocument();
    expect(getByText('child content')).toBeInTheDocument();
  });

  it('uses a distinct id per section, not a shared/hardcoded one', () => {
    const { container: a } = render(
      <Section id="what-they-do" title="A" p={p} padX={16}>
        {null}
      </Section>,
    );
    const { container: b } = render(
      <Section id="money" title="B" p={p} padX={16}>
        {null}
      </Section>,
    );
    expect(a.querySelector('[data-section]')?.getAttribute('data-section')).toBe('what-they-do');
    expect(b.querySelector('[data-section]')?.getAttribute('data-section')).toBe('money');
  });
});

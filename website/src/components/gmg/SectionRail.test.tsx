import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { act } from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { SectionRail } from './SectionRail';
import { gmgPalette } from './tokens';

const p = gmgPalette(false);
const sections = [
  { id: 'what', label: 'What they do' },
  { id: 'money', label: 'Where your money goes' },
  { id: 'trust', label: 'Can you trust this' },
];

beforeEach(() => {
  vi.stubGlobal('IntersectionObserver', class {
    observe() {} unobserve() {} disconnect() {}
    constructor(_cb: unknown) {}
  });
});

describe('SectionRail', () => {
  it('renders a link per section on desktop, laid out as a vertical rail', () => {
    const { container } = render(<SectionRail sections={sections} p={p} isMobile={false} />);
    const links = container.querySelectorAll('a');
    expect(links.length).toBe(3);
    expect(links[0].getAttribute('href')).toBe('#what');
    // Vertical rail, not the horizontal scroller mobile uses.
    expect(container.querySelector('nav')?.style.overflowX).not.toBe('auto');
  });

  it('renders nothing for an empty section list', () => {
    const { container } = render(<SectionRail sections={[]} p={p} isMobile={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders a horizontal, scrollable jump menu on mobile', () => {
    const { container } = render(<SectionRail sections={sections} p={p} isMobile />);
    expect(container.querySelectorAll('a').length).toBe(3);
    expect(container.textContent).toContain('What they do');
    // The mobile variant is a horizontally scrolling strip, not the desktop rail.
    expect(container.querySelector('nav')?.style.overflowX).toBe('auto');
  });

  it('highlights the section the observer reports as intersecting', () => {
    let observed: IntersectionObserverCallback | undefined;
    vi.stubGlobal('IntersectionObserver', class {
      constructor(cb: IntersectionObserverCallback) { observed = cb; }
      observe() {}
      unobserve() {}
      disconnect() {}
    });

    const { container } = render(
      <>
        <div data-section="what" />
        <div data-section="money" />
        <SectionRail sections={sections} p={p} isMobile={false} />
      </>,
    );

    expect(observed).toBeDefined();
    const moneyEl = document.querySelector<HTMLElement>('[data-section="money"]')!;
    act(() => {
      observed!(
        [{ isIntersecting: true, target: moneyEl, boundingClientRect: { top: 0 } } as unknown as IntersectionObserverEntry],
        {} as IntersectionObserver,
      );
    });

    const linkFor = (id: string) =>
      Array.from(container.querySelectorAll('a')).find((a) => a.getAttribute('href') === `#${id}`)!;

    // jsdom normalizes inline hex colors to rgb(...), so compare against the
    // inactive link rather than hardcoding the serialized active color.
    expect(linkFor('money').style.color).not.toBe(linkFor('what').style.color);
  });

  it('disconnects the observer on unmount', () => {
    const disconnect = vi.fn();
    vi.stubGlobal('IntersectionObserver', class {
      constructor(_cb: unknown) {}
      observe() {}
      unobserve() {}
      disconnect() { disconnect(); }
    });

    const { unmount } = render(<SectionRail sections={sections} p={p} isMobile={false} />);
    unmount();
    expect(disconnect).toHaveBeenCalled();
  });

  it('survives an environment with no IntersectionObserver', () => {
    vi.stubGlobal('IntersectionObserver', undefined);
    expect(() =>
      render(<SectionRail sections={sections} p={p} isMobile={false} />),
    ).not.toThrow();
  });

  it('is labelled as navigation for assistive tech', () => {
    const { container } = render(<SectionRail sections={sections} p={p} isMobile={false} />);
    expect(container.querySelector('nav')?.getAttribute('aria-label')).toMatch(/section/i);
  });
});

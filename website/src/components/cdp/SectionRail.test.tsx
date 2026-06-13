import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SectionRail } from './SectionRail';

vi.mock('../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const sections = [
  { id: 'about', label: 'About', applies: () => true },
  { id: 'evidence', label: 'Evidence', applies: () => true },
];

describe('SectionRail', () => {
  it('renders one link per section and marks the active one', () => {
    render(<SectionRail sections={sections} activeId="evidence" />);
    expect(screen.getByText('About')).toBeTruthy();
    expect(screen.getByText('Evidence').getAttribute('aria-current')).toBe('true');
    expect(screen.getByText('About').getAttribute('aria-current')).not.toBe('true');
  });

  it('scrolls to the section on click', () => {
    const scrollIntoView = vi.fn();
    const el = document.createElement('div');
    el.id = 'about';
    (el as any).scrollIntoView = scrollIntoView;
    document.body.appendChild(el);
    render(<SectionRail sections={sections} activeId="about" />);
    fireEvent.click(screen.getByText('About'));
    expect(scrollIntoView).toHaveBeenCalled();
  });
});

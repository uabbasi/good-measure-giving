import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MobileScoreBar } from './MobileScoreBar';
import type { CdpData } from './useCdpData';

vi.mock('../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const sections = [
  { id: 'about', label: 'About', applies: () => true },
  { id: 'evidence', label: 'Evidence', applies: () => true },
];

// Minimal CdpData: MobileScoreBar only reads `amalScore` and `signals.recommendation_cue`.
function makeData(amalScore: number | null): CdpData {
  return {
    amalScore,
    signals: { recommendation_cue: 'Good Match' },
  } as unknown as CdpData;
}

describe('MobileScoreBar', () => {
  it('starts closed: toggle aria-expanded=false and section labels hidden', () => {
    render(<MobileScoreBar data={makeData(82)} sections={sections} />);
    const toggle = screen.getByRole('button', { name: 'Jump to section' });
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByText('About')).toBeNull();
  });

  it('opens the menu on toggle click', () => {
    render(<MobileScoreBar data={makeData(82)} sections={sections} />);
    const toggle = screen.getByRole('button', { name: 'Jump to section' });
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByText('About')).toBeTruthy();
  });

  it('closes the menu and scrolls when a section item is clicked', () => {
    const scrollIntoView = vi.fn();
    const el = document.createElement('div');
    el.id = 'about';
    (el as any).scrollIntoView = scrollIntoView;
    document.body.appendChild(el);

    render(<MobileScoreBar data={makeData(82)} sections={sections} />);
    const toggle = screen.getByRole('button', { name: 'Jump to section' });
    fireEvent.click(toggle);
    fireEvent.click(screen.getByText('About'));

    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(scrollIntoView).toHaveBeenCalled();
  });

  it('omits the score number when amalScore is null but still shows the cue', () => {
    render(<MobileScoreBar data={makeData(null)} sections={sections} />);
    expect(screen.queryByText('/100')).toBeNull();
    // cue is rendered via the shared DISPLAY_LABELS mapping (matches VerdictHero/RecommendationCue)
    expect(screen.getByText('Strong Alignment')).toBeTruthy();
  });
});

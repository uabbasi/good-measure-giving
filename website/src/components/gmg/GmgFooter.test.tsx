import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { LandingThemeProvider } from '../../../contexts/LandingThemeContext';
import { GmgFooter } from './content';
import { gmgPalette } from './tokens';

const p = gmgPalette(false);

// jsdom here has no usable localStorage and no matchMedia, so stub a store that starts on 'light'.
let store: Record<string, string>;
beforeEach(() => {
  store = { 'gmg-theme': 'light' };
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => (k in store ? store[k] : null),
    setItem: (k: string, v: string) => { store[k] = v; },
    removeItem: (k: string) => { delete store[k]; },
  });
  document.documentElement.classList.remove('dark');
});

describe('footer light/dark switch', () => {
  it('flips between light and dark, persists the choice and sets the dark class', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <LandingThemeProvider>
          <GmgFooter p={p} isMobile={false} />
        </LandingThemeProvider>
      </MemoryRouter>,
    );
    const toggle = screen.getByRole('switch', { name: /dark mode/i });
    expect(toggle).toHaveAttribute('aria-checked', 'false');

    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-checked', 'true');
    expect(store['gmg-theme']).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);

    await user.click(toggle);
    expect(store['gmg-theme']).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('still renders without a theme provider, just without the switch', () => {
    render(<MemoryRouter><GmgFooter p={p} isMobile={false} /></MemoryRouter>);
    expect(screen.queryByRole('switch')).toBeNull();
    expect(screen.getByText(/Terms/)).toBeInTheDocument();
  });
});

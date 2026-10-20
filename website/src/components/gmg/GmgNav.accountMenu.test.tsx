import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { GmgNav } from './chrome';
import { gmgPalette } from './tokens';

vi.mock('firebase/auth', () => ({ signOut: vi.fn(() => Promise.resolve()) }));
vi.mock('../../auth/firebase', () => ({ auth: {} }));
vi.mock('../../auth', () => ({ useAuth: () => ({ isSignedIn: true, firstName: 'Aisha' }) }));
vi.mock('./GmgSignIn', () => ({ GmgSignIn: () => null }));
vi.mock('./GmgVersionStrip', () => ({ GmgVersionStrip: () => null }));

const renderNav = () =>
  render(
    <MemoryRouter>
      <GmgNav p={gmgPalette(false)} isMobile={false} />
    </MemoryRouter>,
  );

describe('account menu', () => {
  it('is a real menu: roles, arrow keys, Escape returns focus to the button', async () => {
    const user = userEvent.setup();
    renderNav();
    const trigger = screen.getByRole('button', { name: /Aisha/ });
    expect(trigger).toHaveAttribute('aria-haspopup', 'menu');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    trigger.focus();
    await user.keyboard('{ArrowDown}'); // opens and lands on the first item
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    const menu = screen.getByRole('menu', { name: 'Account' });
    expect(trigger).toHaveAttribute('aria-controls', menu.id);
    const items = screen.getAllByRole('menuitem');
    expect(items.map((i) => i.textContent)).toEqual(['Your giving', 'Sign out']);
    expect(items[0]).toHaveFocus();

    await user.keyboard('{ArrowDown}');
    expect(items[1]).toHaveFocus();
    await user.keyboard('{ArrowDown}'); // wraps
    expect(items[0]).toHaveFocus();
    await user.keyboard('{End}');
    expect(items[1]).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).toBeNull();
    expect(trigger).toHaveFocus();
  });
});

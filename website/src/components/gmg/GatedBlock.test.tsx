import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { GatedBlock } from './GatedBlock';
import { gmgPalette } from './tokens';

const mockMember = vi.fn(() => false);
vi.mock('../../auth/useAuth', () => ({ useCommunityMember: () => mockMember() }));
vi.mock('../../auth/SignInButton', () => ({ SignInButton: () => <button>Sign in</button> }));
vi.mock('../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const p = gmgPalette(false);

describe('GatedBlock', () => {
  it('hides the content from a signed-out visitor', () => {
    mockMember.mockReturnValue(false);
    const { queryByText } = render(
      <GatedBlock label="CEO compensation" p={p}><div>SECRET FIGURE</div></GatedBlock>,
    );
    expect(queryByText('SECRET FIGURE')).toBeNull();
  });

  it('tells a signed-out visitor what is behind the gate rather than showing a blank', () => {
    mockMember.mockReturnValue(false);
    const { container } = render(
      <GatedBlock label="CEO compensation" p={p}><div>SECRET FIGURE</div></GatedBlock>,
    );
    expect(container.textContent).toContain('CEO compensation');
    expect(container.firstChild).not.toBeNull();
  });

  it('shows the content to a signed-in member', () => {
    mockMember.mockReturnValue(true);
    const { getByText } = render(
      <GatedBlock label="CEO compensation" p={p}><div>SECRET FIGURE</div></GatedBlock>,
    );
    expect(getByText('SECRET FIGURE')).toBeInTheDocument();
  });

  it('does not render the teaser to a member', () => {
    mockMember.mockReturnValue(true);
    const { container } = render(
      <GatedBlock label="CEO compensation" p={p}><div>SECRET FIGURE</div></GatedBlock>,
    );
    expect(container.textContent).not.toContain('Sign in');
  });
});

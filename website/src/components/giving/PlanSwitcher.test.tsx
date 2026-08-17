/**
 * Regression test: "+ Shared plan" used to call window.prompt() for the
 * plan name — unstyled, blocks the page, and untestable/undismissable in
 * some embedded contexts. Replaced with an inline input. This verifies the
 * inline flow actually creates the plan and selects it, and that Escape/
 * Cancel back out cleanly without creating anything.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

const createPlan = vi.fn(async (_name: string) => 'plan-123');

vi.mock('../../hooks/useSharedPlans', () => ({
  useSharedPlans: () => ({
    plans: [],
    createPlan,
  }),
}));

import { PlanSwitcher } from './PlanSwitcher';

beforeEach(() => {
  createPlan.mockClear();
});

describe('PlanSwitcher', () => {
  it('creates a plan via the inline input (no window.prompt)', async () => {
    const onSelect = vi.fn();
    const promptSpy = vi.spyOn(window, 'prompt');

    render(<PlanSwitcher selected={null} onSelect={onSelect} />);

    fireEvent.click(screen.getByText('+ Shared plan'));
    const input = screen.getByLabelText('New shared plan name');
    fireEvent.change(input, { target: { value: 'Khan Family' } });
    fireEvent.click(screen.getByText('Create'));

    await vi.waitFor(() => expect(createPlan).toHaveBeenCalledWith('Khan Family'));
    expect(onSelect).toHaveBeenCalledWith('plan-123');
    expect(promptSpy).not.toHaveBeenCalled();
  });

  it('creates a plan on Enter key', async () => {
    const onSelect = vi.fn();
    render(<PlanSwitcher selected={null} onSelect={onSelect} />);

    fireEvent.click(screen.getByText('+ Shared plan'));
    const input = screen.getByLabelText('New shared plan name');
    fireEvent.change(input, { target: { value: 'Osman Household' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await vi.waitFor(() => expect(createPlan).toHaveBeenCalledWith('Osman Household'));
  });

  it('does not create a plan on Escape, and the input closes', () => {
    render(<PlanSwitcher selected={null} onSelect={vi.fn()} />);

    fireEvent.click(screen.getByText('+ Shared plan'));
    const input = screen.getByLabelText('New shared plan name');
    fireEvent.change(input, { target: { value: 'Abandoned' } });
    fireEvent.keyDown(input, { key: 'Escape' });

    expect(createPlan).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('New shared plan name')).toBeNull();
    expect(screen.getByText('+ Shared plan')).toBeTruthy();
  });

  it('does not create a plan with an empty/whitespace name', () => {
    render(<PlanSwitcher selected={null} onSelect={vi.fn()} />);

    fireEvent.click(screen.getByText('+ Shared plan'));
    const input = screen.getByLabelText('New shared plan name');
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.click(screen.getByText('Create'));

    expect(createPlan).not.toHaveBeenCalled();
  });
});

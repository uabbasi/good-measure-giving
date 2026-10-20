import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import React, { useRef, useState } from 'react';
import { useDialog } from './useDialog';

const Harness: React.FC<{ onClose?: () => void }> = ({ onClose }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = () => { onClose?.(); setOpen(false); };
  useDialog(ref, open, close);
  return (
    <div>
      <button onClick={() => setOpen(true)}>Open</button>
      {open && (
        <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label="Test dialog">
          <input aria-label="First" />
          <button>Middle</button>
          <button>Last</button>
        </div>
      )}
    </div>
  );
};

describe('useDialog', () => {
  it('moves focus in, traps Tab, closes on Escape and restores focus', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    const opener = screen.getByRole('button', { name: 'Open' });

    await user.click(opener);
    expect(screen.getByLabelText('First')).toHaveFocus(); // initial focus lands inside

    await user.tab();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Last' })).toHaveFocus();
    await user.tab(); // wraps instead of leaving the dialog
    expect(screen.getByLabelText('First')).toHaveFocus();
    await user.tab({ shift: true }); // and backwards
    expect(screen.getByRole('button', { name: 'Last' })).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(opener).toHaveFocus(); // back where it was
  });
});

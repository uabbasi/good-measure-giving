/**
 * Unit tests for pure status transitions (M4).
 */
import { describe, it, expect } from 'vitest';
import {
  applyDonation,
  applyReceiptToggle,
  type AssignmentStatusState,
} from './recordStatus';

const INTENDED_AT = '2026-01-01T00:00:00.000Z';
const SENT_AT = '2026-02-01T00:00:00.000Z';
const CONFIRMED_AT = '2026-03-01T00:00:00.000Z';
const NEW_EVENT_AT = '2026-04-01T12:00:00.000Z';

function intended(given = 0): AssignmentStatusState {
  return { status: 'intended', given, intendedAt: INTENDED_AT };
}
function sent(given = 100): AssignmentStatusState {
  return { status: 'sent', given, intendedAt: INTENDED_AT, sentAt: SENT_AT };
}
function confirmed(given = 100): AssignmentStatusState {
  return {
    status: 'confirmed',
    given,
    intendedAt: INTENDED_AT,
    sentAt: SENT_AT,
    confirmedAt: CONFIRMED_AT,
  };
}

describe('applyDonation', () => {
  it('transitions intended -> sent when no receipt', () => {
    const next = applyDonation(intended(0), {
      amount: 50,
      receiptReceived: false,
      createdAt: NEW_EVENT_AT,
    });
    expect(next.status).toBe('sent');
    expect(next.given).toBe(50);
    expect(next.sentAt).toBe(NEW_EVENT_AT);
    expect(next.confirmedAt).toBeUndefined();
    expect(next.intendedAt).toBe(INTENDED_AT);
  });

  it('transitions intended -> confirmed when receipt received', () => {
    const next = applyDonation(intended(0), {
      amount: 75,
      receiptReceived: true,
      createdAt: NEW_EVENT_AT,
    });
    expect(next.status).toBe('confirmed');
    expect(next.given).toBe(75);
    expect(next.sentAt).toBe(NEW_EVENT_AT);
    expect(next.confirmedAt).toBe(NEW_EVENT_AT);
  });

  it('increments given when applying to sent (no receipt)', () => {
    const next = applyDonation(sent(100), {
      amount: 40,
      receiptReceived: false,
      createdAt: NEW_EVENT_AT,
    });
    expect(next.status).toBe('sent');
    expect(next.given).toBe(140);
    // sentAt preserved, not overwritten by a later timestamp
    expect(next.sentAt).toBe(SENT_AT);
    expect(next.confirmedAt).toBeUndefined();
  });

  it('bumps sent -> confirmed on new donation with receipt', () => {
    const next = applyDonation(sent(100), {
      amount: 30,
      receiptReceived: true,
      createdAt: NEW_EVENT_AT,
    });
    expect(next.status).toBe('confirmed');
    expect(next.given).toBe(130);
    expect(next.sentAt).toBe(SENT_AT); // preserved
    expect(next.confirmedAt).toBe(NEW_EVENT_AT);
  });

  it('keeps confirmed on subsequent donation without receipt', () => {
    const next = applyDonation(confirmed(100), {
      amount: 25,
      receiptReceived: false,
      createdAt: NEW_EVENT_AT,
    });
    expect(next.status).toBe('confirmed');
    expect(next.given).toBe(125);
    // Both timestamps preserved — no regression.
    expect(next.sentAt).toBe(SENT_AT);
    expect(next.confirmedAt).toBe(CONFIRMED_AT);
  });

  it('keeps confirmed on subsequent donation with receipt (timestamps preserved)', () => {
    const next = applyDonation(confirmed(100), {
      amount: 25,
      receiptReceived: true,
      createdAt: NEW_EVENT_AT,
    });
    expect(next.status).toBe('confirmed');
    expect(next.given).toBe(125);
    expect(next.sentAt).toBe(SENT_AT);
    expect(next.confirmedAt).toBe(CONFIRMED_AT);
  });

  it('treats non-numeric given/amount as zero', () => {
    const next = applyDonation(
      { status: 'intended', given: Number.NaN, intendedAt: INTENDED_AT },
      { amount: Number.NaN, receiptReceived: false, createdAt: NEW_EVENT_AT },
    );
    expect(next.given).toBe(0);
  });

  it('preserves intendedAt across every transition', () => {
    const fromIntended = applyDonation(intended(), {
      amount: 1,
      receiptReceived: false,
      createdAt: NEW_EVENT_AT,
    });
    const fromSent = applyDonation(sent(), {
      amount: 1,
      receiptReceived: true,
      createdAt: NEW_EVENT_AT,
    });
    const fromConfirmed = applyDonation(confirmed(), {
      amount: 1,
      receiptReceived: false,
      createdAt: NEW_EVENT_AT,
    });
    expect(fromIntended.intendedAt).toBe(INTENDED_AT);
    expect(fromSent.intendedAt).toBe(INTENDED_AT);
    expect(fromConfirmed.intendedAt).toBe(INTENDED_AT);
  });
});

describe('applyReceiptToggle', () => {
  it('toggling true on a sent assignment -> confirmed with confirmedAt=now', () => {
    const next = applyReceiptToggle(sent(100), true, NEW_EVENT_AT);
    expect(next.status).toBe('confirmed');
    expect(next.given).toBe(100);
    expect(next.sentAt).toBe(SENT_AT);
    expect(next.confirmedAt).toBe(NEW_EVENT_AT);
  });

  it('toggling true on an already-confirmed assignment is a no-op', () => {
    const next = applyReceiptToggle(confirmed(100), true, NEW_EVENT_AT);
    expect(next.status).toBe('confirmed');
    expect(next.confirmedAt).toBe(CONFIRMED_AT); // preserved, not overwritten
    expect(next.sentAt).toBe(SENT_AT);
  });

  it('toggling true on an intended assignment promotes to confirmed', () => {
    const next = applyReceiptToggle(intended(0), true, NEW_EVENT_AT);
    expect(next.status).toBe('confirmed');
    // sentAt gets backfilled since we don't have one.
    expect(next.sentAt).toBe(NEW_EVENT_AT);
    expect(next.confirmedAt).toBe(NEW_EVENT_AT);
  });

  it('toggling false on confirmed reverts to sent and clears confirmedAt', () => {
    const next = applyReceiptToggle(confirmed(100), false, NEW_EVENT_AT);
    expect(next.status).toBe('sent');
    expect(next.given).toBe(100);
    expect(next.sentAt).toBe(SENT_AT);
    expect(next.confirmedAt).toBeUndefined();
  });

  it('toggling false on sent is a no-op', () => {
    const next = applyReceiptToggle(sent(50), false, NEW_EVENT_AT);
    expect(next.status).toBe('sent');
    expect(next.given).toBe(50);
    expect(next.sentAt).toBe(SENT_AT);
  });

  it('toggling false on intended is a no-op', () => {
    const next = applyReceiptToggle(intended(), false, NEW_EVENT_AT);
    expect(next.status).toBe('intended');
    expect(next.confirmedAt).toBeUndefined();
  });

  it('preserves intendedAt', () => {
    const onTrue = applyReceiptToggle(sent(), true, NEW_EVENT_AT);
    const onFalse = applyReceiptToggle(confirmed(), false, NEW_EVENT_AT);
    expect(onTrue.intendedAt).toBe(INTENDED_AT);
    expect(onFalse.intendedAt).toBe(INTENDED_AT);
  });
});

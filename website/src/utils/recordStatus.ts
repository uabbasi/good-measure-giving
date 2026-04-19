/**
 * Pure status-transition helpers for `CharityBucketAssignment`.
 *
 * These compute the next `{status, given, sentAt?, confirmedAt?, intendedAt}`
 * shape from the current assignment + an event. They never touch Firestore —
 * the caller wires the resulting patch into a `writeBatch`.
 *
 * Semantics (see M4 plan):
 *  - `applyDonation`: logging a donation against an assignment.
 *      - from 'intended': -> 'confirmed' if receipt, else 'sent'. Sets sentAt=createdAt,
 *        confirmedAt=createdAt when receipt. Bumps given += amount.
 *      - from 'sent': increments given; if receipt, bumps to 'confirmed' and sets confirmedAt.
 *        Preserves existing sentAt.
 *      - from 'confirmed': increments given; preserves confirmedAt and sentAt.
 *  - `applyReceiptToggle`: toggling `receiptReceived` on the single backing donation.
 *      - toggling true:  status -> 'confirmed'; confirmedAt = now (if not already set).
 *      - toggling false on 'confirmed' (single-donation assumption):
 *           status -> 'sent'; clears confirmedAt; preserves sentAt (falls back to now).
 *
 * Timestamps: callers pass ISO strings (`new Date().toISOString()`). The helpers
 * never regenerate timestamps that are already set — timestamps don't regress.
 */

export type AssignmentStatus = 'intended' | 'sent' | 'confirmed';

export interface AssignmentStatusState {
  status: AssignmentStatus;
  given: number;
  intendedAt: string;
  sentAt?: string;
  confirmedAt?: string;
}

export interface StatusTransition {
  status: AssignmentStatus;
  given: number;
  intendedAt: string;
  sentAt?: string;
  confirmedAt?: string;
}

export interface DonationEvent {
  amount: number;
  receiptReceived: boolean;
  createdAt: string;
}

/**
 * Apply a donation event to an assignment, returning the next state.
 *
 * - Never regresses status (confirmed stays confirmed; sent never drops to intended).
 * - `given` is additive.
 * - Timestamps are preserved when already set; sentAt is set on first transition out of
 *   'intended'; confirmedAt is set whenever the donation carries a receipt.
 */
export function applyDonation(
  current: AssignmentStatusState,
  donation: DonationEvent,
): StatusTransition {
  const nextGiven = (Number(current.given) || 0) + (Number(donation.amount) || 0);

  // From 'intended': first donation logged for this charity.
  if (current.status === 'intended') {
    const nextStatus: AssignmentStatus = donation.receiptReceived ? 'confirmed' : 'sent';
    return {
      status: nextStatus,
      given: nextGiven,
      intendedAt: current.intendedAt,
      sentAt: donation.createdAt,
      confirmedAt: donation.receiptReceived ? donation.createdAt : current.confirmedAt,
    };
  }

  // From 'sent': already had a sent donation. Preserve sentAt; bump to confirmed on receipt.
  if (current.status === 'sent') {
    if (donation.receiptReceived) {
      return {
        status: 'confirmed',
        given: nextGiven,
        intendedAt: current.intendedAt,
        sentAt: current.sentAt ?? donation.createdAt,
        confirmedAt: current.confirmedAt ?? donation.createdAt,
      };
    }
    return {
      status: 'sent',
      given: nextGiven,
      intendedAt: current.intendedAt,
      sentAt: current.sentAt ?? donation.createdAt,
      confirmedAt: current.confirmedAt,
    };
  }

  // From 'confirmed': increment given, preserve timestamps.
  return {
    status: 'confirmed',
    given: nextGiven,
    intendedAt: current.intendedAt,
    sentAt: current.sentAt ?? donation.createdAt,
    confirmedAt: current.confirmedAt ?? donation.createdAt,
  };
}

/**
 * Toggle the receipt flag on an assignment (single-donation assumption).
 *
 * - true: status -> 'confirmed', confirmedAt set (to `now` if missing).
 * - false: from 'confirmed' -> 'sent', clears confirmedAt. From 'sent'/'intended' is a no-op.
 *
 * For multi-donation assignments, the caller must decide whether to invoke this —
 * this helper is intentionally simple and the modal layer is the correct place
 * for that policy.
 */
export function applyReceiptToggle(
  current: AssignmentStatusState,
  receiptReceived: boolean,
  now: string,
): StatusTransition {
  if (receiptReceived) {
    // Idempotent if already confirmed with a timestamp.
    return {
      status: 'confirmed',
      given: current.given,
      intendedAt: current.intendedAt,
      sentAt: current.sentAt ?? now,
      confirmedAt: current.confirmedAt ?? now,
    };
  }

  // Untoggle receipt.
  if (current.status === 'confirmed') {
    return {
      status: 'sent',
      given: current.given,
      intendedAt: current.intendedAt,
      sentAt: current.sentAt ?? now,
      confirmedAt: undefined,
    };
  }

  // No-op for intended/sent when toggling false.
  return {
    status: current.status,
    given: current.given,
    intendedAt: current.intendedAt,
    sentAt: current.sentAt,
    confirmedAt: current.confirmedAt,
  };
}

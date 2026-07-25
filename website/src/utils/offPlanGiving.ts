/**
 * "Given" is stitched together from two sources that can disagree:
 *
 *  - `assignments[].given` — a per-charity cache for charities in the plan.
 *  - `giving_history` — the ledger of truth, which also holds donations to
 *    charities that were never added to a plan (logged via the header
 *    "Log Donation" modal with no EIN match).
 *
 * Summing only the assignments undercounts; summing both double-counts the
 * overlap. This helper is the single rule for the top-up, so the dashboard
 * card and the zakat progress bar can't drift apart — they did, and briefly
 * showed 100% complete and 5% complete on the same screen.
 */

interface DonationLike {
  charityEin?: string | null;
  amount: number;
}

/**
 * Total of donations that no assignment already accounts for.
 * Add this to the sum of `assignments[].given` to get the real total.
 */
export function offPlanDonationTotal(
  donations: readonly DonationLike[],
  assignedEins: Iterable<string>,
): number {
  const assigned = assignedEins instanceof Set ? assignedEins : new Set(assignedEins);
  let total = 0;
  for (const d of donations) {
    if (!d.charityEin || !assigned.has(d.charityEin)) {
      total += Number(d.amount) || 0;
    }
  }
  return total;
}

// Derives the program/admin/fundraising expense split from real filed
// figures when available (so the split matches the dollar amounts shown
// beside it); falls back to the program ratio alone otherwise. Remainder
// math prevents the split from ever summing past 100%.
//
// Extracted from GmgCharityDetail's Financials card so the "Where your money
// goes" section computes the identical split rather than a second, drifting
// copy of the same math.

export interface ExpenseSplit {
  progPct: number;
  adminPct: number;
  fundPct: number;
}

export const expenseSplit = (c: {
  programRatioPct: number | null;
  programExpenses: number | null;
  adminExpenses: number | null;
  fundraisingExpenses: number | null;
}): ExpenseSplit | null => {
  if (c.programRatioPct == null) return null;

  const prog = c.programExpenses ?? 0;
  const admin = c.adminExpenses ?? 0;
  const fund = c.fundraisingExpenses ?? 0;
  const denom = prog + admin + fund;
  const hasBreakdown = denom > 0;

  const progPct = hasBreakdown ? Math.round((prog / denom) * 100) : c.programRatioPct;
  const adminPct = hasBreakdown
    ? Math.round((admin / denom) * 100)
    : Math.max(0, 100 - c.programRatioPct);
  const fundPct = Math.max(0, 100 - progPct - adminPct);

  return { progPct, adminPct, fundPct };
};

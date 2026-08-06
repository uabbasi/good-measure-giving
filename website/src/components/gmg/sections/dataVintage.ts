// Classifies a charity's data as "dated" once its published age crosses the
// threshold worth flagging to a donor. Age comes from the pipeline's own
// data_age_years (computed once at evaluation time) rather than the wall
// clock, so a prerendered page never disagrees with itself at hydration as
// the calendar rolls forward.
//
// Extracted from GmgCharityDetail's Financials-card badge so "Can you trust
// these numbers?" (TrustTheNumbers) uses the identical dated/not-dated split
// rather than a second, drifting copy of the same threshold.

export interface DataVintage {
  fyAge: number | null;
  fyDated: boolean;
}

export const dataVintage = (c: { dataAgeYears: number | null }): DataVintage => {
  const fyAge = c.dataAgeYears;
  const fyDated = fyAge != null && fyAge >= 3;
  return { fyAge, fyDated };
};

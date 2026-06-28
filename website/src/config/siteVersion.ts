// Single source of truth for the published rubric version on the website.
//
// The upstream source of truth is RUBRIC_VERSION in
// data-pipeline/src/scorers/v2_scorers.py — bump this string when the rubric's
// major/minor/patch version changes there so the methodology page and the
// site-wide version strip can never drift apart.
export const RUBRIC_VERSION = '5.2.0';

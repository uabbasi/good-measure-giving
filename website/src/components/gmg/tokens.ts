// Good Measure Giving — "Modern" design motif tokens.
// Sage on bone (light) / sage on warm charcoal (dark).
// Ported from the claude.ai design handoff (modern-chrome.jsx palette `M`).

export interface GmgPalette {
  bg: string;
  bg2: string;
  bg3: string;
  fg: string;
  sub: string;
  sub2: string;
  rule: string;
  rule2: string;
  accent: string;
  accent2: string;
  warn: string;
  warnBg: string;
  danger: string;
  chip: string;
  chipFg: string;
  card: string;
  // Semantic highlight colors — clearer positive / caution / negative than the
  // muted sage base, used for ratings, risk, strengths and concerns.
  pos: string;
  posBg: string;
  caution: string;
  cautionBg: string;
  neg: string;
  negBg: string;
  /**
   * A surface while it is being pressed. Distinct from bg3, which is a
   * resting elevation step and moves the dark surface only 6/255.
   *
   * Sized by perceived lightness (CIE L*), not by RGB channel — an earlier
   * pass matched the themes on an equal 30/255 channel step and called that
   * equal feedback, which it is not: RGB is least perceptually uniform at the
   * dark end. Light moves dL* 13.6, dark dL* 24.8, dark deliberately ahead
   * because a dim phone screen is where this gets read. Body text stays above
   * 6.8:1 on both, so a held card never swallows the charity's name.
   *
   * The fill is only half the cue; see pressEdge.
   */
  press: string;
  /**
   * The border of a pressed surface.
   *
   * Against the resting card this is 7.6:1 in light and 9.9:1 in dark, where
   * the resting border is 1.4:1 and 1.6:1 — five times the separation any
   * fill shift can buy, and it works by changing hue rather than lightness,
   * which is what survives on a dark screen at low brightness.
   */
  pressEdge: string;
}

const light: GmgPalette = {
  bg: '#f4efde',
  bg2: '#ede6cf',
  bg3: '#e5dcbf',
  fg: '#13160e',
  sub: '#5e6356',
  sub2: '#8a8e80',
  rule: '#dfdac7',
  rule2: '#c9c2a8',
  accent: '#3d4a30',
  accent2: '#6b7a55',
  warn: '#7a6a2a',
  warnBg: '#efe4b8',
  danger: '#9c4a3a',
  chip: '#1f2218',
  chipFg: '#f4efde',
  card: '#ebe4cc',
  pos: '#3a6b34',
  posBg: '#dde9cf',
  caution: '#8a6410',
  cautionBg: '#f0e3b0',
  neg: '#a23824',
  negBg: '#f0d9d0',
  press: '#c7c0a9',
  pressEdge: '#3d4a30',
};

// The dark surface ramp is scaled further from its ground than the light one,
// and deliberately so. Both themes originally stepped bg -> bg2 by about the
// same RGB amount, which put the dark card dL* 2.77 from the page behind it:
// not a surface at all, just a 1px outline, and reported as not being able to
// see where the cards were. Dark now steps dL* 7.1, light stays at 3.1.
//
// Light is NOT matched to it on purpose. There the card is darker than its
// ground, so deepening it pushes muted text the wrong way — and light `sub2`
// already sits at 2.69:1 on the card, under the 4.5:1 small text wants. That
// is a real problem, but it is a pre-existing one, and darkening the surface
// under it would have made it worse rather than better.
const dark: GmgPalette = {
  bg: '#13140e',
  bg2: '#20231a',
  bg3: '#272c22',
  fg: '#ecebe4',
  sub: '#9aa094',
  sub2: '#858a7e',
  rule: '#262921',
  rule2: '#3a3e34',
  accent: '#b8c8a4',
  accent2: '#8fa178',
  warn: '#d4c478',
  warnBg: '#3a3322',
  danger: '#c47a6a',
  chip: '#d6e0c5',
  chipFg: '#13140e',
  card: '#20231a',
  pos: '#9fce8f',
  posBg: '#22311b',
  caution: '#dcc46a',
  cautionBg: '#38311e',
  neg: '#e58a70',
  negBg: '#3a231d',
  press: '#4e5049',
  pressEdge: '#b8c8a4',
};

export const gmgPalette = (isDark: boolean): GmgPalette => (isDark ? dark : light);

// Fonts are referenced through CSS variables set on the motif root, so switching
// type direction is instant (no prop threading through every primitive).
export const FONT_DISPLAY = 'var(--gmg-display)';
export const FONT_TEXT = 'var(--gmg-text)';
export const FONT_MONO = 'var(--gmg-mono)';
export const FONT_ARABIC = 'var(--gmg-arabic)';

export type FontVariant = 'spectral' | 'bricolage' | 'caslon' | 'instrument';

export interface FontTheme {
  display: string;
  text: string;
  mono: string;
  arabic: string;
  label: string;
  // Display serifs read large; tighten tracking less than the sans options.
  displayTracking: string;
}

const TEXT = "'Geist', 'Inter', system-ui, sans-serif";
const MONO = "'JetBrains Mono', ui-monospace, monospace";
const ARABIC = "'Amiri', serif";

export const FONT_THEMES: Record<FontVariant, FontTheme> = {
  spectral: {
    display: "'Spectral', Georgia, serif",
    text: TEXT,
    mono: MONO,
    arabic: ARABIC,
    label: 'Spectral',
    displayTracking: '-0.01em',
  },
  bricolage: {
    display: "'Bricolage Grotesque', 'Geist', sans-serif",
    text: TEXT,
    mono: MONO,
    arabic: ARABIC,
    label: 'Bricolage',
    displayTracking: '-0.02em',
  },
  caslon: {
    display: "'Libre Caslon Display', Georgia, serif",
    text: TEXT,
    mono: MONO,
    arabic: ARABIC,
    label: 'Caslon',
    displayTracking: '-0.005em',
  },
  instrument: {
    display: "'Instrument Serif', Georgia, serif",
    text: TEXT,
    mono: MONO,
    arabic: ARABIC,
    label: 'Instrument',
    displayTracking: '-0.035em',
  },
};

export const DEFAULT_FONT_VARIANT: FontVariant = 'spectral';

export const resolveFontVariant = (raw: string | null | undefined): FontVariant =>
  raw && raw in FONT_THEMES ? (raw as FontVariant) : DEFAULT_FONT_VARIANT;

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
};

const dark: GmgPalette = {
  bg: '#13140e',
  bg2: '#181a13',
  bg3: '#1d2018',
  fg: '#ecebe4',
  sub: '#9aa094',
  sub2: '#6f7468',
  rule: '#262921',
  rule2: '#3a3e34',
  accent: '#b8c8a4',
  accent2: '#8fa178',
  warn: '#d4c478',
  warnBg: '#3a3322',
  danger: '#c47a6a',
  chip: '#d6e0c5',
  chipFg: '#13140e',
  card: '#1a1d15',
  pos: '#9fce8f',
  posBg: '#22311b',
  caution: '#dcc46a',
  cautionBg: '#38311e',
  neg: '#e58a70',
  negBg: '#3a231d',
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

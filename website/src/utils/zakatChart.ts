/**
 * Pure helpers for the gold & silver zakat reference chart.
 *
 * Maps common metal weights to current market value and zakat due (2.5%).
 * No I/O, no React — fully unit-testable. Live prices are injected by the
 * caller (see nisabPrice.ts hooks); this module only does the arithmetic.
 */
import { ZAKAT_RATE } from './zakatCalculator';

export interface MetalWeight {
  label: string;
  grams: number;
  isNisab?: boolean;
}

export interface ChartRow {
  label: string;
  grams: number;
  value: number;
  zakat: number;
  isNisab: boolean;
}

const TROY_OUNCE_GRAMS = 31.1034768;

// Gold nisab = 85g. 1 tola is a culturally familiar South-Asian unit (11.66g).
export const GOLD_WEIGHTS: MetalWeight[] = [
  { label: '1 tola (11.66 g)', grams: 11.66 },
  { label: '10 g', grams: 10 },
  { label: '1 oz', grams: TROY_OUNCE_GRAMS },
  { label: '50 g', grams: 50 },
  { label: '85 g (nisab)', grams: 85, isNisab: true },
  { label: '100 g', grams: 100 },
];

// Silver nisab = 595g (some scholars cite ~612g).
export const SILVER_WEIGHTS: MetalWeight[] = [
  { label: '1 oz', grams: TROY_OUNCE_GRAMS },
  { label: '100 g', grams: 100 },
  { label: '250 g', grams: 250 },
  { label: '500 g', grams: 500 },
  { label: '595 g (nisab)', grams: 595, isNisab: true },
  { label: '1 kg', grams: 1000 },
];

export function buildChartRows(pricePerGram: number, weights: MetalWeight[]): ChartRow[] {
  return weights.map((w) => {
    const value = w.grams * pricePerGram;
    return {
      label: w.label,
      grams: w.grams,
      value,
      zakat: value * ZAKAT_RATE,
      isNisab: w.isNisab ?? false,
    };
  });
}

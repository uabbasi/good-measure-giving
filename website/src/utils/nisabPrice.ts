/**
 * Live nisab calculation from gold spot price.
 *
 * Fetches gold price from a public CORS-enabled API, computes nisab as
 * 85 grams of gold in USD, and caches the result in localStorage for 6
 * hours to avoid hammering the API on every page load.
 *
 * Falls back silently to the hardcoded NISAB_USD constant if the fetch
 * fails, the response is malformed, or the computed value is implausible.
 */

import { useEffect, useState } from 'react';
import { NISAB_USD } from './zakatCalculator';

const GRAMS_PER_TROY_OUNCE = 31.1034768;
const NISAB_GRAMS_OF_GOLD = 85;
const CACHE_KEY = 'gmg_nisab_usd_v1';
const CACHE_TTL_MS = 6 * 60 * 60 * 1000; // 6 hours

// Sanity bounds — if API returns a value outside these, treat as bogus.
const MIN_PLAUSIBLE_NISAB = 3_000;
const MAX_PLAUSIBLE_NISAB = 20_000;

interface CachedNisab {
  value: number;
  fetchedAt: number;
}

function readCache(): CachedNisab | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedNisab;
    if (typeof parsed.value !== 'number' || typeof parsed.fetchedAt !== 'number') return null;
    if (Date.now() - parsed.fetchedAt > CACHE_TTL_MS) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeCache(value: number): void {
  try {
    const payload: CachedNisab = { value, fetchedAt: Date.now() };
    localStorage.setItem(CACHE_KEY, JSON.stringify(payload));
  } catch {
    // localStorage full or blocked — fail silently
  }
}

export function isPlausibleNisab(value: number): boolean {
  return Number.isFinite(value) && value >= MIN_PLAUSIBLE_NISAB && value <= MAX_PLAUSIBLE_NISAB;
}

export function computeNisabFromGoldPricePerOunce(pricePerOunce: number): number {
  const pricePerGram = pricePerOunce / GRAMS_PER_TROY_OUNCE;
  return Math.round(pricePerGram * NISAB_GRAMS_OF_GOLD);
}

async function fetchLiveNisab(): Promise<number | null> {
  try {
    const res = await fetch('https://api.gold-api.com/price/XAU');
    if (!res.ok) return null;
    const data = (await res.json()) as { price?: number };
    if (typeof data.price !== 'number') return null;
    const nisab = computeNisabFromGoldPricePerOunce(data.price);
    return isPlausibleNisab(nisab) ? nisab : null;
  } catch {
    return null;
  }
}

/**
 * React hook returning the current nisab in USD.
 * Returns the hardcoded fallback immediately, then updates to the live
 * value once the API resolves (if it succeeds and is plausible).
 */
export function useNisab(): number {
  const [nisab, setNisab] = useState<number>(() => {
    const cached = readCache();
    return cached?.value ?? NISAB_USD;
  });

  useEffect(() => {
    const cached = readCache();
    if (cached) return; // fresh cache — skip fetch

    let cancelled = false;
    fetchLiveNisab().then((live) => {
      if (cancelled || live == null) return;
      writeCache(live);
      setNisab(live);
    });
    return () => { cancelled = true; };
  }, []);

  return nisab;
}

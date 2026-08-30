/**
 * The pressed surface, in both themes.
 *
 * The mobile charity card's press feedback originally reused `bg3`, a resting
 * elevation step. That looked fine in light mode and was invisible in dark:
 * bg3 moves the light card 16/255 but the dark card only 6/255, because the
 * dark palette's steps are compressed near black. Reported from a phone as
 * "the tap is still hard to see on dark mode".
 *
 * The failure mode is specific and worth pinning: not "the dark press is too
 * subtle" in isolation, but that one token handed the two themes different
 * amounts of feedback. A future palette edit can move both colours freely;
 * what it must not do is let them drift apart again.
 */

import { describe, expect, it } from 'vitest';
import { gmgPalette } from './tokens';

const rgb = (hex: string): [number, number, number] => {
  const h = hex.replace('#', '');
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)) as [number, number, number];
};

const channel = (c: number): number => {
  const s = c / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
};

const luminance = (hex: string): number => {
  const [r, g, b] = rgb(hex);
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
};

/** WCAG contrast ratio, 1 (identical) to 21 (black on white). */
const contrast = (a: string, b: string): number => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

/** Largest single-channel move — how big the step looks, independent of theme. */
const step = (a: string, b: string): number =>
  Math.max(...rgb(a).map((c, i) => Math.abs(c - rgb(b)[i])));

const light = gmgPalette(false);
const dark = gmgPalette(true);

describe('press token', () => {
  it('is a visible change from the card in both themes', () => {
    // bg3 gave 1.098 (light) and 1.064 (dark); the dark one read as no change.
    expect(contrast(light.press, light.bg2)).toBeGreaterThan(1.25);
    expect(contrast(dark.press, dark.bg2)).toBeGreaterThan(1.25);
  });

  it('gives both themes the same amount of feedback', () => {
    // The actual bug: 16/255 versus 6/255 from one shared token.
    const lightStep = step(light.press, light.bg2);
    const darkStep = step(dark.press, dark.bg2);

    expect(lightStep).toBeGreaterThanOrEqual(24);
    expect(darkStep).toBeGreaterThanOrEqual(24);
    expect(Math.abs(lightStep - darkStep)).toBeLessThanOrEqual(6);
  });

  it('keeps card text readable while the card is held down', () => {
    // A press that swallows the charity's name trades one bug for another.
    expect(contrast(light.fg, light.press)).toBeGreaterThan(7);
    expect(contrast(dark.fg, dark.press)).toBeGreaterThan(7);
  });

  it('stays distinct from bg3, the resting step it used to borrow', () => {
    expect(light.press).not.toBe(light.bg3);
    expect(dark.press).not.toBe(dark.bg3);
  });
});

describe('mobile list edges', () => {
  it('draws the card border strongly enough to bound a card in dark mode', () => {
    // The dark card fill sits 1.06:1 from the page behind it, so the border is
    // doing nearly all the work of showing where one card ends. `rule` gave
    // 1.19:1 and the list read as flat.
    expect(contrast(dark.rule2, dark.bg2)).toBeGreaterThan(1.4);
    expect(contrast(light.rule2, light.bg2)).toBeGreaterThan(1.4);
  });

  it('draws the disclosure chevron at the 3:1 floor for a meaningful graphic', () => {
    // On a phone the chevron is the whole affordance — there is no cursor and
    // no hover behind it. sub2, which the desktop table uses, lands at 2.7:1
    // on the light card.
    expect(contrast(light.sub, light.bg2)).toBeGreaterThanOrEqual(3);
    expect(contrast(dark.sub, dark.bg2)).toBeGreaterThanOrEqual(3);
  });
});

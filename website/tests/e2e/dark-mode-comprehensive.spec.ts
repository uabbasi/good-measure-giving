import { test, expect } from '@playwright/test';

/**
 * Parse a CSS color string to RGB values. Returns null for transparent/unresolvable.
 */
function parseColor(
  color: string
): { r: number; g: number; b: number } | null {
  if (!color || color === 'transparent' || color === 'rgba(0, 0, 0, 0)') {
    return null;
  }
  const rgbMatch = color.match(
    /rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/
  );
  if (rgbMatch) {
    const alpha = rgbMatch[4] !== undefined ? parseFloat(rgbMatch[4]) : 1;
    if (alpha === 0) return null;
    return {
      r: parseInt(rgbMatch[1]),
      g: parseInt(rgbMatch[2]),
      b: parseInt(rgbMatch[3]),
    };
  }
  return null;
}

function colorsMatch(
  a: { r: number; g: number; b: number },
  b: { r: number; g: number; b: number }
): boolean {
  return (
    Math.abs(a.r - b.r) < 10 &&
    Math.abs(a.g - b.g) < 10 &&
    Math.abs(a.b - b.b) < 10
  );
}

const RICH_EIN = '01-0548371';
const BASELINE_EIN = '39-2713494';

const PAGES = [
  { name: 'Landing', path: '/' },
  { name: 'Browse', path: '/browse' },
  { name: 'Detail (rich)', path: `/charity/${RICH_EIN}` },
  { name: 'Detail (baseline)', path: `/charity/${BASELINE_EIN}` },
  { name: 'Methodology', path: '/methodology' },
  { name: 'FAQ', path: '/faq' },
  { name: 'About', path: '/about' },
  { name: 'Compare', path: '/compare' },
  { name: 'Prompts', path: '/prompts' },
  { name: 'Profile', path: '/profile' },
];

test.describe('Dark mode comprehensive', () => {
  for (const { name, path } of PAGES) {
    test(`${name} page renders in dark mode`, async ({ page }) => {
      // Set dark mode before navigating
      await page.goto('/');
      await page.evaluate(() =>
        localStorage.setItem('gmg-landing-theme', 'dark')
      );
      await page.goto(path);
      await page.waitForTimeout(2000);

      // Content renders
      const bodyText = await page.locator('body').textContent();
      expect(bodyText!.length).toBeGreaterThan(50);
    });

    test(`${name} page has no invisible text in dark mode`, async ({
      page,
    }) => {
      await page.goto('/');
      await page.evaluate(() =>
        localStorage.setItem('gmg-landing-theme', 'dark')
      );
      await page.goto(path);
      await page.waitForTimeout(2000);

      // Sample up to 5 visible text elements and check for invisible text
      const invisibleTextFound = await page.evaluate(() => {
        const textElements = Array.from(
          document.querySelectorAll('p, span, li, td, th, label, h1, h2, h3')
        ).filter((el) => {
          const text = el.textContent?.trim();
          return text && text.length > 0 && (el as HTMLElement).offsetParent !== null;
        });

        const sampled = textElements.slice(0, 5);
        const issues: string[] = [];

        for (const el of sampled) {
          const style = window.getComputedStyle(el as HTMLElement);
          const color = style.color;
          const bgColor = style.backgroundColor;

          // Parse colors
          const parseRgb = (c: string) => {
            const m = c.match(
              /rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/
            );
            if (!m) return null;
            const alpha = m[4] !== undefined ? parseFloat(m[4]) : 1;
            if (alpha === 0) return null;
            return { r: parseInt(m[1]), g: parseInt(m[2]), b: parseInt(m[3]) };
          };

          const fg = parseRgb(color);
          const bg = parseRgb(bgColor);

          // Only flag when both are solid and nearly identical
          if (fg && bg) {
            const diff =
              Math.abs(fg.r - bg.r) +
              Math.abs(fg.g - bg.g) +
              Math.abs(fg.b - bg.b);
            if (diff < 30) {
              issues.push(
                `Text "${(el as HTMLElement).textContent?.slice(0, 30)}" has color=${color} bg=${bgColor}`
              );
            }
          }
        }

        return issues;
      });

      expect(
        invisibleTextFound,
        `Invisible text detected: ${invisibleTextFound.join('; ')}`
      ).toHaveLength(0);
    });
  }
});

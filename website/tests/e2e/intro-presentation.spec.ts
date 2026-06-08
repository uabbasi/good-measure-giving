import { test, expect } from '@playwright/test';

const STORAGE_KEY = 'gmg_intro_seen_v1';

test('intro presentation shows on first visit and skip dismisses it', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });

  await page.goto('/');
  await page.evaluate((k) => localStorage.removeItem(k), STORAGE_KEY);
  await page.reload();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(800);

  const dialog = page.getByRole('dialog', { name: 'Introduction to Good Measure Giving' });
  await expect(dialog).toBeVisible();

  await expect(page.getByText('Where does your', { exact: false })).toBeVisible();
  await page.screenshot({ path: '/tmp/intro_slide1.png' });

  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(1500);
  await page.screenshot({ path: '/tmp/intro_slide2_score.png' });

  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(1500);
  await page.screenshot({ path: '/tmp/intro_slide3_zakat.png' });

  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(1500);
  await page.screenshot({ path: '/tmp/intro_slide4_cta.png' });

  // Skip dismisses
  await page.getByRole('button', { name: 'Skip intro' }).click();
  await page.waitForTimeout(500);
  await expect(dialog).toBeHidden();

  // Regression guard: dismissing the intro must release the body scroll lock
  // (prerendered HTML once baked `overflow: hidden` into the body, and the
  // intro's restore-previous-value cleanup re-applied it forever).
  const bodyOverflow = await page.evaluate(() => document.body.style.overflow);
  expect(bodyOverflow).not.toBe('hidden');

  // Reload — should NOT show again (localStorage flag set)
  await page.reload();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(800);
  await expect(dialog).toBeHidden();

  expect(errors, errors.join('\n')).toEqual([]);
});

test('escape key dismisses intro', async ({ page }) => {
  await page.goto('/');
  await page.evaluate((k) => localStorage.removeItem(k), STORAGE_KEY);
  await page.reload();
  await page.waitForTimeout(800);

  const dialog = page.getByRole('dialog', { name: 'Introduction to Good Measure Giving' });
  await expect(dialog).toBeVisible();

  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);
  await expect(dialog).toBeHidden();
});

import { test, expect } from '@playwright/test';

// The "free full evaluations" banners were removed; the per-visitor view log is still kept.
test.describe('Viewed-charity log', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/browse/');
    await page.evaluate(() => {
      localStorage.removeItem('gmg_viewed_charities');
    });
  });

  test('revisiting same charity does not count as new view', async ({ page }) => {
    await page.goto('/browse/');

    const firstCard = page.locator('a[href^="/charity/"]:visible').first();
    await expect(firstCard).toBeVisible({ timeout: 15000 });

    await firstCard.click();
    await expect(page).toHaveURL(/\/charity\//);
    const url = page.url();

    // Wait for localStorage to be written by the useEffect + recordView
    await page.waitForFunction(() => {
      const stored = localStorage.getItem('gmg_viewed_charities');
      return stored && JSON.parse(stored).length === 1;
    }, { timeout: 5000 });

    // Navigate away and back to the same charity
    await page.goto('/browse/');
    await page.goto(url);

    // Wait for page to settle
    await page.waitForFunction(() => {
      const stored = localStorage.getItem('gmg_viewed_charities');
      return stored !== null;
    }, { timeout: 5000 });

    const viewedCount = await page.evaluate(() => {
      const stored = localStorage.getItem('gmg_viewed_charities');
      return stored ? JSON.parse(stored).length : 0;
    });
    expect(viewedCount).toBe(1);
  });
});

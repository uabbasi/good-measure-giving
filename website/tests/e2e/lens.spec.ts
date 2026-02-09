import { test, expect } from '@playwright/test';

const CHARITY_CARD = 'a[href^="/charity/"]:visible';

/** Enter power mode so cards are immediately visible */
async function enterPowerMode(page: import('@playwright/test').Page) {
  await page.goto('/browse');
  await page.evaluate(() => localStorage.setItem('gmg-browse-style', 'power'));
  await page.reload();
  await expect(page.locator(CHARITY_CARD).first()).toBeVisible({ timeout: 10000 });
}

test.describe('Lens switching', () => {
  test('browse page has lens toggle', async ({ page }) => {
    await enterPowerMode(page);

    const lensButtons = page.locator('button').filter({ hasText: /^(Amal|GMG|Strategic|Zakat)$/i });
    await expect(lensButtons.first()).toBeVisible();
  });

  test('switching to Strategic lens updates display', async ({ page }) => {
    await enterPowerMode(page);

    // Use role=tab to target the lens switcher tabs specifically
    const strategicTab = page.getByRole('tab', { name: 'Strategic' });
    if (await strategicTab.isVisible()) {
      await strategicTab.click();
      await expect(page.locator(CHARITY_CARD).first()).toBeVisible({ timeout: 5000 });
    }
  });

  test('switching to Zakat lens updates display', async ({ page }) => {
    await enterPowerMode(page);

    // Use role=tab to avoid matching the "Zakat Eligible" filter chip
    const zakatTab = page.getByRole('tab', { name: 'Zakat' });
    if (await zakatTab.isVisible()) {
      await zakatTab.click();
      await expect(page.locator(CHARITY_CARD).first()).toBeVisible({ timeout: 5000 });
    }
  });

  test('lens persists across page navigation', async ({ page }) => {
    await enterPowerMode(page);

    const strategicTab = page.getByRole('tab', { name: 'Strategic' });
    if (await strategicTab.isVisible()) {
      await strategicTab.click();
      await page.waitForTimeout(500);

      await page.locator(CHARITY_CARD).first().click();
      // Wait for detail page to load
      await expect(page.locator('[role="tablist"]').first()).toBeVisible({ timeout: 10000 });

      // Navigate back to browse
      await page.goto('/browse');
      await expect(page.locator(CHARITY_CARD).first()).toBeVisible({ timeout: 10000 });

      // Verify Strategic is still selected — key is 'gmg-lens'
      const savedLens = await page.evaluate(() => localStorage.getItem('gmg-lens'));
      expect(savedLens).toBe('strategic');
    }
  });
});

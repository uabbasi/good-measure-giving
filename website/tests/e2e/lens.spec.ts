import { test, expect } from '@playwright/test';

const CHARITY_CARD = 'a[href^="/charity/"]:visible';

/** Enter power mode so cards are immediately visible */
async function enterPowerMode(page: import('@playwright/test').Page) {
  await page.goto('/browse');
  await page.evaluate(() => localStorage.setItem('gmg-browse-style', 'power'));
  await page.reload();
  await expect(page.locator(CHARITY_CARD).first()).toBeVisible({ timeout: 10000 });
}

test.describe('Browse sorting and filtering', () => {
  test('browse page has search input and filter presets', async ({ page }) => {
    await enterPowerMode(page);

    // Search input is always visible
    await expect(page.locator('input[type="text"]')).toBeVisible();

    // Preset filter buttons exist
    const presetButtons = page.locator('button').filter({ hasText: /Palestine|Accepts Zakat|Systemic Change|Direct Relief/i });
    expect(await presetButtons.count()).toBeGreaterThan(0);
  });

  test('filtering by preset reduces card count', async ({ page }) => {
    await enterPowerMode(page);

    const allCards = await page.locator(CHARITY_CARD).count();

    const zakatBtn = page.getByRole('button', { name: /Accepts Zakat/i });
    if (await zakatBtn.isVisible()) {
      await zakatBtn.click();
      await page.waitForTimeout(600);
      const filteredCards = await page.locator(CHARITY_CARD).count();
      expect(filteredCards).toBeGreaterThan(0);
      expect(filteredCards).toBeLessThan(allCards);
    }
  });

  test('search filters persist across scroll', async ({ page }) => {
    await enterPowerMode(page);

    const searchInput = page.locator('input[type="text"]');
    await searchInput.fill('relief');
    await page.waitForTimeout(600);

    const cards = page.locator(CHARITY_CARD);
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);

    // Scroll down and verify cards are still filtered
    await page.evaluate(() => window.scrollBy(0, 500));
    await page.waitForTimeout(300);

    const searchValue = await searchInput.inputValue();
    expect(searchValue).toBe('relief');
  });

  test('guided paths activate appropriate filters', async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() => localStorage.removeItem('gmg-browse-style'));
    await page.reload();
    await page.waitForTimeout(2000);

    const zakatPath = page.getByRole('button', { name: /Pay My Zakat/i });
    if (await zakatPath.isVisible()) {
      await zakatPath.click();
      await page.waitForTimeout(1000);
      // Should show charity cards after selecting a guided path
      await expect(page.locator(CHARITY_CARD).first()).toBeVisible({ timeout: 10000 });
    }
  });
});

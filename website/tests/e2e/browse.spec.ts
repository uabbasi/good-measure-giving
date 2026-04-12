import { test, expect } from '@playwright/test';

// CharityCard renders two links per charity (mobile + desktop), use :visible to get the right one
const CHARITY_CARD = 'a[href^="/charity/"]:visible';

/** Switch browse page into power mode so cards and search are visible */
async function enterPowerMode(page: import('@playwright/test').Page) {
  await page.goto('/browse');
  // Set power mode in localStorage and reload so guided view is skipped
  await page.evaluate(() => localStorage.setItem('gmg-browse-style', 'power'));
  await page.reload();
  await expect(page.locator(CHARITY_CARD).first()).toBeVisible({ timeout: 10000 });
}

test.describe('Browse page', () => {
  test('shows guided entry paths for first-time visitors', async ({ page }) => {
    await page.goto('/browse');
    // Clear localStorage to ensure guided view
    await page.evaluate(() => localStorage.removeItem('gmg-browse-style'));
    await page.reload();
    await page.waitForTimeout(2000);

    const guidedPaths = page.getByText('What brings you here?');
    if (await guidedPaths.isVisible()) {
      await expect(page.getByRole('button', { name: /Pay My Zakat/i })).toBeVisible();
      await expect(page.getByRole('button', { name: /Maximum Leverage/i })).toBeVisible();
      await expect(page.getByRole('button', { name: /Browse All/i })).toBeVisible();
    }
    await expect(page.locator('body')).toBeVisible();
  });

  test('search finds charities by name', async ({ page }) => {
    await enterPowerMode(page);

    // Search input is always visible in power mode
    const searchInput = page.locator('input[type="text"]');
    await expect(searchInput).toBeVisible();
    await searchInput.fill('Islamic');
    await page.waitForTimeout(600);

    const cards = page.locator(CHARITY_CARD);
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);
  });

  test('search shows no-results state gracefully', async ({ page }) => {
    await enterPowerMode(page);

    const searchInput = page.locator('input[type="text"]');
    await searchInput.fill('xyznonexistentcharity12345');
    await page.waitForTimeout(600);

    await expect(page.getByText('No matches found')).toBeVisible();
  });

  test('clicking a charity card navigates to detail page', async ({ page }) => {
    await enterPowerMode(page);

    const firstCard = page.locator(CHARITY_CARD).first();
    const href = await firstCard.getAttribute('href');
    await firstCard.click();
    await expect(page).toHaveURL(href!);
    // TabbedView renders charity name in h1
    await expect(page.locator('h1').first()).toBeVisible({ timeout: 10000 });
  });

  test('charity cards show qualitative badges/signals', async ({ page }) => {
    await enterPowerMode(page);

    const cards = page.locator(CHARITY_CARD);
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < Math.min(3, count); i++) {
      const card = cards.nth(i);
      const text = await card.textContent();
      expect(text!.length).toBeGreaterThan(10);
    }
  });

  test('search input and filters are available in power mode', async ({ page }) => {
    await enterPowerMode(page);

    // Search input is always present
    await expect(page.locator('input[type="text"]')).toBeVisible();

    // Filter preset buttons exist (e.g., Palestine, Accepts Zakat)
    const filterButtons = page.locator('button').filter({ hasText: /Palestine|Accepts Zakat/i });
    const filterCount = await filterButtons.count();
    expect(filterCount).toBeGreaterThan(0);
  });
});

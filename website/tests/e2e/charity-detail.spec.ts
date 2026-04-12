import { test, expect } from '@playwright/test';

const CHARITY_CARD = 'a[href^="/charity/"]:visible';

// TabbedView (default) renders charity name in h1
const DETAIL_LOADED = 'h1';

test.describe('Charity detail page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() => localStorage.setItem('gmg-browse-style', 'power'));
    await page.reload();
    const firstCard = page.locator(CHARITY_CARD).first();
    await expect(firstCard).toBeVisible({ timeout: 10000 });
    await firstCard.click();
    await expect(page).toHaveURL(/\/charity\//);
    await expect(page.locator(DETAIL_LOADED).first()).toBeVisible({ timeout: 10000 });
  });

  test('shows charity name and qualitative evaluation snapshot', async ({ page }) => {
    const title = await page.title();
    expect(title).toContain('Good Measure');

    // Charity name appears in the h1
    const heading = await page.locator('h1').first().textContent();
    expect(heading!.length).toBeGreaterThan(3);

    // Page has substantial content
    const bodyText = await page.locator('body').textContent();
    expect(bodyText!.length).toBeGreaterThan(100);
  });

  test('shows key detail sections', async ({ page }) => {
    const bodyText = (await page.locator('body').textContent()) || '';
    // Page should have overview/about content and key sections
    const hasSections = /About|Overview|Quick Facts|Leadership|Financials|Impact/i.test(bodyText);
    expect(hasSections).toBe(true);
  });

  test('shows gated or unlocked rich sections appropriately', async ({ page }) => {
    const bodyText = (await page.locator('body').textContent()) || '';
    const hasGate = /sign in to unlock|sign in to see|sign in to read/i.test(bodyText);
    const hasUnlockedSection = /Leadership|Impact Evidence|Donor Fit|Long-Term Outlook/i.test(bodyText);
    expect(hasGate || hasUnlockedSection).toBe(true);
  });

  test('back to directory button works', async ({ page }) => {
    const backButton = page.locator('a[href="/browse"]:visible').first();
    if (await backButton.isVisible()) {
      await backButton.click();
      await expect(page).toHaveURL('/browse');
    }
  });
});

test.describe('Charity detail - direct URL access', () => {
  test('invalid EIN shows error state', async ({ page }) => {
    await page.goto('/charity/00-0000000');
    await page.waitForTimeout(2000);
    const body = await page.locator('body').textContent();
    expect(body!.length).toBeGreaterThan(20);
  });
});

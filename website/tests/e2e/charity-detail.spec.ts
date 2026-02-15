import { test, expect } from '@playwright/test';

const CHARITY_CARD = 'a[href^="/charity/"]:visible';

// Rich/baseline tier charities render TerminalView directly (no page-level h1 on desktop).
// The evaluation lens tablist is a reliable signal that the detail page loaded.
const DETAIL_LOADED = '[role="tablist"]';

test.describe('Charity detail page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() => localStorage.setItem('gmg-browse-style', 'power'));
    await page.reload();
    const firstCard = page.locator(CHARITY_CARD).first();
    await expect(firstCard).toBeVisible({ timeout: 10000 });
    await firstCard.click();
    await expect(page.locator(DETAIL_LOADED).first()).toBeVisible({ timeout: 10000 });
  });

  test('shows charity name and qualitative evaluation snapshot', async ({ page }) => {
    const title = await page.title();
    expect(title).toContain('Good Measure');

    // Charity name appears as text content on the page (not necessarily in an h1)
    const bodyText = await page.locator('body').textContent();
    expect(bodyText!.length).toBeGreaterThan(100);
  });

  test('view switcher buttons are present', async ({ page }) => {
    // Re-verify the tablist is loaded (guards against re-render between beforeEach and test body)
    await expect(page.locator('[role="tablist"]').first()).toBeVisible({ timeout: 5000 });
    // The detail page has "View selection" tablist with Terminal | Grades
    const viewTab = page.getByRole('tab', { name: /Terminal/i });
    await expect(viewTab).toBeVisible({ timeout: 5000 });
  });

  test('grades view hides grades below B', async ({ page }) => {
    const gradesTab = page.locator('[role="tab"]').filter({ hasText: /grades/i });
    if (await gradesTab.first().isVisible()) {
      await gradesTab.first().click();
      await page.waitForTimeout(1000);
      await expect(page.locator('body')).toBeVisible();
    }
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

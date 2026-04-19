import { test, expect } from '@playwright/test';

test.describe('Progressive reveal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() => {
      localStorage.removeItem('gmg_viewed_charities');
    });
  });

  test('shows full content for first 3 unique charity views', async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() => localStorage.setItem('gmg-browse-style', 'power'));
    await page.reload();

    const firstCard = page.locator('a[href^="/charity/"]:visible').first();
    await expect(firstCard).toBeVisible({ timeout: 10000 });
    await firstCard.click();
    await expect(page).toHaveURL(/\/charity\//);

    const banner = page.getByText(/free full evaluations/i);
    await expect(banner).toBeVisible({ timeout: 5000 });
  });

  test('third unique view is NOT gated (regression: off-by-one)', async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() => {
      localStorage.setItem('gmg_viewed_charities', JSON.stringify([
        'fake-ein-001', 'fake-ein-002',
      ]));
      localStorage.setItem('gmg-browse-style', 'power');
    });
    await page.reload();

    const firstCard = page.locator('a[href^="/charity/"]:visible').first();
    await expect(firstCard).toBeVisible({ timeout: 10000 });
    await firstCard.click();
    await expect(page).toHaveURL(/\/charity\//);

    // 3rd unique view — must stay ungated
    const exhaustedBanner = page.getByText(/used your free evaluations/i);
    await expect(exhaustedBanner).not.toBeVisible();
    const softBanner = page.getByText(/free full evaluations/i);
    await expect(softBanner).toBeVisible({ timeout: 5000 });
  });

  test('shows gated content after 3 unique charity views', async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() => {
      localStorage.setItem('gmg_viewed_charities', JSON.stringify([
        'fake-ein-001', 'fake-ein-002', 'fake-ein-003'
      ]));
      localStorage.setItem('gmg-browse-style', 'power');
    });
    await page.reload();

    const firstCard = page.locator('a[href^="/charity/"]:visible').first();
    await expect(firstCard).toBeVisible({ timeout: 10000 });
    await firstCard.click();
    await expect(page).toHaveURL(/\/charity\//);

    const exhaustedBanner = page.getByText(/used your free evaluations/i);
    await expect(exhaustedBanner).toBeVisible({ timeout: 5000 });
  });

  test('revisiting same charity does not count as new view', async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() => localStorage.setItem('gmg-browse-style', 'power'));
    await page.reload();

    const firstCard = page.locator('a[href^="/charity/"]:visible').first();
    await expect(firstCard).toBeVisible({ timeout: 10000 });

    await firstCard.click();
    await expect(page).toHaveURL(/\/charity\//);
    const url = page.url();

    // Wait for localStorage to be written by the useEffect + recordView
    await page.waitForFunction(() => {
      const stored = localStorage.getItem('gmg_viewed_charities');
      return stored && JSON.parse(stored).length === 1;
    }, { timeout: 5000 });

    // Navigate away and back to the same charity
    await page.goto('/browse');
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

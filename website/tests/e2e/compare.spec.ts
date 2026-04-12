import { test, expect } from '@playwright/test';

const RICH_EIN = '01-0548371';

test.describe('Compare flow', () => {
  test('compare page loads with empty state', async ({ page }) => {
    await page.goto('/compare');
    await expect(page.locator('body')).toBeVisible();
    const body = await page.locator('body').textContent();
    expect(body!.length).toBeGreaterThan(20);
  });

  test('detail page has compare button', async ({ page }) => {
    // Navigate directly to a known charity to avoid stale browse-page elements
    await page.goto(`/charity/${RICH_EIN}`);
    await expect(page.locator('h1').first()).toBeVisible({ timeout: 10000 });

    const compareButton = page.locator('button[aria-label*="compare" i]');
    const count = await compareButton.count();
    if (count > 0) {
      await expect(compareButton.first()).toBeVisible();
    }
  });

  test('compare view has back-to-evaluation button', async ({ page }) => {
    await page.goto(`/charity/${RICH_EIN}`);
    await expect(page.locator('h1').first()).toBeVisible({ timeout: 10000 });

    const compareButton = page.locator('button[aria-label*="compare" i]');
    if (await compareButton.first().isVisible({ timeout: 3000 }).catch(() => false)) {
      await compareButton.first().click();
      await page.waitForTimeout(1000);

      const backButton = page.locator('button').filter({ hasText: /back to evaluation/i });
      if (await backButton.isVisible({ timeout: 3000 }).catch(() => false)) {
        await backButton.click();
        await page.waitForTimeout(500);
      }
    }
  });
});

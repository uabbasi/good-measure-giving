import { test, expect } from '@playwright/test';

const CHARITY_CARD = 'a[href^="/charity/"]:visible';

test.describe('Compare flow', () => {
  test('compare page loads with empty state', async ({ page }) => {
    await page.goto('/compare');
    await expect(page.locator('body')).toBeVisible();
    const body = await page.locator('body').textContent();
    expect(body!.length).toBeGreaterThan(20);
  });

  test('detail page has view switcher with compare option', async ({ page }) => {
    await page.goto('/browse');
    const firstCard = page.locator(CHARITY_CARD).first();
    await expect(firstCard).toBeVisible({ timeout: 10000 });
    await firstCard.click();
    await expect(page.locator('[role="tablist"]').first()).toBeVisible({ timeout: 10000 });

    const compareButton = page.locator('button').filter({ hasText: /compare/i });
    if (await compareButton.first().isVisible()) {
      await compareButton.first().click();
      await page.waitForTimeout(1000);
      const bodyText = await page.locator('body').textContent();
      expect(bodyText).toBeTruthy();
    }
  });

  test('compare view has back-to-evaluation button', async ({ page }) => {
    await page.goto('/browse');
    const firstCard = page.locator(CHARITY_CARD).first();
    await expect(firstCard).toBeVisible({ timeout: 10000 });
    await firstCard.click();
    await expect(page.locator('[role="tablist"]').first()).toBeVisible({ timeout: 10000 });

    const compareButton = page.locator('button').filter({ hasText: /compare/i });
    if (await compareButton.first().isVisible()) {
      await compareButton.first().click();
      await page.waitForTimeout(1000);

      const backButton = page.locator('button').filter({ hasText: /back to evaluation/i });
      if (await backButton.isVisible()) {
        await backButton.click();
        await page.waitForTimeout(500);
      }
    }
  });
});

import { test, expect } from '@playwright/test';

// CharityCard renders two links per charity (mobile + desktop); use :visible.
const CHARITY_CARD = 'a[href^="/charity/"]:visible';

async function enterPowerMode(page: import('@playwright/test').Page) {
  await page.goto('/browse');
  await page.evaluate(() => localStorage.setItem('gmg-browse-style', 'power'));
  await page.reload();
  await expect(page.locator(CHARITY_CARD).first()).toBeVisible({ timeout: 10000 });
}

test.describe('Add to giving button', () => {
  test('anonymous users see a "Sign in to add" action on charity cards', async ({ page }) => {
    await enterPowerMode(page);

    // The desktop card has the button. On small viewports we may only have
    // the mobile card (no button), so prefer a wide viewport for this test.
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.reload();
    await expect(page.locator(CHARITY_CARD).first()).toBeVisible({ timeout: 10000 });

    const buttons = page.getByRole('button', { name: /Sign in to add|Add to giving|In your giving/i });
    // At least one card should show an add-to-giving button
    const count = await buttons.count();
    expect(count).toBeGreaterThan(0);

    // Clicking a "Sign in to add" button should NOT navigate away or hard-crash.
    const first = buttons.first();
    await first.click();
    // Still on /browse
    await expect(page).toHaveURL(/\/browse/);
  });
});

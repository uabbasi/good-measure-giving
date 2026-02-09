import { test, expect, devices } from '@playwright/test';

// On mobile, the mobile variant of CharityCard is visible (sm:hidden means visible below sm)
const MOBILE_CHARITY_CARD = 'a[href^="/charity/"]:visible';

test.use({ viewport: { width: 390, height: 844 } });

test.describe('Mobile viewport', () => {
  test('landing page renders on mobile', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Good Measure Giving/);
    // On mobile, the hero CTA link to /browse should be visible
    await expect(page.locator('a[href="/browse"]:visible').first()).toBeVisible();
  });

  test('browse page shows stacked cards on mobile', async ({ page }) => {
    await page.goto('/browse');
    await expect(page.locator(MOBILE_CHARITY_CARD).first()).toBeVisible({ timeout: 10000 });

    const firstCard = page.locator(MOBILE_CHARITY_CARD).first();
    const box = await firstCard.boundingBox();
    expect(box).toBeTruthy();
    // On 390px viewport, card should take most of the width
    expect(box!.width).toBeGreaterThan(300);
  });

  test('charity detail page loads on mobile', async ({ page }) => {
    await page.goto('/browse');
    const firstCard = page.locator(MOBILE_CHARITY_CARD).first();
    await expect(firstCard).toBeVisible({ timeout: 10000 });
    await firstCard.click();

    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 });
    const bodyText = await page.locator('body').textContent();
    expect(bodyText!.length).toBeGreaterThan(100);
  });

  test('FAQ page renders on mobile', async ({ page }) => {
    await page.goto('/faq');
    await expect(page.locator('h1')).toBeVisible();
    const zakatButton = page.getByRole('button', { name: 'Zakat & Sadaqah' });
    await expect(zakatButton).toBeVisible();
  });
});

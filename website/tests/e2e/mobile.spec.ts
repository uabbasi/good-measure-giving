import { test, expect } from '@playwright/test';

// On mobile, the mobile variant of CharityCard is visible (sm:hidden means visible below sm)
const MOBILE_CHARITY_CARD = 'a[href^="/charity/"]:visible';

test.describe('Mobile viewport (375px)', () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test('landing page renders on mobile', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Good Measure Giving/);
    // On mobile, the hero CTA link to /browse should be visible
    await expect(page.locator('a[href="/browse/"]:visible').first()).toBeVisible();
  });

  test('browse page shows stacked cards on mobile', async ({ page }) => {
    await page.goto('/browse/');
    const card = page.locator('[data-charity-card]').first();
    await expect(card).toBeVisible({ timeout: 15000 });
    const box = await card.boundingBox();
    expect(box).toBeTruthy();
    // On a 375px viewport the card takes most of the width.
    expect(box!.width).toBeGreaterThan(280);
  });

  test('charity detail page loads on mobile', async ({ page }) => {
    await page.goto('/browse/');
    const firstCard = page.locator(MOBILE_CHARITY_CARD).first();
    await expect(firstCard).toBeVisible({ timeout: 10000 });
    await firstCard.click();

    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 });
    const bodyText = await page.locator('body').textContent();
    expect(bodyText!.length).toBeGreaterThan(100);
  });

  test('FAQ page renders on mobile', async ({ page }) => {
    await page.goto('/faq/');
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Zakat & Sadaqah' })).toBeVisible();
  });

  test('the menu button opens the site links', async ({ page }) => {
    await page.goto('/browse/');
    const menu = page.getByRole('button', { name: 'Menu' });
    await expect(menu).toBeVisible();
    await expect(menu).toHaveAttribute('aria-expanded', 'false');
    await menu.click();
    await expect(menu).toHaveAttribute('aria-expanded', 'true');
    const nav = page.locator('#gmg-mobile-nav');
    for (const name of ['Methodology', 'FAQ', 'About']) {
      await expect(nav.getByRole('link', { name })).toBeVisible();
    }
  });

  test('the menu navigates', async ({ page }) => {
    await page.goto('/faq/');
    await page.getByRole('button', { name: 'Menu' }).click();
    await page.locator('#gmg-mobile-nav').getByRole('link', { name: 'Browse charities' }).click();
    await expect(page).toHaveURL(/\/browse\/$/);
  });

  test('search input works on mobile', async ({ page }) => {
    await page.goto('/browse/');
    await expect(page.locator('[data-charity-card]').first()).toBeVisible({ timeout: 15000 });
    const all = await page.locator('[data-charity-card]').count();
    await page.locator('#gmg-browse-search').fill('Islamic');
    await expect.poll(async () => page.locator('[data-charity-card]').count()).toBeLessThan(all);
    expect(await page.locator('[data-charity-card]').count()).toBeGreaterThan(0);
  });

  test('detail page has donate and share actions on mobile', async ({ page }) => {
    await page.goto('/charity/01-0548371');
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 });

    // Mobile should show action buttons (donate, save, share)
    const bodyText = await page.locator('body').textContent();
    const hasActions = /Donate|Save|Share|Sign in/i.test(bodyText || '');
    expect(hasActions).toBe(true);
  });

  test('text is readable — no horizontal overflow on mobile', async ({ page }) => {
    await page.goto('/browse/');
    await expect(page.locator(MOBILE_CHARITY_CARD).first()).toBeVisible({ timeout: 15000 });

    // Page should not have horizontal scroll
    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });
    expect(hasHorizontalOverflow).toBe(false);
  });
});

test.describe('Tablet viewport (768px)', () => {
  test.use({ viewport: { width: 768, height: 1024 } });

  test('browse page renders on tablet', async ({ page }) => {
    await page.goto('/browse/');
    await expect(page.locator(MOBILE_CHARITY_CARD).first()).toBeVisible({ timeout: 15000 });
  });

  test('charity detail loads on tablet', async ({ page }) => {
    await page.goto('/charity/01-0548371');
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 });
    const bodyText = await page.locator('body').textContent();
    expect(bodyText!.length).toBeGreaterThan(200);
  });

  test('no horizontal overflow on tablet', async ({ page }) => {
    await page.goto('/browse/');
    await expect(page.locator(MOBILE_CHARITY_CARD).first()).toBeVisible({ timeout: 15000 });

    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });
    expect(hasHorizontalOverflow).toBe(false);
  });

  test('landing page renders on tablet', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Good Measure Giving/);
    await expect(page.locator('a[href="/browse/"]:visible').first()).toBeVisible();
  });

  test('FAQ page renders on tablet', async ({ page }) => {
    await page.goto('/faq/');
    await expect(page.locator('h1')).toBeVisible();
  });
});

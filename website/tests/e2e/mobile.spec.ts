import { test, expect } from '@playwright/test';

// On mobile, the mobile variant of CharityCard is visible (sm:hidden means visible below sm)
const MOBILE_CHARITY_CARD = 'a[href^="/charity/"]:visible';

test.describe('Mobile viewport (375px)', () => {
  test.use({ viewport: { width: 375, height: 812 } });

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
    // On 375px viewport, card should take most of the width
    expect(box!.width).toBeGreaterThan(280);
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

  test('bottom nav bar is visible on mobile', async ({ page }) => {
    await page.goto('/browse');
    // MobileBottomNav has aria-label="Mobile navigation"
    const bottomNav = page.locator('nav[aria-label="Mobile navigation"]');
    await expect(bottomNav).toBeVisible();

    // Should have Browse, Sign In/Giving Plan, and More tabs
    await expect(bottomNav.getByText('Browse')).toBeVisible();
    await expect(bottomNav.getByText('More')).toBeVisible();
  });

  test('bottom nav "More" opens sheet with Methodology, FAQ, About', async ({ page }) => {
    await page.goto('/browse');
    const bottomNav = page.locator('nav[aria-label="Mobile navigation"]');
    await expect(bottomNav).toBeVisible();

    // Click "More" button
    const moreButton = bottomNav.locator('button[aria-label="More options"]');
    await moreButton.click();
    await page.waitForTimeout(500);

    // Sheet should show nav links — scope to the sheet overlay (fixed overlay above bottom nav)
    const sheet = page.locator('.fixed.inset-0');
    await expect(sheet.getByText('Methodology')).toBeVisible();
    await expect(sheet.getByText('FAQ')).toBeVisible();
    await expect(sheet.getByText('About')).toBeVisible();
  });

  test('bottom nav navigates to browse', async ({ page }) => {
    await page.goto('/faq');
    const bottomNav = page.locator('nav[aria-label="Mobile navigation"]');
    await expect(bottomNav).toBeVisible();

    await bottomNav.getByText('Browse').click();
    await expect(page).toHaveURL('/browse');
  });

  test('search input works on mobile', async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() => localStorage.setItem('gmg-browse-style', 'power'));
    await page.reload();
    await expect(page.locator(MOBILE_CHARITY_CARD).first()).toBeVisible({ timeout: 10000 });

    const searchInput = page.locator('input[type="text"]');
    await expect(searchInput).toBeVisible();
    await searchInput.fill('Islamic');
    await page.waitForTimeout(600);

    const cards = page.locator(MOBILE_CHARITY_CARD);
    expect(await cards.count()).toBeGreaterThan(0);
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
    await page.goto('/browse');
    await expect(page.locator(MOBILE_CHARITY_CARD).first()).toBeVisible({ timeout: 10000 });

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
    await page.goto('/browse');
    await expect(page.locator(MOBILE_CHARITY_CARD).first()).toBeVisible({ timeout: 10000 });
  });

  test('charity detail loads on tablet', async ({ page }) => {
    await page.goto('/charity/01-0548371');
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 });
    const bodyText = await page.locator('body').textContent();
    expect(bodyText!.length).toBeGreaterThan(200);
  });

  test('no horizontal overflow on tablet', async ({ page }) => {
    await page.goto('/browse');
    await expect(page.locator(MOBILE_CHARITY_CARD).first()).toBeVisible({ timeout: 10000 });

    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });
    expect(hasHorizontalOverflow).toBe(false);
  });

  test('landing page renders on tablet', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Good Measure Giving/);
    await expect(page.locator('a[href="/browse"]:visible').first()).toBeVisible();
  });

  test('FAQ page renders on tablet', async ({ page }) => {
    await page.goto('/faq');
    await expect(page.locator('h1')).toBeVisible();
  });
});

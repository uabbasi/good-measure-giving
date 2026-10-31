import { test, expect } from '@playwright/test';

const RICH_EIN = '01-0548371';
const EIN1 = '01-0548371';
const EIN2 = '04-2535767';
const NAME1 = 'Muslim Legal Fund';
const NAME2 = 'Union of Concerned Scientists';

test.use({ viewport: { width: 390, height: 844 } });

test.describe('Mobile comprehensive', () => {
  test('browse cards are tappable and full-width', async ({ page }) => {
    await page.goto('/browse/');
    const cards = page.locator('[data-charity-card]');
    await expect(cards.first()).toBeVisible({ timeout: 15000 });
    for (let i = 0; i < 3; i++) {
      const box = await cards.nth(i).boundingBox();
      expect(box).toBeTruthy();
      // On a 390px viewport, cards are wider than 300px
      expect(box!.width).toBeGreaterThan(300);
    }
  });

  test('detail page shows charity name on mobile', async ({ page }) => {
    await page.goto(`/charity/${RICH_EIN}`);
    await page.waitForTimeout(3000);

    // On mobile, charity name should appear in h1 or h2
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10000 });
    const headingText = await heading.textContent();
    expect(headingText!.length).toBeGreaterThan(3);
  });

  test('the mobile menu shows the nav links', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Menu' }).click();
    const nav = page.locator('#gmg-mobile-nav');
    await expect(nav.getByRole('link', { name: 'Methodology' })).toBeVisible();
    await expect(nav.getByRole('link', { name: 'FAQ' })).toBeVisible();
    await expect(nav.getByRole('link', { name: 'About' })).toBeVisible();
  });

  test('the FAQ lists its sections and answers', async ({ page }) => {
    await page.goto('/faq/');
    await expect(page.locator('h1')).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('heading', { name: 'General' })).toBeVisible();
    const bodyText = await page.locator('body').textContent();
    expect(bodyText!.length).toBeGreaterThan(1000);
  });

  test('compare renders on mobile with 2 charities', async ({ page }) => {
    await page.goto(`/compare/?eins=${EIN1},${EIN2}`);
    await expect(page.getByText(NAME1).first()).toBeVisible({ timeout: 15000 });
    const bodyText = await page.locator('body').textContent();
    expect(bodyText).toContain(NAME2);
  });

  test('detail page scrollable on mobile — no content clipping', async ({ page }) => {
    await page.goto(`/charity/${RICH_EIN}`);
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 });

    // Page should be scrollable (content taller than viewport)
    const pageHeight = await page.evaluate(() => document.documentElement.scrollHeight);
    expect(pageHeight).toBeGreaterThan(844); // viewport height
  });

  test('dark mode works on mobile', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('gmg-theme', 'dark'));
    await page.goto('/browse/');
    await expect(page.locator('[data-charity-card]').first()).toBeVisible({ timeout: 15000 });
    await expect(page.locator('html')).toHaveClass(/dark/);
  });

  test('methodology page renders on mobile', async ({ page }) => {
    await page.goto('/methodology');
    await expect(page.locator('h1')).toBeVisible();
    const bodyText = await page.locator('body').textContent();
    expect(bodyText).toMatch(/How We Evaluate/i);
  });

  test('about page renders on mobile', async ({ page }) => {
    await page.goto('/about');
    await expect(page.locator('h1, h2').first()).toBeVisible();
    const bodyText = await page.locator('body').textContent();
    expect(bodyText!.length).toBeGreaterThan(100);
  });

  test('no horizontal overflow on any mobile page', async ({ page }) => {
    const pages = ['/browse', '/faq', '/methodology', '/about', `/charity/${RICH_EIN}`];
    for (const path of pages) {
      await page.goto(path);
      await page.waitForTimeout(2000);

      const hasHorizontalOverflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth;
      });
      expect(hasHorizontalOverflow, `Horizontal overflow on ${path}`).toBe(false);
    }
  });
});

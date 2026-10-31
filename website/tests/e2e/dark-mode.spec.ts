import { test, expect } from '@playwright/test';

const CHARITY_LINK = 'a[href^="/charity/"]:visible';

test.describe('Dark mode', () => {
  test('the footer switch toggles the dark class and the page background', async ({ page }) => {
    await page.goto('/browse/');
    await expect(page.locator(CHARITY_LINK).first()).toBeVisible({ timeout: 15_000 });
    await page.evaluate(() => localStorage.setItem('gmg-theme', 'light'));
    await page.reload();
    await expect(page.locator(CHARITY_LINK).first()).toBeVisible({ timeout: 15_000 });

    const bg = () => page.evaluate(() => getComputedStyle(document.querySelector('header')!.parentElement!).backgroundColor);
    const light = await bg();
    await page.getByRole('button', { name: 'Decline analytics' }).click({ timeout: 5000 }).catch(() => {}); // the consent banner covers the footer
    await page.locator('footer').getByRole('switch', { name: /dark mode/i }).click();
    await expect(page.locator('html')).toHaveClass(/dark/);
    expect(await bg()).not.toBe(light);
  });

  test('dark mode works on the charity detail page', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('gmg-theme', 'dark'));
    await page.goto('/charity/95-4453134/');
    await expect(page.locator('h1').first()).toBeVisible({ timeout: 15_000 });
    await expect(page.locator('html')).toHaveClass(/dark/);
  });

  test('dark mode works on the FAQ page', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('gmg-theme', 'dark'));
    await page.goto('/faq/');
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('html')).toHaveClass(/dark/);
  });

  test('dark mode persists across navigation', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('gmg-theme', 'dark'));
    await page.goto('/browse/');
    await expect(page.locator(CHARITY_LINK).first()).toBeVisible({ timeout: 15_000 });

    await page.getByRole('button', { name: 'Decline analytics' }).click({ timeout: 5000 }).catch(() => {}); // the consent banner covers the footer
    await page.locator('footer a[href="/faq/"]').click();
    await expect(page).toHaveURL(/\/faq\/$/);
    await expect(page.locator('html')).toHaveClass(/dark/);
    expect(await page.evaluate(() => localStorage.getItem('gmg-theme'))).toBe('dark');
  });
});

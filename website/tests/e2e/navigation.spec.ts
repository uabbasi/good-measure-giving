import { test, expect } from '@playwright/test';

const CHARITY_CARD = 'a[href^="/charity/"]:visible';

test.describe('Navigation smoke tests', () => {
  test('landing page loads with hero CTA', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Good Measure Giving/);
    await expect(page.locator('a[href="/browse"]:visible').first()).toBeVisible();
  });

  test('landing page has community CTA section', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Build your giving plan')).toBeVisible();
  });

  test('browse page loads with charities', async ({ page }) => {
    await page.goto('/browse');
    await expect(page.locator(CHARITY_CARD).first()).toBeVisible({ timeout: 10000 });
  });

  test('methodology page loads', async ({ page }) => {
    await page.goto('/methodology');
    await expect(page.locator('h1')).toContainText(/How We Evaluate/i);
  });

  test('FAQ page loads with categories', async ({ page }) => {
    await page.goto('/faq');
    await expect(page.locator('h1')).toContainText(/frequently asked/i);
    await expect(page.getByRole('button', { name: 'General' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Zakat & Sadaqah' })).toBeVisible();
  });

  test('FAQ contact CTA has email link', async ({ page }) => {
    await page.goto('/faq');
    const contactLink = page.locator('a[href="mailto:hello@goodmeasuregiving.org"]');
    await expect(contactLink.first()).toBeVisible();
  });

  test('about page loads', async ({ page }) => {
    await page.goto('/about');
    await expect(page.locator('h1, h2').first()).toBeVisible();
  });

  test('prompts page loads', async ({ page }) => {
    await page.goto('/prompts');
    await expect(page.locator('body')).toBeVisible();
  });

  test('404 shows for unknown route', async ({ page }) => {
    await page.goto('/this-does-not-exist');
    const body = await page.locator('body').textContent();
    expect(body!.length).toBeGreaterThan(20);
  });

  test('navbar links work', async ({ page }) => {
    await page.goto('/');
    const nav = page.locator('nav');
    await expect(nav).toBeVisible();

    // Browse link in desktop nav
    await nav.locator('a[href="/browse"]:visible').click();
    await expect(page).toHaveURL('/browse');

    await nav.locator('a[href="/faq"]:visible').click();
    await expect(page).toHaveURL('/faq');

    await nav.locator('a[href="/about"]:visible').click();
    await expect(page).toHaveURL('/about');
  });

  test('footer has contact link', async ({ page }) => {
    await page.goto('/browse');
    const footer = page.locator('footer');
    await expect(footer.locator('a[href="mailto:hello@goodmeasuregiving.org"]')).toBeVisible();
  });

  test('footer theme toggle works', async ({ page }) => {
    await page.goto('/browse');
    const footer = page.locator('footer');
    const themeButton = footer.locator('button[aria-label*="mode"]');
    await expect(themeButton).toBeVisible();
    await themeButton.click();
    await expect(page.locator('body')).toBeVisible();
  });
});

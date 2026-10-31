import { test, expect } from '@playwright/test';

const CHARITY_CARD = 'a[href^="/charity/"]:visible';

test.describe('Navigation smoke tests', () => {
  test('landing page loads with hero CTA', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Good Measure Giving/);
    await expect(page.locator('a[href="/browse/"]:visible').first()).toBeVisible();
  });

  test('landing page shows the hero and the independence section', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('h1:visible').first()).toContainText(/Give with confidence/i, { timeout: 10000 });
    const body = await page.locator('body').textContent();
    expect(body).toContain('no charity ever pays to be here');
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
    await expect(page.getByRole('heading', { name: 'General' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Zakat & Sadaqah' })).toBeVisible();
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

  test('header nav links work', async ({ page }) => {
    await page.goto('/');
    const nav = page.locator('header nav');
    await expect(nav).toBeVisible();

    await nav.locator('a[href="/browse/"]').click();
    await expect(page).toHaveURL(/\/browse\/$/);

    await page.locator('header nav a[href="/about/"]').click();
    await expect(page).toHaveURL(/\/about\/$/);
  });

  test('footer links to the main sections', async ({ page }) => {
    await page.goto('/browse/');
    const footer = page.locator('footer');
    for (const href of ['/faq/', '/methodology/', '/privacy/', '/terms/']) {
      await expect(footer.locator(`a[href="${href}"]`)).toBeVisible();
    }
  });

  test('footer light/dark switch flips and persists the theme', async ({ page }) => {
    await page.goto('/browse/');
    await page.getByRole('button', { name: 'Decline analytics' }).click({ timeout: 5000 }).catch(() => {}); // the consent banner covers the footer
    const toggle = page.locator('footer').getByRole('switch', { name: /dark mode/i });
    await expect(toggle).toBeVisible();
    const before = await toggle.getAttribute('aria-checked');
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-checked', before === 'true' ? 'false' : 'true');
    const stored = await page.evaluate(() => localStorage.getItem('gmg-theme'));
    expect(stored).toBe(before === 'true' ? 'light' : 'dark');
  });
});

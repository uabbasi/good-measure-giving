import { test, expect } from '@playwright/test';

// Browse is one page now: a table on wide screens and cards on phones, both linking to /charity/<ein>/.
// (The old "guided" / "power" modes are gone.)
const CHARITY_LINK = 'a[href^="/charity/"]:visible';
const SEARCH = '#gmg-browse-search';

async function openBrowse(page: import('@playwright/test').Page) {
  await page.goto('/browse/');
  await expect(page.locator(CHARITY_LINK).first()).toBeVisible({ timeout: 15_000 });
}

test.describe('Browse page', () => {
  test('lists charities with the filter bar', async ({ page }) => {
    await openBrowse(page);
    await expect(page.getByRole('heading', { level: 1 })).toContainText(/Every charity/i);
    await expect(page.locator(SEARCH)).toBeVisible();
    // Zakat / Sadaqah filter pills carry their counts.
    await expect(page.getByRole('button', { name: /^Zakat \d+/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /^Sadaqah \d+/ })).toBeVisible();
  });

  test('search finds charities by name', async ({ page }) => {
    await openBrowse(page);
    const all = await page.locator(CHARITY_LINK).count();
    await page.locator(SEARCH).fill('Islamic');
    await expect.poll(async () => page.locator(CHARITY_LINK).count()).toBeLessThan(all);
    expect(await page.locator(CHARITY_LINK).count()).toBeGreaterThan(0);
  });

  test('search shows a no-results state gracefully', async ({ page }) => {
    await openBrowse(page);
    await page.locator(SEARCH).fill('xyznonexistentcharity12345');
    await expect(page.getByText('No charities match')).toBeVisible();
  });

  test('clicking a charity navigates to its detail page', async ({ page }) => {
    await openBrowse(page);
    const first = page.locator(CHARITY_LINK).first();
    const href = await first.getAttribute('href');
    await first.click();
    await expect(page).toHaveURL(new RegExp(href!.replace(/\//g, '\\/')));
    await expect(page.locator('h1').first()).toBeVisible({ timeout: 15_000 });
  });

  test('rows show the grade signals', async ({ page }) => {
    await openBrowse(page);
    const row = page.locator('tbody tr').first();
    await expect(row).toContainText(/Strong|Good|Moderate|Fair|Weak/);
    // Grades only: the GMG score is never shown as a number.
    expect(await page.locator('tbody').first().textContent()).not.toMatch(/\d+\s*\/\s*100/);
  });

  test('the Zakat filter narrows the list', async ({ page }) => {
    await openBrowse(page);
    const all = await page.locator('tbody tr').count();
    await page.getByRole('button', { name: /^Zakat \d+/ }).click();
    await expect.poll(async () => page.locator('tbody tr').count()).toBeLessThan(all);
    expect(await page.locator('tbody tr').count()).toBeGreaterThan(0);
  });
});

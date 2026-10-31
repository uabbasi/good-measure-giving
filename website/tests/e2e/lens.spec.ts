import { test, expect } from '@playwright/test';

// Browse is one page now: a table on wide screens and cards on phones, both linking to /charity/<ein>/.
// (The old "guided" / "power" modes are gone.)
const CHARITY_LINK = 'a[href^="/charity/"]:visible';
const SEARCH = '#gmg-browse-search';

async function openBrowse(page: import('@playwright/test').Page) {
  await page.goto('/browse/');
  await expect(page.locator(CHARITY_LINK).first()).toBeVisible({ timeout: 15_000 });
}

test.describe('Browse sorting and filtering', () => {
  test('browse has a search box and filter pills', async ({ page }) => {
    await openBrowse(page);
    await expect(page.locator(SEARCH)).toBeVisible();
    await expect(page.getByRole('button', { name: /^Zakat \d+/ })).toBeVisible();
  });

  test('filtering by Zakat reduces the list', async ({ page }) => {
    await openBrowse(page);
    const all = await page.locator('tbody tr').count();
    await page.getByRole('button', { name: /^Zakat \d+/ }).click();
    await expect.poll(async () => page.locator('tbody tr').count()).toBeLessThan(all);
  });

  test('the search term survives scrolling', async ({ page }) => {
    await openBrowse(page);
    await page.locator(SEARCH).fill('relief');
    await expect.poll(async () => page.locator(CHARITY_LINK).count()).toBeGreaterThan(0);
    await page.evaluate(() => window.scrollBy(0, 500));
    await expect(page.locator(SEARCH)).toHaveValue('relief');
  });

  test('column headers are real buttons that sort', async ({ page }) => {
    await openBrowse(page);
    const header = page.getByRole('columnheader', { name: /Program %/ });
    await header.getByRole('button').click();
    await expect(header).toHaveAttribute('aria-sort', /ascending|descending/);
  });
});

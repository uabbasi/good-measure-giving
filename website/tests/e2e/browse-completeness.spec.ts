import { test, expect } from '@playwright/test';

// Browse is one page now: a table on wide screens and cards on phones, both linking to /charity/<ein>/.
// (The old "guided" / "power" modes are gone.)
const CHARITY_LINK = 'a[href^="/charity/"]:visible';
const SEARCH = '#gmg-browse-search';

async function openBrowse(page: import('@playwright/test').Page) {
  await page.goto('/browse/');
  await expect(page.locator(CHARITY_LINK).first()).toBeVisible({ timeout: 15_000 });
}

test.describe('Browse page completeness', () => {
  test('card count: at least 130 unique charity links', async ({ page }) => {
    await openBrowse(page);
    const hrefs = await page.locator('a[href^="/charity/"]').evaluateAll((els) => els.map((e) => e.getAttribute('href')));
    expect(new Set(hrefs).size).toBeGreaterThanOrEqual(130);
  });

  test('no blank rows: every charity link has a name', async ({ page }) => {
    await openBrowse(page);
    const texts = await page.locator(CHARITY_LINK).evaluateAll((els) => els.map((e) => (e.textContent || '').trim()));
    expect(texts.length).toBeGreaterThan(0);
    for (const t of texts) expect(t.length).toBeGreaterThan(2);
  });

  test('the Zakat and Sadaqah pills each return results', async ({ page }) => {
    await openBrowse(page);
    for (const pill of [/^Zakat \d+/, /^Sadaqah \d+/]) {
      await page.getByRole('button', { name: pill }).click();
      await expect.poll(async () => page.locator(CHARITY_LINK).count()).toBeGreaterThan(0);
      await page.getByRole('button', { name: pill }).click(); // toggle back off
    }
  });

  test('More filters opens the cause and region groups', async ({ page }) => {
    await openBrowse(page);
    await page.getByRole('button', { name: /More filters/ }).click();
    await expect(page.getByRole('group', { name: 'Cause' })).toBeVisible();
    await expect(page.getByRole('group', { name: 'Where it works' })).toBeVisible();
  });

  test('search: "Islamic" returns results', async ({ page }) => {
    await openBrowse(page);
    await page.locator(SEARCH).fill('Islamic');
    await expect.poll(async () => page.locator(CHARITY_LINK).count()).toBeGreaterThan(0);
  });

  test('search: a nonsense query shows no matches', async ({ page }) => {
    await openBrowse(page);
    await page.locator(SEARCH).fill('xyznonexistent');
    await expect(page.getByText('No charities match')).toBeVisible();
  });
});

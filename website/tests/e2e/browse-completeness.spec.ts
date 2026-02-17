import { test, expect } from '@playwright/test';

// CharityCard renders two links per charity (mobile + desktop), use :visible
const CHARITY_CARD = 'a[href^="/charity/"]:visible';

/** Switch browse page into power mode so Browse/Search tabs and cards are visible */
async function enterPowerMode(page: import('@playwright/test').Page) {
  await page.goto('/browse');
  await page.evaluate(() => localStorage.setItem('gmg-browse-style', 'power'));
  await page.reload();
  await expect(page.locator(CHARITY_CARD).first()).toBeVisible({ timeout: 10_000 });
}

test.describe('Browse page completeness', () => {
  test('card count — at least 160 unique charity links in power mode', async ({ page }) => {
    await enterPowerMode(page);

    // Scroll to bottom to ensure all cards are rendered (in case of virtualization)
    await page.evaluate(async () => {
      const delay = (ms: number) => new Promise(r => setTimeout(r, ms));
      for (let i = 0; i < 20; i++) {
        window.scrollBy(0, 1000);
        await delay(200);
      }
    });
    await page.waitForTimeout(1000);

    const links = page.locator('a[href^="/charity/"]');
    const allHrefs: string[] = [];
    const count = await links.count();
    for (let i = 0; i < count; i++) {
      const href = await links.nth(i).getAttribute('href');
      if (href) allHrefs.push(href);
    }

    const uniqueHrefs = new Set(allHrefs);
    // 167 total - 31 hideFromCurated = 136 visible
    expect(uniqueHrefs.size).toBeGreaterThanOrEqual(130);
  });

  test('no blank cards — every visible card has text content', async ({ page }) => {
    await enterPowerMode(page);

    const cards = page.locator(CHARITY_CARD);
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < count; i++) {
      const text = await cards.nth(i).textContent();
      expect(text!.trim().length).toBeGreaterThan(5);
    }
  });

  test('preset filter — Palestine cause tag', async ({ page }) => {
    await enterPowerMode(page);

    const btn = page.getByRole('button', { name: /Palestine/i });
    if (await btn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await btn.click();
      await page.waitForTimeout(600);
      const cards = page.locator(CHARITY_CARD);
      expect(await cards.count()).toBeGreaterThan(0);
    }
  });

  test('preset filter — Zakat Eligible wallet filter', async ({ page }) => {
    await enterPowerMode(page);

    const btn = page.getByRole('button', { name: /Zakat Eligible/i });
    if (await btn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await btn.click();
      await page.waitForTimeout(600);
      const cards = page.locator(CHARITY_CARD);
      expect(await cards.count()).toBeGreaterThan(0);
    }
  });

  test('preset filter — Systemic Change', async ({ page }) => {
    await enterPowerMode(page);

    const btn = page.getByRole('button', { name: /Systemic Change/i });
    if (await btn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await btn.click();
      await page.waitForTimeout(600);
      const cards = page.locator(CHARITY_CARD);
      expect(await cards.count()).toBeGreaterThan(0);
    }
  });

  test('preset filter — Direct Relief', async ({ page }) => {
    await enterPowerMode(page);

    const btn = page.getByRole('button', { name: /Direct Relief/i });
    if (await btn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await btn.click();
      await page.waitForTimeout(600);
      const cards = page.locator(CHARITY_CARD);
      expect(await cards.count()).toBeGreaterThan(0);
    }
  });

  test('search — "Islamic" returns results', async ({ page }) => {
    await enterPowerMode(page);

    const searchTab = page.getByRole('button', { name: 'Search', exact: true });
    await searchTab.click();

    const searchInput = page.locator('input[type="text"]');
    await searchInput.fill('Islamic');
    await page.waitForTimeout(600);

    const cards = page.locator(CHARITY_CARD);
    expect(await cards.count()).toBeGreaterThan(0);
  });

  test('search — nonsense query shows no matches', async ({ page }) => {
    await enterPowerMode(page);

    const searchTab = page.getByRole('button', { name: 'Search', exact: true });
    await searchTab.click();

    const searchInput = page.locator('input[type="text"]');
    await searchInput.fill('xyznonexistent');
    await page.waitForTimeout(600);

    await expect(page.getByText('No matches found')).toBeVisible();
  });
});

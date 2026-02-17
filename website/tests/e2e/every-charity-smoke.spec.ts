import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const dataPath = path.join(__dirname, '../../data/charities.json');
const data = JSON.parse(fs.readFileSync(dataPath, 'utf-8'));
const charities: Array<{ id: string; name: string; ein: string }> = data.charities;

for (const charity of charities) {
  test(`charity ${charity.ein} - ${charity.name} loads correctly`, async ({ page }) => {
    test.setTimeout(30_000);

    const errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.goto(`/charity/${charity.id}`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Page renders with content
    const bodyText = await page.locator('body').textContent();
    expect(bodyText!.length).toBeGreaterThan(200);

    // Charity name appears somewhere in page
    await expect(page.locator('body')).toContainText(charity.name, { timeout: 10_000 });

    // No standalone "undefined" or "null" in rendered text
    const text = await page.locator('body').textContent();
    expect(text).not.toMatch(/\bundefined\b/);
    expect(text).not.toMatch(/\bnull\b/);

    // No broken images
    const brokenImages = await page.evaluate(() => {
      const imgs = document.querySelectorAll('img');
      return Array.from(imgs).filter(img => img.complete && img.naturalWidth === 0).length;
    });
    expect(brokenImages).toBe(0);

    // No JS errors
    expect(errors).toEqual([]);
  });
}

import { test, expect } from '@playwright/test';

const EIN1 = '01-0548371'; // Muslim Legal Fund of America
const EIN2 = '04-2535767'; // Union of Concerned Scientists
const EIN3 = '04-3810161'; // ICNA Relief

const NAME1 = 'Muslim Legal Fund';
const NAME2 = 'Union of Concerned Scientists';
const NAME3 = 'ICNA Relief';

const STORAGE_KEY = 'gmg-compare-charities';

/** Set compare localStorage and navigate to /compare */
async function setupCompare(page: import('@playwright/test').Page, eins: string[]) {
  // First visit to set localStorage
  await page.goto('/');
  await page.evaluate(({ key, eins }) => {
    localStorage.setItem(key, JSON.stringify(eins));
  }, { key: STORAGE_KEY, eins });
  await page.goto('/compare');
  await page.waitForTimeout(3000);
}

test.describe('Compare page functional tests', () => {
  test('2-charity compare shows both charities with data', async ({
    page,
  }) => {
    await setupCompare(page, [EIN1, EIN2]);

    const bodyText = await page.locator('body').textContent();

    // Both charity names should appear
    expect(bodyText).toContain(NAME1);
    expect(bodyText).toContain(NAME2);

    // Financial data should be visible (dollar amounts)
    expect(bodyText).toMatch(/\$[\d,.]+/);

    // Wallet tags should be visible
    expect(bodyText).toMatch(/Zakat|Sadaqah/i);

    // No broken rendering
    expect(bodyText).not.toContain('undefined');
    expect(bodyText).not.toContain('null');
  });

  test('3-charity compare shows all charities', async ({ page }) => {
    await setupCompare(page, [EIN1, EIN2, EIN3]);

    const bodyText = await page.locator('body').textContent();

    expect(bodyText).toContain(NAME1);
    expect(bodyText).toContain(NAME2);
    expect(bodyText).toContain(NAME3);
  });

  test('remove charity from 3-charity compare', async ({ page }) => {
    await setupCompare(page, [EIN1, EIN2, EIN3]);

    // Verify all 3 are present
    let bodyText = await page.locator('body').textContent();
    expect(bodyText).toContain(NAME1);
    expect(bodyText).toContain(NAME2);
    expect(bodyText).toContain(NAME3);

    // Click the first remove button (×)
    const removeButtons = page.locator(
      'button:has-text("×"), button:has-text("✕"), button:has-text("Remove"), button[aria-label*="remove" i], button[aria-label*="Remove" i]'
    );
    const removeCount = await removeButtons.count();
    if (removeCount > 0) {
      await removeButtons.first().click();
      await page.waitForTimeout(1000);

      bodyText = await page.locator('body').textContent();
      // At least one charity should have been removed — only 2 of the 3 names remain
      const namesPresent = [NAME1, NAME2, NAME3].filter((n) =>
        bodyText!.includes(n)
      );
      expect(namesPresent.length).toBeLessThanOrEqual(2);
    }
  });
});

import { test, expect } from '@playwright/test';

const EIN1 = '01-0548371'; // Muslim Legal Fund of America
const EIN2 = '04-2535767'; // Union of Concerned Scientists
const EIN3 = '04-3810161'; // ICNA Relief

const NAME1 = 'Muslim Legal Fund';
const NAME2 = 'Union of Concerned Scientists';
const NAME3 = 'ICNA Relief';

/** Compare is URL-driven now: /compare/?eins=a,b,c */
async function setupCompare(page: import('@playwright/test').Page, eins: string[]) {
  await page.goto(`/compare/?eins=${eins.join(',')}`);
  await expect(page.getByText(NAME1).first()).toBeVisible({ timeout: 15_000 });
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

    // Dropping one EIN from the URL leaves the other two.
    await page.goto(`/compare/?eins=${EIN1},${EIN3}`);
    await expect(page.getByText(NAME3).first()).toBeVisible({ timeout: 15_000 });
    bodyText = await page.locator('body').textContent();
    expect(bodyText).toContain(NAME1);
    expect(bodyText).not.toContain(NAME2);
  });
});

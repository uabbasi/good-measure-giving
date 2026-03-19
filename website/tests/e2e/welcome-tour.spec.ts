import { test, expect } from '@playwright/test';

test.describe('Welcome Tour', () => {
  test('shows welcome modal content when gmg:welcome event fires', async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() => {
      localStorage.removeItem('gmg_welcome_tour_shown');
    });

    await page.evaluate(() => {
      window.dispatchEvent(new CustomEvent('gmg:welcome'));
    });

    const modal = page.getByText('Welcome to Good Measure');
    await expect(modal).toBeVisible({ timeout: 3000 });

    await expect(page.getByText('Full evaluations unlocked')).toBeVisible();
    await expect(page.getByText('Set a zakat target')).toBeVisible();
    await expect(page.getByText('Organize with giving buckets')).toBeVisible();
    await expect(page.getByText('Save & compare charities')).toBeVisible();

    await expect(page.getByText('Start exploring')).toBeVisible();
    await expect(page.getByText('Set up giving plan →')).toBeVisible();
  });

  test('dismisses and does not show again', async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() => {
      localStorage.removeItem('gmg_welcome_tour_shown');
    });

    await page.evaluate(() => {
      window.dispatchEvent(new CustomEvent('gmg:welcome'));
    });

    await page.getByText('Start exploring').click();

    await expect(page.getByText('Welcome to Good Measure')).not.toBeVisible();

    await page.evaluate(() => {
      window.dispatchEvent(new CustomEvent('gmg:welcome'));
    });
    await expect(page.getByText('Welcome to Good Measure')).not.toBeVisible();
  });
});

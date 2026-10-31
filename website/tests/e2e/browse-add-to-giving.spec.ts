import { test, expect } from '@playwright/test';

// Saving a charity to the plan lives on the charity page now ("Add to Plan").
test.describe('Add to Plan button', () => {
  test('signed-out visitors get a sign-in hint instead of a crash', async ({ page }) => {
    await page.goto('/charity/95-4453134/');
    await expect(page.locator('h1').first()).toBeVisible({ timeout: 15_000 });

    const button = page.getByRole('button', { name: /Add to Giving Plan/i });
    await expect(button).toBeVisible();
    await button.click();
    await expect(page.getByText(/Sign in to save charities/i)).toBeVisible();
    await expect(page).toHaveURL(/\/charity\/95-4453134/);
  });
});

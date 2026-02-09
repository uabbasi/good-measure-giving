import { test, expect } from '@playwright/test';

test.describe('Profile / auth gate', () => {
  test('profile page shows auth gate for unauthenticated users', async ({ page }) => {
    await page.goto('/profile');
    // Should show login/auth gate content since we're not authenticated
    const body = await page.locator('body').textContent();
    expect(body!.length).toBeGreaterThan(50);
    // Should mention joining or signing in
    const hasAuthContent = /join|sign in|community|member/i.test(body!);
    expect(hasAuthContent).toBe(true);
  });
});

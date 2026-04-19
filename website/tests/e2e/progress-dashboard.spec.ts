/**
 * Progress Dashboard (M3) — smoke test that the /profile route still compiles
 * and the existing auth gate blocks unauthenticated users without regression.
 * No signed-in fixture is available in this repo, so we only assert the
 * gate path; the dashboard itself is unit-tested in ProgressDashboard.test.tsx.
 */
import { test, expect } from '@playwright/test';

test.describe('Progress Dashboard / auth gate (M3)', () => {
  test('profile page still serves the auth gate for unauthenticated users', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('pageerror', (err) => consoleErrors.push(err.message));

    const response = await page.goto('/profile');
    expect(response).not.toBeNull();
    // Vite serves index.html for all routes; response should be 200.
    expect(response!.status()).toBeLessThan(400);

    const body = await page.locator('body').textContent();
    expect(body!.length).toBeGreaterThan(50);

    // Unauthenticated visitors see the sign-in invitation, not the dashboard.
    const hasAuthContent = /join|sign in|community|member/i.test(body!);
    expect(hasAuthContent).toBe(true);

    // The dashboard should never render for unauthenticated visitors.
    await expect(page.getByTestId('progress-dashboard')).toHaveCount(0);
    await expect(page.getByTestId('progress-dashboard-empty')).toHaveCount(0);

    // No uncaught errors from the new component wiring.
    expect(consoleErrors).toEqual([]);
  });
});

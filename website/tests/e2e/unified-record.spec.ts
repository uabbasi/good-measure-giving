import { test, expect } from '@playwright/test';

/**
 * M4 e2e smoke: confirm the /profile route still compiles + serves an auth
 * gate for anonymous users after the UnifiedAllocationView rewrite. We don't
 * exercise the signed-in flow here (no auth fixtures in this repo); that's
 * covered by the unit tests in UnifiedAllocationView.test.tsx.
 */
test.describe('Unified Record / profile route', () => {
  test('profile route serves auth gate without runtime errors', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('pageerror', e => consoleErrors.push(e.message));
    page.on('console', msg => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    await page.goto('/profile');

    const body = await page.locator('body').textContent();
    expect(body!.length).toBeGreaterThan(50);
    // Same auth-gate content assertion as wizard.spec.ts.
    expect(/join|sign in|community|member/i.test(body!)).toBe(true);

    // No runtime errors from the rewrite.
    expect(consoleErrors).toEqual([]);
  });
});

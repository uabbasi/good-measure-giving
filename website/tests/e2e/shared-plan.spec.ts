import { test, expect } from '@playwright/test';

// Revoked/old/nonexistent token → bounced home. Self-contained: a missing plan
// or token mismatch redirects to `/`, so this needs no auth or seeding.
test('stale invite token redirects home', async ({ page }) => {
  await page.goto('/plan/join/nonexistent/badtoken');
  await expect(page).toHaveURL(/\/$/);
});

// Public preview must render without authentication and without exposing money.
// Seeding a real plan needs an authed create flow, so this is gated behind
// E2E_PLAN_ID/E2E_PLAN_TOKEN and skips when they are absent.
test('join page shows a read-only money-free preview', async ({ page }) => {
  const PLAN_ID = process.env.E2E_PLAN_ID;
  const TOKEN = process.env.E2E_PLAN_TOKEN;
  test.skip(!PLAN_ID || !TOKEN, 'no seeded plan; set E2E_PLAN_ID/E2E_PLAN_TOKEN');

  await page.goto(`/plan/join/${PLAN_ID}/${TOKEN}`);
  await expect(page.getByText('planning their giving', { exact: false })).toBeVisible();
  // Money must never appear in the preview.
  await expect(page.locator('body')).not.toContainText('$');
  await expect(page.getByRole('button', { name: /join your family|sign in to join/i })).toBeVisible();
});

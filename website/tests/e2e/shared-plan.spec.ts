import { test, expect } from '@playwright/test';

// Revoked/old/nonexistent token → a clear "not valid" page with a way forward (it used to
// bounce silently to the homepage, which read as a broken app). Self-contained: a missing plan
// or token mismatch needs no auth or seeding.
test('stale invite token explains the link is not valid', async ({ page }) => {
  await page.goto('/plan/join/nonexistent/badtoken');
  await expect(page.getByRole('heading', { name: /invite link isn't valid/i })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole('link', { name: /browse charities/i })).toBeVisible();
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

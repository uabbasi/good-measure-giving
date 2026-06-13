import { test, expect, type Page, type BrowserContext, type ConsoleMessage } from '@playwright/test';

/**
 * Full shared-plan flow against the Firebase Emulator Suite.
 *
 * Run with: `npm run test:e2e:shared` (wraps this in `firebase emulators:exec`
 * so auth :9099 + firestore :8080 are live with the real firestore.rules).
 *
 * Drives two real test users through Chrome:
 *   User A signs up → creates a shared plan → adds a charity → gets the invite link.
 *   User B signs up → opens the invite link → sees the money-free preview → joins.
 * Asserts zero console errors / page errors throughout.
 */

// Benign console noise to ignore (optional assets, dev-only warnings).
const IGNORED = [
  /favicon/i,
  /\.woff2?/i,
  /sourcemap/i,
  /Download the React DevTools/i,
  /\[vite\]/i,
];

function attachConsoleGuard(page: Page, sink: string[]) {
  page.on('console', (msg: ConsoleMessage) => {
    if (msg.type() !== 'error') return;
    const text = msg.text();
    if (IGNORED.some((re) => re.test(text))) return;
    sink.push(`console.error: ${text}`);
  });
  page.on('pageerror', (err) => sink.push(`pageerror: ${err.message}`));
}

async function newUserContext(browser: import('@playwright/test').Browser, errors: string[]) {
  const context: BrowserContext = await browser.newContext();
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await context.addInitScript(() => {
    // Force the clipboard share path (no native share sheet in automation).
    // @ts-expect-error remove navigator.share so the panel copies the link instead
    delete navigator.share;
    // Suppress all first-visit onboarding so overlays don't intercept clicks.
    try {
      localStorage.setItem('gmg_intro_seen_v1', '1');
      localStorage.setItem('gmg_welcome_tour_shown', 'true');
      localStorage.setItem('gmg-nux-browse-tip', '1');
      localStorage.setItem('gmg-nux-details-tip', '1');
      localStorage.setItem('gmg-nux-giving-plan-tip', '1');
      localStorage.setItem('beta-banner-dismissed', '1');
    } catch {
      /* storage unavailable */
    }
  });
  const page = await context.newPage();
  attachConsoleGuard(page, errors);
  return { context, page };
}

async function signIn(page: Page, email: string) {
  await page.goto('/');
  await page.waitForFunction(() => !!(window as unknown as { __TEST_AUTH__?: unknown }).__TEST_AUTH__, null, {
    timeout: 30_000,
  });
  await page.evaluate(async (e) => {
    await (window as unknown as { __TEST_AUTH__: { signUp(a: string, b: string): Promise<void> } }).__TEST_AUTH__.signUp(
      e,
      'test-password-123',
    );
  }, email);
}

test('two family members: create plan → invite → preview → join', async ({ browser }) => {
  const errors: string[] = [];
  const stamp = Date.now();

  // ── User A: create a shared plan, add a charity, grab the invite link ──
  const a = await newUserContext(browser, errors);
  await signIn(a.page, `owner-${stamp}@test.local`);

  await a.page.goto('/profile');
  const createBtn = a.page.getByRole('button', { name: '+ Shared plan' });
  await expect(createBtn).toBeVisible({ timeout: 30_000 });

  a.page.once('dialog', (d) => d.accept('Test Family')); // window.prompt for the name
  await createBtn.click();

  // The shared plan view renders with the chosen name (heading, not the switcher pill).
  await expect(a.page.getByRole('heading', { name: 'Test Family' })).toBeVisible({ timeout: 20_000 });

  // Add a charity via the inline search.
  const search = a.page.getByPlaceholder('Add a charity — search by name');
  await expect(search).toBeVisible();
  await search.fill('Islamic');
  // Click the first result button (charity name).
  const firstResult = a.page.locator('button', { hasText: /Islamic/i }).first();
  await expect(firstResult).toBeVisible({ timeout: 15_000 });
  await firstResult.click();

  // Grab the invite link (Invite family → clipboard, since we removed navigator.share).
  await a.page.getByRole('button', { name: 'Invite family' }).click();
  await expect(a.page.getByRole('button', { name: 'Link copied' })).toBeVisible({ timeout: 10_000 });
  const inviteLink = await a.page.evaluate(() => navigator.clipboard.readText());
  expect(inviteLink).toContain('/plan/join/');

  // ── User B: open the invite, see the money-free preview, join ──
  const b = await newUserContext(browser, errors);
  await signIn(b.page, `member-${stamp}@test.local`);

  const joinPath = new URL(inviteLink).pathname; // strip origin; baseURL handles it
  await b.page.goto(joinPath);
  await expect(b.page.getByText(/planning their giving/i)).toBeVisible({ timeout: 20_000 });
  // Money-free preview: no dollar signs anywhere on the page.
  await expect(b.page.locator('body')).not.toContainText('$');

  await b.page.getByRole('button', { name: /join your family/i }).click();
  await expect(b.page).toHaveURL(/\/profile/, { timeout: 20_000 });

  // ── No console errors across either user ──
  expect(errors, `Console/page errors:\n${errors.join('\n')}`).toEqual([]);

  await a.context.close();
  await b.context.close();
});

import type { Page, BrowserContext, ConsoleMessage, Browser } from '@playwright/test';

/**
 * Shared helpers for the Firebase-emulator-backed shared-plan e2e specs
 * (shared-plan-emulator.spec.ts, shared-plan-concurrency.spec.ts). Kept in one
 * place so a UI change (e.g. the plan-creation dialog → inline-input switch)
 * only needs fixing once instead of drifting between spec files.
 */

// Benign console noise to ignore (optional assets, dev-only warnings).
export const IGNORED = [
  /favicon/i,
  /\.woff2?/i,
  /sourcemap/i,
  /Download the React DevTools/i,
  /\[vite\]/i,
  // Transient Firestore emulator cold-start warning: a transaction can race the
  // emulator connection on the very first write and log a "Could not reach
  // backend / Connection failed N times" that the client immediately recovers
  // from (the writes succeed — asserted by the functional steps below). Benign
  // infrastructure noise, not an app error.
  /Could not reach Cloud Firestore backend/i,
  /Connection failed \d+ times/i,
  // The RUM beacon (static.cloudflareinsights.com) has no network egress in a
  // sandboxed dev environment and always fails with this exact message — but
  // ConsoleMessage.text() for a browser-native resource-load failure never
  // includes the failing URL, only this generic string, so that's what we
  // can match on. The page always continues fine without the beacon; real
  // environments either load it successfully (no error) or don't reach this
  // branch at all.
  /Failed to load resource: net::ERR_CONNECTION_REFUSED/i,
  // Two members' transactions genuinely racing the same plan doc: the losing
  // attempt's commit gets a FAILED_PRECONDITION (stale base version) and the
  // Firestore client SDK automatically retries with a fresh read — expected,
  // successful behavior, not a bug — but Chrome still logs the losing
  // attempt's non-2xx response as a generic console error.
  /Failed to load resource: the server responded with a status of 400/i,
];

export function attachConsoleGuard(page: Page, sink: string[]) {
  page.on('console', (msg: ConsoleMessage) => {
    if (msg.type() !== 'error') return;
    const text = msg.text();
    if (IGNORED.some((re) => re.test(text))) return;
    sink.push(`console.error: ${text}`);
  });
  page.on('pageerror', (err) => sink.push(`pageerror: ${err.message}`));
}

export async function newUserContext(browser: Browser, errors: string[]) {
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

export async function signIn(page: Page, email: string) {
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

/** Create a shared plan via the "+ Shared plan" inline-input UI and land on its view. */
export async function createSharedPlan(page: Page, name: string) {
  await page.goto('/profile');
  const createBtn = page.getByRole('button', { name: '+ Shared plan' });
  await createBtn.waitFor({ state: 'visible', timeout: 30_000 });
  await createBtn.click();
  await page.getByLabel('New shared plan name').fill(name);
  await page.getByRole('button', { name: 'Create' }).click();
  await page.getByRole('heading', { name }).waitFor({ state: 'visible', timeout: 20_000 });
}

/** Invite family → clipboard link (navigator.share removed by newUserContext's initScript). */
export async function grabInviteLink(page: Page): Promise<string> {
  await page.getByRole('button', { name: 'Invite family' }).click();
  await page.getByRole('button', { name: 'Link copied' }).waitFor({ state: 'visible', timeout: 10_000 });
  return page.evaluate(() => navigator.clipboard.readText());
}

/** Join a plan via its invite link and land on /profile. */
export async function joinSharedPlan(page: Page, inviteLink: string) {
  const joinPath = new URL(inviteLink).pathname; // strip origin; baseURL handles it
  await page.goto(joinPath);
  await page.getByRole('button', { name: /join your family/i }).click();
  await page.waitForURL(/\/profile/, { timeout: 20_000 });
}

/** Select an already-created shared plan from the PlanSwitcher pill bar on /profile. */
export async function selectSharedPlan(page: Page, name: string) {
  await page.goto('/profile');
  await page.getByRole('button', { name, exact: true }).click();
  await page.getByRole('heading', { name }).waitFor({ state: 'visible', timeout: 20_000 });
}

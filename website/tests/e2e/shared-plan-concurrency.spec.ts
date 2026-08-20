import { test, expect } from '@playwright/test';
import {
  newUserContext, signIn, createSharedPlan, grabInviteLink, joinSharedPlan, selectSharedPlan,
} from './helpers/sharedPlanTestUtils';

/**
 * Two REAL members editing the SAME shared plan at the same instant, against
 * the real Firebase Emulator (not mocked) — the actual scenario "Family Giving
 * Night" is built for. Each test fires both members' actions via Promise.all
 * so the two writes race for real inside Firestore's transaction retry, not
 * just in a unit test of the pure merge function.
 *
 * Run with: `npm run test:e2e:shared` (same emulator harness as
 * shared-plan-emulator.spec.ts).
 */

async function setUpTwoMemberPlan(browser: import('@playwright/test').Browser, errors: string[], planName: string) {
  const a = await newUserContext(browser, errors);
  await signIn(a.page, `owner-${planName}-${Date.now()}@test.local`);
  await createSharedPlan(a.page, planName);
  const inviteLink = await grabInviteLink(a.page);

  const b = await newUserContext(browser, errors);
  await signIn(b.page, `member-${planName}-${Date.now()}@test.local`);
  await joinSharedPlan(b.page, inviteLink);
  await selectSharedPlan(b.page, planName);

  return { a, b, planName };
}

const searchAdd = (page: import('@playwright/test').Page) => page.getByPlaceholder('Add a charity — search by name');

test('two members adding the SAME charity at the same instant lands as one item, not two', async ({ browser }) => {
  const errors: string[] = [];
  const { a, b, planName } = await setUpTwoMemberPlan(browser, errors, `Race-Same-${Date.now()}`);

  await searchAdd(a.page).fill('Islamic');
  await searchAdd(b.page).fill('Islamic');
  const aResult = a.page.locator('button', { hasText: /Islamic/i }).first();
  const bResult = b.page.locator('button', { hasText: /Islamic/i }).first();
  await expect(aResult).toBeVisible({ timeout: 15_000 });
  await expect(bResult).toBeVisible({ timeout: 15_000 });
  const name = (await aResult.innerText()).split('\n')[0];
  expect((await bResult.innerText()).split('\n')[0]).toBe(name); // same charity, same result

  // Fire both adds for real at the same time — Firestore's transaction retry
  // (re-read + rebuild via addCharityItem's ref dedup) must converge to one item.
  await Promise.all([aResult.click(), bResult.click()]);

  // Both clients must settle on exactly one item — reload to force a fresh
  // read rather than relying on either client's own cache.
  // A full reload drops the SPA's in-memory "which plan is selected" state
  // back to the personal plan (a separate, unrouted-state gap — not what this
  // test targets) — re-select the shared plan instead to force a fresh fetch.
  await selectSharedPlan(a.page, planName);
  await expect(a.page.getByRole('button', { name: `Remove ${name}`, exact: true })).toHaveCount(1, { timeout: 15_000 });
  await selectSharedPlan(b.page, planName);
  await expect(b.page.getByRole('button', { name: `Remove ${name}`, exact: true })).toHaveCount(1, { timeout: 15_000 });

  expect(errors, `Console/page errors:\n${errors.join('\n')}`).toEqual([]);
  await a.context.close();
  await b.context.close();
});

test('two members adding DIFFERENT charities at the same instant: neither write is lost', async ({ browser }) => {
  const errors: string[] = [];
  const { a, b, planName } = await setUpTwoMemberPlan(browser, errors, `Race-Diff-${Date.now()}`);

  await searchAdd(a.page).fill('Islamic');
  await searchAdd(b.page).fill('Islamic');
  const aResult = a.page.locator('button', { hasText: /Islamic/i }).first();
  const bResult = b.page.locator('button', { hasText: /Islamic/i }).nth(1); // deliberately a different charity
  await expect(aResult).toBeVisible({ timeout: 15_000 });
  await expect(bResult).toBeVisible({ timeout: 15_000 });
  const aName = (await aResult.innerText()).split('\n')[0];
  const bName = (await bResult.innerText()).split('\n')[0];
  expect(aName).not.toBe(bName);

  await Promise.all([aResult.click(), bResult.click()]);

  // Don't navigate away immediately: a genuine collision here makes A's write
  // land via Firestore's OWN transaction retry (its first attempt aborts on a
  // stale precondition once B's commit wins the race; the client SDK re-reads
  // and retries automatically) — navigating before that retry's request lands
  // would cancel it mid-flight, which is a test artifact, not a product bug.
  // Wait for both adds to settle on A's own page first (A's own mutation's
  // onSettled invalidation re-fetches the whole doc, so B's item shows too).
  await expect(a.page.getByRole('button', { name: `Remove ${aName}`, exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(a.page.getByRole('button', { name: `Remove ${bName}`, exact: true })).toBeVisible({ timeout: 15_000 });

  // Confirm via a fresh fetch on both clients too.
  await selectSharedPlan(a.page, planName);
  await expect(a.page.getByRole('button', { name: `Remove ${aName}`, exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(a.page.getByRole('button', { name: `Remove ${bName}`, exact: true })).toBeVisible({ timeout: 15_000 });
  await selectSharedPlan(b.page, planName);
  await expect(b.page.getByRole('button', { name: `Remove ${aName}`, exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(b.page.getByRole('button', { name: `Remove ${bName}`, exact: true })).toBeVisible({ timeout: 15_000 });

  expect(errors, `Console/page errors:\n${errors.join('\n')}`).toEqual([]);
  await a.context.close();
  await b.context.close();
});

test('member A edits weight while member B removes the same item: it stays removed, never resurrects', async ({
  browser,
}) => {
  const errors: string[] = [];
  const { a, b, planName } = await setUpTwoMemberPlan(browser, errors, `Race-EditRemove-${Date.now()}`);

  // A adds the only item.
  await searchAdd(a.page).fill('Islamic');
  const result = a.page.locator('button', { hasText: /Islamic/i }).first();
  await expect(result).toBeVisible({ timeout: 15_000 });
  const name = (await result.innerText()).split('\n')[0];
  await result.click();
  await expect(a.page.getByRole('button', { name: `Remove ${name}`, exact: true })).toBeVisible({ timeout: 15_000 });

  // B never triggers a manual refetch — this wait proves the polling freshness
  // fix (staleTime/refetchInterval on useSharedPlan's query) actually delivers
  // A's add to B's already-open page, not just a hard reload.
  await expect(b.page.getByRole('button', { name: `Remove ${name}`, exact: true })).toBeVisible({ timeout: 10_000 });

  // Now race an edit (A) against a removal (B) of the SAME item. Whichever
  // transaction commits first, the outcome must be the same: the item ends up
  // removed. If applyItemLWW ever resurrects on a missing id, A's edit would
  // re-insert a stale copy after B's removal lands.
  const weightInput = a.page.getByLabel(`Weight for ${name}`);
  await Promise.all([
    weightInput.fill('42'),
    b.page.getByRole('button', { name: `Remove ${name}`, exact: true }).click(),
  ]);

  await selectSharedPlan(a.page, planName);
  await expect(a.page.getByRole('button', { name: `Remove ${name}`, exact: true })).toHaveCount(0, { timeout: 15_000 });
  await expect(a.page.getByText(/no charities yet/i)).toBeVisible({ timeout: 15_000 });
  await selectSharedPlan(b.page, planName);
  await expect(b.page.getByRole('button', { name: `Remove ${name}`, exact: true })).toHaveCount(0, { timeout: 15_000 });
  await expect(b.page.getByText(/no charities yet/i)).toBeVisible({ timeout: 15_000 });

  expect(errors, `Console/page errors:\n${errors.join('\n')}`).toEqual([]);
  await a.context.close();
  await b.context.close();
});

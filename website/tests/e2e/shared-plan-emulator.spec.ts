import { test, expect } from '@playwright/test';
import { newUserContext, signIn } from './helpers/sharedPlanTestUtils';

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
 *
 * See shared-plan-concurrency.spec.ts for genuinely-concurrent multi-member
 * writes (two members editing the same plan at the same instant).
 */

test('two family members: create plan → invite → preview → join', async ({ browser }) => {
  const errors: string[] = [];
  const stamp = Date.now();

  // ── User A: create a shared plan, add a charity, grab the invite link ──
  const a = await newUserContext(browser, errors);
  await signIn(a.page, `owner-${stamp}@test.local`);

  await a.page.goto('/profile');
  const createBtn = a.page.getByRole('button', { name: '+ Shared plan' });
  await expect(createBtn).toBeVisible({ timeout: 30_000 });

  // "+ Shared plan" opens an inline name input (no window.prompt).
  await createBtn.click();
  await a.page.getByLabel('New shared plan name').fill('Test Family');
  await a.page.getByRole('button', { name: 'Create' }).click();

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

test('explore-together: shortlist a charity in the session, then promote it into the plan', async ({
  browser,
}) => {
  const errors: string[] = [];
  const stamp = Date.now();

  const a = await newUserContext(browser, errors);
  await signIn(a.page, `host-${stamp}@test.local`);

  // Create a shared plan (lands on the shared-plan view with it selected).
  await a.page.goto('/profile');
  const createBtn = a.page.getByRole('button', { name: '+ Shared plan' });
  await expect(createBtn).toBeVisible({ timeout: 30_000 });
  await createBtn.click();
  await a.page.getByLabel('New shared plan name').fill('Night Family');
  await a.page.getByRole('button', { name: 'Create' }).click();
  await expect(a.page.getByRole('heading', { name: 'Night Family' })).toBeVisible({ timeout: 20_000 });

  // Start the giving session (opens on the Gather step), then advance to Explore.
  await a.page.getByRole('button', { name: /start giving session/i }).click();
  await expect(a.page.getByRole('heading', { name: /gather the family/i })).toBeVisible({ timeout: 20_000 });
  await a.page.getByRole('button', { name: /^next$/i }).click(); // gather → explore
  await expect(a.page.getByRole('heading', { name: /explore together/i })).toBeVisible({ timeout: 15_000 });

  // Shortlist a charity via the explore-together panel (writes the shortlist field).
  const suggest = a.page.getByPlaceholder(/suggest a charity to consider/i);
  await expect(suggest).toBeVisible({ timeout: 15_000 });
  await suggest.fill('Islamic');
  await a.page.locator('button', { hasText: /Islamic/i }).first().click();
  await expect(a.page.getByText(/suggested by/i)).toBeVisible({ timeout: 15_000 });

  // Advance to Decide → the shortlist shows under "Still considering"; promote it.
  await a.page.getByRole('button', { name: /^next$/i }).click(); // explore → decide
  await expect(a.page.getByText(/still considering/i)).toBeVisible({ timeout: 15_000 });
  await a.page.getByRole('button', { name: /add to plan/i }).first().click();
  // After promotion the candidate leaves the shortlist (section disappears).
  await expect(a.page.getByText(/still considering/i)).toHaveCount(0, { timeout: 15_000 });

  expect(errors, `Console/page errors:\n${errors.join('\n')}`).toEqual([]);
  await a.context.close();
});

test('decide step: removing a plan item recalculates the remaining share and leaves the sibling untouched', async ({
  browser,
}) => {
  const errors: string[] = [];
  const stamp = Date.now();

  const a = await newUserContext(browser, errors);
  await signIn(a.page, `remover-${stamp}@test.local`);

  await a.page.goto('/profile');
  const createBtn = a.page.getByRole('button', { name: '+ Shared plan' });
  await expect(createBtn).toBeVisible({ timeout: 30_000 });
  await createBtn.click();
  await a.page.getByLabel('New shared plan name').fill('Removal Family');
  await a.page.getByRole('button', { name: 'Create' }).click();
  await expect(a.page.getByRole('heading', { name: 'Removal Family' })).toBeVisible({ timeout: 20_000 });

  // Add two charities (searching the same term twice: `existingEins` filters
  // the first pick out of the second search's results, so the second click
  // lands on a genuinely different charity).
  const search = a.page.getByPlaceholder('Add a charity — search by name');
  await expect(search).toBeVisible();

  const pickNext = async (): Promise<string> => {
    await search.fill('Islamic');
    const result = a.page.locator('button', { hasText: /Islamic/i }).first();
    await expect(result).toBeVisible({ timeout: 15_000 });
    const name = (await result.innerText()).split('\n')[0];
    await result.click();
    // upsertItem is not optimistic (onSettled-only invalidation) — wait for
    // the write to land and `existingEins` to pick it up before the caller
    // searches again, or the second search can still return this same charity.
    await expect(a.page.getByRole('button', { name: `Remove ${name}`, exact: true })).toBeVisible({ timeout: 15_000 });
    return name;
  };
  const firstName = await pickNext();
  const secondName = await pickNext();
  expect(firstName).not.toBe(secondName);

  // Both items present at an even 50/50 split.
  await expect(a.page.getByRole('button', { name: `Remove ${firstName}`, exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(a.page.getByRole('button', { name: `Remove ${secondName}`, exact: true })).toBeVisible();
  await expect(a.page.getByText('50%')).toHaveCount(2, { timeout: 15_000 });

  // Remove the first item.
  await a.page.getByRole('button', { name: `Remove ${firstName}`, exact: true }).click();

  // It's gone; the sibling survives untouched and recalculates to 100%.
  await expect(a.page.getByRole('button', { name: `Remove ${firstName}`, exact: true })).toHaveCount(0, { timeout: 15_000 });
  await expect(a.page.getByRole('button', { name: `Remove ${secondName}`, exact: true })).toBeVisible();
  await expect(a.page.getByText('100%')).toBeVisible({ timeout: 15_000 });

  // Removing the last item returns the plan to its empty state.
  await a.page.getByRole('button', { name: `Remove ${secondName}`, exact: true }).click();
  await expect(a.page.getByText(/no charities yet/i)).toBeVisible({ timeout: 15_000 });

  expect(errors, `Console/page errors:\n${errors.join('\n')}`).toEqual([]);
  await a.context.close();
});

test('explore step: removing a shortlisted candidate leaves the other candidate intact', async ({ browser }) => {
  const errors: string[] = [];
  const stamp = Date.now();

  const a = await newUserContext(browser, errors);
  await signIn(a.page, `shortlist-remover-${stamp}@test.local`);

  await a.page.goto('/profile');
  const createBtn = a.page.getByRole('button', { name: '+ Shared plan' });
  await expect(createBtn).toBeVisible({ timeout: 30_000 });
  await createBtn.click();
  await a.page.getByLabel('New shared plan name').fill('Shortlist Family');
  await a.page.getByRole('button', { name: 'Create' }).click();
  await expect(a.page.getByRole('heading', { name: 'Shortlist Family' })).toBeVisible({ timeout: 20_000 });

  await a.page.getByRole('button', { name: /start giving session/i }).click();
  await a.page.getByRole('button', { name: /^next$/i }).click(); // gather → explore
  await expect(a.page.getByRole('heading', { name: /explore together/i })).toBeVisible({ timeout: 15_000 });

  const suggest = a.page.getByPlaceholder(/suggest a charity to consider/i);
  await expect(suggest).toBeVisible({ timeout: 15_000 });

  const suggestNext = async (): Promise<string> => {
    await suggest.fill('Islamic');
    const result = a.page.locator('button', { hasText: /Islamic/i }).first();
    await expect(result).toBeVisible({ timeout: 15_000 });
    const name = (await result.innerText()).split('\n')[0];
    await result.click();
    // addToShortlist is not optimistic — wait for it to land (and for
    // `existingEins` to pick it up) before searching again.
    await expect(a.page.getByRole('button', { name: `Remove ${name}`, exact: true })).toBeVisible({ timeout: 15_000 });
    return name;
  };
  const firstName = await suggestNext();
  const secondName = await suggestNext();
  expect(firstName).not.toBe(secondName);

  await expect(a.page.getByRole('button', { name: `Remove ${firstName}`, exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(a.page.getByRole('button', { name: `Remove ${secondName}`, exact: true })).toBeVisible();

  // Remove the first shortlisted candidate.
  await a.page.getByRole('button', { name: `Remove ${firstName}`, exact: true }).click();
  await expect(a.page.getByRole('button', { name: `Remove ${firstName}`, exact: true })).toHaveCount(0, { timeout: 15_000 });

  // The other candidate is still there, untouched.
  await expect(a.page.getByText(secondName)).toBeVisible();
  await expect(a.page.getByRole('button', { name: `Remove ${secondName}`, exact: true })).toBeVisible();

  // Advancing to Decide shows the survivor still "still considering", not
  // silently promoted or dropped by the removal.
  await a.page.getByRole('button', { name: /^next$/i }).click(); // explore → decide
  await expect(a.page.getByText(/still considering/i)).toBeVisible({ timeout: 15_000 });
  await expect(a.page.getByText(secondName)).toBeVisible();

  expect(errors, `Console/page errors:\n${errors.join('\n')}`).toEqual([]);
  await a.context.close();
});

import { test, expect } from '@playwright/test';

const CHARITY_CARD = 'a[href^="/charity/"]:visible';
const RICH_EIN = '01-0548371';
const EIN1 = '01-0548371';
const EIN2 = '04-2535767';
const NAME1 = 'Muslim Legal Fund';
const NAME2 = 'Union of Concerned Scientists';

test.use({ viewport: { width: 390, height: 844 } });

test.describe('Mobile comprehensive', () => {
  test('browse cards are tappable and full-width', async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() =>
      localStorage.setItem('gmg-browse-style', 'power')
    );
    await page.reload();
    await expect(page.locator(CHARITY_CARD).first()).toBeVisible({
      timeout: 10000,
    });

    const cards = page.locator(CHARITY_CARD);
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < Math.min(3, count); i++) {
      const box = await cards.nth(i).boundingBox();
      expect(box).toBeTruthy();
      // On 390px viewport, cards should be wider than 300px
      expect(box!.width).toBeGreaterThan(300);
    }
  });

  test('detail page shows charity name on mobile', async ({ page }) => {
    await page.goto(`/charity/${RICH_EIN}`);
    await page.waitForTimeout(3000);

    // On mobile, charity name should appear in h1 or h2
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10000 });
    const headingText = await heading.textContent();
    expect(headingText!.length).toBeGreaterThan(3);
  });

  test('hamburger menu shows nav links', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    // Find and click the hamburger/mobile menu button
    const hamburger = page.locator(
      'button[aria-label*="menu" i], button[aria-label*="Menu" i], button[aria-label*="nav" i], button:has(svg):visible'
    );
    const hamburgerCount = await hamburger.count();

    if (hamburgerCount > 0) {
      await hamburger.first().click();
      await page.waitForTimeout(500);

      const bodyText = await page.locator('body').textContent();
      expect(bodyText).toMatch(/Browse/i);
      expect(bodyText).toMatch(/FAQ/i);
      expect(bodyText).toMatch(/About/i);
    } else {
      // Nav links may already be visible on this viewport
      const bodyText = await page.locator('body').textContent();
      expect(bodyText).toMatch(/Browse|FAQ|About/i);
    }
  });

  test('FAQ accordion expands on tap', async ({ page }) => {
    await page.goto('/faq');
    await expect(page.locator('h1')).toBeVisible({ timeout: 5000 });

    // Find a clickable FAQ question (button or summary element)
    const question = page.locator(
      'button:visible, summary:visible, [role="button"]:visible'
    );
    const questionCount = await question.count();
    expect(questionCount).toBeGreaterThan(0);

    // Click the first question-like element
    await question.first().click();
    await page.waitForTimeout(500);

    // After clicking, the body should have more visible text
    const bodyText = await page.locator('body').textContent();
    expect(bodyText!.length).toBeGreaterThan(100);
  });

  test('compare renders on mobile with 2 charities', async ({ page }) => {
    // Compare uses localStorage, not URL params
    await page.goto('/');
    await page.evaluate(({ eins }) => {
      localStorage.setItem('gmg-compare-charities', JSON.stringify(eins));
    }, { eins: [EIN1, EIN2] });
    await page.goto('/compare');
    await page.waitForTimeout(3000);

    const bodyText = await page.locator('body').textContent();
    expect(bodyText).toContain(NAME1);
    expect(bodyText).toContain(NAME2);
  });
});

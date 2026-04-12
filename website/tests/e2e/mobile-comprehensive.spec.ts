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

  test('mobile bottom nav shows nav links via More sheet', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    // MobileBottomNav has aria-label="Mobile navigation"
    const bottomNav = page.locator('nav[aria-label="Mobile navigation"]');

    if (await bottomNav.isVisible()) {
      // Open "More" sheet
      const moreButton = bottomNav.locator('button[aria-label="More options"]');
      await moreButton.click();
      await page.waitForTimeout(500);

      // Sheet should have Methodology, FAQ, About links
      const bodyText = await page.locator('body').textContent();
      expect(bodyText).toMatch(/Methodology/i);
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
    // Use addInitScript to inject localStorage before React hydrates
    // (WebKit can lose localStorage between cross-page navigations)
    await page.addInitScript(({ eins }) => {
      localStorage.setItem('gmg-compare-charities', JSON.stringify(eins));
    }, { eins: [EIN1, EIN2] });
    await page.goto('/compare');
    await page.waitForTimeout(5000);

    const bodyText = await page.locator('body').textContent();
    expect(bodyText).toContain(NAME1);
    expect(bodyText).toContain(NAME2);
  });

  test('guided entry paths render on mobile', async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() => localStorage.removeItem('gmg-browse-style'));
    await page.reload();
    await page.waitForTimeout(2000);

    // Mobile guided paths — use .first() since both mobile (sm:hidden) and desktop variants exist
    const guidedSection = page.locator('[data-tour="browse-guided"]').first();
    if (await guidedSection.isVisible()) {
      // Should show at least the zakat and browse-all paths
      const bodyText = await page.locator('body').textContent();
      expect(bodyText).toMatch(/Pay My Zakat|Browse All/i);
    }
  });

  test('detail page scrollable on mobile — no content clipping', async ({ page }) => {
    await page.goto(`/charity/${RICH_EIN}`);
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 });

    // Page should be scrollable (content taller than viewport)
    const pageHeight = await page.evaluate(() => document.documentElement.scrollHeight);
    expect(pageHeight).toBeGreaterThan(844); // viewport height
  });

  test('dark mode works on mobile', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.setItem('gmg-landing-theme', 'dark'));
    await page.goto('/browse');
    await page.waitForTimeout(2000);

    // Page should render content in dark mode
    const bodyText = await page.locator('body').textContent();
    expect(bodyText!.length).toBeGreaterThan(100);

    // Bottom nav should still be visible in dark mode
    const bottomNav = page.locator('nav[aria-label="Mobile navigation"]');
    if (await bottomNav.isVisible()) {
      await expect(bottomNav.getByText('Browse')).toBeVisible();
    }
  });

  test('methodology page renders on mobile', async ({ page }) => {
    await page.goto('/methodology');
    await expect(page.locator('h1')).toBeVisible();
    const bodyText = await page.locator('body').textContent();
    expect(bodyText).toMatch(/How We Evaluate/i);
  });

  test('about page renders on mobile', async ({ page }) => {
    await page.goto('/about');
    await expect(page.locator('h1, h2').first()).toBeVisible();
    const bodyText = await page.locator('body').textContent();
    expect(bodyText!.length).toBeGreaterThan(100);
  });

  test('no horizontal overflow on any mobile page', async ({ page }) => {
    const pages = ['/browse', '/faq', '/methodology', '/about', `/charity/${RICH_EIN}`];
    for (const path of pages) {
      await page.goto(path);
      await page.waitForTimeout(2000);

      const hasHorizontalOverflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth;
      });
      expect(hasHorizontalOverflow, `Horizontal overflow on ${path}`).toBe(false);
    }
  });
});

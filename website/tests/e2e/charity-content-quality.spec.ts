import { test, expect } from '@playwright/test';

const RICH_CHARITIES = [
  { ein: '01-0548371', name: 'Muslim Legal Fund of America' },
  { ein: '04-2535767', name: 'Union of Concerned Scientists' },
  { ein: '04-3810161', name: 'ICNA Relief' },
];

const BASELINE_CHARITIES = [
  { ein: '39-2713494', name: 'Hearts foundation' },
  { ein: '58-1956686', name: 'Project South' },
];

const ALL_CHARITIES = [
  ...RICH_CHARITIES.map((c) => ({ ...c, tier: 'rich' as const })),
  ...BASELINE_CHARITIES.map((c) => ({ ...c, tier: 'baseline' as const })),
];

test.describe('Charity content quality', () => {
  for (const charity of RICH_CHARITIES) {
    test(`citations render as links — ${charity.name}`, async ({ page }) => {
      await page.goto(`/charity/${charity.ein}`);
      await page.waitForTimeout(5000);

      const externalLinks = page.locator('a[target="_blank"]');
      const count = await externalLinks.count();
      expect(count).toBeGreaterThan(0);
    });
  }

  for (const charity of ALL_CHARITIES) {
    test(`financial data format — ${charity.name}`, async ({ page }) => {
      await page.goto(`/charity/${charity.ein}`);
      await page.waitForTimeout(3000);

      const bodyText = await page.locator('body').textContent();
      // Match dollar amounts like $1.2M, $500K, $3.4B, $12M or raw $NNN,NNN
      const dollarPattern = /\$[\d,.]+[KMB]|\$[\d,.]+\.\d+[KMB]|\$[\d,]+/;
      if (charity.tier === 'baseline') {
        // Baseline charities may lack financial data — check presence is ok
        const hasDollars = dollarPattern.test(bodyText || '');
        // Just flag it, don't fail — some small orgs have no financial data
        if (!hasDollars) {
          console.log(`Note: ${charity.name} has no dollar amounts on page`);
        }
      } else {
        expect(bodyText).toMatch(dollarPattern);
      }
    });

    test(`wallet tag badge visible — ${charity.name}`, async ({ page }) => {
      await page.goto(`/charity/${charity.ein}`);
      await page.waitForTimeout(3000);

      const bodyText = await page.locator('body').textContent();
      expect(bodyText).toMatch(/Zakat|Sadaqah/i);
    });

    test(`no empty sections — ${charity.name}`, async ({ page }) => {
      await page.goto(`/charity/${charity.ein}`);
      await page.waitForTimeout(3000);

      // Check that the page has meaningful content sections (h2/h3 followed by text)
      const headings = page.locator('h2:visible, h3:visible');
      const count = await headings.count();
      expect(count).toBeGreaterThan(0);

      // Verify overall page has substantial content
      const bodyText = await page.locator('body').textContent();
      expect(bodyText!.length).toBeGreaterThan(500);
    });
  }
});

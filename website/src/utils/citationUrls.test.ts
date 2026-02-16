import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolveCitationUrls, resolveSourceUrl, type CitationLike } from './citationUrls';

describe('resolveCitationUrls', () => {
  it('upgrades charity homepage citations to topic-matching deep links from context', () => {
    const citations: CitationLike[] = [
      {
        source_name: 'Example Programs',
        source_url: 'https://example.org',
        claim: 'The organization runs multiple education programs.',
      },
    ];

    const context = {
      website: 'https://example.org',
      donationUrl: 'https://example.org/donate',
      sourceAttribution: {
        programs: { source_url: 'https://example.org/programs' },
      },
      notes: [
        'See https://example.org/impact-report for outcomes.',
      ],
    };

    const resolved = resolveCitationUrls(citations, context);
    expect(resolved[0].source_url).toBe('https://example.org/programs');
  });

  it('upgrades Charity Navigator financial claims to #financials section', () => {
    const citations: CitationLike[] = [
      {
        source_name: 'Charity Navigator',
        source_url: 'https://www.charitynavigator.org/ein/131760110',
        claim: 'Program expense ratio and total revenue are strong.',
      },
    ];

    const resolved = resolveCitationUrls(citations);
    expect(resolved[0].source_url).toBe('https://www.charitynavigator.org/ein/131760110#financials');
  });

  it('upgrades Charity Navigator score claims to #ratings section', () => {
    const citations: CitationLike[] = [
      {
        source_name: 'Charity Navigator',
        source_url: 'https://www.charitynavigator.org/ein/131760110',
        claim: 'The organization has a high overall score.',
      },
    ];

    const resolved = resolveCitationUrls(citations);
    expect(resolved[0].source_url).toBe('https://www.charitynavigator.org/ein/131760110#ratings');
  });

  it('does not replace homepage when no matching deep link exists on the same domain', () => {
    const citations: CitationLike[] = [
      {
        source_name: 'Mission',
        source_url: 'https://example.org',
        claim: 'Mission statement',
      },
    ];

    const context = {
      donationUrl: 'https://other.org/donate',
      sourceAttribution: {
        mission: { source_url: 'https://other.org/about' },
      },
    };

    const resolved = resolveCitationUrls(citations, context);
    expect(resolved[0].source_url).toBe('https://example.org');
  });

  it('prefers report/audit deep links for beneficiary-oriented homepage citations', () => {
    const citations: CitationLike[] = [
      {
        source_name: 'Charity Website',
        source_url: 'https://obathelpers.org',
        claim: 'Beneficiaries served annually',
      },
    ];

    const context = {
      donationUrl: 'https://www.obathelpers.org/donate',
      sourceAttribution: {
        beneficiaries_served_annually: { source_url: 'https://obathelpers.org' },
      },
      amalEvaluation: {
        baseline_narrative: {
          all_citations: [
            { source_url: 'https://www.obathelpers.org/s/OBAT-Helpers-Audit-Report-2022-1.pdf' },
            { source_url: 'https://www.obathelpers.org/volunteer' },
          ],
        },
      },
    };

    const resolved = resolveCitationUrls(citations, context);
    expect(resolved[0].source_url).toBe('https://www.obathelpers.org/s/OBAT-Helpers-Audit-Report-2022-1.pdf');
  });
});

describe('resolveSourceUrl', () => {
  it('resolves a single homepage source url to a deeper same-domain url when available', () => {
    const context = {
      website: 'https://example.org',
      references: ['https://example.org/impact/report-2024'],
    };

    const resolved = resolveSourceUrl('https://example.org', context, {
      source_name: 'Charity Website',
      claim: 'beneficiaries served annually',
    });

    expect(resolved).toBe('https://example.org/impact/report-2024');
  });

  it('resolves the OBAT beneficiary source away from homepage to a deep link', () => {
    const dir = path.dirname(fileURLToPath(import.meta.url));
    const file = path.resolve(dir, '../../data/charities/charity-47-0946122.json');
    const obat = JSON.parse(fs.readFileSync(file, 'utf8'));

    const original = obat.sourceAttribution.beneficiaries_served_annually.source_url as string;
    const resolved = resolveSourceUrl(original, obat, {
      source_name: obat.sourceAttribution.beneficiaries_served_annually.source_name,
      claim: 'Beneficiaries served annually (self-reported)',
    });

    expect(resolved).toBeTruthy();
    expect(resolved).not.toBe('https://obathelpers.org');
    expect(resolved).not.toBe('https://obathelpers.org/');
    expect(new URL(resolved!).hostname.replace(/^www\./, '')).toBe('obathelpers.org');
  });
});

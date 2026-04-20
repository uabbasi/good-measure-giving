import { describe, it, expect } from 'vitest';
import { classifyZakatStatus, buildCharityTitle, buildCharityDescription, buildCharityFaqPairs, selectSimilarCharities } from './charity-seo';

describe('classifyZakatStatus', () => {
  it('returns ZAKAT_ELIGIBLE for any wallet_tag containing ZAKAT-ELIGIBLE', () => {
    expect(classifyZakatStatus({ walletTag: 'ZAKAT-ELIGIBLE', zakatClassification: null }))
      .toBe('ZAKAT_ELIGIBLE');
    expect(classifyZakatStatus({ walletTag: 'WIDELY-ZAKAT-ELIGIBLE', zakatClassification: null }))
      .toBe('ZAKAT_ELIGIBLE');
    expect(classifyZakatStatus({ walletTag: 'NARROWLY-ZAKAT-ELIGIBLE', zakatClassification: null }))
      .toBe('ZAKAT_ELIGIBLE');
  });

  it('returns SADAQAH_ONLY when wallet_tag is SADAQAH-ELIGIBLE', () => {
    expect(classifyZakatStatus({ walletTag: 'SADAQAH-ELIGIBLE', zakatClassification: 'sadaqah_only' }))
      .toBe('SADAQAH_ONLY');
  });

  it('returns UNCLEAR when classification is unclear or data is missing', () => {
    expect(classifyZakatStatus({ walletTag: null, zakatClassification: 'unclear' }))
      .toBe('UNCLEAR');
    expect(classifyZakatStatus({ walletTag: null, zakatClassification: null }))
      .toBe('UNCLEAR');
  });
});

describe('buildCharityTitle', () => {
  it('uses zakat-eligibility framing when ZAKAT_ELIGIBLE', () => {
    expect(buildCharityTitle({
      name: 'Islamic Relief',
      score: 78,
      zakatStatus: 'ZAKAT_ELIGIBLE',
    })).toBe('Is Islamic Relief Zakat Eligible? 78/100 Rating & Review | GMG');
  });

  it('uses review framing with zakat status suffix when SADAQAH_ONLY', () => {
    expect(buildCharityTitle({
      name: 'Doctors Without Borders',
      score: 72,
      zakatStatus: 'SADAQAH_ONLY',
    })).toBe('Doctors Without Borders Review: 72/100 Rating & Zakat Status | GMG');
  });

  it('uses review framing when UNCLEAR', () => {
    expect(buildCharityTitle({
      name: 'ICNA Relief',
      score: 74,
      zakatStatus: 'UNCLEAR',
    })).toBe('ICNA Relief Review: 74/100 Rating & Zakat Status | GMG');
  });

  it('uses early-stage framing when NEW_ORG regardless of score', () => {
    expect(buildCharityTitle({
      name: 'Example New Org',
      score: null,
      zakatStatus: 'NEW_ORG',
    })).toBe('Example New Org Review: Early-Stage Muslim Charity | GMG');
  });

  it('falls back to Evaluated when score is null on a rated status', () => {
    expect(buildCharityTitle({
      name: 'Unknown Charity',
      score: null,
      zakatStatus: 'UNCLEAR',
    })).toBe('Unknown Charity Review: Evaluated | GMG');
  });
});

describe('buildCharityDescription', () => {
  it('leads with zakat-eligibility sentence for ZAKAT_ELIGIBLE', () => {
    const desc = buildCharityDescription({
      name: 'Islamic Relief',
      score: 78,
      zakatStatus: 'ZAKAT_ELIGIBLE',
      missionFragment: 'Global humanitarian aid organization.',
    });
    expect(desc).toContain('Zakat Eligible');
    expect(desc).toContain('78/100');
    expect(desc).toContain('Global humanitarian');
    expect(desc.length).toBeLessThanOrEqual(160);
  });

  it('leads with sadaqah-only sentence for SADAQAH_ONLY', () => {
    const desc = buildCharityDescription({
      name: 'Doctors Without Borders',
      score: 72,
      zakatStatus: 'SADAQAH_ONLY',
      missionFragment: 'Medical humanitarian organization.',
    });
    expect(desc).toContain('sadaqah');
    expect(desc.length).toBeLessThanOrEqual(160);
  });

  it('truncates long mission fragments at 160 chars with ellipsis', () => {
    const longMission = 'X'.repeat(400);
    const desc = buildCharityDescription({
      name: 'Test',
      score: 50,
      zakatStatus: 'UNCLEAR',
      missionFragment: longMission,
    });
    expect(desc.length).toBeLessThanOrEqual(160);
    expect(desc.endsWith('\u2026')).toBe(true);
  });
});

describe('buildCharityFaqPairs', () => {
  it('generates 3 Q&A pairs from charity data', () => {
    const pairs = buildCharityFaqPairs({
      name: 'Islamic Relief',
      score: 78,
      zakatStatus: 'ZAKAT_ELIGIBLE',
      mission: 'Global humanitarian aid.',
      city: 'Burbank',
      state: 'CA',
    });
    expect(pairs).toHaveLength(3);
    expect(pairs[0].question).toBe('Is Islamic Relief zakat eligible?');
    expect(pairs[0].answer).toContain('Zakat Eligible');
    expect(pairs[1].question).toBe("What is Islamic Relief's impact rating?");
    expect(pairs[1].answer).toContain('78');
    expect(pairs[2].question).toContain('Where is Islamic Relief based');
    expect(pairs[2].answer).toContain('Burbank');
  });

  it('handles SADAQAH_ONLY in the zakat Q&A answer', () => {
    const pairs = buildCharityFaqPairs({
      name: 'Doctors Without Borders',
      score: 72,
      zakatStatus: 'SADAQAH_ONLY',
      mission: 'Medical aid.',
      city: 'New York',
      state: 'NY',
    });
    expect(pairs[0].answer).toContain('sadaqah');
    expect(pairs[0].answer).not.toContain('Zakat Eligible');
  });

  it('omits location parts gracefully when city/state missing', () => {
    const pairs = buildCharityFaqPairs({
      name: 'Test',
      score: 50,
      zakatStatus: 'UNCLEAR',
      mission: 'Test mission.',
      city: null,
      state: null,
    });
    expect(pairs[2].answer).not.toContain('null');
    expect(pairs[2].answer).toContain('Test mission');
  });
});

describe('selectSimilarCharities', () => {
  const pool = [
    { ein: '1', name: 'A', category: 'Humanitarian', amalScore: 80, zakatStatus: 'ZAKAT_ELIGIBLE' as const },
    { ein: '2', name: 'B', category: 'Humanitarian', amalScore: 90, zakatStatus: 'ZAKAT_ELIGIBLE' as const },
    { ein: '3', name: 'C', category: 'Humanitarian', amalScore: 70, zakatStatus: 'SADAQAH_ONLY' as const },
    { ein: '4', name: 'D', category: 'Education', amalScore: 85, zakatStatus: 'ZAKAT_ELIGIBLE' as const },
    { ein: '5', name: 'E', category: 'Humanitarian', amalScore: 75, zakatStatus: 'ZAKAT_ELIGIBLE' as const },
    { ein: '6', name: 'F', category: 'Humanitarian', amalScore: 95, zakatStatus: 'ZAKAT_ELIGIBLE' as const },
  ];

  it('returns up to 5 charities from the same category and same zakat tier, sorted by score desc', () => {
    const result = selectSimilarCharities({
      currentEin: '1',
      category: 'Humanitarian',
      zakatStatus: 'ZAKAT_ELIGIBLE',
      pool,
      limit: 5,
    });
    expect(result.map(c => c.ein)).toEqual(['6', '2', '5']);
  });

  it('excludes the current charity', () => {
    const result = selectSimilarCharities({
      currentEin: '6',
      category: 'Humanitarian',
      zakatStatus: 'ZAKAT_ELIGIBLE',
      pool,
      limit: 5,
    });
    expect(result.map(c => c.ein)).not.toContain('6');
  });

  it('respects the limit', () => {
    const result = selectSimilarCharities({
      currentEin: '1',
      category: 'Humanitarian',
      zakatStatus: 'ZAKAT_ELIGIBLE',
      pool,
      limit: 2,
    });
    expect(result).toHaveLength(2);
  });

  it('returns empty array when no same-category same-tier charities exist', () => {
    const result = selectSimilarCharities({
      currentEin: '1',
      category: 'NonexistentCategory',
      zakatStatus: 'ZAKAT_ELIGIBLE',
      pool,
      limit: 5,
    });
    expect(result).toEqual([]);
  });
});

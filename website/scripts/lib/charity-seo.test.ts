import { describe, it, expect } from 'vitest';
import { classifyZakatStatus, buildCharityTitle, buildCharityDescription } from './charity-seo';

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

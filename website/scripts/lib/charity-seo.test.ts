import { describe, it, expect } from 'vitest';
import { classifyZakatStatus } from './charity-seo';

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

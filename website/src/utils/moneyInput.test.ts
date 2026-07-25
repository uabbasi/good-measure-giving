import { describe, it, expect } from 'vitest';
import { sanitizeMoneyInput, parseMoneyInput, MAX_MONEY_INPUT } from './moneyInput';

describe('sanitizeMoneyInput', () => {
  it('preserves cents instead of deleting the decimal point', () => {
    // The original bug: `replace(/\D/g,'')` turned these into 1250 / 250075 / 9999.
    expect(sanitizeMoneyInput('12.50')).toBe('12.50');
    expect(sanitizeMoneyInput('2500.75')).toBe('2500.75');
    expect(sanitizeMoneyInput('99.99')).toBe('99.99');
  });

  it('keeps a trailing dot so mid-typing states are not fought', () => {
    expect(sanitizeMoneyInput('12.')).toBe('12.');
  });

  it('truncates past two decimal places', () => {
    expect(sanitizeMoneyInput('12.999')).toBe('12.99');
  });

  it('collapses multiple decimal points to the first', () => {
    expect(sanitizeMoneyInput('1.2.3')).toBe('1.23');
  });

  it('strips signs, letters, and separators', () => {
    expect(sanitizeMoneyInput('-500')).toBe('500');
    expect(sanitizeMoneyInput('abc')).toBe('');
    expect(sanitizeMoneyInput('1,000')).toBe('1000');
    expect(sanitizeMoneyInput('1e9')).toBe('19');
  });

  it('clamps values above the ceiling instead of accepting trillions', () => {
    expect(sanitizeMoneyInput('99999999999999')).toBe(String(MAX_MONEY_INPUT));
    expect(sanitizeMoneyInput('999999999')).toBe('999999999');
  });

  it('drops leading zeros but keeps a lone zero typeable', () => {
    expect(sanitizeMoneyInput('007')).toBe('7');
    expect(sanitizeMoneyInput('0')).toBe('0');
    expect(sanitizeMoneyInput('0.50')).toBe('0.50');
  });

  it('returns empty for empty input', () => {
    expect(sanitizeMoneyInput('')).toBe('');
  });
});

describe('parseMoneyInput', () => {
  it('parses cents correctly', () => {
    expect(parseMoneyInput('12.50')).toBe(12.5);
    expect(parseMoneyInput('2500.75')).toBe(2500.75);
  });

  it('reads partial input as its numeric prefix, never NaN', () => {
    expect(parseMoneyInput('')).toBe(0);
    expect(parseMoneyInput('.')).toBe(0);
    expect(parseMoneyInput('12.')).toBe(12);
    expect(parseMoneyInput('abc')).toBe(0);
  });

  it('never exceeds the ceiling', () => {
    expect(parseMoneyInput('99999999999999')).toBe(MAX_MONEY_INPUT);
  });
});

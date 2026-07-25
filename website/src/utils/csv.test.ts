import { describe, it, expect } from 'vitest';
import { csvField, csvRow, toCSV } from './csv';

describe('csvField', () => {
  it('quotes fields containing a comma', () => {
    // The live bug: Payment Source "Chase, Business Account" went out bare and
    // split into two columns, shifting every later field by one.
    expect(csvField('Chase, Business Account')).toBe('"Chase, Business Account"');
  });

  it('doubles internal quotes', () => {
    expect(csvField('The "Big" Fund')).toBe('"The ""Big"" Fund"');
  });

  it('quotes fields containing newlines', () => {
    expect(csvField('line one\nline two')).toBe('"line one\nline two"');
  });

  it('leaves ordinary fields bare', () => {
    expect(csvField('Bank Transfer')).toBe('Bank Transfer');
    expect(csvField('2026-07-25')).toBe('2026-07-25');
  });

  it('neutralizes spreadsheet formula prefixes', () => {
    expect(csvField('=1+1')).toBe("'=1+1");
    expect(csvField('@SUM(A1)')).toBe("'@SUM(A1)");
    expect(csvField('+cmd')).toBe("'+cmd");
    expect(csvField('-2')).toBe("'-2");
  });

  it('handles empty and nullish values', () => {
    expect(csvField('')).toBe('');
    expect(csvField(null)).toBe('');
    expect(csvField(undefined)).toBe('');
  });

  it('stringifies numbers', () => {
    expect(csvField(42)).toBe('42');
  });
});

describe('toCSV', () => {
  it('keeps every row at the header column count, even with commas in fields', () => {
    const headers = ['Date', 'Charity', 'Payment Source', 'Receipt'];
    const rows = [
      ['2026-07-25', 'CommaTest Charity', 'Chase, Business Account', 'No'],
      ['2026-07-24', 'Plain Charity', 'Bank Transfer', 'Yes'],
    ];
    const csv = toCSV(headers, rows);
    const lines = csv.split('\n');

    expect(lines).toHaveLength(3);
    // Count only the commas that actually separate fields (outside quotes).
    for (const line of lines) {
      let inQuotes = false;
      let separators = 0;
      for (let i = 0; i < line.length; i++) {
        if (line[i] === '"') inQuotes = !inQuotes;
        else if (line[i] === ',' && !inQuotes) separators++;
      }
      expect(separators).toBe(headers.length - 1);
    }
  });
});

describe('csvRow', () => {
  it('joins escaped fields with commas', () => {
    expect(csvRow(['a', 'b,c', 'd'])).toBe('a,"b,c",d');
  });
});

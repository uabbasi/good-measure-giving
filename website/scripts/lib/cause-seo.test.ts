import { describe, it, expect } from 'vitest';
import {
  categoryToSlug,
  slugToCategory,
  CAUSE_SLUGS,
  filterCharitiesByCategory,
  type HubCharity,
} from './cause-seo';

describe('categoryToSlug', () => {
  it('converts MECE category to kebab-case slug', () => {
    expect(categoryToSlug('HUMANITARIAN')).toBe('humanitarian');
    expect(categoryToSlug('RELIGIOUS_CONGREGATION')).toBe('religious-congregation');
    expect(categoryToSlug('CIVIL_RIGHTS_LEGAL')).toBe('civil-rights-legal');
    expect(categoryToSlug('EDUCATION_K12_RELIGIOUS')).toBe('education-k12-religious');
  });

  it('returns null for null/empty input', () => {
    expect(categoryToSlug(null)).toBeNull();
    expect(categoryToSlug('')).toBeNull();
  });
});

describe('slugToCategory', () => {
  it('round-trips every known slug back to its category', () => {
    for (const slug of CAUSE_SLUGS) {
      const category = slugToCategory(slug);
      expect(category).not.toBeNull();
      expect(categoryToSlug(category!)).toBe(slug);
    }
  });

  it('returns null for unknown slug', () => {
    expect(slugToCategory('not-a-real-cause')).toBeNull();
  });
});

describe('CAUSE_SLUGS', () => {
  it('contains all 16 MECE category slugs', () => {
    expect(CAUSE_SLUGS).toHaveLength(16);
    expect(CAUSE_SLUGS).toContain('humanitarian');
    expect(CAUSE_SLUGS).toContain('religious-congregation');
    expect(CAUSE_SLUGS).toContain('civil-rights-legal');
  });
});

describe('filterCharitiesByCategory', () => {
  const pool: HubCharity[] = [
    { ein: '1', name: 'A', primaryCategory: 'HUMANITARIAN', amalScore: 80, walletTag: 'ZAKAT-ELIGIBLE' },
    { ein: '2', name: 'B', primaryCategory: 'HUMANITARIAN', amalScore: 90, walletTag: 'SADAQAH-ELIGIBLE' },
    { ein: '3', name: 'C', primaryCategory: 'MEDICAL_HEALTH', amalScore: 75, walletTag: 'ZAKAT-ELIGIBLE' },
    { ein: '4', name: 'D', primaryCategory: 'HUMANITARIAN', amalScore: null, walletTag: 'UNCLEAR' },
    { ein: '5', name: 'E', primaryCategory: null, amalScore: 70, walletTag: 'ZAKAT-ELIGIBLE' },
  ];

  it('returns charities in the specified category, sorted by amalScore desc, nulls last', () => {
    const result = filterCharitiesByCategory(pool, 'HUMANITARIAN');
    expect(result.map(c => c.ein)).toEqual(['2', '1', '4']);
  });

  it('returns empty array when no charities match', () => {
    expect(filterCharitiesByCategory(pool, 'NONEXISTENT')).toEqual([]);
  });

  it('skips charities with null primaryCategory', () => {
    const result = filterCharitiesByCategory(pool, 'HUMANITARIAN');
    expect(result.map(c => c.ein)).not.toContain('5');
  });
});

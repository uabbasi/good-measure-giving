import { describe, it, expect } from 'vitest';
import { DEV_TEST_USERS } from './devTestUsers';

describe('DEV_TEST_USERS', () => {
  it('defines fresh + active-donor + zakat-focused personas with @test.local emails', () => {
    const ids = DEV_TEST_USERS.map(u => u.id);
    expect(ids).toEqual(['fresh', 'active-donor', 'zakat-focused']);
    expect(DEV_TEST_USERS.every(u => u.email.endsWith('@test.local'))).toBe(true);
  });
  it('seeds the donor personas but not the fresh user', () => {
    expect(DEV_TEST_USERS.find(u => u.id === 'fresh')!.seed).toBeFalsy();
    expect(DEV_TEST_USERS.find(u => u.id === 'active-donor')!.seed).toBe(true);
    expect(DEV_TEST_USERS.find(u => u.id === 'zakat-focused')!.seed).toBe(true);
  });
});

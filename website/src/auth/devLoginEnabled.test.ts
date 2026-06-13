import { describe, it, expect, vi, afterEach } from 'vitest';
import { devLoginEnabled } from './devLoginEnabled';

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe('devLoginEnabled', () => {
  it('is false when the emulator flag is off', () => {
    vi.stubEnv('VITE_USE_FIREBASE_EMULATOR', 'false');
    expect(devLoginEnabled()).toBe(false);
  });
  it('is true in DEV + emulator + localhost', () => {
    vi.stubEnv('DEV', true);
    vi.stubEnv('VITE_USE_FIREBASE_EMULATOR', 'true');
    vi.stubGlobal('window', { location: { hostname: 'localhost' } });
    expect(devLoginEnabled()).toBe(true);
  });
  it('is false on a non-localhost hostname even with emulator flag', () => {
    vi.stubEnv('DEV', true);
    vi.stubEnv('VITE_USE_FIREBASE_EMULATOR', 'true');
    vi.stubGlobal('window', { location: { hostname: 'example.com' } });
    expect(devLoginEnabled()).toBe(false);
  });
});

import { defineConfig, devices } from '@playwright/test';

/**
 * Dedicated Playwright config for the shared-plan flow against the Firebase
 * Emulator Suite. Runs Chrome only (per the dogfood spec) and boots a Vite dev
 * server in emulator mode on an isolated port so it never collides with the
 * default e2e server. The emulators themselves are started by the wrapping
 * `firebase emulators:exec` (see package.json `test:e2e:shared`).
 */
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'shared-plan-emulator.spec.ts',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  timeout: 90_000,
  use: {
    baseURL: 'http://localhost:5180',
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'VITE_USE_FIREBASE_EMULATOR=true npm run dev -- --port 5180 --strictPort',
    url: 'http://localhost:5180',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});

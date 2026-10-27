import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end smoke test configuration.
 *
 * Deliberately separate from `npm run test` (Vitest): this suite needs a real browser
 * and both servers, so it is run on demand with `npm run test:e2e` rather than on
 * every commit. See docs/TESTING.md for the one-time browser install.
 *
 * Playwright starts both servers itself. The backend writes to its own database file
 * (`backend/data/e2e.db`) so an e2e run never touches the development database, and
 * the spec uses a fresh ID number each run so it does not depend on an empty one.
 */

/** The interpreter that has the backend dependencies (``python3`` on most Linux). */
const PYTHON = process.env.SAWIE_PYTHON ?? 'python';

/**
 * An existing Chromium, for images that ship one already (CI runners, containers).
 * Left unset, Playwright uses the browser `npx playwright install chromium` downloads.
 */
const CHROMIUM = process.env.SAWIE_CHROMIUM;

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // The field page asks for the officer's position; granting it keeps the map
    // centred on the cotton belt instead of the fallback region.
    permissions: ['geolocation'],
    geolocation: { latitude: 30.1575, longitude: 71.5249 },
    ...devices['Desktop Chrome'],
    ...(CHROMIUM ? { launchOptions: { executablePath: CHROMIUM } } : {}),
  },
  webServer: [
    {
      command: `${PYTHON} -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        APP_ENV: 'development',
        DATABASE_URL: 'sqlite:///./data/e2e.db',
        SEED_ON_START: 'true',
      },
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});

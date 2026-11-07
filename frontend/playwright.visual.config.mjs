import { defineConfig } from '@playwright/test';

// Remote verification loads the deployed assets and intercepts all application
// API requests in the browser. No production account or database is used.
const remoteURL = process.env.E2E_VISUAL_BASE_URL;

export default defineConfig({
  testDir: './e2e',
  testMatch: 'diary-visual.spec.mjs',
  workers: 1,
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  timeout: 30000,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: remoteURL || 'http://127.0.0.1:3002',
    browserName: 'chromium',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: remoteURL
    ? undefined
    : {
        command: `"${process.execPath}" node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 3002 --strictPort`,
        url: 'http://127.0.0.1:3002',
        reuseExistingServer: false,
      },
});

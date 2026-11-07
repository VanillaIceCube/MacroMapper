import { defineConfig } from '@playwright/test';

const remoteURL = process.env.E2E_DIARY_BASE_URL;

export default defineConfig({
  testDir: './e2e',
  testMatch: 'diary-restoration.spec.mjs',
  workers: 1,
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  timeout: 30000,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: remoteURL || 'http://127.0.0.1:3004',
    browserName: 'chromium',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: remoteURL
    ? undefined
    : {
        command: `"${process.execPath}" node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 3004 --strictPort`,
        url: 'http://127.0.0.1:3004',
        reuseExistingServer: false,
      },
});

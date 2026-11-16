import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: process.env.HOST || 'localhost',
    port: 3000,
    strictPort: true,
    allowedHosts: ['macromapper.localhost'],
    watch: { usePolling: process.env.CHOKIDAR_USEPOLLING === 'true' },
  },
  build: { outDir: 'dist', target: ['chrome117', 'edge121', 'firefox121', 'safari17'] },
  test: {
    include: ['src/**/*.test.{js,jsx}'],
    clearMocks: true,
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test-helpers/setup.js',
    testTimeout: 15_000,
    unstubEnvs: true,
    unstubGlobals: true,
  },
});

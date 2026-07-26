import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiBaseUrl =
    env.REACT_APP_API_BASE_URL === undefined
      ? 'undefined'
      : JSON.stringify(env.REACT_APP_API_BASE_URL);

  return {
    define: {
      'process.env.NODE_ENV': JSON.stringify(mode),
      'process.env.PUBLIC_URL': JSON.stringify(''),
      'process.env.REACT_APP_API_BASE_URL': apiBaseUrl,
    },
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 3000,
    },
    test: {
      clearMocks: true,
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/setupTests.js'],
    },
  };
});

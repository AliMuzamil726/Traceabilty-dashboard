import { fileURLToPath, URL } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

const BACKEND = 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    strictPort: true,
    host: 'localhost',
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/docs': { target: BACKEND, changeOrigin: true },
      '/openapi.json': { target: BACKEND, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    include: ['src/**/*.test.{ts,tsx}'],
    // A test file builds a whole jsdom page; on a busy machine the default 5 s runs out
    // mid-render even though the test itself takes a fraction of that.
    testTimeout: 15_000,
    hookTimeout: 15_000,
  },
});

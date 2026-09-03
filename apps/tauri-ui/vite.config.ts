/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Fixed port matching tauri.conf.json's `devUrl` — Tauri's WebView
  // connects to a known address rather than discovering Vite's port.
  server: {
    port: 1420,
    strictPort: true,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    /* Must stay comfortably above `asyncUtilTimeout` in `src/test-setup.ts`.
       Setting them equal (both 5s) meant a slow-to-appear element killed the
       whole test at its own deadline instead of letting `waitFor` fail first
       with a message naming what it was looking for -- so CI reported "Test
       timed out in 5000ms" where it used to say which element was missing.
       The helper gives up first and explains; the test has headroom behind it. */
    testTimeout: 20000,
  },
})

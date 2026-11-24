import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Run tests in a fixed non-UTC timezone so UTC -> local conversions are
// actually exercised (server timestamps are UTC without an offset).
process.env.TZ = 'America/Tijuana'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    globals: true,
    coverage: {
      provider: 'v8',
      threshold: {
        lines: 80,
      },
    },
  },
})

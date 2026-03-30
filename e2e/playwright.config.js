// @ts-check
const { defineConfig, devices } = require('@playwright/test')

/**
 * Playwright E2E configuration for ZeroRadius.
 *
 * Prerrequisitos para correr los tests:
 *   - Frontend Vite dev server: npm run dev (desde frontend/)
 *   - Backend FastAPI: uvicorn app.main:app --reload (desde backend/)
 *
 * Instalación de browsers:
 *   npx playwright install chromium
 */
module.exports = defineConfig({
  testDir: './tests',
  outputDir: './test-results',
  fullyParallel: false, // Para tests que comparten estado de BD
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1, // Secuencial para evitar race conditions en BD
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],

  use: {
    baseURL: 'http://localhost:5173',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'on-first-retry',
    // Credentials de test para E2E
    storageState: undefined,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // ─── WebServer Setup ────────────────────────────────────────────────────────
  // Frontend (Vite): se levanta automáticamente al correr los tests.
  //
  // Backend (FastAPI + MariaDB): DEBE estar corriendo antes de ejecutar Playwright.
  // Levantar con: docker-compose up -d db backend
  //
  // En Windows, se usa cmd /c para ejecutar .cmd scripts (PowerShell bloquea .ps1)
  webServer: [
    {
      command: 'cmd /c "node_modules\\.bin\\vite.cmd --port 5173"',
      url: 'http://localhost:5173',
      cwd: '../frontend',
      reuseExistingServer: true,
      timeout: 60000,
    },
  ],
})

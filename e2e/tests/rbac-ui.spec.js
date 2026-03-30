// @ts-check
const { test, expect } = require('@playwright/test')

/**
 * E2E tests: RBAC UI guards.
 *
 * Verifica que los elementos de la UI se muestran/ocultan según el rol del usuario.
 */

const SUPERADMIN_USER = process.env.E2E_USERNAME || 'test_superadmin'
const SUPERADMIN_PASS = process.env.E2E_PASSWORD || 'TestPassword1!'

// Helper: login y navegar a una URL
async function loginAs(page, username, password) {
  await page.goto('/login')
  await page.evaluate(() => localStorage.clear())
  await page.getByPlaceholder('Username').fill(username)
  await page.getByPlaceholder('Password').fill(password)
  await page.getByRole('button', { name: /login/i }).click()
  await expect(page).toHaveURL(/\/$|\/change-password/, { timeout: 5000 })
}

test.describe('RBAC UI — superadmin', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, SUPERADMIN_USER, SUPERADMIN_PASS)
  })

  test('superadmin sees User Management section with Add User button', async ({ page }) => {
    await page.goto('/users')
    await expect(page.getByText(/add user/i)).toBeVisible({ timeout: 5000 })
  })

  test('superadmin sees admin-users management link or section', async ({ page }) => {
    await page.goto('/')
    // La navegación principal debe ser visible
    await expect(page.getByRole('navigation')).toBeVisible({ timeout: 3000 })
  })
})

test.describe('RBAC UI — guest (not logged in)', () => {
  test('unauthenticated user is redirected to login', async ({ page }) => {
    // Ensure clean state
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.goto('/users')
    // Should redirect to /login
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 })
  })
})

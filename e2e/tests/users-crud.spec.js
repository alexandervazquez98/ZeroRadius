// @ts-check
const { test, expect } = require('@playwright/test')

/**
 * E2E tests: RADIUS users CRUD flow.
 *
 * Crea un usuario RADIUS único (con timestamp para evitar colisiones)
 * y luego lo elimina. Verifica visibilidad en tabla.
 */

const TEST_USER = process.env.E2E_USERNAME || 'test_superadmin'
const TEST_PASS = process.env.E2E_PASSWORD || 'TestPassword1!'

async function loginAs(page, username, password) {
  await page.goto('/login')
  await page.evaluate(() => localStorage.clear())
  await page.getByPlaceholder('Username').fill(username)
  await page.getByPlaceholder('Password').fill(password)
  await page.getByRole('button', { name: /login/i }).click()
  await expect(page).toHaveURL(/\/$|\/change-password/, { timeout: 5000 })
  // Si hay force_change, va a /change-password — para E2E necesitamos un usuario sin eso
  if (page.url().includes('change-password')) {
    test.skip(true, 'Test user requires password change — set force_password_change=0 for E2E user')
  }
}

test.describe('RADIUS Users CRUD', () => {
  const TEST_USERNAME = `e2e_user_${Date.now()}`

  test.beforeEach(async ({ page }) => {
    await loginAs(page, TEST_USER, TEST_PASS)
  })

  test('superadmin can create a RADIUS user via UI', async ({ page }) => {
    await page.goto('/users')

    // Abrir el wizard de creación — el botón dice "Add User"
    await page.getByText(/add user/i).click()

    // Step 1 — Identity: inputs sin placeholder, usar getByLabel (UserWizard.jsx:103, 123)
    await page.getByLabel(/^username$/i).fill(TEST_USERNAME)
    await page.getByLabel(/^password$/i).fill('TestRadiusPass1!')

    // Next → Step 2 (Policies/Groups — opcionales, no seleccionamos ninguno)
    await page.getByRole('button', { name: /^next$/i }).click()

    // Next → Step 3 (Attributes — opcionales)
    await page.getByRole('button', { name: /^next$/i }).click()

    // Step 3 — Click "Create User" para finalizar (UserWizard.jsx:274)
    await page.getByRole('button', { name: /create user/i }).click()

    // Verificar que el usuario aparece en la tabla
    await expect(page.getByText(TEST_USERNAME)).toBeVisible({ timeout: 8000 })
  })

  test('created RADIUS user can be deleted via UI', async ({ page }) => {
    await page.goto('/users')

    // Buscar la fila del usuario creado
    const userRow = page.locator('tr', { hasText: TEST_USERNAME })

    // Si el usuario no existe (el test anterior falló), skipear
    const count = await userRow.count()
    if (count === 0) {
      test.skip(true, `User ${TEST_USERNAME} not found — create test may have failed`)
    }

    // Hacer click en el botón delete de esa fila
    await userRow.getByRole('button').filter({ hasText: '' }).last().click()

    // Verificar que desapareció de la tabla
    await expect(page.getByText(TEST_USERNAME)).toBeHidden({ timeout: 5000 })
  })
})

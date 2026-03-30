// @ts-check
const { test, expect } = require('@playwright/test')

/**
 * E2E tests: Login flow.
 *
 * Credenciales de test configuradas en el backend:
 *   superadmin / admin (cambiar password en el primer uso)
 * Para E2E se usa una credencial específica — ajustar según el entorno.
 */

const TEST_USER = process.env.E2E_USERNAME || 'test_superadmin'
const TEST_PASS = process.env.E2E_PASSWORD || 'TestPassword1!'

test.describe('Login flow', () => {
  test.beforeEach(async ({ page }) => {
    // Limpiar localStorage antes de cada test
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
  })

  test('renders the login page', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByPlaceholder('Username')).toBeVisible()
    await expect(page.getByPlaceholder('Password')).toBeVisible()
    await expect(page.getByRole('button', { name: /login/i })).toBeVisible()
  })

  test('successful login redirects to dashboard', async ({ page }) => {
    await page.goto('/login')
    await page.getByPlaceholder('Username').fill(TEST_USER)
    await page.getByPlaceholder('Password').fill(TEST_PASS)
    await page.getByRole('button', { name: /login/i }).click()

    // Después del login exitoso debe redirigir a / o /change-password
    await expect(page).toHaveURL(/\/$|\/change-password/, { timeout: 5000 })

    // Verificar que el token fue guardado en localStorage
    const token = await page.evaluate(() => localStorage.getItem('token'))
    expect(token).toBeTruthy()
  })

  test('invalid credentials show error message', async ({ page }) => {
    await page.goto('/login')
    await page.getByPlaceholder('Username').fill('invalid_user')
    await page.getByPlaceholder('Password').fill('wrong_password')
    await page.getByRole('button', { name: /login/i }).click()

    // El componente Login.jsx muestra "Invalid credentials" en el catch (Login.jsx:23)
    // Con el backend real puede tardar más que con MSW mock
    await expect(page.getByText(/invalid credentials/i)).toBeVisible({ timeout: 10000 })
  })

  test('empty form does not submit (HTML5 validation)', async ({ page }) => {
    await page.goto('/login')

    // Registrar si se hace alguna petición a /auth/token
    const requests = []
    page.on('request', (req) => {
      if (req.url().includes('/auth/token')) requests.push(req)
    })

    await page.getByRole('button', { name: /login/i }).click()

    // No debe haberse enviado ningún request porque el input tiene required
    expect(requests.length).toBe(0)
  })
})

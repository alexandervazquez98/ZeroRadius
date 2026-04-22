// @ts-check
const { test, expect } = require('@playwright/test')

const TEST_USER = process.env.E2E_USERNAME || 'test_superadmin'
const TEST_PASS = process.env.E2E_PASSWORD || 'TestPassword1!'

async function loginAs(page, username, password) {
  await page.goto('/login')
  await page.evaluate(() => localStorage.clear())
  await page.getByPlaceholder('Username').fill(username)
  await page.getByPlaceholder('Password').fill(password)
  await page.getByRole('button', { name: /login/i }).click()
  await expect(page).toHaveURL(/\/$|\/change-password/, { timeout: 5000 })
  if (page.url().includes('change-password')) {
    test.skip(true, 'Test user requires password change')
  }
}

test.describe('Access Policies & Segments', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, TEST_USER, TEST_PASS)
  })

  test('can create a network segment and exception policy', async ({ page }) => {
    const uniqueSeg = `E2E Seg ${Date.now()}`

    await page.goto('/network-segments')
    await expect(page.getByRole('heading', { name: /network segments/i })).toBeVisible()

    await page.getByRole('button', { name: /add segment/i }).click()
    await page.getByPlaceholder('e.g. Core Network').fill(uniqueSeg)
    await page.getByPlaceholder('e.g. 10.0.0.0/8').fill('10.250.0.0/24')
    await page.getByPlaceholder('Optional description').fill('E2E Testing Segment')
    await page.getByRole('button', { name: /^save$/i }).click()

    await expect(page.getByText(uniqueSeg)).toBeVisible({ timeout: 8000 })

    await page.goto('/privilege-map')
    await expect(page.getByRole('heading', { name: /access policies/i })).toBeVisible()

    await page.getByRole('button', { name: /add policy/i }).click()
    await page.locator('#pm-username').selectOption('jperez')
    await page.getByRole('button', { name: /ip or range \(exception\)/i }).click()
    await page.getByRole('combobox').nth(1).selectOption({ label: `${uniqueSeg} (10.250.0.0/24)` })
    await page.getByPlaceholder('e.g. 10.0.1.50').fill('10.250.0.10')
    await page.locator('#pm-radius-group').selectOption({ index: 1 })
    await page.locator('#pm-approved-by').fill('E2E Test')
    await page.getByRole('button', { name: /save policy/i }).click()

    await expect(page.getByRole('heading', { name: /new policy/i })).toBeHidden({ timeout: 8000 })

    await page.getByRole('button', { name: /jperez/i }).click()
    await expect(page.getByText(uniqueSeg)).toBeVisible({ timeout: 8000 })
    await expect(page.getByText('10.250.0.10')).toBeVisible()
  })
})

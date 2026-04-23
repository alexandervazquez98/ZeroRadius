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

test.describe('Access Policies & Bandwidth Profiles', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, TEST_USER, TEST_PASS)
  })

  test('can create a network segment, a bandwidth profile, and an assignment', async ({ page }) => {
    const uniqueSeg = `E2E Seg ${Date.now()}`
    const profileName = `E2E-100M-${Date.now()}`

    // 1. Create a Network Segment
    await page.goto('/network-segments')
    await expect(page.getByRole('heading', { name: /network segments/i })).toBeVisible()

    await page.getByRole('button', { name: /add segment/i }).click()
    await page.getByPlaceholder('e.g. Core Network').fill(uniqueSeg)
    await page.getByPlaceholder('e.g. 10.0.0.0/8').fill(`10.${Math.floor(Math.random() * 255)}.0.0/24`)
    await page.getByPlaceholder('Optional description').fill('E2E Testing Segment')
    await page.getByRole('button', { name: /^save$/i }).click()

    await expect(page.getByText(uniqueSeg)).toBeVisible({ timeout: 8000 })

    // 2. Go to Access Policies
    await page.goto('/access-policies')
    await expect(page.getByRole('heading', { name: /access policies/i })).toBeVisible()

    // 3. Create a Bandwidth Profile
    await page.getByRole('button', { name: /bandwidth profiles/i }).click()
    
    await page.getByLabel('Profile Name').fill(profileName)
    await page.getByLabel('Downlink High').fill('100M')
    await page.getByLabel('Uplink High').fill('50M')
    await page.getByLabel('Downlink Low').fill('10M')
    await page.getByLabel('Uplink Low').fill('5M')
    
    await page.getByRole('button', { name: /save profile/i }).click()
    await expect(page.getByText(/bandwidth profile saved/i)).toBeVisible({ timeout: 8000 })

    // 4. Create an Assignment
    await page.getByRole('button', { name: /^assignments$/i }).click()
    
    await page.getByRole('button', { name: /add policy/i }).click()
    await page.locator('#pm-username').selectOption('jperez')
    
    // Target Mode: IP or Range (Exception)
    await page.getByRole('button', { name: /ip or range \(exception\)/i }).click()
    
    // Select the segment
    // It's the select immediately after target mode buttons, but we can find it by its default option
    await page.getByRole('combobox').filter({ hasText: '-- Select Parent Segment --' }).selectOption({ label: new RegExp(uniqueSeg) })
    
    await page.getByPlaceholder('e.g. 10.0.1.50').fill('10.250.0.10')
    
    // Select the newly created Bandwidth Profile
    await page.locator('#pm-radius-group').selectOption({ label: profileName })
    
    await page.locator('#pm-approved-by').fill('E2E Test')
    
    await page.getByRole('button', { name: /save policy/i }).click()

    await expect(page.getByRole('heading', { name: /new policy/i })).toBeHidden({ timeout: 8000 })

    // Verify assignment exists in the list for the user
    await page.getByRole('button', { name: /jperez/i }).click()
    await expect(page.getByText(uniqueSeg)).toBeVisible({ timeout: 8000 })
    await expect(page.getByText('10.250.0.10')).toBeVisible()
    await expect(page.getByText(profileName)).toBeVisible()

    // 5. Test Preview Resolution Tab
    await page.getByRole('button', { name: /preview resolution/i }).click()
    
    await page.getByLabel('Preview Username').fill('jperez')
    await page.getByLabel('Preview NAS IP').fill('10.250.0.10')
    await page.getByRole('button', { name: /run preview/i }).click()

    await expect(page.getByText('Winning bandwidth profile:')).toBeVisible({ timeout: 8000 })
    await expect(page.getByText(profileName)).toBeVisible()
    await expect(page.getByText(/matched segment/i)).toBeVisible()
  })
})

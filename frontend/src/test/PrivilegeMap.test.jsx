import React from 'react'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import PrivilegeMapPage from '../pages/PrivilegeMap'
import { AuthProvider } from '../context/AuthContext'

function makeJwt(role) {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  const body = btoa(JSON.stringify({ sub: 'testuser', role, exp: 9999999999 }))
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `${header}.${body}.fakesig`
}

function renderPrivilegeMap() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider initialToken={makeJwt('superadmin')}>
          <PrivilegeMapPage />
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>
  )
}

describe('PrivilegeMapPage — Mapping with Categories', () => {
  it('renders mappings table with users', async () => {
    renderPrivilegeMap()
    
    // We expect "jperez" to be in the users list on the left based on handlers.js
    await waitFor(() => {
      expect(screen.getAllByText('jperez').length).toBeGreaterThan(0)
    })
  })

  it('toggles between Specific IPs and By Category in Add Mapping modal', async () => {
    const user = userEvent.setup()
    renderPrivilegeMap()
    
    // Select a user first to enable adding NAS mappings for them, though we can just open global Add Mapping
    const addBtn = await screen.findByRole('button', { name: /Add Mapping/i })
    await user.click(addBtn)
    
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Add Mapping/i })).toBeInTheDocument()
      expect(screen.getByText('Specific IPs')).toBeInTheDocument()
      expect(screen.getByText('By Category')).toBeInTheDocument()
    })
    
    // Default is Specific IPs, we should see IP checkboxes
    // Our handler mocked 10.0.0.1 and 10.0.0.2
    expect(screen.getByText('10.0.0.1')).toBeInTheDocument()

    // Click By Category
    await user.click(screen.getByText('By Category'))
    
    // IP multi-select list should disappear, and category select appear
    await waitFor(() => {
      expect(screen.queryByText('10.0.0.1')).not.toBeInTheDocument()
      // Should have a dropdown for Categories
      expect(document.getElementById('pm-category')).toBeInTheDocument()
    })
  })

  it('can submit a category-based mapping', async () => {
    const user = userEvent.setup()
    renderPrivilegeMap()
    
    // Open modal
    const addBtn = await screen.findByRole('button', { name: /Add Mapping/i })
    await user.click(addBtn)
    
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Add Mapping/i })).toBeInTheDocument()
    })

    // 1. Pick user
    await waitFor(() => {
      expect(document.getElementById('pm-username')).toBeInTheDocument()
    })
    const userSelect = document.getElementById('pm-username')
    // The handlers mock returns empty array or we use the usersList mock
    // In our `handlers.js` Users are `jperez` and `mgarcia`
    await user.selectOptions(userSelect, 'jperez')
    expect(userSelect.value).toBe('jperez')

    // 2. Click By Category
    await user.click(screen.getByText('By Category'))
    
    // 3. Select a category
    await waitFor(() => {
      expect(document.getElementById('pm-category')).toBeInTheDocument()
    })
    const catSelect = document.getElementById('pm-category')
    // In handlers.js we have category id=1 (AP_CAMBIUM)
    await user.selectOptions(catSelect, '1')
    expect(catSelect.value).toBe('1')

    // 4. Select a Radius Group
    const groupSelect = document.getElementById('pm-radius-group')
    // In handlers.js we have `helpdesk_group` and `admin_group`
    await user.selectOptions(groupSelect, 'admin_group')
    expect(groupSelect.value).toBe('admin_group')

    // 4.5 Fill Approved By
    const approvedByInput = document.getElementById('pm-approved-by')
    await user.type(approvedByInput, 'Test Approver')

    // 5. Submit the form
    const submitBtn = screen.getByRole('button', { name: /Create Mapping/i })
    await user.click(submitBtn)

    // Check for any errors
    await waitFor(() => {
      const errorMsg = screen.queryByText(/Error saving mapping/)
      if (errorMsg) console.error("Found error:", errorMsg.textContent)
      expect(screen.queryByRole('heading', { name: /Add Mapping/i })).not.toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('displays the category badge in the mapping table', async () => {
    const user = userEvent.setup()
    renderPrivilegeMap()

    // Select mgarcia which has a category mapping
    const userBtn = await screen.findByText('mgarcia')
    await user.click(userBtn)

    // The table should show the AP_CAMBIUM badge
    await waitFor(() => {
      // AP_CAMBIUM should appear as a category rule badge
      const badges = screen.getAllByText('AP_CAMBIUM')
      expect(badges.length).toBeGreaterThan(0)
    })
  })
})

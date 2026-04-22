import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import { http, HttpResponse } from 'msw'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import PrivilegeMapPage from '../pages/PrivilegeMap'
import { AuthProvider } from '../context/AuthContext'
import { ToastProvider } from '../context/ToastContext'
import { server } from './mocks/server'

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
          <ToastProvider>
            <PrivilegeMapPage />
          </ToastProvider>
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

  it('toggles between Segment, Exception and Legacy Category in Add Policy modal', async () => {
    const user = userEvent.setup()
    renderPrivilegeMap()
    
    // Open modal
    const addBtn = await screen.findByRole('button', { name: /Add Policy/i })
    await user.click(addBtn)
    
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /New Policy/i })).toBeInTheDocument()
      expect(screen.getByText('Network Segment')).toBeInTheDocument()
      expect(screen.getByText('IP or Range (Exception)')).toBeInTheDocument()
    })
    
    // Default is Network Segment
    // Wait for segments list to load
    await waitFor(() => {
      // The select should have the segments from the mock
      expect(screen.getByText(/Core Network/i)).toBeInTheDocument()
    })

    // Click IP or Range (Exception)
    await user.click(screen.getByText('IP or Range (Exception)'))
    
    // Should show Target Start IP
    await waitFor(() => {
      expect(screen.getByText('Start IP / Single IP')).toBeInTheDocument()
    })

    // Click help circle to show advanced options
    const advancedBtn = screen.getByText('Advanced / Legacy Compatibility');
    await user.click(advancedBtn);
    
    // Click Switch to Category Target
    const catTargetBtn = await screen.findByText('Switch to Category Target')
    await user.click(catTargetBtn)
    
    // Should have a dropdown for Categories
    await waitFor(() => {
      expect(screen.getByText('-- Select Category --')).toBeInTheDocument()
    })
  })

  it('can submit a category-based mapping', async () => {
    const user = userEvent.setup()
    const mappings = [
      {
        id: 1,
        username: 'jperez',
        nas_ip: '10.0.0.1',
        nas_category_id: null,
        nas_category_name: null,
        radius_group: 'admin_group',
        privilege_level: 'level-15',
        approved_by: 'superadmin',
        review_date: '2027-01-01',
        is_active: 1,
      },
      {
        id: 2,
        username: 'mgarcia',
        nas_ip: null,
        nas_category_id: 1,
        nas_category_name: 'AP_CAMBIUM',
        radius_group: 'helpdesk_group',
        privilege_level: 'level-5',
        approved_by: 'superadmin',
        review_date: '2028-01-01',
        is_active: 1,
      },
    ]
    let capturedPayload = null

    server.use(
      http.get('/api/privilege-map', () => HttpResponse.json(mappings)),
      http.post('/api/privilege-map/category', async ({ request }) => {
        capturedPayload = await request.json()
        mappings.push({
          id: 99,
          username: capturedPayload.username,
          nas_ip: null,
          nas_category_id: capturedPayload.nas_category_id,
          nas_category_name: 'AP_CAMBIUM',
          segment_id: null,
          segment_name: null,
          target_start_ip: null,
          target_end_ip: null,
          radius_group: capturedPayload.radius_group,
          privilege_level: capturedPayload.privilege_level,
          justification: capturedPayload.justification ?? null,
          approved_by: capturedPayload.approved_by,
          review_date: capturedPayload.review_date,
          is_active: capturedPayload.is_active,
        })
        return HttpResponse.json({ id: 99, ...capturedPayload }, { status: 201 })
      })
    )

    renderPrivilegeMap()
    
    // Open modal
    const addBtn = await screen.findByRole('button', { name: /Add Policy/i })
    await user.click(addBtn)
    
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /New Policy/i })).toBeInTheDocument()
    })

    // 1. Pick user
    await waitFor(() => {
      expect(document.getElementById('pm-username')).toBeInTheDocument()
    })
    const userSelect = document.getElementById('pm-username')
    await user.selectOptions(userSelect, 'jperez')
    expect(userSelect.value).toBe('jperez')

    // 2. Open advanced and click Category
    const advancedBtn = screen.getByText('Advanced / Legacy Compatibility');
    if (advancedBtn) await user.click(advancedBtn);
    
    const catTargetBtn = await screen.findByText('Switch to Category Target')
    await user.click(catTargetBtn)
    
    // 3. Select a category
    await waitFor(() => {
      expect(screen.getByText('-- Select Category --')).toBeInTheDocument()
    })
    const catSelect = screen.getByText('-- Select Category --').closest('select')
    await user.selectOptions(catSelect, '1')
    expect(catSelect.value).toBe('1')

    // 4. Select a Radius Group
    const groupSelect = document.getElementById('pm-radius-group')
    await user.selectOptions(groupSelect, 'admin_group')
    expect(groupSelect.value).toBe('admin_group')

    // 4.5 Fill Approved By
    const approvedByInput = document.getElementById('pm-approved-by')
    await user.type(approvedByInput, 'Test Approver')

    // 5. Submit the form
    const submitBtn = screen.getByRole('button', { name: /Save Policy/i })
    await user.click(submitBtn)

    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: /New Policy/i })).not.toBeInTheDocument()
    }, { timeout: 3000 })

    expect(capturedPayload).toEqual({
      username: 'jperez',
      nas_category_id: 1,
      radius_group: 'admin_group',
      approved_by: 'Test Approver',
      review_date: null,
      is_active: true,
    })

    const jperezButton = await screen.findByRole('button', { name: /jperez/i })
    await user.click(jperezButton)

    await waitFor(() => {
      expect(screen.getByText('AP_CAMBIUM')).toBeInTheDocument()
      expect(screen.getAllByText('admin_group').length).toBeGreaterThan(1)
      expect(screen.getByRole('heading', { name: 'jperez' })).toBeInTheDocument()
    })
  })

  it('displays the category badge in the mapping table', async () => {
    const user = userEvent.setup()
    renderPrivilegeMap()

    // Select mgarcia which has a category mapping
    const userBtn = await screen.findByText('mgarcia')
    await user.click(userBtn)

    // The table should show the AP_CAMBIUM badge
    await waitFor(() => {
      const badges = screen.getAllByText('AP_CAMBIUM')
      expect(badges.length).toBeGreaterThan(0)
    })
  })
})

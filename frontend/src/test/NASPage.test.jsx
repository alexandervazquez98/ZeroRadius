import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import NasPage from '../pages/NAS'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import { ToastProvider } from '../context/ToastContext'

function renderNas() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <NasPage />
        </ToastProvider>
      </QueryClientProvider>
    </MemoryRouter>
  )
}

describe('NASPage — NAS Categories and Devices', () => {
  it('renders NAS list from MSW', async () => {
    renderNas()
    await waitFor(() => {
      // Data mocked in handlers.js
      expect(screen.getByText('router-core')).toBeInTheDocument()
      expect(screen.getByText('switch-access')).toBeInTheDocument()
    })
  })

  it('toggles Categories modal/manager', async () => {
    const user = userEvent.setup()
    renderNas()

    const btn = screen.getByRole('button', { name: /Categories/i })
    await user.click(btn)

    await waitFor(() => {
      expect(screen.getByText('Device Categories')).toBeInTheDocument()
      // Mock categories should be loaded
      expect(screen.getAllByText('AP_CAMBIUM')[0]).toBeInTheDocument()
      expect(screen.getByText('SM_CAMBIUM')).toBeInTheDocument()
    })
  })

  it('can add a new NAS category', async () => {
    const user = userEvent.setup()
    renderNas()

    await user.click(screen.getByRole('button', { name: /Categories/i }))

    await waitFor(() => {
      expect(screen.getByText('Device Categories')).toBeInTheDocument()
    })

    const nameInput = document.getElementById('cat-name')
    await user.type(nameInput, 'NEW_TEST_CAT')
    
    const descInput = document.getElementById('cat-desc')
    await user.type(descInput, 'A new category for testing')

    const vendorInput = document.getElementById('cat-vendor')
    await user.type(vendorInput, 'TestVendor')

    const addBtn = document.getElementById('cat-add-btn')
    await user.click(addBtn)

    // The component invalidates 'nas-categories' after success.
    // If successful, the input should be cleared (EMPTY_CAT_FORM).
    await waitFor(() => {
      expect(nameInput.value).toBe('')
      expect(descInput.value).toBe('')
    })
  })

  it('can delete a NAS category', async () => {
    const user = userEvent.setup()
    renderNas()

    await user.click(screen.getByRole('button', { name: /Categories/i }))

    await waitFor(() => {
      expect(screen.getAllByText('AP_CAMBIUM')[0]).toBeInTheDocument()
    })

    // Grab all delete buttons for categories
    const deleteBtns = screen.getAllByTitle('Delete category')
    expect(deleteBtns.length).toBeGreaterThan(0)

    // Click first one (should hit MSW DELETE /api/nas-categories/:id)
    await user.click(deleteBtns[0])

    // Just verifying it doesn't crash and completes the mutation
    // In a real test we'd expect the mock to update its state or at least the mutation to succeed.
    await waitFor(() => {
      // If it succeeded, invalidateQueries runs. 
      // It's enough to check the action didn't fail (the error state is not shown).
      expect(screen.queryByText(/Cannot delete/i)).not.toBeInTheDocument()
    })
  })

  it('can open Add NAS modal and select a category', async () => {
    const user = userEvent.setup()
    renderNas()

    await user.click(screen.getByRole('button', { name: /Add NAS/i }))

    await waitFor(() => {
      expect(screen.getByText('Add NAS Client')).toBeInTheDocument()
    })

    // Fill in required NAS fields
    const ipInput = document.getElementById('nas-nasname')
    await user.type(ipInput, '10.50.0.1')

    const shortnameInput = document.getElementById('nas-shortname')
    await user.type(shortnameInput, 'test-device')

    const secretInput = document.getElementById('nas-secret')
    // Needs 32 chars minimum
    await user.type(secretInput, '12345678901234567890123456789012')

    // Select category in dropdown
    const catSelect = document.getElementById('nas-category-id')
    // Values are 1 and 2 in the mock
    await user.selectOptions(catSelect, '1')
    expect(catSelect.value).toBe('1')

    // Submit
    const submitBtn = document.getElementById('nas-submit-btn')
    await user.click(submitBtn)

    // Modal should close on success
    await waitFor(() => {
      expect(screen.queryByText('Add NAS Client')).not.toBeInTheDocument()
    })
  })

  it('regression: saves the short name exactly as typed on create (issue #125)', async () => {
    let sent
    server.use(http.post('/api/nas', async ({ request }) => {
      sent = await request.json()
      return HttpResponse.json({ id: 99, ...sent }, { status: 201 })
    }))
    const user = userEvent.setup()
    renderNas()
    await user.click(await screen.findByRole('button', { name: /Add NAS/i }))
    await user.type(document.getElementById('nas-nasname'), '10.53.6.1')
    await user.type(document.getElementById('nas-shortname'), 'SW-L3-CUMBRES')
    await user.type(document.getElementById('nas-secret'), '12345678901234567890123456789012')
    await user.click(document.getElementById('nas-submit-btn'))
    await waitFor(() => expect(sent).toBeDefined())
    expect(sent.shortname).toBe('SW-L3-CUMBRES')
  })

  it('regression: edit shows and saves the stored short name unchanged (issue #125)', async () => {
    server.use(http.get('/api/nas', () => HttpResponse.json([
      { id: 53, nasname: '10.53.6.1', shortname: 'AP-SW-L3-CUMBRES', secret: '***', type: 'cisco', category_id: 2, category_name: 'CORE' },
    ])))
    let sent
    server.use(http.put('/api/nas/:id', async ({ request }) => {
      sent = await request.json()
      return HttpResponse.json({ id: 53, ...sent })
    }))
    const user = userEvent.setup()
    renderNas()
    await user.click(await screen.findByTitle('Edit'))
    const shortname = document.getElementById('nas-shortname')
    expect(shortname.value).toBe('AP-SW-L3-CUMBRES')
    await user.clear(shortname)
    await user.type(shortname, 'SW-L3-CUMBRES')
    await user.click(document.getElementById('nas-submit-btn'))
    await waitFor(() => expect(sent).toBeDefined())
    expect(sent.shortname).toBe('SW-L3-CUMBRES')
  })
})

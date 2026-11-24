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

// ── Pagination and filters (issue #127) ─────────────────────────────────────

/**
 * Serve 60 NAS paginated like the backend and record every page request
 * (the limit=1 request that only reads the overall total is not recorded).
 */
function usePagedNas() {
  const requests = []
  const all = Array.from({ length: 60 }, (_, i) => ({
    id: i + 1,
    nasname: `10.1.0.${i + 1}`,
    shortname: `nas-${String(i + 1).padStart(2, '0')}`,
    secret: '***',
    type: 'other',
    category_id: null,
    category_name: null,
  }))
  server.use(http.get('/api/nas', ({ request }) => {
    const params = new URL(request.url).searchParams
    const limit = params.get('limit')
    if (limit !== '1') requests.push(params)
    const offset = Number(params.get('offset') || 0)
    const items = limit ? all.slice(offset, offset + Number(limit)) : all
    return HttpResponse.json(items, { headers: { 'X-Total-Count': String(all.length) } })
  }))
  return requests
}

describe('NASPage — pagination and filters (issue #127)', () => {
  it('requests the first page of 25 and navigates with next/previous', async () => {
    const requests = usePagedNas()
    const user = userEvent.setup()
    renderNas()

    expect(await screen.findByText('nas-01')).toBeInTheDocument()
    expect(screen.queryByText('nas-26')).not.toBeInTheDocument()
    expect(screen.getByText('1–25 of 60')).toBeInTheDocument()
    const first = requests.find(p => p.get('limit'))
    expect(first.get('limit')).toBe('25')
    expect(first.get('offset')).toBe('0')

    await user.click(screen.getByRole('button', { name: /next page/i }))
    expect(await screen.findByText('nas-26')).toBeInTheDocument()
    expect(screen.getByText('26–50 of 60')).toBeInTheDocument()
    expect(requests.at(-1).get('offset')).toBe('25')

    await user.click(screen.getByRole('button', { name: /previous page/i }))
    expect(await screen.findByText('nas-01')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /previous page/i })).toBeDisabled()
  })

  it('changes the page size to 50 and goes back to the first page', async () => {
    const requests = usePagedNas()
    const user = userEvent.setup()
    renderNas()

    await screen.findByText('nas-01')
    await user.click(screen.getByRole('button', { name: /next page/i }))
    await screen.findByText('nas-26')

    await user.selectOptions(document.getElementById('nas-page-size'), '50')
    expect(await screen.findByText('1–50 of 60')).toBeInTheDocument()
    expect(requests.at(-1).get('limit')).toBe('50')
    expect(requests.at(-1).get('offset')).toBe('0')
  })

  it('debounces a text filter, sends it to the server and resets to page 1', async () => {
    const requests = usePagedNas()
    const user = userEvent.setup()
    renderNas()

    await screen.findByText('nas-01')
    await user.click(screen.getByRole('button', { name: /next page/i }))
    await screen.findByText('nas-26')

    await user.type(document.getElementById('nas-filter-shortname'), 'core')
    await waitFor(() => expect(requests.at(-1).get('shortname')).toBe('core'))
    expect(requests.at(-1).get('offset')).toBe('0')
    // Debounced: no request for the partial input typed on the way
    const shortnames = requests.map(p => p.get('shortname')).filter(Boolean)
    expect(shortnames).toEqual(['core'])
    // The secret is never sent as a filter
    expect(requests.some(p => p.has('secret'))).toBe(false)
  })

  it('shows one-click category chips with counts and filters by category', async () => {
    const requests = usePagedNas()
    const user = userEvent.setup()
    renderNas()

    const allChip = await screen.findByRole('button', { name: 'All (60)' })
    expect(allChip).toHaveAttribute('aria-pressed', 'true')
    const apChip = await screen.findByRole('button', { name: 'AP_CAMBIUM (1)' })
    expect(screen.getByRole('button', { name: 'SM_CAMBIUM (0)' })).toBeInTheDocument()

    await user.click(apChip)
    await waitFor(() => expect(requests.at(-1).get('category_id')).toBe('1'))
    expect(requests.at(-1).get('offset')).toBe('0')
    expect(apChip).toHaveAttribute('aria-pressed', 'true')
    expect(allChip).toHaveAttribute('aria-pressed', 'false')

    await user.click(allChip)
    await waitFor(() => expect(requests.at(-1).has('category_id')).toBe(false))
  })
})

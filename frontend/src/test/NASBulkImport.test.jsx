import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import NasPage from '../pages/NAS'
import { AuthProvider } from '../context/AuthContext'
import { ToastProvider } from '../context/ToastContext'

function makeJwt(role) {
  const enc = (o) => btoa(JSON.stringify(o)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `${enc({ alg: 'HS256', typ: 'JWT' })}.${enc({ sub: 'u', role, exp: 9999999999 })}.sig`
}

function renderNas(role) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const utils = render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider initialToken={makeJwt(role)}>
          <ToastProvider>
            <NasPage />
          </ToastProvider>
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>
  )
  return { ...utils, queryClient }
}

// jsdom's Blob lacks arrayBuffer()/stream(); without them MSW never finishes
// reading a multipart FormData body and the upload request hangs.
function readBlob(blob) {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.readAsArrayBuffer(blob)
  })
}

beforeAll(() => {
  if (typeof Blob.prototype.arrayBuffer !== 'function') {
    Blob.prototype.arrayBuffer = function arrayBuffer() { return readBlob(this) }
  }
  if (typeof Blob.prototype.stream !== 'function') {
    Blob.prototype.stream = function stream() {
      const blob = this
      return new ReadableStream({
        async start(controller) {
          controller.enqueue(new Uint8Array(await readBlob(blob)))
          controller.close()
        },
      })
    }
  }
})

const csvFile = () => new File(['nasname,secret\n10.0.0.9,abc\n'], 'nas.csv', { type: 'text/csv' })

async function openBulk(user) {
  await user.click(await screen.findByRole('button', { name: /bulk import \(csv\)/i }))
}

describe('NAS page — bulk import (CSV)', () => {
  beforeEach(() => {
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock')
    globalThis.URL.revokeObjectURL = vi.fn()
  })

  it('hides the bulk import action for readonly users', async () => {
    renderNas('readonly')
    await screen.findByText('router-core')
    expect(screen.queryByRole('button', { name: /bulk import \(csv\)/i })).not.toBeInTheDocument()
  })

  it('shows the bulk import section for admin users with template download', async () => {
    const user = userEvent.setup()
    let templateRequested = false
    server.use(
      http.get('/api/nas/bulk/template', () => {
        templateRequested = true
        return new HttpResponse('nasname\n', { headers: { 'Content-Type': 'text/csv' } })
      }),
    )
    renderNas('admin')
    await openBulk(user)

    expect(screen.getByLabelText(/validate only \(dry run\)/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /download template/i }))
    await waitFor(() => expect(templateRequested).toBe(true))
  })

  it('sends dry_run=true when "Validate only" is checked and renders results with row errors', async () => {
    const user = userEvent.setup()
    let captured = null
    server.use(
      http.post('/api/nas/bulk/csv', ({ request }) => {
        captured = new URL(request.url).searchParams
        return HttpResponse.json({
          created: 2,
          updated: 1,
          dry_run: true,
          errors: [
            { row: 3, nasname: 'bad host', error: 'nasname: nasname must be a valid IP, CIDR, or hostname' },
            { row: 5, nasname: null, error: 'nasname is required' },
          ],
        })
      }),
    )
    const { queryClient } = renderNas('admin')
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    await openBulk(user)

    await user.click(screen.getByLabelText(/validate only \(dry run\)/i))
    await user.upload(screen.getByTestId('nas-bulk-file'), csvFile())
    await user.click(screen.getByRole('button', { name: /^validate$/i }))

    await waitFor(() => expect(captured?.get('dry_run')).toBe('true'))
    expect(await screen.findByText(/would create: 2/i)).toBeInTheDocument()
    expect(screen.getByText(/would update: 1/i)).toBeInTheDocument()
    expect(screen.getByText(/row 3 \(bad host\): nasname: nasname must be a valid IP/i)).toBeInTheDocument()
    expect(screen.getByText(/row 5: nasname is required/i)).toBeInTheDocument()
    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ['nas'] })
  })

  it('performs a real import with dry_run=false and refreshes the NAS list', async () => {
    const user = userEvent.setup()
    let captured = null
    server.use(
      http.post('/api/nas/bulk/csv', ({ request }) => {
        captured = new URL(request.url).searchParams
        return HttpResponse.json({ created: 4, updated: 0, errors: [], dry_run: false })
      }),
    )
    const { queryClient } = renderNas('superadmin')
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    await openBulk(user)

    await user.upload(screen.getByTestId('nas-bulk-file'), csvFile())
    await user.click(screen.getByRole('button', { name: /^import$/i }))

    await waitFor(() => expect(captured?.get('dry_run')).toBe('false'))
    expect(await screen.findByText(/created: 4/i)).toBeInTheDocument()
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['nas'] })
  })
})

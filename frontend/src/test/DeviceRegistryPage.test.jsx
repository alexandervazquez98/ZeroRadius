import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import DeviceRegistryPage from '../pages/DeviceRegistry'
import { AuthProvider } from '../context/AuthContext'
import { ToastProvider } from '../context/ToastContext'
import DeviceRegistryService from '../services/deviceRegistry'
import NasCategoriesService from '../services/nasCategoriesService'

vi.mock('../services/deviceRegistry', () => ({
  default: {
    getAll: vi.fn(),
    getStats: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    bulkCreate: vi.fn(),
    bulkCsv: vi.fn(),
    downloadBulkTemplate: vi.fn(),
  },
}))

vi.mock('../services/nasCategoriesService', () => ({
  default: {
    getAll: vi.fn(),
  },
}))

function makeJwt(role) {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  const body = btoa(JSON.stringify({ sub: 'test_admin', role, exp: 9999999999 })).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `${header}.${body}.fakesig`
}

function renderDeviceRegistry(role = 'admin') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider initialToken={makeJwt(role)}>
          <ToastProvider>
            <DeviceRegistryPage />
          </ToastProvider>
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>
  )
}

describe('DeviceRegistry page bulk import helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    DeviceRegistryService.getAll.mockResolvedValue([])
    DeviceRegistryService.getStats.mockResolvedValue({ total: 0, active: 0 })
    DeviceRegistryService.create.mockResolvedValue({})
    DeviceRegistryService.update.mockResolvedValue({})
    DeviceRegistryService.remove.mockResolvedValue({ ok: true })
    DeviceRegistryService.bulkCreate.mockResolvedValue({ created: 0, updated: 0, errors: [] })
    DeviceRegistryService.bulkCsv.mockResolvedValue({ created: 0, updated: 0, errors: [] })
    DeviceRegistryService.downloadBulkTemplate.mockResolvedValue(new Blob(['header'], { type: 'text/csv' }))

    NasCategoriesService.getAll.mockResolvedValue([{ id: 2, name: 'SM_CAMBIUM' }])

    globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock-template')
    globalThis.URL.revokeObjectURL = vi.fn()
    HTMLAnchorElement.prototype.click = vi.fn()
  })

  it('shows template download action and required columns including name', async () => {
    const user = userEvent.setup()
    renderDeviceRegistry('admin')

    await user.click(await screen.findByRole('button', { name: /bulk import/i }))

    expect(screen.getByText(/required columns: mac, nas_ip, name, description/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /descargar template/i })).toBeInTheDocument()
    expect(screen.getByText(/one per line: mac,nas_ip,name,description/i)).toBeInTheDocument()
  })

  it('calls downloadBulkTemplate when user clicks Descargar template', async () => {
    const user = userEvent.setup()
    renderDeviceRegistry('admin')

    await user.click(await screen.findByRole('button', { name: /bulk import/i }))
    await user.click(screen.getByRole('button', { name: /descargar template/i }))

    await waitFor(() => {
      expect(DeviceRegistryService.downloadBulkTemplate).toHaveBeenCalledTimes(1)
    })
  })
})

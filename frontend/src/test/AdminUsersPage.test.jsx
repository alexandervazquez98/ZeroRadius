import React from 'react'
import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import AdminUsers from '../pages/AdminUsers'
import { ToastProvider } from '../context/ToastContext'

const USERS = [
  { id: 1, username: 'root', email: null, is_active: 1, role: 'superadmin', force_password_change: 0 },
  { id: 2, username: 'ana', email: null, is_active: 1, role: 'helpdesk', force_password_change: 1 },
]

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AdminUsers />
      </ToastProvider>
    </QueryClientProvider>
  )
}

function mockList() {
  server.use(http.get('/api/admin-users', () => HttpResponse.json(USERS)))
}

describe('Admin users page — roles', () => {
  it('shows each account role in the table', async () => {
    mockList()
    renderPage()
    const row = (await screen.findByText('ana')).closest('tr')
    expect(within(row).getByText('helpdesk')).toBeInTheDocument()
    expect(within(screen.getByText('root').closest('tr')).getByText('superadmin')).toBeInTheDocument()
  })

  it('creates an account with the selected role', async () => {
    mockList()
    let body
    server.use(
      http.post('/api/admin-users', async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ id: 3, ...body, force_password_change: 1 })
      })
    )
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('button', { name: /add admin/i }))
    const dialog = screen.getByRole('heading', { name: /add new administrator/i }).closest('div')
    const roleSelect = within(dialog).getByLabelText(/role/i)
    expect(within(roleSelect).getAllByRole('option').map((o) => o.value)).toEqual([
      'superadmin', 'admin', 'helpdesk', 'auditor', 'readonly',
    ])
    expect(roleSelect).toHaveValue('admin')
    await user.type(within(dialog).getByLabelText(/username/i), 'nuevo')
    await user.type(within(dialog).getByLabelText(/password/i), 'Str0ng-Passw0rd!')
    await user.selectOptions(roleSelect, 'superadmin')
    await user.click(within(dialog).getByRole('button', { name: /create user/i }))
    await waitFor(() => expect(body).toBeDefined())
    expect(body).toEqual({ username: 'nuevo', password: 'Str0ng-Passw0rd!', is_active: 1, role: 'superadmin' })
  })

  it('changes the role of an existing account', async () => {
    mockList()
    let body
    server.use(
      http.put('/api/admin-users/2', async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ ...USERS[1], ...body })
      })
    )
    const user = userEvent.setup()
    renderPage()
    const row = (await screen.findByText('ana')).closest('tr')
    await user.click(within(row).getByTitle(/edit user/i))
    const roleSelect = screen.getByLabelText(/role/i)
    expect(roleSelect).toHaveValue('helpdesk')
    await user.selectOptions(roleSelect, 'auditor')
    await user.click(screen.getByRole('button', { name: /save changes/i }))
    await waitFor(() => expect(body).toBeDefined())
    expect(body).toEqual({ is_active: 1, role: 'auditor' })
  })

  it('does not send the role when only the status changes', async () => {
    mockList()
    let body
    server.use(
      http.put('/api/admin-users/2', async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ ...USERS[1], ...body })
      })
    )
    const user = userEvent.setup()
    renderPage()
    const row = (await screen.findByText('ana')).closest('tr')
    await user.click(within(row).getByTitle(/edit user/i))
    await user.selectOptions(screen.getByLabelText(/status/i), '0')
    await user.click(screen.getByRole('button', { name: /save changes/i }))
    await waitFor(() => expect(body).toBeDefined())
    expect(body).toEqual({ is_active: 0 })
  })

  it('shows the backend error when an update is rejected', async () => {
    mockList()
    server.use(
      http.put('/api/admin-users/1', () =>
        HttpResponse.json({ detail: 'Cannot demote or deactivate the last active superadmin.' }, { status: 400 })
      )
    )
    const user = userEvent.setup()
    renderPage()
    const row = (await screen.findByText('root')).closest('tr')
    await user.click(within(row).getByTitle(/edit user/i))
    await user.selectOptions(screen.getByLabelText(/role/i), 'admin')
    await user.click(screen.getByRole('button', { name: /save changes/i }))
    expect(await screen.findByText(/last active superadmin/i)).toBeInTheDocument()
  })
})

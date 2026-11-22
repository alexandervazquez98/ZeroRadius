/**
 * Tests para UsersPage (src/pages/Users.jsx).
 *
 * Cubre:
 * - Renderiza la lista de usuarios desde MSW mock
 * - Los usernames de los mock users aparecen en el DOM
 * - El botón "Add User" está presente (todos los roles en UsersPage lo ven,
 *   ya que UsersPage no tiene RBAC — el RBAC está en el router de la app)
 */

import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import UsersPage from '../pages/Users'
import { AuthProvider } from '../context/AuthContext'
import { ToastProvider } from '../context/ToastContext'

function makeJwt(role) {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  const body = btoa(JSON.stringify({ sub: 'testuser', role, exp: 9999999999 }))
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `${header}.${body}.fakesig`
}

function renderUsers(role = 'superadmin') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider initialToken={makeJwt(role)}>
          <ToastProvider>
            <UsersPage />
          </ToastProvider>
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>
  )
}

describe('UsersPage — renders user list from MSW', () => {
  it('shows mock users from API in the table', async () => {
    renderUsers('superadmin')

    // Los mock users retornados por MSW son jperez y mgarcia
    await waitFor(() => {
      expect(screen.getByText('jperez')).toBeInTheDocument()
      expect(screen.getByText('mgarcia')).toBeInTheDocument()
    })
  })

  it('renders Add User button', async () => {
    renderUsers('superadmin')

    await waitFor(() => {
      expect(screen.getByText(/add user/i)).toBeInTheDocument()
    })
  })

  it('renders table headers', async () => {
    renderUsers('admin')

    await waitFor(() => {
      expect(screen.getByText('Username')).toBeInTheDocument()
      expect(screen.getByText('Attribute')).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Issues #101 (part A) and #95: credentials are never shown or prefilled
// ---------------------------------------------------------------------------

import { fireEvent, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'

function captureUpdates() {
  const bodies = []
  server.use(
    http.put('/api/users/check/:id', async ({ request, params }) => {
      const body = await request.json()
      bodies.push({ id: params.id, body })
      return HttpResponse.json({ id: Number(params.id), ...body, value: null, has_password: true })
    })
  )
  return bodies
}

async function openEdit(rowText) {
  const cell = await screen.findByText(rowText)
  const row = cell.closest('tr')
  const buttons = within(row).getAllByRole('button')
  // Actions: JIT, Edit, Delete
  fireEvent.click(buttons[1])
  return screen.getByText('Edit User Attribute').closest('div').parentElement
}

describe('UsersPage — credentials are not exposed (#101, #95)', () => {
  it('masks password rows and still shows non-password values', async () => {
    renderUsers('superadmin')
    await screen.findByText('mgarcia')
    expect(screen.getAllByText('(password set)')).toHaveLength(2)
    expect(screen.getByText('01 Jan 2030 00:00')).toBeInTheDocument()
  })

  it('edit modal offers a password type selector and an empty password field', async () => {
    renderUsers('superadmin')
    const modal = await openEdit('MD5-Password')

    const typeSelect = within(modal).getByLabelText('Password type')
    expect(typeSelect.tagName).toBe('SELECT')
    expect(typeSelect).toHaveValue('MD5-Password')
    expect(within(typeSelect).getAllByRole('option').map(o => o.value)).toEqual([
      'Cleartext-Password',
      'MD5-Password',
    ])

    const password = within(modal).getByLabelText('New password')
    expect(password).toHaveValue('')
    expect(password).toHaveAttribute('type', 'password')
    expect(password).not.toBeRequired()
  })

  it('requires a new password when the password type changes', async () => {
    const updates = captureUpdates()
    renderUsers('superadmin')
    const modal = await openEdit('MD5-Password')

    fireEvent.change(within(modal).getByLabelText('Password type'), {
      target: { value: 'Cleartext-Password' },
    })
    const password = within(modal).getByLabelText('New password')
    expect(password).toBeRequired()

    fireEvent.change(password, { target: { value: 'new-pw' } })
    fireEvent.click(within(modal).getByText('Save Changes'))

    await waitFor(() => expect(updates).toHaveLength(1))
    expect(updates[0].body).toEqual({
      username: 'mgarcia',
      attribute: 'Cleartext-Password',
      op: ':=',
      value: 'new-pw',
    })
  })

  it('keeps the current password when the field is left blank', async () => {
    const updates = captureUpdates()
    renderUsers('superadmin')
    const modal = await openEdit('MD5-Password')

    fireEvent.change(within(modal).getByLabelText('Username'), {
      target: { value: 'mgarcia2' },
    })
    fireEvent.click(within(modal).getByText('Save Changes'))

    await waitFor(() => expect(updates).toHaveLength(1))
    expect(updates[0].body).toEqual({ username: 'mgarcia2', attribute: 'MD5-Password', op: ':=' })
  })

  it('non-password attributes keep the free-text attribute and value fields', async () => {
    const updates = captureUpdates()
    renderUsers('superadmin')
    const modal = await openEdit('Expiration')

    expect(within(modal).getByLabelText('Attribute').tagName).toBe('INPUT')
    const value = within(modal).getByLabelText('Value')
    expect(value).toHaveValue('01 Jan 2030 00:00')

    fireEvent.change(value, { target: { value: '02 Feb 2031 00:00' } })
    fireEvent.click(within(modal).getByText('Save Changes'))

    await waitFor(() => expect(updates).toHaveLength(1))
    expect(updates[0].body).toEqual({
      username: 'lruiz',
      attribute: 'Expiration',
      op: ':=',
      value: '02 Feb 2031 00:00',
    })
  })
})

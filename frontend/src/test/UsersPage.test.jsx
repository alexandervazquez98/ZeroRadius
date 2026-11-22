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
  fireEvent.click(within(row).getByTitle('Edit'))
  return screen.getByText('Edit User Attribute').closest('div').parentElement
}

describe('UsersPage — credentials are not exposed (#101, #95)', () => {
  it('masks password rows and still shows non-password values', async () => {
    renderUsers('superadmin')
    await screen.findByText('mgarcia')
    expect(screen.getAllByText('(password set)')).toHaveLength(2)
    expect(screen.getByText('01 Jan 2030 00:00')).toBeInTheDocument()
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

function captureResets(response = {}) {
  const bodies = []
  server.use(
    http.post('/api/users/check/:id/reset-password', async ({ request, params }) => {
      const body = await request.json()
      bodies.push({ id: params.id, body })
      return HttpResponse.json({
        id: Number(params.id),
        username: 'mgarcia',
        attribute: body.password_type,
        generated_password: null,
        ...response,
      })
    })
  )
  return bodies
}

async function openReset(rowText) {
  const cell = await screen.findByText(rowText)
  const row = cell.closest('tr')
  fireEvent.click(within(row).getByTitle('Reset password'))
  return screen.getByText('Reset password', { selector: 'h3' }).closest('div').parentElement
}

describe('UsersPage — admin password reset (#101 B)', () => {
  it('edit modal no longer edits the password or its type', async () => {
    renderUsers('superadmin')
    const modal = await openEdit('MD5-Password')
    expect(within(modal).queryByLabelText('New password')).toBeNull()
    expect(within(modal).queryByLabelText('Password type')).toBeNull()
    expect(within(modal).getByText(/Use Reset password to change it/)).toBeInTheDocument()
  })

  it('offers reset only on password rows', async () => {
    renderUsers('superadmin')
    await screen.findByText('lruiz')
    expect(screen.getAllByTitle('Reset password')).toHaveLength(2)
    const expirationRow = screen.getByText('Expiration').closest('tr')
    expect(within(expirationRow).queryByTitle('Reset password')).toBeNull()
  })

  it('sets a typed password with the chosen type', async () => {
    const resets = captureResets()
    renderUsers('superadmin')
    const modal = await openReset('MD5-Password')

    const typeSelect = within(modal).getByLabelText('Password type')
    expect(typeSelect).toHaveValue('MD5-Password')
    expect(within(typeSelect).getAllByRole('option').map(o => o.value)).toEqual([
      'Cleartext-Password',
      'MD5-Password',
      'NT-Password',
    ])
    fireEvent.change(typeSelect, { target: { value: 'NT-Password' } })
    expect(within(modal).getByText(/NT-Password works with PAP and MS-CHAPv2/)).toBeInTheDocument()

    const password = within(modal).getByLabelText('New password')
    expect(password).toHaveAttribute('type', 'password')
    fireEvent.change(password, { target: { value: 'new-pw' } })
    fireEvent.click(within(modal).getByRole('button', { name: 'Set password' }))

    await waitFor(() => expect(resets).toHaveLength(1))
    expect(resets[0]).toEqual({ id: '2', body: { password: 'new-pw', password_type: 'NT-Password' } })
    await waitFor(() => expect(screen.queryByText('Reset password', { selector: 'h3' })).toBeNull())
  })

  it('shows a generated password once', async () => {
    const resets = captureResets({ attribute: 'MD5-Password', generated_password: 'Gen-Once-123456789' })
    renderUsers('superadmin')
    let modal = await openReset('MD5-Password')

    fireEvent.click(within(modal).getByRole('button', { name: 'Generate password' }))
    await waitFor(() => expect(resets).toHaveLength(1))
    expect(resets[0].body).toEqual({ generate: true, password_type: 'MD5-Password' })
    expect(await within(modal).findByText('Gen-Once-123456789')).toBeInTheDocument()
    expect(within(modal).getByText(/will not be shown again/)).toBeInTheDocument()

    fireEvent.click(within(modal).getByRole('button', { name: 'Done' }))
    expect(screen.queryByText('Gen-Once-123456789')).toBeNull()

    modal = await openReset('MD5-Password')
    expect(within(modal).queryByText('Gen-Once-123456789')).toBeNull()
  })
})

describe('UsersPage — reset defaults to a settable type', () => {
  it('offers only settable types and defaults legacy or lowercase types sensibly', async () => {
    server.use(
      http.get('/api/users', () =>
        HttpResponse.json([
          { id: 7, username: 'legacy', attribute: 'Crypt-Password', op: ':=', value: null, has_password: true },
          { id: 8, username: 'lower', attribute: 'nt-password', op: ':=', value: null, has_password: true },
        ])
      )
    )
    renderUsers('superadmin')

    let modal = await openReset('Crypt-Password')
    let typeSelect = within(modal).getByLabelText('Password type')
    expect(within(typeSelect).getAllByRole('option').map(o => o.value)).toEqual([
      'Cleartext-Password',
      'MD5-Password',
      'NT-Password',
    ])
    expect(typeSelect).toHaveValue('NT-Password')
    fireEvent.click(within(modal).getByLabelText('Close'))

    modal = await openReset('nt-password')
    typeSelect = within(modal).getByLabelText('Password type')
    expect(within(typeSelect).getAllByRole('option')).toHaveLength(3)
    expect(typeSelect).toHaveValue('NT-Password')
  })
})

describe('UsersPage — self-service setup link (#101 C)', () => {
  it('generates a one-time URL from the reset modal', async () => {
    const posts = []
    server.use(
      http.post('/api/users/check/:id/setup-link', async ({ request, params }) => {
        posts.push({ id: params.id, body: await request.json() })
        return HttpResponse.json({
          id: Number(params.id), username: 'mgarcia', attribute: 'NT-Password',
          token: 'TOKEN-abc_123', expires_at: '2030-01-04T10:00:00',
        })
      })
    )
    renderUsers('superadmin')
    let modal = await openReset('MD5-Password')
    fireEvent.change(within(modal).getByLabelText('Password type'), { target: { value: 'NT-Password' } })
    fireEvent.click(within(modal).getByRole('button', { name: 'Generate setup link' }))

    await waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0]).toEqual({ id: '2', body: { password_type: 'NT-Password' } })
    const url = `${window.location.origin}/setup-password/TOKEN-abc_123`
    expect(await within(modal).findByText(url)).toBeInTheDocument()
    expect(within(modal).getByText(/current password is blocked until the link is used/i)).toBeInTheDocument()
    expect(within(modal).getByText(/will not be shown again/)).toBeInTheDocument()

    fireEvent.click(within(modal).getByRole('button', { name: 'Done' }))
    expect(screen.queryByText(url)).toBeNull()
  })

  it('shows whether each setup link is still valid', async () => {
    server.use(
      http.get('/api/users', () =>
        HttpResponse.json([
          { id: 1, username: 'pend', attribute: 'NT-Password', op: ':=', value: null, has_password: true,
            setup_link: { status: 'pending', created_by: 'admin', created_at: '2030-01-01T10:00:00', expires_at: '2030-01-04T10:00:00', used_at: null } },
          { id: 2, username: 'exp', attribute: 'NT-Password', op: ':=', value: null, has_password: true,
            setup_link: { status: 'expired', created_by: 'claude', created_at: '2020-01-01T10:00:00', expires_at: '2020-01-04T10:00:00', used_at: null } },
          { id: 3, username: 'done', attribute: 'NT-Password', op: ':=', value: null, has_password: true,
            setup_link: { status: 'used', created_by: 'admin', created_at: '2030-01-01T10:00:00', expires_at: '2030-01-04T10:00:00', used_at: '2030-01-02T09:00:00' } },
          { id: 4, username: 'plain', attribute: 'NT-Password', op: ':=', value: null, has_password: true, setup_link: null },
        ])
      )
    )
    renderUsers('superadmin')
    const pending = (await screen.findByText('pend')).closest('tr')
    expect(within(pending).getByText(/Setup link pending/)).toBeInTheDocument()
    expect(within(pending).getByText(/by admin/)).toBeInTheDocument()
    expect(within(pending).getByText(/valid until/)).toBeInTheDocument()

    const expired = screen.getByText('exp').closest('tr')
    expect(within(expired).getByText(/Setup link expired/)).toBeInTheDocument()
    expect(within(expired).getByText(/by claude/)).toBeInTheDocument()

    const used = screen.getByText('done').closest('tr')
    expect(within(used).getByText(/Set via link/)).toBeInTheDocument()

    const plain = screen.getByText('plain').closest('tr')
    expect(within(plain).queryByText(/Setup link/)).toBeNull()
  })
})

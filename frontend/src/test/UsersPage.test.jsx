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

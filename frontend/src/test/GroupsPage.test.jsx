/**
 * Tests para GroupsPage (src/pages/Groups.jsx → PoliciesPage).
 *
 * GroupsPage es un wrapper de PoliciesPage que muestra la lista de políticas/grupos.
 * Cubre:
 * - Renderiza el título "Policies"
 * - Renderiza el botón "Create Policy"
 * - Los grupos del mock (helpdesk_group, admin_group) aparecen en la tabla
 */

import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import GroupsPage from '../pages/Groups'
import { AuthProvider } from '../context/AuthContext'

function makeJwt(role = 'superadmin') {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  const body = btoa(JSON.stringify({ sub: 'testuser', role, exp: 9999999999 }))
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `${header}.${body}.fakesig`
}

function renderGroups(role = 'superadmin') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider initialToken={makeJwt(role)}>
          <GroupsPage />
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>
  )
}

describe('GroupsPage — rendering', () => {
  it('renders the Policies heading', async () => {
    renderGroups()
    await waitFor(() => {
      expect(screen.getByText('Policies')).toBeInTheDocument()
    })
  })

  it('renders Create Policy button', async () => {
    renderGroups()
    await waitFor(() => {
      expect(screen.getByText(/create policy/i)).toBeInTheDocument()
    })
  })

  it('renders mock group names from API', async () => {
    renderGroups()
    // MSW /api/groups/list retorna helpdesk_group y admin_group
    await waitFor(() => {
      expect(screen.getByText('helpdesk_group')).toBeInTheDocument()
      expect(screen.getByText('admin_group')).toBeInTheDocument()
    })
  })
})

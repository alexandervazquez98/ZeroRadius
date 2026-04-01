/**
 * Tests para GroupsPage (src/pages/Groups.jsx → PoliciesPage).
 *
 * GroupsPage es un wrapper de PoliciesPage que muestra la lista de Macros/NAC Policies.
 * Cubre:
 * - Renderiza el título "Macro Policy Builder"
 * - Renderiza el botón "Nueva Macro"
 * - Muestra mensaje cuando no hay macros definidas
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
  it('renders the Macro Policy Builder heading', async () => {
    renderGroups()
    await waitFor(() => {
      expect(screen.getByText('Macro Policy Builder')).toBeInTheDocument()
    })
  })

  it('renders Nueva Macro button', async () => {
    renderGroups()
    await waitFor(() => {
      expect(screen.getByText('Nueva Macro')).toBeInTheDocument()
    })
  })

  it('renders empty state when no macros defined', async () => {
    renderGroups()
    // MSW /api/iam-nac/macros retorna [] (vacío)
    await waitFor(() => {
      expect(screen.getByText(/No hay Macros definidas/i)).toBeInTheDocument()
    })
  })
})

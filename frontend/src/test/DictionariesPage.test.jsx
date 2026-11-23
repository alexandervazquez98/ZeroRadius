/**
 * DictionariesPage — write actions follow the API role rules.
 * Upload, rename, edit and delete restart RADIUS and are limited to
 * superadmin/admin (backend/app/routers/dictionary.py). Every role can read.
 */
import React from 'react'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { describe, it, expect, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import DictionariesPage from '../pages/Dictionaries'
import { AuthProvider } from '../context/AuthContext'

function makeJwt(role) {
  const enc = (o) => btoa(JSON.stringify(o)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `${enc({ alg: 'HS256', typ: 'JWT' })}.${enc({ sub: 'testuser', role, exp: 9999999999 })}.fakesig`
}

function renderPage(role) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        <AuthProvider initialToken={makeJwt(role)}>
          <DictionariesPage />
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>
  )
}

const card = async () => (await screen.findByTitle('Cambium_450i')).closest('div.group')

beforeEach(() => {
  server.use(
    http.get('/api/dictionary/files', () => HttpResponse.json(['Cambium_450i'])),
    http.get('/api/dictionary/content/:filename', () =>
      HttpResponse.json({ content: 'VENDOR Motorola 161\n' })
    )
  )
})

describe('DictionariesPage — actions follow the API role rules', () => {
  it.each(['readonly', 'auditor', 'helpdesk'])('%s can view but not change dictionaries', async (role) => {
    renderPage(role)
    const c = await card()
    expect(screen.queryByText('Upload Dictionary')).toBeNull()
    expect(screen.queryByText('FreeRADIUS Logs')).toBeNull()
    expect(within(c).queryByTitle('Rename')).toBeNull()
    expect(within(c).queryByTitle('Delete')).toBeNull()

    fireEvent.click(within(c).getByTitle('View / Edit content'))
    expect(await screen.findByDisplayValue(/VENDOR Motorola 161/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /save/i })).toBeNull()
  })

  it.each(['admin', 'superadmin'])('%s keeps upload, rename, delete, logs and save', async (role) => {
    renderPage(role)
    const c = await card()
    expect(screen.getByText('Upload Dictionary')).toBeInTheDocument()
    expect(screen.getByText('FreeRADIUS Logs')).toBeInTheDocument()
    expect(within(c).getByTitle('Rename')).toBeInTheDocument()
    expect(within(c).getByTitle('Delete')).toBeInTheDocument()

    fireEvent.click(within(c).getByTitle('View / Edit content'))
    expect(await screen.findByDisplayValue(/VENDOR Motorola 161/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument()
  })
})

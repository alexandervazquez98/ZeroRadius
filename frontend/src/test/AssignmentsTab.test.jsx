/**
 * AssignmentsTab (access policies) — #97.
 * Spec: odd/tasks/access-policies-bulk-edit.md (S1-S6).
 */
import React from 'react'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import AssignmentsTab from '../components/access-policies/AssignmentsTab'
import { AuthProvider } from '../context/AuthContext'
import { ToastProvider } from '../context/ToastContext'

function makeJwt(role) {
  const enc = (o) => btoa(JSON.stringify(o)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `${enc({ alg: 'HS256', typ: 'JWT' })}.${enc({ sub: 'tester', role, exp: 9999999999 })}.sig`
}

const row = (over) => ({
  id: 1, username: 'alice', nas_ip: null, calling_station_id: null, nas_category_id: null,
  nas_category_name: null, segment_id: null, segment_name: null, cir_id: null,
  target_start_ip: null, target_end_ip: null, nas_identifier: null, nas_vendor: 'Cisco',
  radius_group: 'net-admins', privilege_level: '15', justification: null, approved_by: 'tester',
  review_date: null, is_active: 1, created_at: null, updated_at: null, days_until_review: null,
  ...over,
})

const ASSIGNMENTS = [
  row({ id: 11, nas_ip: '10.0.0.1', cir_id: 5, nas_identifier: 'sw-core-1' }),
  row({ id: 12, nas_ip: '10.0.0.2' }),
  row({ id: 13, nas_ip: '10.0.0.3', is_active: 0 }),
  row({ id: 21, username: 'bob', nas_ip: '10.0.0.9' }),
]

function useApi({ assignments = ASSIGNMENTS } = {}) {
  const calls = { put: [], patch: [], bulkDelete: [] }
  server.use(
    http.get('/api/access-policies/assignments', () => HttpResponse.json(assignments)),
    http.get('/api/nas-categories', () => HttpResponse.json([{ id: 3, name: 'Switches' }])),
    http.get('/api/network-segments', () => HttpResponse.json([])),
    http.get('/api/groups/list', () =>
      HttpResponse.json([{ groupname: 'net-admins' }, { groupname: 'net-read' }])
    ),
    http.put('/api/access-policies/assignments/:id', async ({ request, params }) => {
      const body = await request.json()
      calls.put.push({ id: params.id, body })
      return HttpResponse.json(row({ id: Number(params.id), ...body }))
    }),
    http.patch('/api/access-policies/assignments/bulk', async ({ request }) => {
      const body = await request.json()
      calls.patch.push(body)
      return HttpResponse.json(body.ids.map(id => row({ id })))
    }),
    http.post('/api/access-policies/assignments/bulk-delete', async ({ request }) => {
      const body = await request.json()
      calls.bulkDelete.push(body)
      return HttpResponse.json({ deleted: body.ids.length })
    })
  )
  return calls
}

function renderTab(role = 'superadmin') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider initialToken={makeJwt(role)}>
          <ToastProvider>
            <AssignmentsTab />
          </ToastProvider>
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>
  )
}

async function selectUser(name) {
  fireEvent.click(await screen.findByText(name, { selector: 'button *, button' }))
  await screen.findByText(name, { selector: 'h3' })
}

describe('AssignmentsTab — single edit (#97 S6)', () => {
  it('keeps cir_id and nas_identifier when editing a row', async () => {
    const calls = useApi()
    renderTab()
    await selectUser('alice')
    const target = screen.getByText('10.0.0.1').closest('tr')
    fireEvent.click(within(target).getByTitle('Edit'))
    fireEvent.click(await screen.findByText('Save Policy'))

    await waitFor(() => expect(calls.put).toHaveLength(1))
    expect(calls.put[0].id).toBe('11')
    expect(calls.put[0].body).toMatchObject({ cir_id: 5, nas_identifier: 'sw-core-1', nas_ip: '10.0.0.1' })
  })
})

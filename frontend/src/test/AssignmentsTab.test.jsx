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

import { vi } from 'vitest'

async function selectAll() {
  fireEvent.click(await screen.findByLabelText('Select all policies'))
}

describe('AssignmentsTab — bulk actions (#97 S1-S3)', () => {
  it('selects all policies of the user and shows the bulk bar', async () => {
    useApi()
    renderTab()
    await selectUser('alice')
    expect(screen.queryByText(/selected/)).toBeNull()
    await selectAll()
    expect(screen.getByText('3 selected')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Select policy 12'))
    expect(screen.getByText('2 selected')).toBeInTheDocument()
  })

  it.each([
    ['group', () => {
      fireEvent.change(screen.getByLabelText('Bulk RADIUS group'), { target: { value: 'net-read' } })
      fireEvent.click(screen.getByRole('button', { name: 'Apply group' }))
    }, { radius_group: 'net-read' }],
    ['privilege', () => {
      fireEvent.change(screen.getByLabelText('Bulk privilege level'), { target: { value: '1' } })
      fireEvent.click(screen.getByRole('button', { name: 'Apply privilege' }))
    }, { privilege_level: '1' }],
    ['review date', () => {
      fireEvent.change(screen.getByLabelText('Bulk review date'), { target: { value: '2031-03-15' } })
      fireEvent.click(screen.getByRole('button', { name: 'Apply review date' }))
    }, { review_date: '2031-03-15' }],
    ['deactivate', () => fireEvent.click(screen.getByRole('button', { name: 'Deactivate' })), { is_active: 0 }],
    ['activate', () => fireEvent.click(screen.getByRole('button', { name: 'Activate' })), { is_active: 1 }],
  ])('applies %s to the selected policies', async (_name, act, change) => {
    const calls = useApi()
    renderTab('admin')
    await selectUser('alice')
    await selectAll()
    act()
    await waitFor(() => expect(calls.patch).toHaveLength(1))
    expect(calls.patch[0]).toEqual({ ids: [11, 12, 13], ...change })
    await waitFor(() => expect(screen.queryByText(/selected/)).toBeNull())
  })

  it('lets only superadmin delete the selection', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const calls = useApi()
    renderTab('superadmin')
    await selectUser('alice')
    await selectAll()
    fireEvent.click(screen.getByRole('button', { name: 'Delete selected' }))
    await waitFor(() => expect(calls.bulkDelete).toHaveLength(1))
    expect(calls.bulkDelete[0]).toEqual({ ids: [11, 12, 13] })
    confirm.mockRestore()
  })

  it('hides bulk delete for admin', async () => {
    useApi()
    renderTab('admin')
    await selectUser('alice')
    await selectAll()
    expect(screen.queryByRole('button', { name: 'Delete selected' })).toBeNull()
  })

  it('clears the selection when switching user', async () => {
    useApi()
    renderTab()
    await selectUser('alice')
    await selectAll()
    await selectUser('bob')
    expect(screen.queryByText(/selected/)).toBeNull()
  })
})

describe('AssignmentsTab — category hint (#97 S4)', () => {
  it('offers a category target when many NAS are picked one by one', async () => {
    useApi()
    server.use(
      http.get('/api/nas', () =>
        HttpResponse.json([
          { id: 1, nasname: '10.0.1.1', shortname: 'a', type: 'cisco' },
          { id: 2, nasname: '10.0.1.2', shortname: 'b', type: 'cisco' },
          { id: 3, nasname: '10.0.1.3', shortname: 'c', type: 'cisco' },
        ])
      )
    )
    renderTab()
    await selectUser('alice')
    const addButtons = screen.getAllByRole('button', { name: /Add Policy/ })
    fireEvent.click(addButtons[addButtons.length - 1])
    expect(screen.getByRole('button', { name: 'NAS Category' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Specific NAS / IPs (Legacy)' }))
    for (const ip of ['10.0.1.1', '10.0.1.2']) fireEvent.click(await screen.findByText(ip))
    expect(screen.queryByText(/one policy per NAS/)).toBeNull()
    fireEvent.click(screen.getByText('10.0.1.3'))
    expect(screen.getByText(/one policy per NAS/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Use a NAS category' }))
    expect(await screen.findByRole('option', { name: 'Switches' })).toBeInTheDocument()
  })
})

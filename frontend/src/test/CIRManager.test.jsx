import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'

import { AuthProvider } from '../context/AuthContext'
import { ToastProvider } from '../context/ToastContext'
import { server } from './mocks/server'
import CIRManager from '../pages/CIRManager'

function makeJwt(role) {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  const body = btoa(JSON.stringify({ sub: 'testuser', role, exp: 9999999999 }))
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `${header}.${body}.fakesig`
}

function renderCIR(role = 'superadmin') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider initialToken={makeJwt(role)}>
          <ToastProvider>
            <CIRManager />
          </ToastProvider>
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>
  )
}

describe('CIRManager', () => {
  it('creates a profile from empty state and refreshes list', async () => {
    const user = userEvent.setup()

    let created = false
    server.use(
      http.get('/api/cir/profiles', () => {
        if (!created) return HttpResponse.json([])
        return HttpResponse.json([
          {
            name: 'gold',
            groupname: 'cir_gold',
            downlink_high: '12000000',
            uplink_high: '6000000',
            downlink_low: '4000000',
            uplink_low: '2000000',
          },
        ])
      }),
      http.post('/api/cir/profiles', async ({ request }) => {
        const payload = await request.json()
        created = true
        return HttpResponse.json({ ...payload, groupname: 'cir_gold' }, { status: 201 })
      })
    )

    renderCIR('superadmin')

    expect(await screen.findByText('No CIR profiles yet')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Profile Name'), 'gold')
    await user.type(screen.getByLabelText('Downlink High'), '12000000')
    await user.type(screen.getByLabelText('Uplink High'), '6000000')
    await user.type(screen.getByLabelText('Downlink Low'), '4000000')
    await user.type(screen.getByLabelText('Uplink Low'), '2000000')
    await user.click(screen.getByRole('button', { name: 'Save Profile' }))

    await waitFor(() => {
      expect(screen.getAllByText('gold').length).toBeGreaterThan(0)
    })
  })

  it('renders inline validation without losing input', async () => {
    const user = userEvent.setup()
    renderCIR('superadmin')

    await user.type(screen.getByLabelText('Profile Name'), 'gold')
    await user.click(screen.getByRole('button', { name: 'Save Profile' }))

    expect(await screen.findByText('Downlink High is required')).toBeInTheDocument()
    expect(screen.getByLabelText('Profile Name')).toHaveValue('gold')
  })

  it('shows replacement confirmation for same assignment target', async () => {
    const user = userEvent.setup()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

    server.use(
      http.get('/api/cir/profiles', () =>
        HttpResponse.json([
          {
            name: 'gold',
            groupname: 'cir_gold',
            downlink_high: '12000000',
            uplink_high: '6000000',
            downlink_low: '4000000',
            uplink_low: '2000000',
          },
        ])
      ),
      http.get('/api/cir/assignments', () =>
        HttpResponse.json([
          {
            id: 91,
            username: 'jperez',
            nas_ip: '10.0.0.10',
            radius_group: 'cir_gold',
            is_active: 1,
          },
        ])
      ),
      http.post('/api/cir/assignments', async ({ request }) => {
        const payload = await request.json()
        return HttpResponse.json({ id: 91, ...payload }, { status: 201 })
      })
    )

    renderCIR('admin')

    await user.type(await screen.findByLabelText('Assign Username'), 'jperez')
    await user.selectOptions(screen.getByLabelText('Target Type'), 'nas_ip')
    await user.type(screen.getByLabelText('Target NAS IP'), '10.0.0.10')
    await user.selectOptions(screen.getByLabelText('CIR Profile'), 'cir_gold')
    await user.click(screen.getByRole('button', { name: 'Save Assignment' }))

    expect(confirmSpy).toHaveBeenCalledTimes(1)
    confirmSpy.mockRestore()
  })

  it('renders preview success and explicit no-match message', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('/api/cir/preview', async ({ request }) => {
        const payload = await request.json()
        if (payload.username === 'missing') {
          return HttpResponse.json({
            resolution_path: 'none',
            mapping: null,
            profile: null,
            trace: [
              { step: 'exact_or_range', matched: false },
              { step: 'segment', matched: false },
              { step: 'category', matched: false },
            ],
          })
        }

        return HttpResponse.json({
          resolution_path: 'exact',
          mapping: { username: 'jperez', nas_ip: '10.0.0.10', radius_group: 'cir_gold' },
          profile: {
            name: 'gold',
            groupname: 'cir_gold',
            downlink_high: '12000000',
            uplink_high: '6000000',
            downlink_low: '4000000',
            uplink_low: '2000000',
          },
          trace: [
            { step: 'exact_or_range', matched: true },
            { step: 'segment', matched: false },
            { step: 'category', matched: false },
          ],
        })
      })
    )

    renderCIR('auditor')

    await user.type(await screen.findByLabelText('Preview Username'), 'jperez')
    await user.type(screen.getByLabelText('Preview NAS IP'), '10.0.0.10')
    await user.click(screen.getByRole('button', { name: 'Run Preview' }))

    expect(await screen.findByText('Winning profile: gold')).toBeInTheDocument()

    await user.clear(screen.getByLabelText('Preview Username'))
    await user.type(screen.getByLabelText('Preview Username'), 'missing')
    await user.click(screen.getByRole('button', { name: 'Run Preview' }))

    expect(await screen.findByText('No CIR match for this request.')).toBeInTheDocument()
  })

  it('enforces read-only behavior for auditor role', async () => {
    renderCIR('auditor')

    expect(await screen.findByText('CIR Manager')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save Profile' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save Assignment' })).not.toBeInTheDocument()
  })

  it('shows retry state on fetch failure', async () => {
    const user = userEvent.setup()
    let fail = true

    server.use(
      http.get('/api/cir/profiles', () => {
        if (fail) {
          return HttpResponse.json({ detail: 'boom' }, { status: 500 })
        }
        return HttpResponse.json([])
      })
    )

    renderCIR('superadmin')
    expect(await screen.findByText('Unable to load CIR data.')).toBeInTheDocument()

    fail = false
    await user.click(screen.getByRole('button', { name: 'Retry' }))

    await waitFor(() => {
      expect(screen.getByText('No CIR profiles yet')).toBeInTheDocument()
    })
  })

  it('keeps v1 boundary with profile/assignment/preview only controls', async () => {
    renderCIR('superadmin')

    expect(await screen.findByText('CIR Manager')).toBeInTheDocument()
    expect(screen.getByText('v1 boundary: profile, assignment and preview only')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /export/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /report/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /analytics/i })).not.toBeInTheDocument()
  })
})

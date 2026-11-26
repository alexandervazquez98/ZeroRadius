/**
 * SyslogDashboard — 8-hour window and keyset pagination (#136).
 * Spec: odd/tasks/syslog-query-scale.md (S1, S2).
 */
import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import SyslogDashboard from '../pages/SyslogDashboard'

const event = (id, message) => ({
  id,
  received_at: '2026-11-25T17:00:00',
  device_ip: '10.3.152.213',
  facility: 16,
  severity: 5,
  program: 'CANOPY',
  message,
  previous_hash: 'a',
  hash: 'b',
})

const PAGE = {
  start_date: '2026-11-25T10:00:00',
  end_date: '2026-11-25T18:00:00',
  max_range_hours: 8,
}

function renderPage(handler) {
  const requests = []
  server.use(
    http.get('/api/syslog/nas-status', () =>
      HttpResponse.json({ threshold_hours: 24, total: 0, silent_count: 0, reporting_count: 0, devices: [] })
    ),
    http.get('/api/syslog', ({ request }) => {
      const params = new URL(request.url).searchParams
      requests.push(params)
      return handler(params)
    })
  )
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <SyslogDashboard />
    </QueryClientProvider>
  )
  return requests
}

const twoPages = (params) =>
  params.get('cursor') === 'c1'
    ? HttpResponse.json({ ...PAGE, events: [event(1, 'older event')], has_more: false, next_cursor: null })
    : HttpResponse.json({ ...PAGE, events: [event(2, 'newest event')], has_more: true, next_cursor: 'c1' })

describe('SyslogDashboard', () => {
  it('shows the queried window instead of a total count', async () => {
    renderPage(twoPages)
    expect(await screen.findByText('newest event')).toBeInTheDocument()
    // Window is UTC: 10:00-18:00 UTC = 02:00-10:00 PST.
    expect(screen.getByText(/2026-11-25 02:00 → 2026-11-25 10:00/)).toBeInTheDocument()
    expect(screen.queryByText(/total events/i)).not.toBeInTheDocument()
    expect(screen.getByText(/up to 8 hours/i)).toBeInTheDocument()
  })

  it('pages older with the cursor and back to newer without it', async () => {
    const requests = renderPage(twoPages)
    await screen.findByText('newest event')
    expect(screen.getByRole('button', { name: /newer/i })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: /older/i }))
    expect(await screen.findByText('older event')).toBeInTheDocument()
    expect(requests.at(-1).get('cursor')).toBe('c1')
    expect(screen.getByRole('button', { name: /older/i })).toBeDisabled()
    expect(screen.getByText('Page 2')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /newer/i }))
    expect(await screen.findByText('newest event')).toBeInTheDocument()
    expect(screen.getByText('Page 1')).toBeInTheDocument()
    expect(requests.every((p) => !p.has('offset'))).toBe(true)
  })

  it('goes back to the first page when a filter changes', async () => {
    const requests = renderPage(twoPages)
    await screen.findByText('newest event')
    fireEvent.click(screen.getByRole('button', { name: /older/i }))
    await screen.findByText('older event')

    fireEvent.change(screen.getByPlaceholderText('192.168'), { target: { value: '10.3' } })
    await waitFor(() => expect(requests.at(-1).get('device_ip')).toBe('10.3'))
    expect(requests.at(-1).has('cursor')).toBe(false)
  })

  it('shows the backend reason when the range is too long', async () => {
    renderPage(() =>
      HttpResponse.json({ detail: 'The time range cannot exceed 8 hours.' }, { status: 422 })
    )
    expect(await screen.findByText(/the time range cannot exceed 8 hours/i)).toBeInTheDocument()
  })

  it('falls back to the generic error when detail is a validation list', async () => {
    renderPage(() =>
      HttpResponse.json({ detail: [{ loc: ['query', 'limit'], msg: 'too big' }] }, { status: 422 })
    )
    expect(await screen.findByText(/request failed with status code 422/i)).toBeInTheDocument()
  })
})

/**
 * NasSyslogStatusCard — registered NAS not sending syslog.
 * Spec: odd/tasks/syslog-retention-nas-status.md (S3, S4).
 */
import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import NasSyslogStatusCard from '../components/NasSyslogStatusCard'

const STATUS = {
  threshold_hours: 24,
  total: 3,
  silent_count: 2,
  reporting_count: 1,
  devices: [
    { id: 3, nasname: '192.168.1.191', shortname: 'moxa', last_seen: null, silent: true },
    { id: 2, nasname: '192.168.1.190', shortname: 'mikrotik', last_seen: '2026-11-20T10:00:00', silent: true },
    { id: 1, nasname: '192.168.1.10', shortname: 'sw-oficina', last_seen: '2026-11-23T09:00:00', silent: false },
  ],
}

function renderCard(status = STATUS) {
  server.use(http.get('/api/syslog/nas-status', () => HttpResponse.json(status)))
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <NasSyslogStatusCard />
    </QueryClientProvider>
  )
}

describe('NasSyslogStatusCard', () => {
  it('shows how many registered NAS are not sending syslog', async () => {
    renderCard()
    expect(await screen.findByText('2 of 3')).toBeInTheDocument()
    expect(screen.getByText(/no syslog in the last 24 h/i)).toBeInTheDocument()
  })

  it('lists only silent NAS with their last message time when expanded', async () => {
    renderCard()
    fireEvent.click(await screen.findByRole('button', { name: /show silent nas/i }))
    expect(screen.getByText('moxa')).toBeInTheDocument()
    expect(screen.getByText('mikrotik')).toBeInTheDocument()
    expect(screen.getByText('Never')).toBeInTheDocument()
    // last_seen is UTC: 2026-11-20 10:00 UTC = 02:00 PST (issue #123)
    expect(screen.getByText('2026-11-20 02:00')).toBeInTheDocument()
    expect(screen.queryByText('sw-oficina')).not.toBeInTheDocument()
  })

  it('reports all NAS sending when none are silent', async () => {
    renderCard({ ...STATUS, silent_count: 0, reporting_count: 3, devices: STATUS.devices.map(d => ({ ...d, silent: false })) })
    expect(await screen.findByText('0 of 3')).toBeInTheDocument()
    expect(screen.getByText(/all registered nas are sending syslog/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /show silent nas/i })).not.toBeInTheDocument()
  })
})

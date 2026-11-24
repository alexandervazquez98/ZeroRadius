/**
 * NTPIndicator — header NTP status chip (#122).
 */
import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import NTPIndicator from '../components/NTPIndicator'

function renderWith(body, status = 200) {
  server.use(http.get('/api/system/ntp-status', () => HttpResponse.json(body, { status })))
  return render(<NTPIndicator />)
}

const OK = { synchronized: true, offset_ms: 1.2, stratum: 2, reference_server: '10.3.152.209', last_sync: null, alert: false, configured: true }

describe('NTPIndicator', () => {
  it('is green when synchronized', async () => {
    renderWith(OK)
    const chip = await screen.findByTestId('ntp-indicator')
    expect(chip).toHaveAttribute('data-state', 'ok')
    expect(chip.title).toMatch(/Synced/)
  })

  it('is red when the offset raises an alert', async () => {
    renderWith({ ...OK, offset_ms: 2000, alert: true })
    expect(await screen.findByTestId('ntp-indicator')).toHaveAttribute('data-state', 'alert')
  })

  it('is neutral, not red, when NTP_SERVER is not configured', async () => {
    renderWith({ ...OK, synchronized: false, reference_server: null, configured: false })
    const chip = await screen.findByTestId('ntp-indicator')
    expect(chip).toHaveAttribute('data-state', 'not-configured')
    expect(chip.title).toMatch(/not configured/i)
  })

  it('is red when the status cannot be read', async () => {
    renderWith({ detail: 'boom' }, 500)
    expect(await screen.findByTestId('ntp-indicator')).toHaveAttribute('data-state', 'alert')
  })
})

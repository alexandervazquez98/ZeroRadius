/**
 * T42 — Frontend unit tests: AuthContext (role extraction) + ReviewBadge.
 *
 * AuthContext tests:
 * - Extracts superadmin role from JWT
 * - Extracts helpdesk role from JWT
 * - role is null when no token
 * - hasRole() returns true/false correctly
 *
 * ReviewBadge tests:
 * - Shows "Overdue" when reviewDate is in the past
 * - Shows "Review Soon" when reviewDate is within 30 days
 * - Shows nothing when reviewDate is more than 30 days away
 * - Shows nothing when reviewDate is null
 */

import React from 'react'
import { renderHook, render, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AuthProvider, useAuth } from '../context/AuthContext'
import { ReviewBadge } from '../pages/PrivilegeMap'

// ---------------------------------------------------------------------------
// JWT helpers — build mock tokens that jwtDecode can parse
// ---------------------------------------------------------------------------

function makeJwt(payload) {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  const body = btoa(JSON.stringify(payload))
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `${header}.${body}.fakesignature`
}

const MOCK_JWT_SUPERADMIN = makeJwt({ sub: 'jperez', role: 'superadmin', exp: 9999999999 })
const MOCK_JWT_HELPDESK = makeJwt({ sub: 'hdesk', role: 'helpdesk', exp: 9999999999 })

// ---------------------------------------------------------------------------
// AuthContext — role extraction from JWT
// ---------------------------------------------------------------------------

describe('AuthContext — role extraction from JWT', () => {
  it('extracts superadmin role correctly from JWT', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => (
        <AuthProvider initialToken={MOCK_JWT_SUPERADMIN}>{children}</AuthProvider>
      ),
    })
    expect(result.current.role).toBe('superadmin')
  })

  it('extracts helpdesk role correctly from JWT', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => (
        <AuthProvider initialToken={MOCK_JWT_HELPDESK}>{children}</AuthProvider>
      ),
    })
    expect(result.current.role).toBe('helpdesk')
  })

  it('role is null when no token is provided', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    })
    expect(result.current.role).toBeNull()
  })

  it('hasRole returns true when user has one of the specified roles', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => (
        <AuthProvider initialToken={MOCK_JWT_SUPERADMIN}>{children}</AuthProvider>
      ),
    })
    expect(result.current.hasRole(['superadmin', 'admin'])).toBe(true)
  })

  it('hasRole returns false when user does not have any of the specified roles', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => (
        <AuthProvider initialToken={MOCK_JWT_HELPDESK}>{children}</AuthProvider>
      ),
    })
    expect(result.current.hasRole(['superadmin', 'admin'])).toBe(false)
  })

  it('hasRole returns false when no token (unauthenticated)', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    })
    expect(result.current.hasRole(['superadmin', 'admin', 'helpdesk'])).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// ReviewBadge — review status badges
// ---------------------------------------------------------------------------

function futureDate(daysFromNow) {
  const d = new Date()
  d.setDate(d.getDate() + daysFromNow)
  return d.toISOString()
}

function pastDate(daysAgo) {
  const d = new Date()
  d.setDate(d.getDate() - daysAgo)
  return d.toISOString()
}

describe('ReviewBadge — review status indicator', () => {
  it('shows "Overdue" when review_date is in the past', () => {
    const { getByText } = render(<ReviewBadge reviewDate={pastDate(1)} />)
    expect(getByText(/Overdue/i)).toBeInTheDocument()
  })

  it('shows "Review Soon" when review_date is within 30 days (future)', () => {
    const { getByText } = render(<ReviewBadge reviewDate={futureDate(15)} />)
    expect(getByText(/Review Soon/i)).toBeInTheDocument()
  })

  it('shows no badge when review_date is more than 30 days away', () => {
    const { container } = render(<ReviewBadge reviewDate={futureDate(60)} />)
    expect(container.firstChild).toBeNull()
  })

  it('shows no badge when reviewDate is null/undefined', () => {
    const { container } = render(<ReviewBadge reviewDate={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('shows "Review Soon" at exactly 30 days from now', () => {
    const { getByText } = render(<ReviewBadge reviewDate={futureDate(30)} />)
    expect(getByText(/Review Soon/i)).toBeInTheDocument()
  })
})

/**
 * T42 — Frontend unit tests: RoleGuard component.
 *
 * Tests cover:
 * - Renders children when user has an allowed role
 * - Renders fallback when user role is not allowed
 * - Renders null (no fallback) when fallback prop is omitted
 * - Auditor sees allowed content when auditor is in allowedRoles
 * - Unauthenticated user (role=null) cannot see protected content
 */

import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import RoleGuard from '../components/RoleGuard'

// Mock the useAuth hook
vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}))
import { useAuth } from '../context/AuthContext'

describe('RoleGuard', () => {
  it('renders children when user has an allowed role', () => {
    useAuth.mockReturnValue({ role: 'superadmin' })
    render(
      <RoleGuard allowedRoles={['superadmin', 'admin']}>
        <span>Protected Content</span>
      </RoleGuard>
    )
    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('renders fallback when user role is not in allowedRoles', () => {
    useAuth.mockReturnValue({ role: 'helpdesk' })
    render(
      <RoleGuard allowedRoles={['superadmin', 'admin']} fallback={<span>Access Denied</span>}>
        <span>Protected Content</span>
      </RoleGuard>
    )
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
    expect(screen.getByText('Access Denied')).toBeInTheDocument()
  })

  it('renders nothing (null) when fallback is not provided and role is denied', () => {
    useAuth.mockReturnValue({ role: 'readonly' })
    const { container } = render(
      <RoleGuard allowedRoles={['superadmin']}>
        <span>Protected Content</span>
      </RoleGuard>
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders children when user is auditor and auditor is in allowedRoles', () => {
    useAuth.mockReturnValue({ role: 'auditor' })
    render(
      <RoleGuard allowedRoles={['auditor', 'admin', 'superadmin']}>
        <span>Audit View</span>
      </RoleGuard>
    )
    expect(screen.getByText('Audit View')).toBeInTheDocument()
  })

  it('does not render children for unauthenticated user (role=null)', () => {
    useAuth.mockReturnValue({ role: null })
    const { container } = render(
      <RoleGuard allowedRoles={['superadmin']}>
        <span>Should Not Appear</span>
      </RoleGuard>
    )
    expect(screen.queryByText('Should Not Appear')).not.toBeInTheDocument()
    expect(container.firstChild).toBeNull()
  })

  it('renders children for admin when admin is in allowedRoles', () => {
    useAuth.mockReturnValue({ role: 'admin' })
    render(
      <RoleGuard allowedRoles={['superadmin', 'admin']}>
        <span>Admin Area</span>
      </RoleGuard>
    )
    expect(screen.getByText('Admin Area')).toBeInTheDocument()
  })
})

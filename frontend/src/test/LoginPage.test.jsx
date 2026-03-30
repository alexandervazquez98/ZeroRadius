/**
 * Tests para LoginPage (src/pages/Login.jsx).
 *
 * Cubre:
 * - Renderiza los inputs de username y password
 * - Login exitoso (MSW retorna 200 + JWT) → navega al dashboard
 * - Login fallido (MSW retorna 401) → muestra "Invalid credentials"
 */

import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import Login from '../pages/Login'
import { AuthProvider } from '../context/AuthContext'

// Helper JWT mínimo que jwtDecode puede parsear
const MOCK_TOKEN = [
  btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' })),
  btoa(JSON.stringify({ sub: 'admin', role: 'superadmin', force_change: false, exp: 9999999999 })),
  'fakesig',
].join('.')

// Mock de useNavigate para capturar la navegación
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => mockNavigate }
})

function renderLogin() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <Login />
      </AuthProvider>
    </MemoryRouter>
  )
}

describe('LoginPage — rendering', () => {
  it('renders username input', () => {
    renderLogin()
    expect(screen.getByPlaceholderText('Username')).toBeInTheDocument()
  })

  it('renders password input', () => {
    renderLogin()
    expect(screen.getByPlaceholderText('Password')).toBeInTheDocument()
  })

  it('renders Login button', () => {
    renderLogin()
    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument()
  })
})

describe('LoginPage — successful login', () => {
  it('navigates to / after successful login', async () => {
    // El handler default en mocks/handlers.js ya retorna 200 + token
    renderLogin()

    await userEvent.type(screen.getByPlaceholderText('Username'), 'admin')
    await userEvent.type(screen.getByPlaceholderText('Password'), 'password')
    fireEvent.click(screen.getByRole('button', { name: /login/i }))

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/')
    })
  })
})

describe('LoginPage — failed login', () => {
  it('shows "Invalid credentials" when API returns 401', async () => {
    // Override the default handler for this test only
    server.use(
      http.post('/api/auth/token', () => {
        return HttpResponse.json(
          { detail: 'Incorrect username or password' },
          { status: 401 }
        )
      })
    )

    renderLogin()

    await userEvent.type(screen.getByPlaceholderText('Username'), 'admin')
    await userEvent.type(screen.getByPlaceholderText('Password'), 'wrongpass')
    fireEvent.click(screen.getByRole('button', { name: /login/i }))

    await waitFor(() => {
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument()
    })
  })
})

/**
 * SessionManager — keep active sessions alive, warn before idle expiry, and
 * re-authenticate in place on expiry or 401 (#135).
 * Spec: odd/tasks/session-keepalive.md (S1, S3, S4).
 */
import React, { useState } from 'react'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import { AuthProvider } from '../context/AuthContext'
import SessionManager from '../components/SessionManager'
import api from '../api'

function makeJwt(payload) {
  const enc = (o) => btoa(JSON.stringify(o)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `${enc({ alg: 'HS256', typ: 'JWT' })}.${enc(payload)}.sig`
}

const nowS = () => Math.floor(Date.now() / 1000)
const tokenExpiringIn = (seconds, extra = {}) =>
  makeJwt({ sub: 'jperez', role: 'admin', force_change: false, auth_time: nowS() - 600, exp: nowS() + seconds, ...extra })

function LoginProbe() {
  const location = useLocation()
  return <div>login page from {location.state?.from?.pathname}</div>
}

function Probe() {
  // Page with in-progress state: a typed draft and an API call.
  const [draft, setDraft] = useState('')
  const [result, setResult] = useState('')
  return (
    <div>
      <input aria-label="draft" value={draft} onChange={(e) => setDraft(e.target.value)} />
      <button onClick={() => api.get('/thing').then((r) => setResult(r.data.ok))}>load</button>
      <span>result: {result}</span>
    </div>
  )
}

function renderWithSession(token, props = {}) {
  localStorage.setItem('token', token)
  return render(
    <MemoryRouter initialEntries={['/nas']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginProbe />} />
          <Route path="/nas" element={<><SessionManager tickMs={50} {...props} /><Probe /></>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  )
}

let refreshCalls
let loginCalls

beforeEach(() => {
  refreshCalls = 0
  loginCalls = []
  server.use(
    http.post('/api/auth/refresh', () => {
      refreshCalls += 1
      return HttpResponse.json({ access_token: tokenExpiringIn(1800), token_type: 'bearer' })
    }),
    http.post('/api/auth/token', async ({ request }) => {
      const form = await request.formData()
      loginCalls.push(form.get('username'))
      if (form.get('password') !== 'right') {
        return HttpResponse.json({ detail: 'Incorrect username or password' }, { status: 401 })
      }
      return HttpResponse.json({ access_token: tokenExpiringIn(1800), token_type: 'bearer' })
    })
  )
})

afterEach(() => localStorage.clear())

describe('SessionManager', () => {
  it('refreshes the token before it expires while the admin is active', async () => {
    renderWithSession(tokenExpiringIn(240))
    fireEvent.keyDown(window, { key: 'a' })
    await waitFor(() => expect(refreshCalls).toBe(1))
    const claims = JSON.parse(atob(localStorage.getItem('token').split('.')[1]))
    expect(claims.exp).toBeGreaterThan(nowS() + 1700)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('does not refresh an idle session and warns two minutes before expiry', async () => {
    renderWithSession(tokenExpiringIn(100))
    expect(await screen.findByText(/your session expires in 1:/i)).toBeInTheDocument()
    expect(refreshCalls).toBe(0)

    fireEvent.click(screen.getByRole('button', { name: /keep working/i }))
    await waitFor(() => expect(refreshCalls).toBe(1))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('asks to sign in again in place when the token has expired, keeping page state', async () => {
    renderWithSession(tokenExpiringIn(600))
    fireEvent.change(screen.getByLabelText('draft'), { target: { value: 'half-typed note' } })
    act(() => localStorage.setItem('token', tokenExpiringIn(-5)))

    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent(/session has expired/i)
    expect(screen.getByText('jperez')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'right' } })
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(loginCalls).toEqual(['jperez'])
    expect(screen.getByLabelText('draft')).toHaveValue('half-typed note')
  })

  it('retries the failed request after re-authenticating on a 401', async () => {
    let calls = 0
    server.use(
      http.get('/api/thing', () => {
        calls += 1
        return calls === 1
          ? HttpResponse.json({ detail: 'Could not validate credentials' }, { status: 401 })
          : HttpResponse.json({ ok: 'yes' })
      })
    )
    renderWithSession(tokenExpiringIn(1800))
    fireEvent.click(screen.getByRole('button', { name: 'load' }))

    await screen.findByRole('dialog')
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'right' } })
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText('result: yes')).toBeInTheDocument()
    expect(calls).toBe(2)
  })

  it('keeps the dialog open and shows the error on a wrong password', async () => {
    renderWithSession(tokenExpiringIn(-5))
    await screen.findByRole('dialog')
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByText('Incorrect username or password')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('signs out to the login page and remembers the current route', async () => {
    renderWithSession(tokenExpiringIn(-5))
    await screen.findByRole('dialog')
    fireEvent.click(screen.getByRole('button', { name: /sign out/i }))
    expect(await screen.findByText('login page from /nas')).toBeInTheDocument()
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('tells the admin to sign in again when the session reached its maximum length', async () => {
    const capped = tokenExpiringIn(100)
    server.use(
      // At the absolute lifetime the backend can only return the same expiry.
      http.post('/api/auth/refresh', () => {
        refreshCalls += 1
        return HttpResponse.json({ access_token: capped, token_type: 'bearer' })
      })
    )
    renderWithSession(capped)
    fireEvent.click(await screen.findByRole('button', { name: /keep working/i }))
    expect(await screen.findByText(/maximum length/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in again/i })).toBeInTheDocument()
  })

  it('opens the sign-in dialog when refresh is rejected', async () => {
    server.use(
      http.post('/api/auth/refresh', () =>
        HttpResponse.json({ detail: 'Session expired. Please sign in again.' }, { status: 401 })
      )
    )
    renderWithSession(tokenExpiringIn(240))
    fireEvent.keyDown(window, { key: 'a' })
    expect(await screen.findByLabelText(/password/i)).toBeInTheDocument()
  })
})

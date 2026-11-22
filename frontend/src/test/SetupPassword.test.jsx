/**
 * Public self-service password setup page (#101 part C).
 * Spec: odd/tasks/radius-password-setup-link.md (S1, S3, S4, S7).
 */
import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import SetupPassword from '../pages/SetupPassword'

function renderPage(token = 'tok123') {
  return render(
    <MemoryRouter initialEntries={[`/setup-password/${token}`]}>
      <Routes>
        <Route path="/setup-password/:token" element={<SetupPassword />} />
      </Routes>
    </MemoryRouter>
  )
}

function validLink(posts = []) {
  server.use(
    http.get('/api/password-setup/:token', () =>
      HttpResponse.json({ username: 'jperez', expires_at: '2030-01-01T00:00:00' })
    ),
    http.post('/api/password-setup/:token', async ({ request, params }) => {
      posts.push({ token: params.token, body: await request.json(), auth: request.headers.get('Authorization') })
      return HttpResponse.json({ ok: true, username: 'jperez' })
    })
  )
  return posts
}

describe('SetupPassword page', () => {
  it('lets the user set a password once the link is validated', async () => {
    localStorage.setItem('token', 'admin-token-in-same-browser')
    const posts = validLink()
    renderPage()

    expect(await screen.findByText(/jperez/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'my-new-pw' } })
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'my-new-pw' } })
    fireEvent.click(screen.getByRole('button', { name: 'Set password' }))

    await waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0]).toEqual({ token: 'tok123', body: { password: 'my-new-pw' }, auth: null })
    expect(await screen.findByText(/Your password has been set/)).toBeInTheDocument()
    localStorage.removeItem('token')
  })

  it('does not submit when the confirmation does not match', async () => {
    const posts = validLink()
    renderPage()
    await screen.findByText(/jperez/)
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'a-password' } })
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'different' } })
    fireEvent.click(screen.getByRole('button', { name: 'Set password' }))
    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument()
    expect(posts).toHaveLength(0)
  })

  it('shows why a link cannot be used', async () => {
    server.use(
      http.get('/api/password-setup/:token', () =>
        HttpResponse.json({ detail: 'This link has expired' }, { status: 410 })
      )
    )
    renderPage()
    expect(await screen.findByText('This link has expired')).toBeInTheDocument()
    expect(screen.queryByLabelText('New password')).toBeNull()
  })
})

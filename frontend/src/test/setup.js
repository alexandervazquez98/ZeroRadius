import '@testing-library/jest-dom'
import { server } from './mocks/server'

// Start MSW server before all tests, reset handlers after each test,
// and clean up after the suite finishes.
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

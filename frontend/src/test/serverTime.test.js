/**
 * Server timestamps are stored in UTC and serialized without an offset.
 * They must be shown in the browser's local time (issue #123).
 * Tests run with TZ=America/Tijuana (see vitest.config.js).
 */
import { describe, it, expect } from 'vitest'
import { parseServerTime, toServerTime } from '../utils/serverTime'

describe('parseServerTime', () => {
  it('regression: offset-less server timestamps are UTC, shown in local time', () => {
    // 17:01 UTC = 09:01 PST (UTC-8 in November)
    expect(parseServerTime('2026-11-24T17:01:15').format('YYYY-MM-DD HH:mm:ss')).toBe('2026-11-24 09:01:15')
  })

  it('applies daylight saving time in summer', () => {
    // 17:01 UTC = 10:01 PDT (UTC-7 in July)
    expect(parseServerTime('2026-07-24T17:01:15').format('HH:mm')).toBe('10:01')
  })

  it('keeps an explicit offset as given', () => {
    expect(parseServerTime('2026-11-24T17:01:15Z').format('HH:mm')).toBe('09:01')
    expect(parseServerTime('2026-11-24T17:01:15+00:00').format('HH:mm')).toBe('09:01')
  })

  it('accepts microseconds from MySQL DATETIME(6)', () => {
    expect(parseServerTime('2026-11-24T17:01:15.123456').format('HH:mm:ss')).toBe('09:01:15')
  })
})

describe('toServerTime', () => {
  it('converts a local datetime-local value to offset-less UTC for the API', () => {
    expect(toServerTime('2026-11-24T09:01')).toBe('2026-11-24T17:01:00')
  })
})

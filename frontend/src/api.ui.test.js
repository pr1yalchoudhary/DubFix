import { afterEach, expect, it, vi } from 'vitest'
import { request, downloadAudio } from './api'

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

it('times out a stalled generation without retrying or leaving its promise pending', async () => {
  vi.useFakeTimers()
  const fetch = vi.fn((path, options) => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))))
  vi.stubGlobal('fetch', fetch)
  const pending = expect(request('/api/preview', { replacement_text: 'fixture' })).rejects.toThrow('request timed out')
  await vi.advanceTimersByTimeAsync(150001); await pending
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(vi.getTimerCount()).toBe(0)
})

it('keeps backend errors actionable and clears the timeout after failure', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: 'Session expired. Upload again.' }) }))
  await expect(request('/api/replace', {})).rejects.toThrow('Session expired. Upload again.')
  expect(vi.getTimerCount()).toBe(0)
})

it('downloads the existing export endpoint as a blob', async () => {
  const blob = new Blob(['fixture'], { type: 'audio/mpeg' })
  const fetch = vi.fn().mockResolvedValue({ ok: true, blob: async () => blob })
  vi.stubGlobal('fetch', fetch)
  expect(await downloadAudio('/api/export/local-fixture')).toBe(blob)
  expect(fetch.mock.calls[0][0]).toBe('/api/export/local-fixture')
  expect(fetch.mock.calls[0][1].cache).toBe('no-store')
})

it('explains an invalid JSON response instead of exposing parser errors', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => { throw new SyntaxError('Unexpected token') } }))
  await expect(request('/api/preview', {})).rejects.toThrow('backend returned an unreadable response')
})

it('retains safe HTTP and provider diagnostics for the preview failure display', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 502,
    json: async () => ({ detail: 'Fish Audio credits or quota are insufficient.', error_code: 'fish_http_402', upstream_status: 402 }) }))
  await expect(request('/api/preview', {})).rejects.toMatchObject({ status: 502, code: 'fish_http_402', upstreamStatus: 402 })
})

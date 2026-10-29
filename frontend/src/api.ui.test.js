import { afterEach, expect, it, vi } from 'vitest'
import { request, downloadAudio } from './api'

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.resetModules() })

it('routes deployed requests and media URLs without leaking demo codes into URLs or downloads', async () => {
  vi.stubEnv('VITE_API_BASE_URL', 'https://tweeq-backend.onrender.com///')
  vi.resetModules()
  const api = await import('./api')
  api.setDemoAccessToken('private-demo-code')
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}), blob: async () => new Blob() })
  vi.stubGlobal('fetch', fetch)
  await api.request('/api/preview', {})
  expect(fetch.mock.calls[0][0]).toBe('https://tweeq-backend.onrender.com/api/preview')
  expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer private-demo-code')
  await api.request('/api/transcribe', {})
  expect(fetch.mock.calls[1][1].headers.Authorization).toBe('Bearer private-demo-code')
  await api.downloadAudio('/api/export/example')
  expect(fetch.mock.calls[2][0]).toBe('https://tweeq-backend.onrender.com/api/export/example')
  expect(fetch.mock.calls[2][1].headers.Authorization).toBeUndefined()
  for (const path of ['/api/audio/example?revision=2', '/api/reference/example', '/api/preview/example', '/api/cleanup/example']) {
    expect(api.apiUrl(path)).toBe('https://tweeq-backend.onrender.com' + path)
  }
  expect(api.apiUrl('blob:local')).toBe('blob:local')
  expect(api.apiUrl('https://example.com/audio.wav')).toBe('https://example.com/audio.wav')
  const open = vi.fn()
  vi.stubGlobal('XMLHttpRequest', class {
    constructor() { this.upload = {} }
    open = open
    send() { this.status = 200; this.responseText = '{}'; this.onload() }
  })
  await api.uploadAudio(new Blob(['audio']), true, vi.fn())
  expect(open).toHaveBeenCalledWith('POST', 'https://tweeq-backend.onrender.com/api/upload')
})

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

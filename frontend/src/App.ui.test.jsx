import React, { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { request, uploadAudio, downloadAudio, subscribeUsage, initializeUsage } from './api'

const { mock, emitter } = vi.hoisted(() => {
  function emitter() {
    const handlers = new Map()
    return { on(name, callback) { if (!handlers.has(name)) handlers.set(name, []); handlers.get(name).push(callback); return () => {} },
      emit(name, ...args) { for (const callback of handlers.get(name) || []) callback(...args) } }
  }
  return { mock: { waves: [], plugins: [], timelines: [] }, emitter }
})
vi.mock('./api', () => ({ request: vi.fn(), uploadAudio: vi.fn(), downloadAudio: vi.fn(), apiUrl: path => path, setDemoAccessToken: vi.fn(), initializeUsage: vi.fn().mockResolvedValue({ mode: 'demo' }), subscribeUsage: vi.fn(() => () => {}) }))
vi.mock('wavesurfer.js', () => ({ default: { create(options) {
  const wave = Object.assign(emitter(), { options, getDuration: () => 90, getWidth: () => 800, zoom: vi.fn(), setScrollTime: vi.fn(), destroy: vi.fn() })
  wave.pause = vi.fn(() => wave.emit('pause'))
  wave.play = vi.fn(async () => wave.emit('play')); wave.playPause = wave.play
  mock.waves.push(wave); queueMicrotask(() => wave.emit('ready')); return wave
} } }))
vi.mock('wavesurfer.js/dist/plugins/regions.esm.js', () => ({ default: { create() {
  const items = [], plugin = emitter()
  plugin.getRegions = () => [...items]
  plugin.addRegion = options => {
    const region = { ...options, id: String(Math.random()), setOptions(next) { Object.assign(region, next); plugin.emit('region-update', region) },
      remove() { const index = items.indexOf(region); if (index >= 0) items.splice(index, 1) } }
    items.push(region); plugin.emit('region-created', region); return region
  }
  plugin.enableDragSelection = () => () => {}
  mock.plugins.push(plugin); return plugin
} } }))
vi.mock('wavesurfer.js/dist/plugins/timeline.esm.js', () => ({ default: { create(options) { mock.timelines.push(options); return {} } } }))

const uploaded = { session_id: 'local-fixture-session', name: 'demo.wav', duration: 90, original_duration: 90, revision: 0,
  voice_status: 'ready', voice_error: null, reference: { start: 5, end: 15 }, reference_url: '/api/reference/local-fixture-session' }
const generated = { preview_id: 'fixture-preview', preview_url: '/api/preview/fixture-preview', duration: 2, mode: 'correct' }

it('shows free usage and exhaustion without a password in public mode', async () => {
  const listener = subscribeUsage.mock.calls.at(-1)[0]
  await act(async () => listener({ mode: 'public', remaining: 2, global_remaining: 10, message: 'Each provider attempt counts.' }))
  expect(document.body.textContent).toContain('2 free AI uses remaining')
  expect(document.querySelector('input[type=password]')).toBeNull()
  await act(async () => listener({ mode: 'public', remaining: 0, global_remaining: 8, message: 'Each provider attempt counts.' }))
  expect(document.body.textContent).toContain('Your free allowance has been reached')
  expect(document.body.textContent).toContain('export remain available')
})

it('keeps the demo protection UI in rollback mode', async () => {
  await act(async () => subscribeUsage.mock.calls.at(-1)[0]({ mode: 'demo' }))
  expect(document.querySelector('input[type=password]')).not.toBeNull()
})
let root
const field = id => document.getElementById(id)
const buttons = () => [...document.querySelectorAll('button')]
function button(text) { const result = buttons().find(el => el.textContent.trim() === text) || buttons().find(el => el.textContent.includes(text)); if (!result) throw new Error(`No button: ${text}`); return result }
async function click(text) { await act(async () => button(text).click()) }
async function type(id, value) {
  const input = field(id), prototype = input.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : input.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype
  await act(async () => { Object.getOwnPropertyDescriptor(prototype, 'value').set.call(input, value); input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true })) })
}
async function openEditor({ select = true } = {}) {
  await act(async () => {
    const input = document.querySelector('input[type=file]')
    Object.defineProperty(input, 'files', { configurable: true, value: [new File(['local fixture'], 'demo.wav', { type: 'audio/wav' })] })
    input.dispatchEvent(new Event('change', { bubbles: true }))
    document.querySelector('input[type=checkbox]').click()
  })
  await click('Open recording')
  if (select && document.getElementById('step-select')) await click('Edit selection')
}
async function readyToGenerate() { await openEditor(); await type('replacement', 'April fifth.') }

beforeEach(async () => {
  initializeUsage.mockResolvedValue({ mode: 'demo' })
  subscribeUsage.mockImplementation(() => () => {})
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  document.body.innerHTML = '<div id="test-root"></div>'
  mock.waves.length = 0; mock.plugins.length = 0; mock.timelines.length = 0
  request.mockReset(); uploadAudio.mockReset(); downloadAudio.mockReset()
  uploadAudio.mockResolvedValue({ ...uploaded }); request.mockImplementation(async (path, body) => path === '/api/transcribe' ? { ...body, text: "I can't wait for you to try it!" } : { ...generated })
  vi.stubGlobal('fetch', vi.fn(() => { throw new Error('Network is forbidden in UI tests') }))
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(function () { this.dispatchEvent(new Event('pause')) })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  URL.createObjectURL = vi.fn(() => 'blob:fixture'); URL.revokeObjectURL = vi.fn()
  root = createRoot(field('test-root')); await act(async () => root.render(<App/>))
})
afterEach(async () => { await act(async () => root.unmount()); vi.unstubAllGlobals() })

describe('Sequential editor workflow with local mocks', () => {
  it('uploads with consent and reveals the editing sections after confirming a selection', async () => {
    await openEditor()
    expect(uploadAudio.mock.calls[0][1]).toBe(true)
    expect([...document.querySelectorAll('.step-heading h2')].map(el => el.textContent)).toEqual(['Recording', 'What would you like to change?', 'Preview and compare'])
    expect(mock.timelines).toHaveLength(1)
    expect(document.querySelector('.recording-meta h1').textContent).toBe('demo.wav')
    expect(document.querySelector('#step-compare [aria-label="Replacement preview"]')).not.toBeNull()
    expect(document.querySelector('.workspace > #step-edit')).not.toBeNull()
    expect(document.querySelector('.workspace > #step-compare')).not.toBeNull()
    expect(mock.waves[0].options.cursorWidth).toBe(2)
    expect(document.body.textContent).toContain('Step 2: enter the replacement text')
    expect(field('reference-text')).toBeNull()
    expect(button('Generate Preview').disabled).toBe(true)
    expect(button('Apply Edit').disabled).toBe(true)
    expect(field('replacement').disabled).toBe(false)
  })

  it('keeps boundary fields and drag selection synchronized without losing drafts', async () => {
    await readyToGenerate()
    await type('selection-start', '1.125'); await type('selection-end', '5.625')
    expect(mock.plugins[0].getRegions()[0].start).toBe(1.125)
    expect(mock.plugins[0].getRegions()[0].end).toBe(5.625)
    expect(document.body.textContent).toContain('4.500s')
    await act(async () => mock.plugins[0].addRegion({ start: 12.25, end: 15.75 }))
    expect(field('selection-start').value).toBe('12.25'); expect(field('selection-end').value).toBe('15.75')
    expect(field('replacement').value).toBe('April fifth.')
    expect(button('Generate Preview').disabled).toBe(false)
  })

  it('allows clearing a timestamp and explains invalid selection while keeping text editable', async () => {
    await readyToGenerate()
    await type('selection-start', '')
    expect(field('selection-start').value).toBe('')
    expect(button('Generate Preview').disabled).toBe(true)
    expect(field('replacement').disabled).toBe(false)
    expect(document.body.textContent).toContain('End must follow Start')
    await type('selection-start', '1.2')
    expect(button('Generate Preview').disabled).toBe(false)
    expect(field('replacement').value).toBe('April fifth.')
  })

  it('compares versions without reloading the waveform, resetting selection, or disabling text', async () => {
    await readyToGenerate(); await type('selection-start', '1'); await type('selection-end', '4')
    await click('Generate Preview')
    expect(document.querySelector('audio[aria-label="Generated replacement speech"]')).not.toBeNull()
    await click('Original')
    expect(field('replacement').disabled).toBe(false)
    expect(field('replacement').value).toBe('April fifth.')
    expect(field('selection-start').value).toBe('1'); expect(field('selection-end').value).toBe('4')
    expect(mock.waves).toHaveLength(1)
    expect(document.querySelector('audio[aria-label="Original recording comparison"]').getAttribute('src')).toContain('version=original')
    expect(document.querySelector('audio[aria-label="Generated replacement speech"]')).not.toBeNull()
    await act(async () => mock.plugins[0].emit('region-updated', mock.plugins[0].getRegions()[0]))
    expect(document.querySelector('audio[aria-label="Generated replacement speech"]')).not.toBeNull()
    await click('Edited'); await type('selection-end', '4.25')
    expect(document.querySelector('audio[aria-label="Generated replacement speech"]')).toBeNull()
    expect(field('replacement').value).toBe('April fifth.')
  })

  it('zooms in, out and resets without changing selection or drafts', async () => {
    await readyToGenerate(); await type('selection-start', '1.25')
    await act(async () => document.querySelector('button[aria-label="Zoom in"]').click())
    expect(mock.waves[0].zoom).toHaveBeenLastCalledWith(800 / 90 * 2)
    expect(document.querySelector('.zoom-controls output').textContent).toBe('2×')
    await act(async () => document.querySelector('button[aria-label="Zoom in"]').click())
    await act(async () => document.querySelector('button[aria-label="Zoom out"]').click())
    await click('Reset zoom')
    expect(mock.waves[0].zoom).toHaveBeenLastCalledWith(0)
    expect(field('selection-start').value).toBe('1.25')
    expect(field('replacement').value).toBe('April fifth.')
  })

  it('preserves both modes and sends the existing delivery request format', async () => {
    await readyToGenerate(); await click('Change Delivery')
    await type('delivery-direction', 'excited'); await type('segment-text', 'Welcome everyone.')
    await click('Original')
    expect(field('delivery-direction').disabled).toBe(false)
    await click('Correct Speech'); expect(field('replacement').value).toBe('April fifth.')
    await click('Change Delivery'); expect(field('segment-text').value).toBe('Welcome everyone.')
    await click('Generate Preview')
    expect(request).toHaveBeenLastCalledWith('/api/preview', expect.objectContaining({ mode: 'delivery', direction: 'excited', segment_text: 'Welcome everyone.', replacement_text: 'Welcome everyone.' }))
  })

  it('unlocks controls after a failed generation and preserves entered text', async () => {
    await readyToGenerate()
    let reject
    request.mockReturnValueOnce(new Promise((resolve, fail) => { reject = fail }))
    await click('Generate Preview')
    expect(field('replacement').disabled).toBe(true)
    expect(document.body.textContent).toContain('Preparing your voice and preview')
    await act(async () => reject(new Error('Fixture: provider unavailable. Try again.')))
    expect(field('replacement').disabled).toBe(false)
    expect(field('replacement').value).toBe('April fifth.')
    expect(document.querySelector('.busy-banner')).toBeNull()
    expect(document.querySelector('[role=alert]').textContent).toContain('Fixture: provider unavailable')
    expect(button('Generate Preview').disabled).toBe(false)
  })

  it('inserts the saved preview without another generation and handles export failure then success', async () => {
    await readyToGenerate(); await click('Generate Preview')
    request.mockResolvedValueOnce({ ...uploaded, duration: 89, revision: 1 })
    await click('Apply Edit')
    expect(request).toHaveBeenCalledTimes(2)
    expect(request.mock.calls[1]).toEqual(['/api/replace', { session_id: uploaded.session_id, preview_id: generated.preview_id, revision: 0, mode: 'correct', start: 0, end: 3 }])
    expect(field('replacement').value).toBe('April fifth.')
    expect(mock.waves).toHaveLength(2)
    expect(mock.waves[1].options.url).toContain('version=current&revision=1')
    expect(document.querySelector('audio[aria-label="Current recording comparison"]').getAttribute('src')).toContain('version=current&revision=1')
    expect(button('Apply Edit').disabled).toBe(true)
    expect(document.querySelector('.success').textContent).toContain('Replacement applied')
    expect(field('selection-end').value).toBe('')
    downloadAudio.mockRejectedValueOnce(new Error('Fixture export failed. Retry download.'))
    await click('Download MP3')
    expect(document.querySelector('.busy-banner')).toBeNull()
    expect(button('Download MP3').disabled).toBe(false)
    downloadAudio.mockResolvedValueOnce(new Blob(['local fixture mp3'], { type: 'audio/mpeg' }))
    await click('Download MP3')
    expect(downloadAudio).toHaveBeenLastCalledWith(`/api/export/${uploaded.session_id}`)
    expect(URL.createObjectURL).toHaveBeenCalledOnce()
    expect(document.body.textContent).toContain('Your MP3 is ready')
    await click('Back to editor')
    expect(field('replacement').value).toBe('April fifth.')
    expect(field('selection-end').value).toBe('')
  })

  it('explains missing configuration without disabling draft text inputs', async () => {
    uploadAudio.mockResolvedValueOnce({ ...uploaded, voice_status: 'configuration_required' })
    await readyToGenerate()
    expect(field('reference-text')).toBeNull()
    expect(field('replacement').disabled).toBe(false)
    expect(button('Generate Preview').disabled).toBe(true)
    expect(document.getElementById('preview-help').textContent).toContain('Speech generation is not configured')
    expect(request).not.toHaveBeenCalled()
  })

  it('recovers from upload failure without losing the file and consent', async () => {
    uploadAudio.mockRejectedValueOnce(new Error('Fixture invalid audio. Choose another WAV.'))
    await openEditor()
    expect(document.querySelector('[role=alert]').textContent).toContain('Fixture invalid audio')
    expect(button('Open recording').disabled).toBe(false)
    expect(document.querySelector('input[type=checkbox]').checked).toBe(true)
    await click('Open recording')
    expect(field('replacement')).not.toBeNull()
  })

  it('requires manual translated text and keeps delivery controls usable in Original comparison', async () => {
    await readyToGenerate(); await click('Change Delivery'); await type('segment-text', 'Welcome.')
    await type('delivery-language', 'es')
    expect(button('Generate Preview').disabled).toBe(true)
    expect(document.getElementById('preview-help').textContent).toContain('enter the text in your selected language')
    await type('translated-text', 'Bienvenidos.'); await click('Original')
    expect(field('translated-text').disabled).toBe(false)
    expect(button('Generate Preview').disabled).toBe(false)
  })

  it('keeps an approved preview available after insertion fails', async () => {
    await readyToGenerate(); await click('Generate Preview')
    request.mockRejectedValueOnce(new Error('Fixture: insertion failed. Try again.'))
    await click('Apply Edit')
    expect(document.querySelector('.busy-banner')).toBeNull()
    expect(button('Apply Edit').disabled).toBe(false)
    expect(field('replacement').value).toBe('April fifth.')
    expect(document.querySelector('audio[aria-label="Generated replacement speech"]')).not.toBeNull()
  })

  it('shows Apply Edit below the preview player and invalidates it on text or mode changes', async () => {
    await readyToGenerate()
    expect(button('Apply Edit').disabled).toBe(true)
    await click('Generate Preview')
    const player = document.querySelector('audio[aria-label="Generated replacement speech"]')
    expect(button('Apply Edit').disabled).toBe(false)
    expect(player.compareDocumentPosition(button('Apply Edit')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(document.querySelector('audio[aria-label="Current recording comparison"]').getAttribute('src')).toContain('revision=0')
    await type('replacement', 'May fifth.')
    expect(button('Apply Edit').disabled).toBe(true)
    await click('Generate Preview'); await click('Change Delivery')
    expect(button('Apply Edit').disabled).toBe(true)
    expect(request.mock.calls.filter(([path]) => path === '/api/replace')).toHaveLength(0)
  })

  it('handles a preview without optional duration metadata and rejects a missing clip', async () => {
    await readyToGenerate()
    request.mockResolvedValueOnce({ preview_id: 'fixture-preview', preview_url: '/api/preview/fixture-preview' })
    await click('Generate Preview')
    expect(button('Apply Edit').disabled).toBe(false)
    await type('replacement', 'Different words.')
    request.mockResolvedValueOnce({ preview_id: 'broken-response' })
    await click('Generate Preview')
    expect(button('Apply Edit').disabled).toBe(true)
    expect(document.querySelector('[role=alert]').textContent).toContain('playable clip')
  })

  it('shows an HTTP 502 beside the preview instead of silently returning to the empty state', async () => {
    await readyToGenerate(); await type('replacement', 'Friday')
    request.mockRejectedValueOnce(Object.assign(new Error('Fish Audio denied access to this model or voice.'), { status: 502, code: 'fish_http_403' }))
    await click('Generate Preview')
    expect(request).toHaveBeenLastCalledWith('/api/preview', expect.objectContaining({ replacement_text: 'Friday' }))
    const failure = document.querySelector('.preview-box [role=alert]')
    expect(failure.textContent).toContain('HTTP 502')
    expect(failure.textContent).toContain('fish_http_403')
    expect(failure.textContent).toContain('No playable replacement is available')
    expect(button('Apply Edit').disabled).toBe(true)
    expect(document.querySelector('.busy-banner')).toBeNull()
    await act(async () => document.querySelector('button[aria-label="Dismiss error"]').click())
    expect(document.querySelector('.preview-box [role=alert]')).not.toBeNull()
    await click('Generate Preview')
    expect(document.querySelector('.preview-box [role=alert]')).toBeNull()
    expect(document.querySelector('audio[aria-label="Generated replacement speech"]')).not.toBeNull()
    expect(button('Apply Edit').disabled).toBe(false)
  })

  it('keeps Friday preview through waveform rerenders and applies it without regeneration', async () => {
    await readyToGenerate(); await type('replacement', 'Friday'); await click('Generate Preview')
    await act(async () => {
      mock.waves[0].emit('timeupdate', 1.2)
      mock.waves[0].emit('pause')
      mock.waves[0].emit('resize')
      mock.plugins[0].emit('region-updated', mock.plugins[0].getRegions()[0])
    })
    expect(button('Apply Edit').disabled).toBe(false)
    expect(mock.waves).toHaveLength(1)
    request.mockResolvedValueOnce({ ...uploaded, duration: 89, revision: 1 })
    await click('Apply Edit')
    expect(request.mock.calls.map(([path]) => path)).toEqual(['/api/preview', '/api/replace'])
    expect(request.mock.calls[1][1].preview_id).toBe(generated.preview_id)
    expect(document.querySelector('audio[aria-label="Current recording comparison"]').getAttribute('src')).toContain('revision=1')
  })

  it('disables Apply with an explicit error when the preview audio URL cannot play', async () => {
    await readyToGenerate(); await click('Generate Preview')
    await act(async () => document.querySelector('audio[aria-label="Generated replacement speech"]').dispatchEvent(new Event('error')))
    expect(button('Apply Edit').disabled).toBe(true)
    expect(document.querySelector('.preview-box [role=alert]').textContent).toContain('could not load')
  })

  it('brands the app Tweeq and previews a one-word correction without a reference transcript', async () => {
    expect(document.querySelector('.brand').textContent).toContain('Tweeq')
    expect(document.querySelector('.brand').getAttribute('aria-label')).toBe('Tweeq home')
    await openEditor(); await type('replacement', 'Friday')
    expect(field('reference-text')).toBeNull()
    expect(document.body.textContent).toContain('Ready to edit.')
    expect(document.getElementById('step-reference')).toBeNull()
    expect(document.querySelector('[aria-label="Voice reference audio"]')).toBeNull()
    expect(document.querySelector('[role=note]').textContent).toContain('For seamless edits')
    expect(button('Generate Preview').disabled).toBe(false)
    await click('Generate Preview')
    expect(request.mock.calls[0][1].replacement_text).toBe('Friday')
    expect(request.mock.calls[0][1]).not.toHaveProperty('reference_text')
    expect(button('Apply Edit').disabled).toBe(false)
  })

  it('shows the subtle tip only for one or two words in Correct Speech', async () => {
    await openEditor()
    expect(document.querySelector('[role=note]')).toBeNull()
    await type('replacement', 'next Friday')
    expect(document.querySelector('[role=note]')).not.toBeNull()
    await type('replacement', 'The meeting is next Friday.')
    expect(document.querySelector('[role=note]')).toBeNull()
    await click('Change Delivery')
    expect(document.querySelector('[role=note]')).toBeNull()
  })

  it('applies independent Correct Speech then Change Delivery edits on the refreshed timeline and undoes the second', async () => {
    await openEditor(); await type('original-phrase', "We're launching next Monday")
    await type('replacement', "We're launching next Friday.")
    await click('Generate Preview')
    const edit1 = { number: 1, mode: 'correct', original_text: "We're launching next Monday", replacement_text: "We're launching next Friday.", status: 'applied' }
    request.mockResolvedValueOnce({ ...uploaded, revision: 1, duration: 91.5, edit_count: 1, edit_history: [edit1] })
    await click('Apply Edit')
    expect(field('selection-start').value).toBe(''); expect(field('selection-end').value).toBe('')
    expect(mock.plugins.at(-1).getRegions()).toHaveLength(0)
    await click('Change Delivery')
    await type('delivery-direction', 'excited and dramatic')
    expect(button('Generate Preview').disabled).toBe(true)
    await act(async () => { const plugin = mock.plugins.at(-1); const r = plugin.addRegion({ start: 7.5, end: 11.2 }); plugin.emit('region-updated', r) })
    expect(field('segment-text').value).toBe("I can't wait for you to try it!")
    request.mockResolvedValueOnce({ ...generated, preview_id: 'second-preview', mode: 'delivery' })
    await click('Generate Preview')
    expect(request.mock.calls[3][1]).toMatchObject({ revision: 1, mode: 'delivery', start: 7.5, end: 11.2, segment_text: "I can't wait for you to try it!", direction: 'excited and dramatic' })
    const edit2 = { number: 2, mode: 'delivery', direction: 'excited and dramatic', status: 'applied' }
    request.mockResolvedValueOnce({ ...uploaded, revision: 2, duration: 92, edit_count: 2, edit_history: [edit1, edit2] })
    await click('Apply Edit')
    expect(request.mock.calls.map(([path]) => path)).toEqual(['/api/preview', '/api/replace', '/api/transcribe', '/api/preview', '/api/replace'])
    expect(request.mock.calls[4][1]).toMatchObject({ revision: 1, mode: 'delivery', preview_id: 'second-preview', start: 7.5, end: 11.2 })
    expect(document.querySelector('[aria-label="Edit History"]').textContent).toContain('Edit 1 — Correct Speech')
    expect(document.querySelector('[aria-label="Edit History"]').textContent).toContain('Edit 2 — Change Delivery')
    expect(document.querySelector('[aria-label="Edit History"]').textContent).toContain('excited and dramatic')
    expect(mock.waves.at(-1).options.url).toContain('revision=2')
    expect(field('selection-end').value).toBe('')
    request.mockResolvedValueOnce({ ...uploaded, revision: 3, duration: 91.5, edit_count: 1, edit_history: [edit1, { ...edit2, status: 'undone' }] })
    await click('Undo last edit')
    expect(request.mock.calls.at(-1)).toEqual([`/api/undo/${uploaded.session_id}`, { revision: 2 }])
    expect(mock.waves.at(-1).options.url).toContain('revision=3')
    expect(document.querySelector('[aria-label="Edit History"]').textContent).toContain('Undone')
    expect(button('Apply Edit').disabled).toBe(true)
  })
  it('waits for finalized selection, caches detected words and ignores stale results', async () => {
    await openEditor()
    let resolveOld
    request.mockImplementation((path, body) => path === '/api/transcribe'
      ? body.start === 0 ? new Promise(resolve => { resolveOld = () => resolve({ ...body, text: 'Outdated words' }) })
        : Promise.resolve({ ...body, text: 'New selected words' })
      : Promise.resolve(generated))
    await click('Change Delivery')
    expect(button('Generate Preview').disabled).toBe(true)
    const plugin = mock.plugins.at(-1), r = plugin.getRegions()[0]
    await act(async () => { r.start = 5; r.end = 8; plugin.emit('region-update', r) })
    expect(request.mock.calls.filter(([p]) => p === '/api/transcribe')).toHaveLength(1)
    await act(async () => plugin.emit('region-updated', r))
    expect(field('segment-text').value).toBe('New selected words')
    await act(async () => resolveOld())
    expect(field('segment-text').value).toBe('New selected words')
    await click('Correct Speech'); await click('Change Delivery')
    expect(field('segment-text').value).toBe('New selected words')
    expect(request.mock.calls.filter(([p]) => p === '/api/transcribe')).toHaveLength(2)
  })

  it('shows detection errors and permits manual fallback without forcing Apply enabled', async () => {
    await openEditor()
    request.mockRejectedValueOnce(new Error('ASR access denied'))
    await click('Change Delivery')
    expect(document.body.textContent).toContain('ASR access denied')
    expect(field('segment-text').disabled).toBe(false)
    expect(button('Generate Preview').disabled).toBe(true)
    await type('segment-text', 'Manual fallback words')
    expect(button('Generate Preview').disabled).toBe(false)
    expect(button('Apply Edit').disabled).toBe(true)
    await click('Generate Preview')
    expect(request).toHaveBeenLastCalledWith('/api/preview', expect.objectContaining({ segment_text: 'Manual fallback words' }))
  })

  it('shows boundary and pacing guidance while preserving explicit preview approval', async () => {
    await readyToGenerate()
    request.mockResolvedValueOnce({ ...generated, continuity_warnings: ['Start is in audible audio. Select a quieter gap if needed.'], duration_change: .25 })
    await click('Generate Preview')
    expect(document.body.textContent).toContain('Start is in audible audio')
    expect(document.body.textContent).toContain('+0.25s')
    expect(button('Apply Edit').disabled).toBe(false)
    expect(request.mock.calls).toHaveLength(1)
  })

  it('offers cleanup only on a quality warning and accepts it without changing Current', async () => {
    const quality = { status: 'review', warnings: [{ code: 'background_energy', message: 'Persistent background energy.', recommendation: 'Listen before deciding.', intervals: [{ start: 2, end: 4 }] }] }
    uploadAudio.mockResolvedValueOnce({ ...uploaded, quality, cleanup_available: true, reference_revision: 0 })
    await openEditor()
    expect(document.body.textContent).toContain('Persistent background energy')
    expect(document.body.textContent).toContain('00:02.00–00:04.00')
    request.mockResolvedValueOnce({ cleanup_id: 'local-cleanup', cleaned_url: '/api/cleanup/local', can_accept: true })
    await click('Compare gentle cleanup')
    expect(request).toHaveBeenLastCalledWith(`/api/cleanup/${uploaded.session_id}`, { revision: 0 })
    expect(document.querySelector('[aria-label="Gentle cleanup preview"]')).not.toBeNull()
    expect(document.querySelector('[aria-label="Original for cleanup comparison"]')).not.toBeNull()
    request.mockResolvedValueOnce({ ...uploaded, quality, cleanup_accepted: true, reference_revision: 1 })
    await click('Use cleanup for voice setup')
    expect(request).toHaveBeenLastCalledWith(`/api/cleanup/${uploaded.session_id}/choice`, { revision: 0, cleanup_id: 'local-cleanup', accept: true })
    expect(document.body.textContent).toContain('Original and Current recordings are unchanged')
    expect(mock.waves).toHaveLength(1)
    expect(button('Apply Edit').disabled).toBe(true)
  })

  it('rejects cleanup without discarding an already approved preview', async () => {
    uploadAudio.mockResolvedValueOnce({ ...uploaded, cleanup_available: true })
    await readyToGenerate()
    await click('Generate Preview')
    expect(button('Apply Edit').disabled).toBe(false)
    request.mockResolvedValueOnce({ cleanup_id: 'local-cleanup', cleaned_url: '/api/cleanup/local', can_accept: true })
    await click('Compare gentle cleanup')
    request.mockResolvedValueOnce({ ...uploaded, cleanup_available: false, voice_prepared: true })
    await click('Keep original voice')
    expect(button('Apply Edit').disabled).toBe(false)
    expect(request.mock.calls.filter(([path]) => path === '/api/preview')).toHaveLength(1)
  })

  it('keeps Undo and Redo in the waveform toolbar with the existing revision workflow', async () => {
    uploadAudio.mockResolvedValueOnce({ ...uploaded, revision: 1, edit_count: 1, can_redo: false })
    await openEditor()
    const undo = document.querySelector('.transport [aria-label="Undo last edit"]')
    const redo = document.querySelector('.transport [aria-label="Redo last edit"]')
    expect(undo.disabled).toBe(false)
    expect(redo.disabled).toBe(true)
    expect(undo.getAttribute('title')).toBe('Undo last edit')
    request.mockResolvedValueOnce({ ...uploaded, revision: 2, edit_count: 0, can_redo: true })
    await click('Undo last edit')
    expect(request).toHaveBeenLastCalledWith(`/api/undo/${uploaded.session_id}`, { revision: 1 })
    expect(document.querySelector('.transport [aria-label="Redo last edit"]').disabled).toBe(false)
    request.mockResolvedValueOnce({ ...uploaded, revision: 3, edit_count: 1, can_redo: false })
    await click('Redo last edit')
    expect(request).toHaveBeenLastCalledWith(`/api/redo/${uploaded.session_id}`, { revision: 2 })
    expect(mock.waves.at(-1).options.url).toContain('revision=3')
    expect(request.mock.calls.map(([path]) => path)).toEqual([`/api/undo/${uploaded.session_id}`, `/api/redo/${uploaded.session_id}`])
  })

  it('opens on a compact upload card without a hero or editor navigation strip', async () => {
    expect(document.querySelector('h1').textContent).toBe('Upload your recording')
    expect(document.querySelector('.header-inner .brand-block p').textContent).toBe("One mistake shouldn't mean another take.")
    expect(document.querySelector('.button.primary').textContent).toBe('Choose File')
    expect(document.querySelector('.workflow-nav')).toBeNull()
    expect(document.querySelector('.features')).toBeNull()
    expect(request).not.toHaveBeenCalled()
  })

  it('reveals the editing form only after an explicit selection and hides it after Apply', async () => {
    await openEditor({ select: false })
    expect(field('step-edit').hidden).toBe(true)
    expect(field('step-compare').hidden).toBe(true)
    expect(document.querySelector('.selection-prompt')).not.toBeNull()
    expect(document.querySelector('[aria-label="Replacement preview"]').hidden).toBe(true)
    const plugin=mock.plugins.at(-1), region=plugin.getRegions()[0]
    await act(async () => { region.start=2;region.end=4;plugin.emit('region-update',region) })
    expect(field('step-edit').hidden).toBe(true)
    await act(async () => plugin.emit('region-updated',region))
    expect(field('step-edit').hidden).toBe(false)
    expect(document.querySelector('.selection-prompt')).toBeNull()
    expect(request).not.toHaveBeenCalled()
    await type('replacement','Friday')
    await click('Generate Preview')
    expect(document.querySelector('[aria-label="Replacement preview"]').hidden).toBe(false)
    request.mockResolvedValueOnce({ ...uploaded,revision:1,edit_count:1 })
    await click('Apply Edit')
    expect(field('step-edit').hidden).toBe(true)
    expect(document.querySelector('[aria-label="Replacement preview"]').hidden).toBe(true)
    expect(field('replacement').value).toBe('Friday')
    expect(field('selection-start').value).toBe('')
  })

  it('puts detected words first and keeps word effects, language and existing tones under More options', async () => {
    await openEditor();await click('Change Delivery')
    expect(document.querySelector('label[for="segment-text"]').textContent).toBe('Your words')
    expect(field('segment-text').value).toBe("I can't wait for you to try it!")
    expect([...document.querySelectorAll('.presets button')].map(el=>el.textContent)).toEqual(['Natural','Excited','Calm','Confident','Sad','Nervous','Whisper','Dramatic'])
    const more=document.querySelector('.more-options')
    expect(more.open).toBe(false)
    expect(more.contains(field('delivery-language'))).toBe(true)
    expect(more.querySelector('.delivery-toolbar')).not.toBeNull()
    await act(async()=>more.querySelector('summary').click())
    expect(more.open).toBe(true)
    expect(button('Sarcastic')).toBeTruthy()
    await click('Dramatic')
    await click('Generate Preview')
    expect(request).toHaveBeenLastCalledWith('/api/preview',expect.objectContaining({mode:'delivery',direction:'dramatic but restrained, with natural pacing and subtle emphasis'}))
  })

  it('uses the existing export and reset handlers from the new header', async () => {
    uploadAudio.mockResolvedValueOnce({...uploaded,revision:1,edit_count:1})
    await openEditor()
    downloadAudio.mockResolvedValueOnce(new Blob(['local audio'],{type:'audio/mpeg'}))
    await click('Export')
    expect(downloadAudio).toHaveBeenLastCalledWith(`/api/export/${uploaded.session_id}`)
    await click('New Recording')
    expect(document.querySelector('h1').textContent).toBe('Upload your recording')
    expect(document.querySelector('.header-actions')).toBeNull()
  })

})
